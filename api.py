from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db import get_db, init_db
from models import User
from auth import hash_password, verify_password, create_access_token, get_current_user
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


# ─── Startup ───────────────────────────────────────────

@app.on_event("startup")
async def startup():
    await init_db()


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
            "license_active": user.license_active,
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
            "license_active": user.license_active,
        },
    }


@app.get("/auth/me")
async def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "license_active": user.license_active,
    }


# ─── Licencia ─────────────────────────────────────────

@app.post("/license/activate")
async def activate_license(
    body: ActivateLicenseRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.license_active:
        return {"message": "La licencia ya esta activa", "license_active": True}

    # Verificar que la clave no esté en uso por otro usuario
    existing = await db.execute(
        select(User).where(User.license_key == body.license_key)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Clave de licencia ya utilizada")

    user.license_key = body.license_key
    user.license_active = True
    await db.commit()
    await db.refresh(user)

    return {"message": "Licencia activada", "license_active": True}


@app.get("/license/status")
async def license_status(user: User = Depends(get_current_user)):
    return {
        "license_active": user.license_active,
        "license_key": user.license_key,
    }


# ─── Landing page ─────────────────────────────────────

app.mount("/", StaticFiles(directory="web", html=True), name="web")
