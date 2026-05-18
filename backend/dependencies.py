"""
Dependencies compartides per obtenir DB de dades segons usuari autenticat
"""
from fastapi import Depends

from auth_utils import get_current_user
from database import get_data_db


def get_db(current_user=Depends(get_current_user)):
    yield from get_data_db(current_user.institucio)
