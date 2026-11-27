"""
L'ordre dels cursos dins de cada hora (ordre_curs.clau_curs): per etapa (les
lletres del nivell), pel número i pel grup, sense cap paraula fixa. El mateix
a Substitucions (files.ordena_per_mostrar), Vigilàncies (clau_automatica)
i els PDF, que fan servir aquestes dues.
"""

import pytest

from ordre_curs import clau_curs
from substitucions.files import FilaSubstitucio, ordena_per_mostrar
from vigilancies.files import FilaVigilancia
from vigilancies.services import clau_automatica


@pytest.mark.parametrize(
    "grups, esperat",
    [
        # Abans, pel text: 1-BATX, 1-ESO, 2-BATX, 2-ESO...
        (
            ["2-ESO-A", "1-ESO-B", "2-BATX-A", "1-ESO-A", "4-ESO-B", "1-BATX-A", "4-ESO-A"],
            ["1-BATX-A", "2-BATX-A", "1-ESO-A", "1-ESO-B", "2-ESO-A", "4-ESO-A", "4-ESO-B"],
        ),
        # Un altre estil de codi: el número darrere de l'etapa
        (["ESO2A", "BAC1A", "ESO1B", "BAC2A", "ESO1A"], ["BAC1A", "BAC2A", "ESO1A", "ESO1B", "ESO2A"]),
        # Un combinat, al costat dels seus grups; uns grups junts, al seu nivell
        (
            ["4-ESO-B", "1-BAT-A,1-BAT-B", "4-ESO-AB", "4-ESO-A", "2-BAT-A"],
            ["1-BAT-A,1-BAT-B", "2-BAT-A", "4-ESO-A", "4-ESO-AB", "4-ESO-B"],
        ),
        # Número de dues xifres, en ordre natural
        (["10-ESO-A", "2-ESO-A"], ["2-ESO-A", "10-ESO-A"]),
    ],
)
def test_per_etapa_numero_i_grup(grups, esperat):
    assert sorted(grups, key=clau_curs) == esperat


def test_el_nivell_de_la_fila_mana_sobre_el_del_grup():
    # Vigilàncies: el nivell és un camp de la fila; el grup «X» no en diu res
    assert sorted([("4-ESO-A", "4-ESO"), ("X", "1-BATX")], key=lambda f: clau_curs(*f)) == [
        ("X", "1-BATX"),
        ("4-ESO-A", "4-ESO"),
    ]


def test_substitucions_dins_de_cada_hora_per_curs_i_professor():
    files = [
        FilaSubstitucio(**{"hora": "10:00", "professor_absent": "Prof 9", "grup": "2-ESO-A"}),
        FilaSubstitucio(**{"hora": "10:00", "professor_absent": "Prof 3", "grup": "1-ESO-A"}),
        FilaSubstitucio(**{"hora": "10:00", "professor_absent": "Prof 1", "grup": "2-BATX-A"}),
        FilaSubstitucio(**{"hora": "10:00", "professor_absent": "Prof 2", "grup": "1-ESO-A"}),
    ]
    ordre = [(f.grup, f.professor_absent) for f in ordena_per_mostrar(files, ["10:00"])]
    assert ordre == [("2-BATX-A", "Prof 1"), ("1-ESO-A", "Prof 2"), ("1-ESO-A", "Prof 3"), ("2-ESO-A", "Prof 9")]


def test_vigilancies_per_curs_aula_i_creacio():
    vigs = [
        {"id": 1, "nivell": "2-ESO", "grups": "2-ESO-A", "aula": "A1"},
        {"id": 2, "nivell": "2-BATX", "grups": "2-BATX-A", "aula": "A2"},
        {"id": 3, "nivell": "1-ESO", "grups": "1-ESO-A", "aula": "A2"},
        {"id": 4, "nivell": "1-ESO", "grups": "1-ESO-A", "aula": "A1"},
        {"id": 5, "nivell": "", "grups": "1-BATX-A", "aula": ""},
    ]
    vigs = [FilaVigilancia(**v) for v in vigs]
    assert [v.id for v in sorted(vigs, key=clau_automatica)] == [5, 2, 4, 3, 1]


def _fila(hora, absent, grup, substitut="", tipus="ABSENCIA"):
    return FilaSubstitucio(
        **{"hora": hora, "professor_absent": absent, "grup": grup, "substitut": substitut, "tipus_absencia": tipus}
    )


# Prof 7 fa una guàrdia i substitueix Prof 3: la seva encadenada (pendent) va
# just a sota de la substitució de Prof 3, en tots dos ordres
UNA_HORA = [
    _fila("10:00", "Prof 9", "1-ESO-A"),
    _fila("10:00", "Prof 7", "", tipus="ENCADENADA"),
    _fila("10:00", "Prof 3", "2-BATX-A", "Prof 7"),
    _fila("10:00", "Prof 2", "4-ESO-A"),
]
DUES_HORES = [
    _fila("10:00", "Prof 9", "", "Prof 4", "ENCADENADA"),
    _fila("10:00", "Prof 1", "3-ESO-C", "Prof 9"),
    _fila("09:00", "Prof 3", "2-BAT-A"),
    _fila("10:00", "Prof 15", "3-ESO-A", "Prof 2"),
    _fila("10:00", "Prof 7", "10-ESO-A"),
]


@pytest.mark.parametrize(
    "files, ordre, esperat",
    [
        # 2-BATX-A, 1-ESO-A, 4-ESO-A
        (UNA_HORA, "curs", [("10:00", p) for p in ("Prof 3", "Prof 7", "Prof 9", "Prof 2")]),
        (UNA_HORA, "professor", [("10:00", p) for p in ("Prof 2", "Prof 3", "Prof 7", "Prof 9")]),
        # L'ordre per defecte, el de la pantalla i el PDF
        (
            DUES_HORES,
            None,
            [
                ("09:00", "Prof 3"),
                ("10:00", "Prof 15"),  # 3-ESO-A
                ("10:00", "Prof 1"),  # 3-ESO-C
                ("10:00", "Prof 9"),  # l'encadenada del seu substitut
                ("10:00", "Prof 7"),  # 10-ESO-A: ordre natural
            ],
        ),
    ],
    ids=["curs", "professor", "per defecte i per hores"],
)
def test_tots_dos_ordres_amb_l_encadenada_sota_la_seva_substitucio(files, ordre, esperat):
    ordenades = ordena_per_mostrar(files, ["09:00", "10:00"], **({"ordre": ordre} if ordre else {}))
    assert [(f.hora, f.professor_absent) for f in ordenades] == esperat


def test_un_ordre_desconegut_no_s_accepta():
    with pytest.raises(ValueError):
        ordena_per_mostrar([], [], ordre="nom")
