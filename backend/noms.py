"""
Els noms de professors, assignatures (activitats) i aules: una sola regla.

- Identitat: un nom és el text sense espais al principi ni al final. Es
  normalitza en entrar (en llegir l'XML i en rebre dades de l'API), en un sol
  lloc: nom_net() i, per a l'API, el tipus NomNet. Així «Guàrdia», «Guàrdia »
  i « Guàrdia» són la mateixa activitat a tot arreu.
- El text buit és un nom vàlid: a «No substituir» representa les hores de
  l'XML sense cap activitat. Un nom fet només d'espais queda buit.
- L'ordre no és cosa del nom: és la posició a l'XML. Els espais del davant
  dels professors (que FET fa servir per ordenar-los per nivells) no formen
  part del nom; l'XML es desa tal com es puja i no es reescriu mai.
"""

import re
import unicodedata
from typing import Annotated, Optional

from pydantic import AfterValidator


def nom_net(valor: Optional[str]) -> Optional[str]:
    """El nom sense espais al principi ni al final (None continua sent None)."""
    if valor is None:
        return None
    return valor.strip()


def _sense_accents(text: str) -> str:
    # NFKD i no NFD: també «ª» i «º» passen a «a» i «o», com a Intl.Collator('ca')
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def ordre_alfabetic(nom: str) -> tuple:
    """La clau per a les llistes que van per ordre alfabètic (no per la
    posició a l'XML): natural («Prof 6» abans de «Prof 10») i com en català,
    sense distingir majúscules i amb les lletres accentuades al lloc de la
    lletra sense accent («Àlex» abans d'«Andreu»). Com Intl.Collator('ca',
    {numeric: true}) al frontend. A igualtat, el nom tal com és."""
    trossos = [
        (0, int(t), "") if t.isdigit() else (1, 0, _sense_accents(t).casefold())
        for t in re.split(r"(\d+)", nom or "")
        if t
    ]
    return trossos, nom or ""


def _nom_net_validador(valor):
    return nom_net(valor) if isinstance(valor, str) else valor


def neteja_noms(dades: dict, *claus: str) -> dict:
    """Una còpia de `dades` amb els camps `claus` nets (per als cossos de l'API
    que encara arriben com a diccionari en lloc d'un model amb NomNet)."""
    return {k: nom_net(v) if k in claus and isinstance(v, str) else v for k, v in dades.items()}


# Tipus per als camps i paràmetres de l'API que porten un nom de professor,
# assignatura o aula: arriben sempre nets.
#   class Peticio(BaseModel): professor: NomNet
#   def ruta(assignatura: NomNet)
NomNet = Annotated[str, AfterValidator(_nom_net_validador)]
