# Actualitzar una instal·lació existent

Passos per actualitzar un servidor que ja té l'aplicació en marxa a la versió
amb migracions d'esquema, contenidor sense root i configuració a la carpeta de
dades. Feu-ho fora de l'horari en què els centres hi treballen, i comproveu
abans que no hi ha ningú connectat. No mostreu dades dels centres, secrets ni
registres.

## Com funciona el codi

- `0001_base` congela l’esquema canònic inicial per a auth i dades.
  Les BD noves creen aquesta base i arriben a la darrera revisió
  (`0004_vigencia_no_substituir`). Cap revisió no importa els models vius.
- `--comprova` valida en només lectura, abans de qualsevol còpia o escriptura,
  **tota** la llista. Una forma històrica coneguda només s’accepta com a punt
  de partida d’una actualització explícita. Una BD `vigent` ha de coincidir
  estrictament amb el canònic: ordre de columnes, tipus, nul·labilitat, defaults,
  PK, unicitat, índexs, col·lacions, FK, checks i objectes SQL. No es normalitza
  la comparació per amagar diferències. Una 0003 amb un ALTER històric es rebutja.
- Les estructures de versions anteriors que es reconeixen són a
  `backend/schema_migrations/historical_schema.json`. Només s’admeten les
  formes exactes i els conjunts de taules documentats, incloses mescles que
  l’antic `create_all` podia deixar en actualitzar. No s’executa codi antic.
  Una forma desconeguda atura la comprovació sense tocar cap BD ni crear còpies;
  el missatge indica restaurar una còpia compatible o demanar ajuda, sense
  imprimir camins, noms de taules alienes ni dades. Mai fer `alembic stamp`
  manual per saltar aquestes comprovacions.
- `0002_neteja_historiques` **retira de dades les taules `users`,
  `configuracio_assignatures` i `exam_schedules`**, si hi són, amb les seves
  files antigues sense ús. La còpia SQLite prèvia les conserva íntegres.
  Completa `idx_configuracio_clau`. La seva comprovació intermèdia encara
  admet les formes conegudes: la normalització es fa a la revisió següent.
- `0003_esquema_canonic` refà **només les taules diferents del canònic**:
  crea una taula auxiliar canònica, hi copia totes les files per nom de columna,
  retira l’original, la torna a crear amb el DDL congelat i hi recupera les files
  i els índexs. No usa RENAME, per evitar reescriure FK dels fills. Tot passa
  dins del mateix `BEGIN IMMEDIATE` que ja fa el migrador, **després de la còpia**.
  Davant una fallada es recuperen dades, DDL i versió dins d’aquella BD.
  La reversió posterior requereix restaurar la còpia, no fer downgrade.
- Llista de taules vigents que, segons la forma d’origen, es poden reconstruir:
  `abreviatures_grups`, `assignatures`, `assignatures_prioritat`, `aules`,
  `configuracio`, `exam_costos_professors`, `exam_restriccions`, `grups`,
  `grups_alliberats`, `nivells`, `substitucions`, `vigilancies` i **`users`
  només a auth**. També es retiren les auxiliars `_migra3_<taula>`, creades
  dins de la transacció. L’operador ha de conèixer aquesta llista abans d’aplicar.
- Es conserven totes les files i valors de les taules vigents, inclosos NULL,
  zeros, valors diferents del default, BLOB, dates, ids i rowid. En esquemes
  inicials es creen les taules que encara no existien; les columnes absents
  prenen NULL, excepte `users.versio_sessio`, que necessita 0. No s’omple ni
  recalcula cap `vigilancies.ordre` existent. Les dues columnes antigues
  d’abreviatures passen als noms canònics conservant els valors.
- Abans del BEGIN, només en la connexió del migrador, es desactiven les FK
  de SQLite per evitar esborrats en cascada durant la reconstrucció de pares.
  L’esquema final conserva les claus canòniques; l’aplicació continua activant
  les FK a cada connexió. Les proves amb pares i fills poblats comproven que
  no es perd cap fila i que `foreign_key_check` queda buit.
- `0004_vigencia_no_substituir` refà **només `no_substituir`**: hi afegeix
  `vigent_des_de` i `vigent_fins_a` (nul·les) i en treu la unicitat
  d’`assignatura`. Només parteix del canònic exacte de la 0003; copia les files
  per rowid sense canviar cap valor, i les dates queden nul·les (les entrades
  existents valen des de sempre: cap xifra no canvia). Si la taula ja té la forma
  nova, no fa res. Les taules d’auth no canvien; només se n’avança la revisió.
- Les BD existents **sense versió, a 0001, a 0002 o a 0003** necessiten l’script
  explícit amb backend i reset aturats abans d’arrencar. La transacció és
  per BD, no per tota la llista: si falla després d’haver migrat alguna BD,
  mantenir els serveis aturats i restaurar la còpia completa.
- `--comprova` no crea fitxers inexistents. `--aplica` exigeix `--backup-dir`.
  La sortida i els noms de les còpies només identifiquen les BD per número i
  tipus. Repetir l’aplicació sobre BD vigents no toca ni un byte ni fa més còpies.
- Configuració mutable: `APP_CONFIG_PATH`, o per defecte `DATA_DIR/config.json`.
  Si encara no existeix, es llegeix `backend/config/config.json` com a transició;
  els desats sempre van al camí nou. `APP_INSTITUCIO` conserva la precedència.
  Els recursos estàtics versionats com `config/pdf.json` són de només lectura.
- El backend s’executa com `10001:10001`. El codi continua sent propietat de
  root i de només lectura per a l’aplicació; només els volums de dades i la
  carpeta de còpies que s’hi munti necessiten escriptura.
- Zona horària: «avui» i l’hora local de l’aplicació són sempre els
  d’Europe/Madrid (`backend/rellotge.py`, amb el paquet `tzdata`), encara que el
  servidor vagi en UTC; la imatge porta també `TZ=Europe/Madrid` per als scripts
  i els registres. **No cal canviar res al servidor** ni al Compose. Comprovació
  després d’arrencar: `docker compose exec -T backend python -c "import rellotge;
  print(rellotge.ara())"` ha de donar l’hora local, no la UTC.

## Preparar la finestra de desplegament

L’operador ha d’identificar en la configuració real els dos projectes Compose,
els noms de projecte Compose, els serveis backend, els dos DATA_DIR, qualsevol AUTH_DB_PATH extern i el mecanisme
del reset nocturn (timer o cron). Aquests detalls no són al repositori. Anotar els
valors sense publicar-los; les variables següents són exemples de disposició,
no adreces reals:

```bash
set -euo pipefail
APP_ROOT=/ruta/absoluta/aplicacio
PROD_COMPOSE="$APP_ROOT/docker-compose.yml"
DEMO_COMPOSE="$APP_ROOT/docker-compose.demo.yml"
PROD_PROJECT=gestor
DEMO_PROJECT=gestor-demo
PROD_SERVICE=backend
DEMO_SERVICE=backend
PROD_DATA="$APP_ROOT/data"
DEMO_DATA="$APP_ROOT/data-demo"
PROD_AUTH="$PROD_DATA/auth.db"
DEMO_AUTH="$DEMO_DATA/auth.db"
DEMO_SNAPSHOT="$APP_ROOT/demo_reset/demo/gestor.db"
RUN_ID=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_DIR="/ruta/absoluta/copies/actualitzacio-$RUN_ID"
```

La carpeta de còpies ha de ser fora d’APP_ROOT i accessible només a l’operador.
Comprovar els muntatges Compose abans de parar. No assumir que producció i demo
comparteixen auth.db. Si la comparteixen, indicar-la només una vegada.

1. Registrar commit anterior i imatges anteriors. Conservar els fitxers Compose i
   d’entorn dins de la còpia privada; no imprimir-los ni incorporar-los a git.
2. Pausar el reset de demo i les altres tasques que escriguin BD. Si és systemd:
   `sudo systemctl stop NOM.timer NOM.service`; si és cron, desactivar només la
   línia del reset i guardar abans una còpia privada del crontab. Esperar que no
   quedi cap reset en curs. Anotar com reactivar exactament el mecanisme trobat.
3. Recuperar abans de reconstruir la imatge la configuració antiga de cada
   contenidor que en tingui (no n’imprimeix el contingut):

```bash
umask 077
mkdir -p "$BACKUP_DIR"
git -C "$APP_ROOT" rev-parse HEAD > "$BACKUP_DIR/commit-anterior.txt"
docker compose -p "$PROD_PROJECT" -f "$PROD_COMPOSE" images -q "$PROD_SERVICE" > "$BACKUP_DIR/imatge-prod.txt"
docker compose -p "$DEMO_PROJECT" -f "$DEMO_COMPOSE" images -q "$DEMO_SERVICE" > "$BACKUP_DIR/imatge-demo.txt"
test -s "$BACKUP_DIR/imatge-prod.txt"
test -s "$BACKUP_DIR/imatge-demo.txt"
docker image tag "$(cat "$BACKUP_DIR/imatge-prod.txt")" "gestor-backend-prod-rollback:$RUN_ID"
docker image tag "$(cat "$BACKUP_DIR/imatge-demo.txt")" "gestor-backend-demo-rollback:$RUN_ID"
if docker compose -p "$PROD_PROJECT" -f "$PROD_COMPOSE" exec -T "$PROD_SERVICE" test -f /app/config/config.json; then
  docker compose -p "$PROD_PROJECT" -f "$PROD_COMPOSE" cp "$PROD_SERVICE":/app/config/config.json "$BACKUP_DIR/config-prod.json"
fi
if docker compose -p "$DEMO_PROJECT" -f "$DEMO_COMPOSE" exec -T "$DEMO_SERVICE" test -f /app/config/config.json; then
  docker compose -p "$DEMO_PROJECT" -f "$DEMO_COMPOSE" cp "$DEMO_SERVICE":/app/config/config.json "$BACKUP_DIR/config-demo.json"
fi
docker compose -p "$PROD_PROJECT" -f "$PROD_COMPOSE" stop "$PROD_SERVICE"
docker compose -p "$DEMO_PROJECT" -f "$DEMO_COMPOSE" stop "$DEMO_SERVICE"
sudo tar --acls --xattrs --numeric-owner -C "$APP_ROOT" --exclude='./logs' --exclude='*.log' \
  --exclude='./backend/venv' --exclude='./frontend/node_modules' \
  -czpf "$BACKUP_DIR/aplicacio-abans.tar.gz" .
sudo tar -tzf "$BACKUP_DIR/aplicacio-abans.tar.gz" > "$BACKUP_DIR/inventari-privat.txt"
```

Amb tots els escriptors aturats, la còpia completa inclou BD i fitxers WAL/SHM
coherents, configuració, demo activa i instantània del reset. Si algun volum o
AUTH_DB_PATH és fora d’APP_ROOT, copiar-lo també amb propietaris i permisos
preservats i anotar el camí a l’inventari privat. Verificar l’arxiu i la còpia
abans de continuar. No compartir l’inventari: pot contenir noms de centres.

## Esquemes anteriors als antics _ensure_*

La 0003 ja tracta directament els esquemes coneguts que encara no tenen
`substitucions.aula`, `vigilancies.ordre` o `users.versio_sessio`, també a la
instantània de demo. **No executar prèviament els `_ensure_*` de la imatge
anterior**: el seu ompliment d’ordre podia modificar valors. L’actualització
normalitza l’esquema i conserva els valors que ja hi ha, sense reconstruir
regles de negoci antigues ni reexecutar migradors de dades.

Si la comprovació rebutja una estructura, mantenir els serveis aturats i
restaurar una còpia compatible o demanar ajuda. No improvisar ALTER, DROP,
stamp ni preparacions amb versions anteriors.

## Actualitzar codi, configuració i permisos

Actualitzeu el codi (`git fetch`, reviseu els canvis i `git pull`). Després, amb
els backends encara aturats:

```bash
# Instal·lar les còpies antigues només si no hi ha ja configuració al volum.
if [ -f "$BACKUP_DIR/config-prod.json" ] && [ ! -e "$PROD_DATA/config.json" ]; then
  sudo install -m 600 -o 10001 -g 10001 "$BACKUP_DIR/config-prod.json" "$PROD_DATA/config.json"
fi
if [ -f "$BACKUP_DIR/config-demo.json" ] && [ ! -e "$DEMO_DATA/config.json" ]; then
  sudo install -m 600 -o 10001 -g 10001 "$BACKUP_DIR/config-demo.json" "$DEMO_DATA/config.json"
fi
# Els directoris, no només els .db, necessiten escriptura per a WAL i journals.
sudo chown -R 10001:10001 "$PROD_DATA" "$DEMO_DATA"
sudo chmod -R u+rwX "$PROD_DATA" "$DEMO_DATA"
sudo chown -R 10001:10001 "$(dirname "$DEMO_SNAPSHOT")"
sudo chmod -R u+rwX "$(dirname "$DEMO_SNAPSHOT")"
docker compose -p "$PROD_PROJECT" -f "$PROD_COMPOSE" build "$PROD_SERVICE"
docker compose -p "$DEMO_PROJECT" -f "$DEMO_COMPOSE" build "$DEMO_SERVICE"
```

No fer `chmod 777` ni `chown` de la carpeta de codi. Si hi ha volums o fitxers
externs, incloent-hi un APP_CONFIG_PATH explícit, donar els mateixos permisos a
les seves carpetes de dades. Ajustar la tasca de reset perquè les còpies que
creï també siguin de `10001:10001`, llegibles i escrivibles per aquest usuari.
Si el reset usa `cp -a`, la propietat de la instantània anterior ho garanteix;
si usa una altra ordre, definir la propietat explícitament després de copiar.
No reactivar el reset fins que s’hagi comprovat aquest punt.

## Migrar totes les BD, també la instantània

Crear un manifest privat de camins explícits, sense imprimir noms de centres.
Inclou tots els `*/gestor.db` dels dos DATA_DIR (també centres desactivats), les
auth i la instantània. Executar el codi nou dins d’un contenidor efímer amb els
mateixos UID/GID. Els muntatges conserven els camins absoluts del manifest;
només es munten els directoris indicats, mai l’arrel sencera del servidor.

```bash
export PROD_DATA DEMO_DATA PROD_AUTH DEMO_AUTH DEMO_SNAPSHOT BACKUP_DIR
python3 - <<'PY'
import os
from pathlib import Path
roots = [Path(os.environ[k]).resolve() for k in ('PROD_DATA', 'DEMO_DATA')]
items = [('auth', Path(os.environ[k]).resolve()) for k in ('PROD_AUTH', 'DEMO_AUTH')]
items += [('data', p.resolve()) for root in roots for p in sorted(root.glob('*/gestor.db'))]
items += [('data', Path(os.environ['DEMO_SNAPSHOT']).resolve())]
seen = set()
with open(Path(os.environ['BACKUP_DIR']) / 'bd-manifest.nul', 'xb') as f:
    for kind, path in items:
        if path in seen:
            continue
        if not path.is_file():
            raise SystemExit('Falta una BD esperada; no continuar.')
        seen.add(path)
        f.write(('--' + kind).encode() + b'\0' + str(path).encode() + b'\0')
print('BD previstes:', len(seen))
PY
mapfile -d '' -t DB_ARGS < "$BACKUP_DIR/bd-manifest.nul"
sudo install -d -m 700 -o 10001 -g 10001 "$BACKUP_DIR/sqlite"
# Cal que els camins dins del contenidor coincideixin amb els del manifest.
MOUNTS=(-v "$PROD_DATA:$PROD_DATA" -v "$DEMO_DATA:$DEMO_DATA"
        -v "$(dirname "$DEMO_SNAPSHOT"):$(dirname "$DEMO_SNAPSHOT")"
        -v "$BACKUP_DIR/sqlite:/copies")
docker compose -p "$PROD_PROJECT" -f "$PROD_COMPOSE" run --rm --no-deps --user 10001:10001 \
  "${MOUNTS[@]}" --entrypoint python "$PROD_SERVICE" \
  -m scripts.migra_esquemes --comprova "${DB_ARGS[@]}"
# Reviseu el resultat de la comprovació abans d'aplicar la migració.
docker compose -p "$PROD_PROJECT" -f "$PROD_COMPOSE" run --rm --no-deps --user 10001:10001 \
  "${MOUNTS[@]}" --entrypoint python "$PROD_SERVICE" \
  -m scripts.migra_esquemes --aplica --backup-dir /copies "${DB_ARGS[@]}"
docker compose -p "$PROD_PROJECT" -f "$PROD_COMPOSE" run --rm --no-deps --user 10001:10001 \
  "${MOUNTS[@]}" --entrypoint python "$PROD_SERVICE" \
  -m scripts.migra_esquemes --comprova "${DB_ARGS[@]}"
```

Afegir muntatges explícits per a qualsevol auth fora dels dos DATA_DIR. El nou
script no carrega `.env` ni busca centres pel seu compte. A la tercera ordre,
totes les BD han de dir `vigent`; repetir `--aplica` no ha de fer cap canvi ni
crear més còpies. Qualsevol error ha de donar sortida diferent de zero.

## Aplicar la 0004 en una instal·lació que ja era a la 0003

Quan el desplegament porta la 0004 i les BD ja eren `vigent` a la 0003, el
backend nou **no arrenca** fins que s’han migrat («Migracions pendents»). Seguir
els mateixos passos d’aquesta guia, en aquest ordre:

1. Aturar els dos backends i el reset de la demo; cap escriptor actiu.
2. Còpia de la carpeta de l’aplicació (sense logs), com a cada desplegament.
3. `git pull` i construir la imatge nova **sense arrencar-la**
   (`docker compose build`).
4. Fer el manifest i executar `--comprova`, `--aplica --backup-dir` i un altre
   `--comprova` (apartat anterior), incloent-hi **totes** les `gestor.db` dels
   centres, `data-demo/demo/gestor.db` i la instantània
   `demo_reset/demo/gestor.db`, que el reinici nocturn copia sense reiniciar el
   backend: si no es migra, l’endemà la demo no arrencaria. Incloure-hi també
   **les dues `auth.db`** (la principal i la de la demo): la 0004 no hi canvia
   cap taula, però n'avança la revisió, i sense migrar-les el backend tampoc no
   arrenca. La primera comprovació ha de dir `pendent` per a totes; la darrera,
   `vigent` per a totes.
5. Arrencar i comprovar (apartat següent). A Prioritats, «No substituir» ha de
   mostrar les mateixes activitats que abans, sense cap data al costat.
6. **Abans de reactivar el reset nocturn**, fer un reinici manual de la demo (o
   el `--comprova` d’una còpia temporal de la instantània, com diu «Arrencar i
   comprovar») i comprovar que arrenca: el reset copia la instantània sencera i,
   si no s’hagués migrat, la demo no cauria ara sinó l’endemà a les 4:00.

Desfer: com a «Desfer el desplegament», restaurant les còpies de `--backup-dir`
(la 0004 no té downgrade).

## Arrencar i comprovar

```bash
docker compose -p "$PROD_PROJECT" -f "$PROD_COMPOSE" up -d --no-deps "$PROD_SERVICE"
docker compose -p "$DEMO_PROJECT" -f "$DEMO_COMPOSE" up -d --no-deps "$DEMO_SERVICE"
docker compose -p "$PROD_PROJECT" -f "$PROD_COMPOSE" exec -T "$PROD_SERVICE" id -u
docker compose -p "$DEMO_PROJECT" -f "$DEMO_COMPOSE" exec -T "$DEMO_SERVICE" id -u
```

Els dos UID han de ser 10001. Comprovar web i `/api/health` (200), entrada i
operacions diàries en un centre de prova, configuració persistent després d’un
reinici, i escriptures de BD sense errors de permisos. Revisar errors d’arrencada
sense compartir IP ni dades dels registres. No cal cap canvi al frontend.
Comprovar també una còpia **temporal** de la instantània amb el mateix mecanisme
de reset i `--comprova`: ha de mantenir la revisió i els permisos. Reactivar el
reset i les tasques periòdiques exactament com estaven només després d’aquesta
validació. Conserveu la còpia completa fins que hàgiu validat l'actualització.

## Desfer el desplegament

1. Aturar altre cop els dos backends i el reset. No permetre escriptures mentre
   es restaura. Si hi ha hagut activitat des del desplegament, fer-ne una còpia
   separada abans i decidir com conservar-la: restaurar perd els
   canvis posteriors a la còpia.
2. Mostrar abans el llistat de fitxers que se sobreescriuran o retiraran. Inclou
   els `config.json` nous i qualsevol `.db-wal`/`.db-shm` creat després de la
   còpia. No restaurar un .db sobre un WAL d’una altra versió.
3. Apartar la instal·lació fallida en una carpeta privada i restaurar l’arxiu
   complet a APP_ROOT, amb el mateix propietari/permisos que tenia abans. Amb
   APP_ROOT i BACKUP_DIR ja verificats, exemple (no executar sobre un directori
   en ús):

```bash
FAILED_ROOT="${APP_ROOT}.fallida-$RUN_ID"
sudo mv "$APP_ROOT" "$FAILED_ROOT"
sudo mkdir -p "$APP_ROOT"
sudo tar --acls --xattrs --numeric-owner -xzpf "$BACKUP_DIR/aplicacio-abans.tar.gz" -C "$APP_ROOT"
```

4. Restaurar també els volums externs des de les còpies anotades. Verificar que
   codi, Compose, variables d’entorn, configuració, auth, centres, demo activa i
   instantània del reset són els del mateix instant. Els permisos originals es
   restauren amb l’arxiu; no cal deduir quin UID tenia cada fitxer.
5. Arrencar amb el codi de l’arxiu i les imatges anteriors conservades:

```bash
test "$(git -C "$APP_ROOT" rev-parse HEAD)" = "$(cat "$BACKUP_DIR/commit-anterior.txt")"
# Fer servir exactament les imatges conservades, sense reconstruir dependències.
export BACKUP_DIR PROD_SERVICE DEMO_SERVICE RUN_ID
python3 - <<'PY_RETORN'
import json
import os
from pathlib import Path
for kind, key in [('prod', 'PROD_SERVICE'), ('demo', 'DEMO_SERVICE')]:
    override = {'services': {os.environ[key]: {'image': f"gestor-backend-{kind}-rollback:{os.environ['RUN_ID']}"}}}
    path = Path(os.environ['BACKUP_DIR']) / f'rollback-{kind}.json'
    path.write_text(json.dumps(override))
PY_RETORN
docker compose -p "$PROD_PROJECT" -f "$PROD_COMPOSE" -f "$BACKUP_DIR/rollback-prod.json" \
  up -d --no-deps --no-build --pull never --force-recreate "$PROD_SERVICE"
docker compose -p "$DEMO_PROJECT" -f "$DEMO_COMPOSE" -f "$BACKUP_DIR/rollback-demo.json" \
  up -d --no-deps --no-build --pull never --force-recreate "$DEMO_SERVICE"
```

Comprovar 200, entrada i dades del centre de prova; reactivar el reset anterior.
Conserveu aquests tags locals fins que s'hagi validat l'actualització; no feu neteja
d’imatges durant la finestra de desplegament.
No executar `alembic downgrade base`: es nega a esborrar les taules. La reversió
segura és la còpia completa.

Per crear revisions futures, afegir un fitxer a `schema_migrations/versions/`
amb `down_revision` apuntant a l’anterior, usar `op`/SQL congelat i discriminar
`context.config.attributes['kind']` quan només afecti auth o dades. Mai editar la
base ni importar els models actuals des d’una revisió. Afegir tests d’upgrade,
rollback i creació nova; el guardià dels models/base s’haurà d’adaptar a l’esquema
vigent quan canviï l’esquema canònic.

## Registres d’accés i retenció de 30 dies

El backend registra data i hora, usuari, rol, centre, mètode HTTP, plantilla de
la ruta, codi de resposta i durada. Per exemple, la ruta queda com
`/api/substitucions/{data}/{hora}/{professor}`: no hi desa els valors dels
paràmetres, la query ni la IP. Uvicorn no genera un segon registre d’accés.
Els errors que indiquen la ruta també fan servir la plantilla; les traces de
diagnòstic continuen al registre d’errors de la consola.

Sense `ACCESS_LOG_PATH`, els resums continuen a la consola del backend. Per
conservar-los en un fitxer independent, cal configurar
`ACCESS_LOG_PATH=/var/log/gestor/access.log`. El backend rota el fitxer diàriament
a mitjanit UTC i en conserva 30 còpies; no duplica aquests resums a la consola.

Caddy desa l’accés a `/var/log/caddy/access.log` (volum `./logs/caddy`), amb les
IP escapçades, sense query i amb els segments de professor i assignatura
substituïts per `{professor}`, `{nom}` o `{assignatura}`. El filtre compartit
cobreix Substitucions (absències, hores i assignació), Estadístiques (detall)
i les assignatures de Configuració i Prioritats. Els fitxers rotats tenen un
termini màxim de `720h` (30 dies) i un màxim de 10 còpies. La sintaxi de filtratge
i de retenció és la de la [documentació de Caddy](https://caddyserver.com/docs/caddyfile/directives/log).

Canvis que cal fer al servidor en actualitzar una instal·lació existent:

1. Crear `logs/backend` i donar-hi propietat `10001:10001`, l’UID/GID del backend.
2. Afegir la variable `ACCESS_LOG_PATH` indicada a l’entorn del backend i el volum
   `./logs/backend:/var/log/gestor` al servei `backend` (hi ha el comentari a
   `docker-compose.yml.example`). El fitxer ha de ser escrivible per aquest UID.
3. Incorporar el filtre i `roll_keep_for 720h` de `Caddyfile.example` al Caddyfile
   del servidor, conservant el domini i els altres ajustos propis. Mantenir el
   volum de Caddy existent.
4. Validar el Caddyfile amb `caddy validate --config /etc/caddy/Caddyfile`, i
   reiniciar Caddy quan es desplegui: els canvis de rotació d’un fitxer ja obert
   necessiten reinici. Recrear el backend perquè rebi la variable i el volum.
5. Comprovar que el filtre funciona, no només que la configuració és vàlida: fer
   una petició sense sessió amb un nom inventat, per exemple
   `/api/substitucions/2026-01-01/1/NomDeProva?x=1`, i confirmar que a la línia
   del registre de Caddy hi ha `{professor}` i no hi ha `NomDeProva` ni `x=1`.

La retenció de la consola sense `ACCESS_LOG_PATH` continua depenent del sistema
que la recull (a l’exemple de Compose, rotació per mida de Docker).

## Temps límit de la generació del planificador

Cada motor del planificador té un temps màxim de cerca que es tria a la
pantalla (paràmetres avançats del motor): 20 s per defecte i **120 s com a
màxim** (`scheduler_engine/defaults.py`: `SEGONS_MAXIMS_PER_DEFECTE` i
`SEGONS_MAXIMS_LIMIT`; el servidor respon 422 per sobre). Quan s’acaba el temps,
el motor es queda amb la millor solució trobada i ho diu (`motiu_aturada`).
La petició de generar dura aquest temps més la preparació i la validació, i
cap pas de la cadena no l’ha de tallar abans:

| Pas | Temps límit | Cal canviar res? |
|---|---|---|
| Pantalla (axios) | 300 s per a generar i per a l’anàlisi | No |
| Caddy (`reverse_proxy`) | sense temps de lectura per defecte | No, si el Caddyfile del servidor no n’hi ha afegit cap (`grep -n timeout Caddyfile`); si en té, que sigui de 180 s o més |
| nginx del contenidor del frontend (`/api/`, només sense Caddy davant: `docker-compose.local.yml`) | `proxy_read_timeout 180s` a `frontend/nginx.conf` | Reconstruir la imatge del frontend en actualitzar (`docker compose up --build -d`) |
| uvicorn | sense temps límit per petició | No |

Mentre es genera, el backend continua atenent la resta de peticions (la ruta
és síncrona i s’executa en un fil a part; ho comprova
`tests/test_planificador_no_bloqueja.py`). Una generació llarga ocupa un fil i
una CPU durant tot el temps triat: per això el màxim és de 120 s i no més.
