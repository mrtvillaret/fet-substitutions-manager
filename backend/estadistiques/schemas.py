"""Schemas de sortida de les rutes d'Estadístiques."""

from typing import Optional

from pydantic import BaseModel


class Periode(BaseModel):
    data_inici: str
    data_final: str


class Cobertura(BaseModel):
    """Les absències i els serveis (les hores a cobrir) i quantes tenen substitut."""

    absencies: int
    serveis: int
    a_cobrir: int
    cobertes: int
    pendents: int
    percentatge: float


class Vigilancies(BaseModel):
    """Les vigilàncies d'examen per resultat: hi va el vigilant, hi va el
    substitut de la seva fila de vigilant absent, o ningú (descobertes)."""

    total: int
    vigilant: int
    substitut: int
    cobertes: int
    descobertes: int
    percentatge: float


class Activitat(BaseModel):
    dies_amb_absencies: int
    dies_amb_vigilancies: int


class ResumResponse(BaseModel):
    periode: Periode
    cobertura: Cobertura
    vigilancies: Vigilancies
    activitat: Activitat


class TotalProfessor(BaseModel):
    professor: str
    total: int


class AbsenciesProfessor(BaseModel):
    professor: str
    absencies: int
    serveis: int
    total: int


class ProfessorsResponse(BaseModel):
    periode: Periode
    professors_absents: list[AbsenciesProfessor]
    top_substituts: list[TotalProfessor]


class DiaTemporal(BaseModel):
    dia: str
    a_cobrir: int
    cobertes: int
    vigilancies: int


class HoraTemporal(BaseModel):
    hora: str
    a_cobrir: int
    cobertes: int
    vigilancies: int


class TotalsTemporals(BaseModel):
    a_cobrir: int
    cobertes: int
    vigilancies: int


class TemporalResponse(BaseModel):
    periode: Periode
    dies: list[DiaTemporal]
    hores: list[HoraTemporal]
    totals: TotalsTemporals


class Classe(BaseModel):
    grup: str
    a_cobrir: int
    cobertes: int
    percentatge: int
    assignatura_top: str
    professor_top: str


class ClassesResponse(BaseModel):
    periode: Periode
    classes: list[Classe]


class FilaClasse(BaseModel):
    data: str
    dia_setmana: str
    hora: str
    grup: str
    assignatura: str
    professor_absent: str
    substitut: str
    tipus_substitut: str


class TotalGrup(BaseModel):
    grup: str
    total: int


class TopNom(BaseModel):
    nom: str
    total: int


class ResumClasses(BaseModel):
    total: int
    per_grup: list[TotalGrup]
    top_assignatura: Optional[TopNom]
    top_professor: Optional[TopNom]
    top_substitut: Optional[TopNom]


class ClassesDetallResponse(BaseModel):
    periode: Periode
    grups: list[str]
    resultats: list[FilaClasse]
    resum: ResumClasses


class FilaTaulaProfessor(BaseModel):
    professor: str
    absencies: int
    serveis: int
    total_absencies: int
    substitucions_fetes: int
    vigilancies_fetes: int
    balanc: int


class TaulaProfessorsResponse(BaseModel):
    periode: Periode
    professors: list[FilaTaulaProfessor]


class AbsenciaProfessor(BaseModel):
    data: str
    dia_setmana: str
    hora: str
    grup: str
    assignatura: str
    substitut: str
    tipus_absencia: str


class SubstitucioProfessor(BaseModel):
    data: str
    dia_setmana: str
    hora: str
    grup: str
    assignatura: str
    professor_absent: str
    tipus_absencia: str
    tipus_substitut: str


class DetallProfessorResponse(BaseModel):
    periode: Periode
    professor: str
    absencies: list[AbsenciaProfessor]
    substitucions: list[SubstitucioProfessor]


class FrangesPerNombre(BaseModel):
    num_substitucions: int
    professors: list[TotalProfessor]


class FrangesResponse(BaseModel):
    periode: Periode
    dia: str
    hora: str
    total_slots: int
    total_substitucions: int
    franges: list[FrangesPerNombre]


class HoresResponse(BaseModel):
    periode: Periode
    hores: list[str]
