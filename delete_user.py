"""Script temporal para eliminar un usuario de la base de datos."""
import asyncio
from sqlalchemy import select, delete
from db import SessionLocal
from models import User, WeeklyUsage, UserConfig

async def delete_user_by_email(email: str):
    email = email.lower().strip()
    async with SessionLocal() as db:
        # Buscar usuario
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            print(f"❌ Usuario con email '{email}' no encontrado")
            return

        print(f"✓ Usuario encontrado: {user.email} (ID: {user.id})")

        # Eliminar registros relacionados
        await db.execute(delete(WeeklyUsage).where(WeeklyUsage.user_id == user.id))
        await db.execute(delete(UserConfig).where(UserConfig.user_id == user.id))

        # Eliminar usuario
        await db.delete(user)
        await db.commit()

        print(f"✓ Usuario '{email}' eliminado correctamente")

if __name__ == "__main__":
    email = "juanjosepujols3@gmail.com"
    asyncio.run(delete_user_by_email(email))
