"""Alliberats efectius del dia o d’un interval, resolts amb l’horari vigent."""

from sqlalchemy.orm import Session

from dates import parse_date
from errors_domini import MissingXmlError
from grups.alliberaments import resol_alliberats
from grups.repositories import AlliberamentsPeriodeRepository, GrupsAlliberatsRepository
from horari.context import get_horari, horaris_per_dates


class AlliberatsDelDia:
    @staticmethod
    def get_by_date(db: Session, data: str) -> dict[str, list[str]]:
        """Alliberats efectius per hora en una data: els marcats aquell dia més
        els que vénen d'un alliberament per període; les activitats alliberades
        es resolen als professors que les fan (perquè compti com qualsevol
        professor alliberat)."""
        result = GrupsAlliberatsRepository.get_dia_by_date(db, data)

        try:
            horari = get_horari(db.info.get("institucio"), data_iso=data)
        except MissingXmlError:
            return result  # sense horari no hi ha activitats ni períodes a resoldre

        dia = horari.get_dia_name(parse_date(data).weekday())
        return resol_alliberats(
            result,
            horari,
            parse_date(data),
            AlliberamentsPeriodeRepository.darrers(db, data, dia),
            set(GrupsAlliberatsRepository.activitats_per_defecte(db)),
        )

    @staticmethod
    def get_entre_dates(db: Session, dates: list[str]) -> dict[str, dict[str, list[str]]]:
        """Els alliberats de les dates demanades, amb consultes per interval
        i un horari per versió de l'XML. Memòria només d'aquesta crida."""

        dates = sorted(set(dates))
        if not dates:
            return {}
        resultat, canvis = GrupsAlliberatsRepository.llegeix_interval(db, dates)
        per_defecte = set(GrupsAlliberatsRepository.activitats_per_defecte(db))
        horaris = horaris_per_dates(db)
        darrers, index = {}, 0
        for data in dates:
            data_obj = parse_date(data)
            while index < len(canvis) and canvis[index].des_de <= data_obj:
                c = canvis[index]
                darrers[(c.tipus, c.clau, c.dia_setmana, c.hora)] = c
                index += 1
            try:
                horari = horaris(data)
            except MissingXmlError:
                continue  # com la lectura d'un dia: només les marques manuals
            resultat[data] = resol_alliberats(resultat[data], horari, data_obj, darrers, per_defecte)
        return resultat
