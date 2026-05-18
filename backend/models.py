"""
Models SQLAlchemy per a la base de dades SQLite
"""

from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, Text, Date, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime

Base = declarative_base()


class Nivell(Base):
    __tablename__ = 'nivells'

    id = Column(Integer, primary_key=True, autoincrement=True)
    codi = Column(String, unique=True, nullable=False)
    nom = Column(String, nullable=False)
    ordre = Column(Integer, nullable=False)
    actiu = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Assignatura(Base):
    __tablename__ = 'assignatures'

    id = Column(Integer, primary_key=True, autoincrement=True)
    nom = Column(String, nullable=False)
    nivell_id = Column(Integer, ForeignKey('nivells.id', ondelete='CASCADE'), nullable=False)
    ordre = Column(Integer)
    activa = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_assignatura_nivell', 'nom', 'nivell_id', unique=True),
    )


class Grup(Base):
    __tablename__ = 'grups'

    id = Column(Integer, primary_key=True, autoincrement=True)
    codi = Column(String, unique=True, nullable=False)
    nom = Column(String, nullable=False)
    nivell_id = Column(Integer, ForeignKey('nivells.id', ondelete='CASCADE'), nullable=False)
    es_combinat = Column(Boolean, default=False)
    grups_components = Column(Text)
    ordre = Column(Integer)
    actiu = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Aula(Base):
    __tablename__ = 'aules'

    id = Column(Integer, primary_key=True, autoincrement=True)
    codi = Column(String, unique=True, nullable=False)
    nom = Column(String, nullable=False)
    tipus = Column(String)
    capacitat = Column(Integer)
    ordre = Column(Integer)
    activa = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Vigilancia(Base):
    __tablename__ = 'vigilancies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(Date, nullable=False)
    hora = Column(String, nullable=False)
    tipus = Column(String, nullable=False)
    grups = Column(String, nullable=False)
    aula = Column(String, nullable=False)
    vigilant = Column(String)
    comentaris = Column(Text)
    nivell = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_vigilancies_data', 'data'),
        Index('idx_vigilancies_data_nivell', 'data', 'nivell'),
        Index('idx_vigilancies_data_hora', 'data', 'hora'),
        Index('idx_vigilancies_vigilant', 'vigilant'),
    )


class Substitucio(Base):
    __tablename__ = 'substitucions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(Date, nullable=False)
    hora = Column(String, nullable=False)
    professor_absent = Column(String, nullable=False)
    assignatura = Column(String)
    grup = Column(String)
    aula = Column(String)
    substitut = Column(String)
    tipus_substitut = Column(String)
    tipus_absencia = Column(String)
    comentaris = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_substitucions_data', 'data'),
        Index('idx_substitucions_professor', 'professor_absent'),
        Index('idx_substitucions_substitut', 'substitut'),
    )


class GrupAlliberat(Base):
    __tablename__ = 'grups_alliberats'

    id = Column(Integer, primary_key=True, autoincrement=True)
    data = Column(Date, nullable=False)
    hora = Column(String, nullable=False)
    grups = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_grups_alliberats_data', 'data'),
        Index('idx_grups_alliberats_data_hora', 'data', 'hora'),
    )


class Configuracio(Base):
    __tablename__ = 'configuracio'

    clau = Column(String, primary_key=True)
    valor = Column(Text)
    tipus = Column(String, default='string')
    descripcio = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_configuracio_clau', 'clau'),
    )


class XMLVersion(Base):
    """
    Històric de versions de l'XML d'horari per data.
    """
    __tablename__ = 'xml_versions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    path = Column(String, nullable=False)
    data_inici = Column(Date, nullable=False)
    data_fi = Column(Date)
    hash_contingut = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_xml_versions_inici', 'data_inici'),
        Index('idx_xml_versions_fi', 'data_fi'),
    )


class ConfiguracioExamen(Base):
    """
    Assignacions professor-titular per exàmens
    Relaciona: Assignatura → Grup → Professor Titular → Aula
    """
    __tablename__ = 'configuracio_examens'

    id = Column(Integer, primary_key=True, autoincrement=True)
    assignatura = Column(String, nullable=False)
    grup = Column(String, nullable=False)
    titular = Column(String, nullable=True)  # Pot estar buit
    aula = Column(String, nullable=True)  # Pot estar buida
    ordre = Column(Integer, default=0)  # Ordre dins de l'assignatura
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_config_examens_assignatura', 'assignatura'),
        Index('idx_config_examens_grup', 'grup'),
        Index('idx_config_examens_titular', 'titular'),
    )


class AbreviaturaGrup(Base):
    """
    Abreviatures per agrupar múltiples grups
    Ex: "1-ESO-A,1-ESO-B,1-ESO-C" → "1-ESO-ABC"
    """
    __tablename__ = 'abreviatures_grups'

    id = Column(Integer, primary_key=True, autoincrement=True)
    grups_originals = Column(String, unique=True, nullable=False)  # "1-ESO-A,1-ESO-B,1-ESO-C"
    abreviatura = Column(String, nullable=False)  # "1-ESO-ABC"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_abreviatura', 'abreviatura'),
    )


class Professor(Base):
    """
    Taula històrica de professors per evitar pèrdua de substitucions
    quan un professor desapareix del nou XML.
    """
    __tablename__ = 'professors'

    id = Column(Integer, primary_key=True, autoincrement=True)
    nom = Column(String, unique=True, nullable=False)
    actiu = Column(Boolean, default=True)
    primera_aparicio = Column(Date)
    ultima_aparicio = Column(Date)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_professors_nom', 'nom'),
        Index('idx_professors_actiu', 'actiu'),
    )


class ProfessorBaixa(Base):
    """
    Professors de baixa temporal
    Durant el període especificat, no substitueixen ni són substituïts
    """
    __tablename__ = 'professors_baixa'

    id = Column(Integer, primary_key=True, autoincrement=True)
    professor = Column(String, nullable=False)
    data_inici = Column(Date, nullable=False)
    data_final = Column(Date, nullable=False)
    motiu = Column(String)  # Opcional: malaltia, permís, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_professor_baixa', 'professor'),
        Index('idx_baixa_dates', 'data_inici', 'data_final'),
    )


class CategoriaPrioritat(Base):
    """
    Categories de prioritat per a substitucions
    Ordre més baix = més prioritat
    """
    __tablename__ = 'categories_prioritat'

    id = Column(Integer, primary_key=True, autoincrement=True)
    nom = Column(String, nullable=False)  # Nom descriptiu (opcional)
    ordre = Column(Integer, nullable=False, unique=True)
    activa = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AssignaturaPrioritat(Base):
    """
    Assignatures dins de cada categoria amb el seu pes
    Pes més baix = més probabilitat de ser triat (dins de la mateixa categoria)
    """
    __tablename__ = 'assignatures_prioritat'

    id = Column(Integer, primary_key=True, autoincrement=True)
    assignatura = Column(String, nullable=False)
    categoria_id = Column(Integer, ForeignKey('categories_prioritat.id', ondelete='CASCADE'), nullable=False)
    pes = Column(Integer, default=1)  # 1-10: menor = més prioritat dins categoria
    ordre = Column(Integer, default=0)  # Ordre dins de la categoria
    auto_assignada = Column(Boolean, default=False)  # S'assigna automàticament (ex: "alliberat")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_assignatura_prioritat', 'assignatura'),
        Index('idx_assignatura_categoria', 'categoria_id'),
    )


class NoSubstituir(Base):
    """
    Assignatures que NO necessiten substitució
    Ex: "", "-x-", "Reforç", "alliberat", etc.
    """
    __tablename__ = 'no_substituir'

    id = Column(Integer, primary_key=True, autoincrement=True)
    assignatura = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    institucio = Column(String, nullable=False)
    role = Column(String, default="user")
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExamRestriccio(Base):
    """
    Restriccions d'exàmens unificades.
    Cada restricció té el seu propi pes (0-100%):
    - 100% = obligatòria (hard constraint)
    - 0-99% = preferència amb diferent importància (soft constraint)
    """
    __tablename__ = 'exam_restriccions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tipus = Column(String, nullable=False)  # dia_fix, hora_fix, dies_diferents, mateix_slot, etc.
    clau = Column(String)  # Identificador (assignatura, nom grup, etc.)
    configuracio = Column(Text)  # JSON amb detalls
    pes = Column(Integer, default=100)  # 0-100% (100 = obligatori)
    activa = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_exam_restriccio_tipus', 'tipus'),
        Index('idx_exam_restriccio_clau', 'clau'),
    )


class ExamPreferencia(Base):
    """LEGACY: Migrat a ExamRestriccio (tipus='mateix_dia'/'dies_diferents'). Mantingut per compatibilitat amb BDs existents."""
    __tablename__ = 'exam_preferencies'

    id = Column(Integer, primary_key=True, autoincrement=True)
    tipus = Column(String, nullable=False)
    assignatures = Column(Text, nullable=False)
    pes = Column(Integer, default=1)
    activa = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_exam_preferencia_tipus', 'tipus'),
    )


class ExamPesOptimitzacio(Base):
    """LEGACY: Migrat a ExamRestriccio (tipus='pes_optimitzacio'). Mantingut per compatibilitat amb BDs existents."""
    __tablename__ = 'exam_pesos_optimitzacio'

    id = Column(Integer, primary_key=True, autoincrement=True)
    clau = Column(String, unique=True, nullable=False)
    valor = Column(Integer, nullable=False)
    descripcio = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class ExamCostProfessor(Base):
    """
    Costos de professors per l'optimització d'horaris d'exàmens.

    - professor = NULL → cost global (aplica a tots)
    - professor = "Nom" → cost específic per aquest professor (override)

    Tipus disponibles:
    - substitucio: quan cal substitut perquè té classe
    - abans_jornada: quan ha de venir abans de la seva primera hora
    - despres_jornada: quan ha de quedar-se després de l'última hora
    - no_treballa_dia: quan ha de venir un dia que no treballa
    """
    __tablename__ = 'exam_costos_professors'

    id = Column(Integer, primary_key=True, autoincrement=True)
    professor = Column(String, nullable=True)  # NULL = global, "Nom" = individual
    tipus = Column(String, nullable=False)  # substitucio, abans_jornada, despres_jornada, no_treballa_dia
    pes = Column(Integer, default=100)  # 0-100%
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_exam_cost_professor', 'professor'),
        Index('idx_exam_cost_tipus', 'tipus'),
    )


class ExamSchedule(Base):
    __tablename__ = 'exam_schedules'

    id = Column(Integer, primary_key=True, autoincrement=True)
    nom = Column(String)
    data_generacio = Column(DateTime, default=datetime.utcnow)
    dies_seleccionats = Column(Text, nullable=False)
    horari_resultat = Column(Text, nullable=False)
    cost_total = Column(Integer)
    substitucions_eso = Column(Integer)
    conflictes_detectats = Column(Text)
    usuari_generador = Column(String)
    estat = Column(String, default='generat')
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
