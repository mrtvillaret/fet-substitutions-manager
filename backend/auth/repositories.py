"""Consultes de la taula users (auth.db).

Els repositoris no fan commit: el fa qui crida (el servei), un cop per
operació, perquè una operació amb diverses escriptures sigui atòmica. flush
envia els canvis a la BD dins de la transacció (l'id d'un usuari nou ja hi
és) sense desar-los encara."""

from typing import Optional

from sqlalchemy.orm import Session

from models import User


class UserRepository:
    """Repositori per gestionar usuaris"""

    @staticmethod
    def get_by_username(db: Session, username: str) -> Optional[User]:
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def count(db: Session) -> int:
        return db.query(User).count()

    @staticmethod
    def list_all(db: Session) -> list[User]:
        return db.query(User).order_by(User.username.asc()).all()

    @staticmethod
    def list_by_institucio(db: Session, institucio: str) -> list[User]:
        return db.query(User).filter(User.institucio == institucio).order_by(User.username.asc()).all()

    @staticmethod
    def create(
        db: Session, username: str, password_hash: str, institucio: str, role: str = "user", active: bool = True
    ) -> User:
        user = User(username=username, password_hash=password_hash, institucio=institucio, role=role, active=active)
        db.add(user)
        db.flush()
        return user

    @staticmethod
    def update(db: Session, user: User, **fields) -> User:
        for key, value in fields.items():
            setattr(user, key, value)
        db.flush()
        return user

    @staticmethod
    def delete(db: Session, user: User) -> None:
        db.delete(user)
        db.flush()
