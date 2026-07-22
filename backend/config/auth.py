"""
Configuració d'autenticació JWT
"""
import os

# La SECRET_KEY signa els testimonis de sessió. Sense valor per defecte a
# propòsit: qui conegui la clau pot fabricar-se un testimoni vàlid de qualsevol
# usuari, sense necessitat de cap contrasenya i sense deixar cap intent fallit
# als registres. Un valor per defecte al codi és públic, així que val més
# aturar-se aquí que arrencar amb una instal·lació oberta.
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise SystemExit(
        "\nERROR: la variable SECRET_KEY no està definida.\n"
        "Genera'n una amb:  openssl rand -hex 32\n"
        "i posa-la al fitxer .env abans d'arrencar.\n"
    )

ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "8"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"

# Les contrasenyes no tenen valor per defecte a propòsit. Si no es defineixen
# per variable d'entorn, `ensure_default_users` en genera una d'aleatòria en
# crear cada usuari i la mostra un sol cop. Amb un valor fix aquí, qualsevol
# instal·lació que no llegís les instruccions quedaria exposada amb credencials
# que consten al codi públic.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "super_admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_INSTITUCIO = os.getenv("ADMIN_INSTITUCIO", "exemple")

DEFAULT_USERS = [
    {
        "username": os.getenv("ADMIN_CENTRE1_USERNAME", "admin_centre1"),
        "password": os.getenv("ADMIN_CENTRE1_PASSWORD"),
        "institucio": os.getenv("ADMIN_CENTRE1_INSTITUCIO", "exemple"),
        "role": "admin",
    },
    {
        "username": os.getenv("USER_CENTRE1_USERNAME", "user_centre1"),
        "password": os.getenv("USER_CENTRE1_PASSWORD"),
        "institucio": os.getenv("USER_CENTRE1_INSTITUCIO", "exemple"),
        "role": "user",
    },
]
