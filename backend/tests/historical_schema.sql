-- DDL històric facilitat a l’assaig, sense cap dada de centres.

CREATE TABLE assignatures_prioritat (
	id INTEGER NOT NULL,
	assignatura VARCHAR NOT NULL,
	categoria_id INTEGER NOT NULL,
	pes INTEGER,
	ordre INTEGER,
	created_at DATETIME,
	updated_at DATETIME, auto_assignada BOOLEAN DEFAULT 0,
	PRIMARY KEY (id),
	FOREIGN KEY(categoria_id) REFERENCES categories_prioritat (id) ON DELETE CASCADE
);
CREATE INDEX idx_assignatura_prioritat ON assignatures_prioritat (assignatura);
CREATE INDEX idx_assignatura_categoria ON assignatures_prioritat (categoria_id);

CREATE TABLE exam_schedules (
	id INTEGER NOT NULL,
	nom VARCHAR,
	data_generacio DATETIME,
	dies_seleccionats TEXT NOT NULL,
	horari_resultat TEXT NOT NULL,
	cost_total INTEGER,
	substitucions_eso INTEGER,
	conflictes_detectats TEXT,
	usuari_generador VARCHAR,
	estat VARCHAR,
	created_at DATETIME,
	updated_at DATETIME,
	PRIMARY KEY (id)
);

CREATE TABLE configuracio_assignatures (
	id INTEGER NOT NULL,
	assignatura VARCHAR NOT NULL,
	grup VARCHAR,
	aula VARCHAR,
	titular VARCHAR NOT NULL,
	ordre INTEGER,
	created_at DATETIME,
	updated_at DATETIME,
	PRIMARY KEY (id)
);

CREATE INDEX idx_config_assignatures ON configuracio_assignatures (assignatura, grup, aula);

CREATE TABLE users (
	id INTEGER NOT NULL,
	username VARCHAR NOT NULL,
	password_hash VARCHAR NOT NULL,
	institucio VARCHAR NOT NULL,
	role VARCHAR,
	active BOOLEAN,
	created_at DATETIME,
	updated_at DATETIME,
	PRIMARY KEY (id),
	UNIQUE (username)
);
