# Inventari d’esquemes SQLite (05/11/2026)

Revisió de **tots** els commits accessibles amb `git log --all` que toquen
`models.py` o `database.py`: 65 al privat i 17 al clon públic local (inclou
historial compartit i branques antigues). Revisats també tots els canvis de
`_ensure_*` i de DDL explícit dels migradors. Només lectura dels objectes git:
cap arrencada ni import del programa antic, cap lectura de BD, centres,
registres o `.env`,
cap connexió al servidor, cap modificació del públic.

`schema_history.json` congela el DDL generat per les classes declaratives de
cada versió (extraient només les classes amb `__tablename__`), sense importar
`database.py`. Els esquemes idèntics s’agrupen; `sources` en conserva tots els
commits revisats. S’inclouen les còpies antigues i portables de l’historial.
Els canvis de format, rellotge, noms de classe i organització no alteren el DDL.

## Formes trobades

- 14 metadades diferents dels models, de `cb1ab02` fins a `32f15ca`;
  també cobreixen totes les versions del públic fins a `3eea962`.
- Les primeres abreviatures (`cb1ab02`) tenen `grups_origen`, `grup_abreviat`
  i no tenen `updated_at` ni `idx_abreviatura`. Des de `58f1100`,
  `grups_originals`, `abreviatura`, `updated_at` i l’índex.
- `substitucions.aula`: absent als models inicials; al mig en crear una BD
  nova; al final amb `ALTER ... ADD COLUMN aula VARCHAR` (`99d85ca`,
  incloent els commits equivalents `1016df4`, `a2366fa`, `47c3c4e`). Sense default.
- `vigilancies.ordre`: absent abans de `7e824b6`; al mig al model nou;
  al final amb `ALTER ... ADD COLUMN ordre INTEGER`. Sense default.
- Auth `users.versio_sessio`: absent abans de `0f360af`; al mig, amb
  `DEFAULT '0' NOT NULL`, al model nou; al final, amb `NOT NULL DEFAULT 0`,
  a l’ALTER antic. Usuaris en BD de dades: forma antiga sense versió.
- `assignatures_prioritat.auto_assignada`: forma del model sense default;
  també les dues formes comunicades a l’assaig i congelades als tests previs:
  `DEFAULT '0'` a la posició canònica i `DEFAULT 0` al final. L’ALTER d’aquesta
  última no figura en el codi versionat; no se n’inventa una procedència.
- `idx_configuracio_clau`: absent en esquemes antics; `create_all` no el
  completa si la taula ja existeix.
- Taules afegides successivament: autenticació (`d92c7ad`), versions XML i
  professors (`348154b`), prioritats/configuració d’exàmens/baixes (`58f1100`),
  restriccions/preferències/pesos/costos d’exàmens (`fa10a04`), cursos
  (`ce2a88d`), grups amagats (`9410f15`), propostes descartades (`e01b734`),
  alliberaments per període (`79b1ac6`). `create_all` les afegia sense tocar
  les files de les taules existents.
- Taules retirades: `configuracio_assignatures` (`c69b1c5`), `exam_schedules`
  (`38564c0`), i usuaris locals en separar auth/dades. La 0002 en conserva la
  còpia i les retira; no són files vigents que reconstrueixi la 0003.
- Migrador JSON `migrate_to_sqlite.py` (`a19e83e`): `TEXT`, `TIMESTAMP`,
  `AUTOINCREMENT`, defaults SQL; unicitat implícita a assignatures i grups
  alliberats. Nou taules inicials, amb abreviatures antigues i sense `aula`.
- Migrador `migrate_restriccions_pes.py` (`fa10a04`/`f6302e2`):
  `exam_restriccions.pes INTEGER DEFAULT 100` al final si faltava; costos amb
  `id INTEGER PRIMARY KEY AUTOINCREMENT`, `pes DEFAULT 100` i dates
  `DEFAULT CURRENT_TIMESTAMP`. No es reexecuta la seva transformació de dades.
- `_ensure_cursos_schema` (`ce2a88d`, retirat a `92e4f3e`): només eliminava
  `actiu` i el seu índex; **cap model versionat no creava aquesta columna**.
  Per tant, `cursos.actiu` continua sent desconeguda, no una variant admesa.

Les 17 instantànies de prova (14 models + JSON + 2 formes del migrador de
restriccions) contenen **44 formes exactes de taula**, amb els seus índexs i
claus. Les variants d’ALTER i de l’assaig tenen, a més, regressions específiques.
Les combinacions produïdes en actualitzar conserven estructures antigues:
cal provar tant la instantània original com la completada amb `create_all`.

## Estat

Inventari i fixtures congelats; 0003 implementada. El catàleg de producció
conté 52 formes exactes: les 44 anteriors més ALTER i variants d’índex/default.
Cada instantània es prova original, completada amb `create_all` i amb les
columnes dels `_ensure_*` afegides al final; cada forma de taula es prova també
amb la resta del canònic. La prova aïlla el contingut abans/després de la 0003,
posterior a la neteja autoritzada de 0002. Les formes conegudes es rebutgen
si es declaren 0003 sense ser canòniques. SQL final comparat també independentment
del validador, incloent ordre, índexs i claus; proves de rollback en cada fase,
BLOB i rowid dispersos. Cap referència dels arnesos canviada.
