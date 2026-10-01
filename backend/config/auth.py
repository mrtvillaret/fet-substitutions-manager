"""
Configuració d'autenticació JWT
"""
import os

# "development" habilita la documentació interactiva de l'API i permet els
# valors de mostra del backend/.env.example. Qualsevol altre valor —i el
# defecte— es considera un desplegament real.
ENVIRONMENT = os.getenv("ENVIRONMENT", "production").strip().lower()
IS_DEVELOPMENT = ENVIRONMENT == "development"

# Valors que consten al backend/.env.example perquè es pugui provar
# l'aplicació en local sense configurar res, més els marcadors que han sortit
# en versions anteriors de les plantilles. Com que són públics, fora de
# desenvolupament val més aturar-se que arrencar amb ells.
_VALORS_DE_MOSTRA = frozenset({
    "dev-secret-key-change-in-production",
    "admin123",
    "user123",
    "change-me",
    "canvia-aquesta-contrasenya",
})


def _comprova_valor_de_mostra(nom: str, valor: str | None) -> None:
    if not valor or IS_DEVELOPMENT or valor not in _VALORS_DE_MOSTRA:
        return
    raise SystemExit(
        f"\nERROR: {nom} té el valor de mostra del backend/.env.example, que és\n"
        f"públic. Posa-hi un valor propi, o bé ENVIRONMENT=development si això\n"
        f"és una prova en local.\n"
    )


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
_comprova_valor_de_mostra("SECRET_KEY", SECRET_KEY)

ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "8"))
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "true").lower() == "true"
# Nom de la galeta de sessió. Dues instal·lacions al mateix domini (p.ex. la
# principal a / i una demo a /demo/) necessiten noms diferents: si no, entrar a
# una tancaria la sessió de l'altra.
COOKIE_NAME = os.getenv("COOKIE_NAME", "gestor_token").strip() or "gestor_token"

# Delegació del login: usuaris que no són d'aquesta instal·lació sinó d'una
# altra (p.ex. una demo). Si algú entra amb un d'aquests noms, el login no
# valida res i indica on ha d'anar. Els noms queden reservats: aquí mai no
# poden correspondre a cap usuari. La URL pot ser:
#   - una ruta del mateix domini (p.ex. /demo/): el frontend hi entra amb les
#     mateixes credencials;
#   - una adreça https d'un altre (sub)domini: el frontend hi porta l'usuari,
#     amb el nom ja escrit, però no hi envia la contrasenya.
#   LOGIN_DELEGACIO_USUARIS=user_demo,admin_demo
#   LOGIN_DELEGACIO_URL=/demo/   o bé   https://demo.exemple.cat/
LOGIN_DELEGACIO_USUARIS = frozenset(
    u.strip() for u in os.getenv("LOGIN_DELEGACIO_USUARIS", "").split(",") if u.strip()
)
LOGIN_DELEGACIO_URL = os.getenv("LOGIN_DELEGACIO_URL", "").strip()
_delegacio_ruta = LOGIN_DELEGACIO_URL.startswith("/") and not LOGIN_DELEGACIO_URL.startswith("//")
_delegacio_https = LOGIN_DELEGACIO_URL.startswith("https://") and len(LOGIN_DELEGACIO_URL) > len("https://")
if LOGIN_DELEGACIO_USUARIS and not (_delegacio_ruta or _delegacio_https):
    raise SystemExit(
        "\nERROR: LOGIN_DELEGACIO_URL ha de ser una ruta del mateix domini que "
        "comenci per '/' (p.ex. /demo/) o una adreça https (p.ex. https://demo.exemple.cat/).\n"
    )

# Les contrasenyes no tenen valor per defecte a propòsit. Si no es defineixen
# per variable d'entorn, l'usuari administrador no es pot crear i l'aplicació
# s'atura; els usuaris de mostra, simplement, no es creen. Amb un valor fix
# aquí, qualsevol instal·lació que no llegís les instruccions quedaria exposada
# amb credencials que consten al codi públic.
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "super_admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
ADMIN_INSTITUCIO = os.getenv("ADMIN_INSTITUCIO", "exemple")
_comprova_valor_de_mostra("ADMIN_PASSWORD", ADMIN_PASSWORD)

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

for _usuari in DEFAULT_USERS:
    _comprova_valor_de_mostra(f"la contrasenya de {_usuari['username']}", _usuari["password"])
