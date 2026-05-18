#!/usr/bin/env python3
"""
Script de prova per al motor v3 (Simulated Annealing)
Usa les dades de demo per BAC2
"""

import json
import sqlite3
import sys
import os

# Afegir el path per importar el motor
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scheduler_engine.generators.v3_sa import GeneradorV3SA as GeneradorSessionsExamensV3

def carregar_config_examens_db(db_path: str, nivell: str = "BAC2") -> dict:
    """Carrega la configuració d'exàmens des de la BD"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Obtenir assignatures de BAC2
    cursor.execute("""
        SELECT assignatura, grup, titular, aula
        FROM configuracio_examens
        WHERE grup LIKE ?
    """, (f"%{nivell}%",))

    assignatures = {}
    for row in cursor.fetchall():
        assignatura, grup, titular, aula = row
        if assignatura not in assignatures:
            assignatures[assignatura] = {'assignacions': []}
        assignatures[assignatura]['assignacions'].append({
            'grup': grup,
            'titular': titular,
            'aula': aula or ''
        })

    conn.close()
    return {'assignatures': assignatures}


def carregar_restriccions_db(db_path: str) -> dict:
    """Carrega les restriccions des de la BD"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    restriccions = {
        'restriccions_dures': {
            'mateix_slot': [],
            'no_mateix_slot': {},
            'no_mateix_dia': [],
            'combinacions_permeses': [],
            'assignatures_dia_fix': {},
            'assignatures_hora_fix': {},
            'assignatures_dies_exclosos': []
        },
        'preferencies': {
            'dies_diferents': [],
            'mateix_dia': []
        },
        'pesos_percentatge': {
            'dies_diferents': 75,
            'mateix_dia': 50,
            'substitucio': 80,
            'professor_abans': 30,
            'professor_despres': 30,
            'professor_no_treballa': 60
        }
    }

    cursor.execute("SELECT tipus, clau, configuracio FROM exam_restriccions WHERE activa = 1")
    for row in cursor.fetchall():
        tipus, clau, configuracio = row
        try:
            valor_parsed = json.loads(configuracio) if configuracio else None
        except:
            valor_parsed = configuracio

        if tipus == 'assignatures_dia_fix':
            restriccions['restriccions_dures']['assignatures_dia_fix'][clau] = valor_parsed
        elif tipus == 'assignatures_hora_fix':
            restriccions['restriccions_dures']['assignatures_hora_fix'][clau] = valor_parsed
        elif tipus == 'combinacions_permeses':
            restriccions['restriccions_dures']['combinacions_permeses'].append({
                'assignatures': valor_parsed
            })
        elif tipus == 'assignatures_dies_exclosos':
            restriccions['restriccions_dures']['assignatures_dies_exclosos'].append(valor_parsed)

    conn.close()
    return restriccions


def main():
    # Paths
    data_dir = os.environ.get("TEST_DATA_DIR", "data/demo")
    db_path = f"{data_dir}/gestor.db"
    xml_path = f"{data_dir}/teachers.xml"

    # Paràmetres de prova
    dies_utilitzar = ["Dijous", "Divendres", "Dilluns", "Dimarts"]
    nivells_actius = ["BAC2"]
    hores_examen = ["9:15", "11:45", "13:35"]
    durada_titular = 2

    print("=" * 60)
    print("PROVA DEL MOTOR V3 - SIMULATED ANNEALING")
    print("=" * 60)
    print(f"Institució: demo")
    print(f"Dies: {', '.join(dies_utilitzar)}")
    print(f"Nivells: {', '.join(nivells_actius)}")
    print(f"Hores d'examen: {', '.join(hores_examen)}")
    print(f"Durada titular: {durada_titular} hores")
    print("=" * 60)

    # Carregar dades
    print("\n📚 Carregant configuració d'exàmens...")
    config = carregar_config_examens_db(db_path, "BAC2")
    print(f"   Assignatures carregades: {len(config['assignatures'])}")
    for nom in sorted(config['assignatures'].keys()):
        grups = [a['grup'] for a in config['assignatures'][nom]['assignacions']]
        print(f"      - {nom}: {', '.join(grups)}")

    print("\n📋 Carregant restriccions...")
    restriccions = carregar_restriccions_db(db_path)
    print(f"   Dies fixos: {restriccions['restriccions_dures']['assignatures_dia_fix']}")
    print(f"   Hores fixes: {restriccions['restriccions_dures']['assignatures_hora_fix']}")
    print(f"   Combinacions permeses: {len(restriccions['restriccions_dures']['combinacions_permeses'])}")
    for i, c in enumerate(restriccions['restriccions_dures']['combinacions_permeses']):
        print(f"      {i+1}. {c['assignatures']}")

    # Crear fitxers temporals
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(config, f, ensure_ascii=False)
        config_path = f.name

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(restriccions, f, ensure_ascii=False)
        restriccions_path = f.name

    try:
        # Crear i executar el motor
        print("\n🔧 Creant generador...")
        gen = GeneradorSessionsExamensV3(
            config_examens_path=config_path,
            horari_xml_path=xml_path,
            restriccions_path=restriccions_path,
            nivells_actius=nivells_actius,
            hores_examen=hores_examen,
            durada_titular=durada_titular
        )

        print("\n📚 Carregant dades del generador...")
        gen.carregar_dades()
        gen.carregar_horaris_professors()

        print("\n🚀 Generant horari optimitzat...")
        horari = gen.generar_horari_optimitzat(
            dies_utilitzar=dies_utilitzar,
            verbose=True
        )

        # Mostrar resultats
        print("\n" + "=" * 60)
        print("RESULTATS")
        print("=" * 60)

        meta = horari.get('metadata', {})
        print(f"\n📊 Estadístiques:")
        print(f"   Total sessions: {meta.get('total_sessions', 0)}")
        print(f"   Cost total: {meta.get('cost_total', 0):.2f}")
        print(f"   Viable: {meta.get('viable', False)}")
        print(f"   Violacions dures: {meta.get('violacions_dures', 0)}")
        print(f"   Violacions toves: {meta.get('violacions_toves', 0)}")
        print(f"   Substitucions: {meta.get('total_substitucions', 0)}")
        print(f"   Professors abans: {meta.get('professors_abans', 0)}")
        print(f"   Professors després: {meta.get('professors_despres', 0)}")

        print(f"\n📅 Horari generat:")
        for dia in horari.get('dies', []):
            print(f"\n   {dia['dia']}:")
            for slot in dia.get('sessions', []):
                hora = slot['hora']
                sessions = slot.get('sessions_simultanees', [])
                noms = [s['nom'] for s in sessions]
                print(f"      {hora}: {', '.join(noms) if noms else '(buit)'}")

        print(f"\n📝 Logs ({len(meta.get('logs', []))}):")
        for log in meta.get('logs', [])[:20]:  # Limitar a 20
            print(f"   {log}")
        if len(meta.get('logs', [])) > 20:
            print(f"   ... i {len(meta.get('logs', [])) - 20} més")

        # Cost breakdown
        breakdown = meta.get('cost_breakdown', {})
        if breakdown:
            print(f"\n💰 Desglossament de costos:")
            for tipus, data in sorted(breakdown.items()):
                if data['count'] > 0:
                    print(f"   {tipus}: {data['count']} ocurrències → {data['points']} punts")

    finally:
        # Netejar fitxers temporals
        os.unlink(config_path)
        os.unlink(restriccions_path)

    print("\n" + "=" * 60)
    print("PROVA COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    main()
