"""Lectura de l'horari dels professors des de l'XML de FET."""
from scheduler_engine.core.normalitzacio import normalitzar_dia
from utils.hores import normalitzar_hora


def horaris_professors(root, ultim_professor: str = "", normalitza_hores: bool = False) -> dict:
    """{professor: {dia: {hora: {'assignatura', 'grup'}}}} de les hores amb
    classe o activitat. Els professors van en l'ordre de l'XML fins a
    `ultim_professor` inclòs (el límit de "Configuració"); buit, tots."""
    ultim = (ultim_professor or "").strip()
    horaris = {}
    for teacher in root.findall('Teacher'):
        nom = teacher.get('name').strip()
        horaris[nom] = {}
        for day in teacher.findall('Day'):
            dia = normalitzar_dia(day.get('name'))
            horaris[nom][dia] = {}
            for hour in day.findall('Hour'):
                hora = normalitzar_hora(hour.get('name')) if normalitza_hores else hour.get('name')
                sub = hour.find('Subject')
                act = hour.find('Activity')
                if (act is not None and act.get('id')) or sub is not None:
                    students = hour.find('Students')
                    horaris[nom][dia][hora] = {
                        'assignatura': sub.get('name') if sub is not None else '',
                        'grup': students.get('name') if students is not None else '',
                    }
        if ultim and nom == ultim:
            break
    return horaris
