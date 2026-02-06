from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db import get_db, init_db
from models import User, WeeklyUsage
from auth import hash_password, verify_password, create_access_token, get_current_user
from engine.transcriber import Transcriber
from datetime import date, timedelta
import tempfile
import os
import uuid

app = FastAPI(title="Vox Easy API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FREE_WORD_LIMIT = 3000

# Whisper config
MODEL_SIZE = os.getenv("WHISPER_MODEL", "tiny")
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

transcriber: Transcriber | None = None


# ─── Schemas ───────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ActivateLicenseRequest(BaseModel):
    license_key: str


# ─── Helpers ───────────────────────────────────────────

def get_week_start() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


async def get_weekly_usage(user_id: int, db: AsyncSession) -> WeeklyUsage:
    week_start = get_week_start()
    result = await db.execute(
        select(WeeklyUsage).where(
            WeeklyUsage.user_id == user_id,
            WeeklyUsage.week_start == week_start,
        )
    )
    usage = result.scalar_one_or_none()
    if not usage:
        usage = WeeklyUsage(user_id=user_id, week_start=week_start, words_used=0)
        db.add(usage)
        await db.commit()
        await db.refresh(usage)
    return usage


# ─── Startup ───────────────────────────────────────────

@app.on_event("startup")
async def startup():
    global transcriber
    await init_db()
    transcriber = Transcriber(
        model_size=MODEL_SIZE,
        device=DEVICE,
        compute_type=COMPUTE_TYPE,
    )


# ─── Health ────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}


# ─── Auth ──────────────────────────────────────────────

@app.post("/auth/register")
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        name=body.name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "is_pro": user.is_pro,
        },
    }


@app.post("/auth/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id)
    return {
        "token": token,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "is_pro": user.is_pro,
        },
    }


@app.get("/auth/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "is_pro": user.is_pro,
    }


# ─── Transcripcion ────────────────────────────────────

@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verificar limite semanal para usuarios free
    usage = await get_weekly_usage(user.id, db)
    if not user.is_pro and usage.words_used >= FREE_WORD_LIMIT:
        raise HTTPException(
            status_code=403,
            detail=f"Limite semanal alcanzado ({FREE_WORD_LIMIT} palabras). Actualiza a Pro para uso ilimitado.",
        )

    # Validar que sea audio
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm"):
        if not file.content_type or not file.content_type.startswith("audio/"):
            raise HTTPException(status_code=400, detail="El archivo debe ser audio")

    tmp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}{ext or '.wav'}")
    try:
        contents = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(contents)

        text = transcriber.transcribe(tmp_path)
        word_count = len(text.split()) if text else 0

        # Actualizar uso semanal
        usage.words_used += word_count
        await db.commit()
        await db.refresh(usage)

        remaining = max(0, FREE_WORD_LIMIT - usage.words_used) if not user.is_pro else -1

        return {
            "text": text,
            "words": word_count,
            "words_used_this_week": usage.words_used,
            "words_remaining": remaining,
            "is_pro": user.is_pro,
        }
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


# ─── Uso ───────────────────────────────────────────────

@app.get("/usage")
async def get_usage(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    usage = await get_weekly_usage(user.id, db)
    remaining = max(0, FREE_WORD_LIMIT - usage.words_used) if not user.is_pro else -1
    return {
        "words_used_this_week": usage.words_used,
        "words_remaining": remaining,
        "weekly_limit": FREE_WORD_LIMIT,
        "is_pro": user.is_pro,
    }


# ─── Licencia ─────────────────────────────────────────

@app.post("/license/activate")
async def activate_license(
    body: ActivateLicenseRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.is_pro:
        return {"message": "Ya eres Pro", "is_pro": True}

    existing = await db.execute(
        select(User).where(User.license_key == body.license_key)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Clave de licencia ya utilizada")

    user.license_key = body.license_key
    user.is_pro = True
    await db.commit()
    await db.refresh(user)

    return {"message": "Licencia activada, ahora eres Pro", "is_pro": True}


@app.get("/license/status")
async def license_status(user: User = Depends(get_current_user)):
    return {"is_pro": user.is_pro, "license_key": user.license_key}


# ─── Landing page ─────────────────────────────────────

app.mount("/", StaticFiles(directory="web", html=True), name="web")
