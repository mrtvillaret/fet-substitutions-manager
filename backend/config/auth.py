"""
Configuració d'autenticació JWT
"""
import os

SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-canviar-en-produccio")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "8"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "super_admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
ADMIN_INSTITUCIO = os.getenv("ADMIN_INSTITUCIO", "exemple")

DEFAULT_USERS = [
    {
        "username": os.getenv("ADMIN_CENTRE1_USERNAME", "admin_centre1"),
        "password": os.getenv("ADMIN_CENTRE1_PASSWORD", "admin123"),
        "institucio": os.getenv("ADMIN_CENTRE1_INSTITUCIO", "exemple"),
        "role": "admin",
    },
    {
        "username": os.getenv("USER_CENTRE1_USERNAME", "user_centre1"),
        "password": os.getenv("USER_CENTRE1_PASSWORD", "user123"),
        "institucio": os.getenv("USER_CENTRE1_INSTITUCIO", "exemple"),
        "role": "user",
    },
]
