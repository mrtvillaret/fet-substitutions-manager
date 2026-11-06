"""Resolució dels alliberaments del dia i dels períodes, sense consultes."""

from grups.disponibilitat import activitats_de, clau_ocupat, clau_professor, ocupats_de


def resol_alliberats(result, horari, data, darrers, per_defecte):
    dia = horari.get_dia_name(data.weekday())

    for (_tipus, professor, dia_canvi, hora), canvi in darrers.items():
        if dia_canvi == dia and canvi.alliberat:
            clau = clau_professor(professor)
            if clau not in result.setdefault(hora, []):
                result[hora].append(clau)

    for hora, valors in result.items():
        activitats = set(activitats_de(valors))
        if not activitats:
            continue
        for professor in horari.professors:
            act = horari.get_activitat(dia, hora, professor) or {}
            if (act.get("assignatura") or "") in activitats:
                clau = clau_professor(professor)
                if clau not in valors:
                    valors.append(clau)

    # Activitats «alliberades fins que tinguin alumnes» (p.ex. Reforç): qui
    # les fa està alliberat, tret de les franges marcades amb alumnes
    if per_defecte:
        for hora in horari.hores:
            for professor in horari.professors:
                act = horari.get_activitat(dia, hora, professor) or {}
                if act.get("grup") or (act.get("assignatura") or "") not in per_defecte:
                    continue
                canvi = darrers.get(("professor", professor, dia, hora))
                if canvi is not None and not canvi.alliberat:
                    continue  # ja té alumnes
                if clau_ocupat(professor) in result.get(hora, []):
                    continue  # aquell dia sí que té alumnes
                clau = clau_professor(professor)
                if clau not in result.setdefault(hora, []):
                    result[hora].append(clau)

    # Un professor marcat «ocupat» aquell dia no està alliberat, vingui d'on
    # vingui l'alliberament (per defecte o per un canvi d'estat)
    for valors in result.values():
        for professor in ocupats_de(valors):
            clau = clau_professor(professor)
            while clau in valors:
                valors.remove(clau)
    return result
