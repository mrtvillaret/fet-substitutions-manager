"""Dates i límits JWT amb el mateix rellotge, sense esperar temps real."""

from datetime import date, datetime, timedelta, timezone

import jwt
import pytest

import rellotge
from auth.security import create_access_token, decode_access_token
from config.auth import get_config_auth
from horari.domain import Dia


def test_canviar_el_dia_i_l_hora_arriba_al_domini_i_al_testimoni(rellotge_fix):
    rellotge_fix.moment = datetime(2032, 2, 29, 18, tzinfo=timezone.utc)
    assert rellotge.avui() == date(2032, 2, 29)
    assert Dia.avui("centre_de_prova").data == date(2032, 2, 29)
    token = create_access_token({"sub": "usuari_de_prova"})
    assert decode_access_token(token)["iat"] == int(rellotge_fix.moment.timestamp())


@pytest.mark.parametrize(
    "camp, desplacament, error",
    [
        ("exp", 0, jwt.ExpiredSignatureError),
        ("exp", -1, jwt.ExpiredSignatureError),
        ("iat", 1, jwt.ImmatureSignatureError),
        ("nbf", 1, jwt.ImmatureSignatureError),
        ("exp", "invalid", jwt.DecodeError),
        ("iat", "invalid", jwt.InvalidIssuedAtError),
        ("nbf", "invalid", jwt.DecodeError),
    ],
)
def test_es_mantenen_les_validacions_temporals_de_pyjwt(rellotge_fix, camp, desplacament, error):
    ara = int(rellotge_fix.moment.timestamp())
    payload = {"sub": "usuari_de_prova", "exp": ara + 60}
    payload[camp] = ara + desplacament if isinstance(desplacament, int) else desplacament
    token = jwt.encode(payload, get_config_auth().secret_key, algorithm=get_config_auth().algorithm)
    with pytest.raises(error):
        decode_access_token(token)


def test_els_limits_nbf_i_exp_inclouen_el_segon_correcte(rellotge_fix):
    ara = int(rellotge_fix.moment.timestamp())
    token = jwt.encode(
        {"sub": "prova", "iat": ara, "nbf": ara, "exp": ara + 1},
        get_config_auth().secret_key,
        algorithm=get_config_auth().algorithm,
    )
    assert decode_access_token(token)["sub"] == "prova"
    rellotge_fix.avanca(seconds=1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_el_rellotge_no_evita_la_comprovacio_de_signatura(rellotge_fix):
    token = jwt.encode(
        {"sub": "prova"}, "una-altra-clau-de-prova-amb-mida-suficient", algorithm=get_config_auth().algorithm
    )
    with pytest.raises(jwt.InvalidSignatureError):
        decode_access_token(token)


def test_es_preserva_el_fus_utc_i_el_format_local(rellotge_fix):
    assert rellotge.ara(timezone.utc).utcoffset() == timedelta(0)
    assert rellotge.ara().tzinfo is None
