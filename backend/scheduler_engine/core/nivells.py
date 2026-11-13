"""El nivell d'un grup per al planificador, sempre amb les taules de la
configuració d'exàmens (els grups de cada nivell i les abreviatures), mai per
trossos del nom del grup (regla del domini). És l'únic lloc on el planificador
decideix de quin nivell és un grup: el de les assignacions (quins exàmens té
cada nivell), el de les classes de l'XML (si el professor queda alliberat) i
el dels grups que es publiquen sense classe.

Un text de grup pot ser una llista separada per comes (com a l'XML), una
abreviatura («1-BAT-AB» → 1-BAT-A, 1-BAT-B) o el codi d'un nivell sencer; es
desfà com a Vigilàncies (`vigilancies.assignacio.grups_de`). Un grup que no és
a cap nivell no en té: no es dedueix res, i qui el fa servir ho avisa.
"""


class NivellsDelsGrups:
    """{nivell: [grups]} i {abreviatura: [grups]} de la configuració d'exàmens."""

    def __init__(self, grups_per_nivell: dict | None = None, abreviatures: dict | None = None):
        self.grups_per_nivell = {nivell: list(grups or []) for nivell, grups in (grups_per_nivell or {}).items()}
        self.abreviatures = {abreviatura: list(grups or []) for abreviatura, grups in (abreviatures or {}).items()}
        self._nivell_de = {grup: nivell for nivell, grups in self.grups_per_nivell.items() for grup in grups}

    # -------------------------------------------------------------- d'on surt

    @classmethod
    def de_master(cls, master: dict | None) -> "NivellsDelsGrups":
        """De la configuració mestra (`MasterConfigRepository.get_master_config`):
        `nivells` {codi: {grups}} i `abreviatures` {«A,B» originals: abreviatura}."""
        master = master or {}
        nivells = {codi: (dades or {}).get("grups", []) for codi, dades in (master.get("nivells") or {}).items()}
        abreviatures = {
            abreviatura: [g.strip() for g in originals.split(",") if g.strip()]
            for originals, abreviatura in (master.get("abreviatures") or {}).items()
        }
        return cls(nivells, abreviatures)

    def a_config(self) -> dict:
        """Les taules dins de la configuració que llegeixen els motors (JSON)."""
        return {"nivells_grups": self.grups_per_nivell, "abreviatures_grups": self.abreviatures}

    @classmethod
    def de_config(cls, config: dict | None) -> "NivellsDelsGrups":
        config = config or {}
        return cls(config.get("nivells_grups"), config.get("abreviatures_grups"))

    # -------------------------------------------------------------- consultes

    def _grups(self, text: str):
        """Els grups d'un text: llista per comes i abreviatures desfetes."""
        for part in (text or "").split(","):
            part = part.strip()
            if part:
                yield from self.abreviatures.get(part, [part])

    def nivells(self, text: str) -> set[str]:
        """Els nivells dels grups d'un text (un codi de nivell és el seu nivell)."""
        resultat = set()
        for grup in self._grups(text):
            if grup in self.grups_per_nivell:
                resultat.add(grup)
            elif grup in self._nivell_de:
                resultat.add(self._nivell_de[grup])
        return resultat

    def nivell(self, text: str, entre: list[str] | None = None) -> str | None:
        """El nivell d'un text de grup si tots els seus grups són d'un sol nivell
        (i, amb `entre`, si és un d'aquests); si no, cap."""
        nivells = self.nivells(text)
        if len(nivells) != 1:
            return None
        (nivell,) = nivells
        return nivell if entre is None or nivell in entre else None

    def sense_nivell(self, text: str) -> list[str]:
        """Els grups d'un text que no són a cap nivell (sense repetir, en ordre)."""
        resultat = []
        for grup in self._grups(text):
            if grup not in self.grups_per_nivell and grup not in self._nivell_de and grup not in resultat:
                resultat.append(grup)
        return resultat
