"""Configuració d'autenticació validada, substituïble com un sol objecte."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ConfigAuth:
    environment: str
    is_development: bool
    secret_key: str = field(repr=False)
    algorithm: str
    sessio_inactivitat_minuts: int
    sessio_maxima_hores: int
    sessio_renovacio_minuts: int
    cookie_secure: bool
    cookie_name: str
    login_delegacio_usuaris: frozenset[str]
    login_delegacio_url: str
    admin_username: str
    admin_password: str | None = field(repr=False)
    admin_institucio: str
    admin_password_recuperacio: str | None = field(repr=False)
    default_users: list[dict] = field(repr=False)
    usuaris_protegits: frozenset[str]


def carrega_config_auth(env: Mapping[str, str]) -> ConfigAuth:
    """Llegeix un entorn explícit amb els defaults i errors històrics."""
    # "development" habilita la documentació interactiva de l'API i permet els
    # valors de mostra del backend/.env.example. Qualsevol altre valor —i el
    # defecte— es considera un desplegament real.
    environment = env.get("ENVIRONMENT", "production").strip().lower()
    is_development = environment == "development"

    # Valors que consten al backend/.env.example perquè es pugui provar
    # l'aplicació en local sense configurar res, més els marcadors que han sortit
    # en versions anteriors de les plantilles. Com que són públics, fora de
    # desenvolupament val més aturar-se que arrencar amb ells.
    _VALORS_DE_MOSTRA = frozenset(
        {
            "dev-secret-key-change-in-production",
            "admin123",
            "user123",
            "change-me",
            "canvia-aquesta-contrasenya",
        }
    )

    def _comprova_valor_de_mostra(nom: str, valor: str | None) -> None:
        if not valor or is_development or valor not in _VALORS_DE_MOSTRA:
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
    secret_key = env.get("SECRET_KEY")
    if not secret_key:
        raise SystemExit(
            "\nERROR: la variable SECRET_KEY no està definida.\n"
            "Genera'n una amb:  openssl rand -hex 32\n"
            "i posa-la al fitxer .env abans d'arrencar.\n"
        )
    _comprova_valor_de_mostra("SECRET_KEY", secret_key)

    algorithm = env.get("JWT_ALGORITHM", "HS256")
    # Sessions: caduquen al cap de SESSIO_INACTIVITAT_MINUTS sense cap petició; mentre
    # s'hi treballa es renoven (com a molt cada SESSIO_RENOVACIO_MINUTS), fins a un
    # màxim de SESSIO_MAXIMA_HORES des de l'entrada.
    sessio_inactivitat_minuts = int(env.get("SESSIO_INACTIVITAT_MINUTS", "60"))
    sessio_maxima_hores = int(env.get("SESSIO_MAXIMA_HORES", "24"))
    sessio_renovacio_minuts = 5
    cookie_secure = env.get("COOKIE_SECURE", "true").lower() == "true"
    # Nom de la galeta de sessió. Dues instal·lacions al mateix domini (p.ex. la
    # principal a / i una demo a /demo/) necessiten noms diferents: si no, entrar a
    # una tancaria la sessió de l'altra.
    cookie_name = env.get("COOKIE_NAME", "gestor_token").strip() or "gestor_token"

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
    login_delegacio_usuaris = frozenset(
        u.strip() for u in env.get("LOGIN_DELEGACIO_USUARIS", "").split(",") if u.strip()
    )
    login_delegacio_url = env.get("LOGIN_DELEGACIO_URL", "").strip()
    _delegacio_ruta = login_delegacio_url.startswith("/") and not login_delegacio_url.startswith("//")
    _delegacio_https = login_delegacio_url.startswith("https://") and len(login_delegacio_url) > len("https://")
    if login_delegacio_usuaris and not (_delegacio_ruta or _delegacio_https):
        raise SystemExit(
            "\nERROR: LOGIN_DELEGACIO_URL ha de ser una ruta del mateix domini que "
            "comenci per '/' (p.ex. /demo/) o una adreça https (p.ex. https://demo.exemple.cat/).\n"
        )

    # Usuaris inicials: només es creen en una instal·lació nova (taula d'usuaris
    # buida); després no es toquen mai sols (auth.services.crea_usuaris_inicials).
    # Les contrasenyes no tenen valor per defecte a propòsit. Sense ADMIN_PASSWORD,
    # una instal·lació nova no pot crear l'administrador i l'aplicació s'atura; els
    # usuaris de mostra, simplement, no es creen. Amb un valor fix aquí, qualsevol
    # instal·lació que no llegís les instruccions quedaria exposada amb
    # credencials que consten al codi públic.
    admin_username = env.get("ADMIN_USERNAME", "super_admin")
    admin_password = env.get("ADMIN_PASSWORD")
    admin_institucio = env.get("ADMIN_INSTITUCIO", "exemple")
    _comprova_valor_de_mostra("ADMIN_PASSWORD", admin_password)

    # Recuperació del superadmin (p.ex. si s'ha perdut la contrasenya o s'ha
    # desactivat): només si es defineix expressament. En arrencar, el superadmin
    # ADMIN_USERNAME es crea o es reactiva amb aquesta contrasenya, i se li tanquen
    # les sessions. Cal treure-la de l'entorn tan bon punt s'hagi fet servir: si no,
    # cada reinici tornaria a posar aquesta contrasenya.
    admin_password_recuperacio = env.get("ADMIN_PASSWORD_RECUPERACIO") or None
    _comprova_valor_de_mostra("ADMIN_PASSWORD_RECUPERACIO", admin_password_recuperacio)

    default_users = [
        {
            "username": env.get("ADMIN_CENTRE1_USERNAME", "admin_centre1"),
            "password": env.get("ADMIN_CENTRE1_PASSWORD"),
            "institucio": env.get("ADMIN_CENTRE1_INSTITUCIO", "exemple"),
            "role": "admin",
        },
        {
            "username": env.get("USER_CENTRE1_USERNAME", "user_centre1"),
            "password": env.get("USER_CENTRE1_PASSWORD"),
            "institucio": env.get("USER_CENTRE1_INSTITUCIO", "exemple"),
            "role": "user",
        },
    ]

    for _usuari in default_users:
        _comprova_valor_de_mostra(f"la contrasenya de {_usuari['username']}", _usuari["password"])

    # Usuaris que només el superadmin pot modificar: ni ells mateixos (contrasenya,
    # tancar les altres sessions) ni cap admin (editar, desactivar). Per a una demo
    # pública, on la contrasenya és coneguda i qualsevol visitant hi pot entrar.
    #   USUARIS_PROTEGITS=user_demo,admin_demo
    usuaris_protegits = frozenset(u.strip() for u in env.get("USUARIS_PROTEGITS", "").split(",") if u.strip())

    return ConfigAuth(
        environment=environment,
        is_development=is_development,
        secret_key=secret_key,
        algorithm=algorithm,
        sessio_inactivitat_minuts=sessio_inactivitat_minuts,
        sessio_maxima_hores=sessio_maxima_hores,
        sessio_renovacio_minuts=sessio_renovacio_minuts,
        cookie_secure=cookie_secure,
        cookie_name=cookie_name,
        login_delegacio_usuaris=login_delegacio_usuaris,
        login_delegacio_url=login_delegacio_url,
        admin_username=admin_username,
        admin_password=admin_password,
        admin_institucio=admin_institucio,
        admin_password_recuperacio=admin_password_recuperacio,
        default_users=default_users,
        usuaris_protegits=usuaris_protegits,
    )


_config_auth = carrega_config_auth(os.environ)


def get_config_auth() -> ConfigAuth:
    return _config_auth
