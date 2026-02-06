from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from engine.transcriber import Transcriber
from db import get_db, init_db
from models import User, Transcription
from auth import hash_password, verify_password, create_access_token, get_current_user
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
    return {"status": "ok", "model": MODEL_SIZE}


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
    return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name}}


@app.post("/auth/login")
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user.id)
    return {"token": token, "user": {"id": user.id, "email": user.email, "name": user.name}}


@app.get("/auth/me")
async def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "name": user.name}


# ─── Transcription ─────────────────────────────────────

@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not file.content_type or not file.content_type.startswith("audio/"):
        ext = os.path.splitext(file.filename or "")[1].lower()
        if ext not in (".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm"):
            raise HTTPException(
                status_code=400,
                detail="File must be an audio file (wav, mp3, m4a, ogg, flac, webm)",
            )

    tmp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}.wav")
    try:
        contents = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(contents)

        text = transcriber.transcribe(tmp_path)

        # Save to database
        record = Transcription(
            user_id=user.id,
            filename=file.filename,
            text=text,
        )
        db.add(record)
        await db.commit()
        await db.refresh(record)

        return {
            "id": record.id,
            "text": text,
            "filename": file.filename,
            "created_at": str(record.created_at),
        }
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.get("/transcriptions")
async def get_transcriptions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Transcription)
        .where(Transcription.user_id == user.id)
        .order_by(Transcription.created_at.desc())
        .limit(100)
    )
    rows = result.scalars().all()
    return [
        {
            "id": r.id,
            "filename": r.filename,
            "text": r.text,
            "created_at": str(r.created_at),
        }
        for r in rows
    ]


# ─── Landing page ─────────────────────────────────────

app.mount("/", StaticFiles(directory="web", html=True), name="web")
