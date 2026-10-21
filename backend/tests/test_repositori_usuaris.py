"""
Els repositoris no fan commit: el fa el servei, un cop per operació. Si una
operació falla a mig camí, el que ja s'havia escrit es desfà.
"""

import uuid

from suport_api import CONTRASENYA, crea_usuari

from auth.repositories import UserRepository
from auth.security import hash_password
from database import AuthSessionLocal, create_auth_tables


def _nom():
    return f"repo_{uuid.uuid4().hex[:8]}"


def test_crear_sense_commit_no_desa_res():
    create_auth_tables()
    nom = _nom()
    with AuthSessionLocal() as db:
        user = UserRepository.create(db, nom, hash_password(CONTRASENYA), "exemple")
        assert user.id is not None  # flush: l'id ja hi és dins de la transacció
        db.rollback()
    with AuthSessionLocal() as db:
        assert UserRepository.get_by_username(db, nom) is None


def test_modificar_i_esborrar_sense_commit_no_desen_res():
    nom = _nom()
    crea_usuari(nom, "exemple")
    with AuthSessionLocal() as db:
        UserRepository.update(db, UserRepository.get_by_username(db, nom), active=False)
        db.rollback()
        UserRepository.delete(db, UserRepository.get_by_username(db, nom))
        db.rollback()
    with AuthSessionLocal() as db:
        assert UserRepository.get_by_username(db, nom).active is True
