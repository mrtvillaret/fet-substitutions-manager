"""
Lògica unificada per analitzar la disponibilitat dels professors.
"""

from typing import List, Dict, Set, Union, Any, Optional
from scheduler_engine.core.normalitzacio import normalitzar_dia, normalitzar_text
from scheduler_engine.core.constraints import detectar_nivell_grup
from utils.hores import normalitzar_hora as _normalitzar_hora

def analitzar_disponibilitat_sessio(
    sessio: Union[Dict, Any],
    dia: str,
    hora: str,
    horaris_professors: Dict,
    totes_hores: List[str],
    nivells_actius: List[str],
    durada_titular: int = 1,
    no_substituir_norm: Set[str] = None,
    sessions_al_slot: List[Union[Dict, Any]] = None,
    hores_override: Optional[List[str]] = None,
    alliberaments_per_nivell: Optional[Dict] = None,
    data_iso: Optional[str] = None,
    hores_supervisio: Optional[List[str]] = None,
    horaris_professors_norm: Optional[Dict] = None,
) -> Dict:
    """
    Analitza la disponibilitat dels professors d'una sessió en un slot determinat.

    Paràmetres:
    - alliberaments_per_nivell: Dict amb estructura { nivell: { config: { "YYYY-MM-DD": { "HH:MM": { a: bool } } } } }
      On 'a' indica si el nivell està alliberat a aquella data/hora.
    - data_iso: Data en format ISO (YYYY-MM-DD) per consultar els alliberaments.

    Retorna un diccionari amb les categories de professors:
    - lliures: sense classe ni obligacions
    - alliberats: tindrien classe però els seus alumnes estan alliberats (no tenen classe)
    - substitucions: necessiten algú que els cobreixi la classe
    - abans_jornada: haurien d'arribar abans de la seva primera classe
    - despres_jornada: haurien de marxar després de la seva última classe
    - no_treballa_dia: el professor no té cap activitat aquest dia
    - classe_{nivell}: detall de quina classe tenen (per a estadístiques)
    - altres: activitats sense grup o assignatures que no es substitueixen
    """
    if no_substituir_norm is None:
        no_substituir_norm = set()

    # Preparar el resultat
    analisi = {
        'lliures': [],
        'alliberats': [],
        'abans_jornada': [],
        'despres_jornada': [],
        'no_treballa_dia': [],
        'substitucions': [],
        'altres': [],
        'zona_examen': [],  # Conflictes a la zona examen sense titular (cost=0)
    }
    for nivell in nivells_actius:
        analisi[f'classe_{nivell}'] = []

    def _dedup(seq):
        seen = set()
        out = []
        for item in seq:
            if item in seen:
                continue
            seen.add(item)
            out.append(item)
        return out

    def _nivell_alliberat_a_slot(nivell: str, data: str, hora: str) -> bool:
        """
        Comprova si un nivell està alliberat (🟩) a una data/hora concreta.
        Si no hi ha informació d'alliberaments, retorna True per compatibilitat
        amb el comportament anterior (tots els nivells actius alliberats).
        """
        if not alliberaments_per_nivell:
            # Comportament antic: si no hi ha alliberaments definits,
            # tots els nivells actius es consideren alliberats
            return nivell in nivells_actius

        nivell_data = alliberaments_per_nivell.get(nivell)
        if not nivell_data:
            return False

        config = nivell_data.get('config', {})
        if not config:
            return False

        # Buscar la data (format YYYY-MM-DD)
        dia_config = config.get(data)
        if not dia_config:
            return False

        # Buscar l'hora (format HH:MM)
        hora_norm = _normalitzar_hora(hora)
        hora_config = dia_config.get(hora_norm)
        if not hora_config:
            return False

        # Comprovar si està alliberat (clau 'a')
        return hora_config.get('a', False) is True

    def _detectar_nivell_del_grup(grup: str) -> Optional[str]:
        """
        Detecta quin nivell correspon a un grup.
        Per exemple: "1-BATX-A" -> "1-BATX"
        """
        if not grup:
            return None
        for nivell in nivells_actius:
            if nivell in grup:
                return nivell
        return None

    # Normalitzar dia per comparació
    dia_norm = normalitzar_dia(dia)

    totes_hores_norm = _dedup([_normalitzar_hora(h) for h in (totes_hores or [])])
    hora_norm = _normalitzar_hora(hora)

    if hora_norm not in totes_hores_norm:
        return analisi

    # Usar exactament la durada passada pel caller (ja calculada per get_durada_per_sessio_key)
    durada_sessio = durada_titular

    # Determinar hores afectades per l'examen (finestra completa)
    if hores_override is not None:
        hores_examen = [_normalitzar_hora(h) for h in hores_override]
        idx_inici = totes_hores_norm.index(hora_norm) if hora_norm in totes_hores_norm else None
    else:
        idx_inici = totes_hores_norm.index(hora_norm)
        idx_final = min(idx_inici + durada_sessio, len(totes_hores_norm))
        hores_examen = totes_hores_norm[idx_inici:idx_final]

    # Zona de supervisió: hores on el titular HA d'estar present (cost real)
    # Si hores_supervisio és None → totes les hores d'examen són de supervisió (compat. anterior)
    if hores_supervisio is not None:
        hores_supervisio_set = {_normalitzar_hora(h) for h in hores_supervisio}
    else:
        hores_supervisio_set = set(hores_examen)

    # Identificar professors titulars d'altres sessions al mateix slot (per alliberaments)
    profs_altres = set()
    if sessions_al_slot:
        sessio_nom = sessio.get('nom') if isinstance(sessio, dict) else getattr(sessio, 'nom', None)
        for s_info in sessions_al_slot:
            s_real = s_info.get('sessio', s_info) if isinstance(s_info, dict) else s_info
            curr_nom = s_real.get('nom') if isinstance(s_real, dict) else getattr(s_real, 'nom', None)
            
            if curr_nom != sessio_nom:
                # Extraure professors de la sessió (suport Dict i Objecte)
                examens = s_real.get('examens', []) if isinstance(s_real, dict) else getattr(s_real, 'examens', [])
                for ex in examens:
                    p = ex.get('titular') if isinstance(ex, dict) else getattr(ex, 'titular', None)
                    if p: profs_altres.add(p)

    # DEBUG: mostrar paràmetres d'entrada
    sessio_nom = sessio.get('nom') if isinstance(sessio, dict) else getattr(sessio, 'nom', '?')
    _debug = False  # Canviar a True per activar logs
    if _debug:
        print(f"[DEBUG avail] sessio={sessio_nom}, dia={dia_norm}, hora={hora}, hores_examen={hores_examen}")
        print(f"[DEBUG avail] data_iso={data_iso}, alliberaments_per_nivell={'present' if alliberaments_per_nivell else 'NONE'}")

    # Analitzar cada professor de la sessió actual
    examens_actuals = sessio.get('examens', []) if isinstance(sessio, dict) else getattr(sessio, 'examens', [])

    for ex in examens_actuals:
        prof = ex.get('titular') if isinstance(ex, dict) else getattr(ex, 'titular', None)
        if not prof:
            continue

        if _debug:
            print(f"[DEBUG avail]   prof={prof}, en_horaris={prof in horaris_professors}")

        if prof not in horaris_professors:
            analisi['lliures'].append({'professor': prof, 'examen': ex})
            continue

        if _debug:
            dies_prof = list(horaris_professors[prof].keys())
            print(f"[DEBUG avail]   dies_prof={dies_prof}, dia_norm={dia_norm}, te_dia={dia_norm in horaris_professors[prof]}")

        if horaris_professors_norm:
            prof_dies_norm = horaris_professors_norm.get(prof, {})
            if dia_norm not in prof_dies_norm:
                for h in hores_examen:
                    if h in hores_supervisio_set:
                        analisi['no_treballa_dia'].append({'professor': prof, 'examen': ex, 'dia': dia_norm, 'hora': h})
                continue
            horari_dia_norm = prof_dies_norm[dia_norm]
        else:
            if dia_norm not in horaris_professors[prof]:
                for h in hores_examen:
                    if h in hores_supervisio_set:
                        analisi['no_treballa_dia'].append({'professor': prof, 'examen': ex, 'dia': dia_norm, 'hora': h})
                continue
            horari_dia = horaris_professors[prof][dia_norm]
            horari_dia_norm = {}
            for h_k, act in horari_dia.items():
                h_norm = _normalitzar_hora(h_k)
                if h_norm and h_norm not in horari_dia_norm:
                    horari_dia_norm[h_norm] = act
        # Determinar jornada del professor
        primera = None
        ultima = None
        for h in totes_hores_norm:
            if h in horari_dia_norm:
                if primera is None:
                    primera = h
                ultima = h

        index_map = {h: i for i, h in enumerate(totes_hores_norm)}
        idx_primera = index_map.get(primera) if primera else None
        idx_ultima = index_map.get(ultima) if ultima else None
        if idx_primera is None and idx_ultima is not None:
            idx_primera = idx_ultima
        if idx_ultima is None and idx_primera is not None:
            idx_ultima = idx_primera

        te_substitucio = False
        te_alliberat = False
        is_in_altres = prof in profs_altres
        had_overlap = False
        any_outside = False
        any_inside_no_overlap = False

        for h in hores_examen:
            es_supervisio = h in hores_supervisio_set
            act = horari_dia_norm.get(h)
            if _debug:
                print(f"[DEBUG avail]     hora={h}, act={act}, es_supervisio={es_supervisio}")
            if act:
                grup = act.get('grup', '') or ''
                assig = act.get('assignatura', '') or ''

                if not es_supervisio:
                    # Zona examen: el titular ja no ha d'estar present → no cost real
                    # Registrem el conflicte com a informatiu (zona_examen) si és classe real
                    nivell_del_grup_z = _detectar_nivell_del_grup(grup)
                    is_alliberat_z = nivell_del_grup_z and _nivell_alliberat_a_slot(nivell_del_grup_z, data_iso, h)
                    is_no_subst_z = not grup.strip() or normalitzar_text(assig) in no_substituir_norm
                    if not is_alliberat_z and not is_no_subst_z:
                        analisi['zona_examen'].append({'professor': prof, 'examen': ex, 'activitat': act, 'hora': h})
                    continue  # cap cost real per zona examen

                # Zona supervisió: el titular HA d'estar → cost real
                had_overlap = True

                # Cas 1: Alliberat perquè els seus alumnes estan alliberats (no tenen classe)
                nivell_del_grup = _detectar_nivell_del_grup(grup)
                if nivell_del_grup:
                    if _nivell_alliberat_a_slot(nivell_del_grup, data_iso, h):
                        if _debug:
                            print(f"[DEBUG avail]     -> ALLIBERAT (grup={grup}, nivell={nivell_del_grup} alliberat a {data_iso} {h})")
                        te_alliberat = True
                        continue
                    if _debug:
                        print(f"[DEBUG avail]     -> NO ALLIBERAT (grup={grup}, nivell={nivell_del_grup} NO alliberat a {data_iso} {h})")

                # Cas 2: Altres activitats (guàrdies, CD, etc.) o assignatures No Substituir
                if not grup.strip() or normalitzar_text(assig) in no_substituir_norm:
                    if _debug:
                        print(f"[DEBUG avail]     -> ALTRES (grup buit o no_substituir)")
                    analisi['altres'].append({'professor': prof, 'examen': ex, 'activitat': act, 'hora': h})
                    continue

                # Cas 3: Substitució real
                if _debug:
                    print(f"[DEBUG avail]     -> SUBSTITUCIO (grup={grup}, assig={assig})")
                te_substitucio = True
                detall = {'professor': prof, 'examen': ex, 'activitat': act, 'hora': h}

                nivell_detectat = detectar_nivell_grup(grup, nivells_actius)
                clau_classe = f'classe_{nivell_detectat}'
                if clau_classe in analisi:
                    analisi[clau_classe].append(detall)
                else:
                    analisi['altres'].append(detall)
                analisi['substitucions'].append(detall)
            else:
                if not es_supervisio:
                    continue  # No avant/despres per zona examen
                if idx_primera is None or idx_ultima is None:
                    any_inside_no_overlap = True
                    continue
                idx_h = index_map.get(h)
                if idx_h is None:
                    continue
                if idx_h < idx_primera:
                    analisi['abans_jornada'].append({'professor': prof, 'examen': ex, 'primera_hora': primera, 'hora': h})
                    any_outside = True
                elif idx_h > idx_ultima:
                    analisi['despres_jornada'].append({'professor': prof, 'examen': ex, 'ultima_hora': ultima, 'hora': h})
                    any_outside = True
                else:
                    any_inside_no_overlap = True

        if not had_overlap and not any_outside and any_inside_no_overlap:
            analisi['lliures'].append({'professor': prof, 'examen': ex})

        if had_overlap and not te_substitucio and (te_alliberat or is_in_altres):
            analisi['alliberats'].append({'professor': prof, 'examen': ex})
                
    return analisi
