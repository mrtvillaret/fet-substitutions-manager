# Com funciona l'aplicació i com es compta cada cosa

Esquema del domini: d'on surt cada dada, quines files de substitució hi ha i què
compta cada pantalla, PDF i informe. Les regles detallades són a `CLAUDE.md`
(«Regles del domini»); aquí només el mapa. Si una regla canvia, canvia aquí també.

## 1. Les entrades

| Dada | Qui la posa | On és |
|---|---|---|
| Horari (XML de FET, per versions amb data d'inici) | admin | `xml_versions`, `Dia` en tria la vigent de cada data |
| Absències del dia (professor, hores, absència o servei) | user | files de `substitucions` |
| Absència coberta (abans «baixa»): període amb el substitut ja a l'XML | user | `professors_baixa` |
| Grups i professors alliberats d'un dia; activitats alliberables | user | `grups_alliberats`, `alliberaments_periode` |
| «No substituir»: activitats que no cal cobrir (buit = hora sense activitat) | admin | `no_substituir` |
| Prioritats: activitats de qui pot anar a substituir, per categoria i pes | admin | `prioritats` |
| Vigilàncies d'examen del dia (a mà o publicades pel planificador) | user | `vigilancies` |

## 2. El dia: qui hi és i qui té classe

```
XML vigent aquella data ──► Dia / DiaEscolar
                              │
   absència coberta ─────────►├─ l'absent desapareix de l'horari (no és res: ni
                              │  substituït, ni substitut, ni vigilant, ni disponible)
   grups / professors ───────►├─ sense_classe(): el professor queda lliure
   alliberats                 │  (substitucions: un examen NO allibera; vigilàncies: sí)
   No substituir ────────────►└─ aquelles activitats no generen res a cobrir
```

## 3. Els tipus de fila de substitució (`tipus_absencia`)

Una fila = una hora d'un professor que algú ha de cobrir.

| Tipus | Què és | Qui la crea | Compta com a absència? |
|---|---|---|---|
| `ABSENCIA` | La classe d'un professor absent | En marcar l'absència | Sí (absència) |
| `SERVEI` | La classe d'un professor fora per servei (sortida, formació…) | En marcar-la com a servei | Sí (servei) |
| `VIGILANCIA_ABSENT` | La vigilància d'examen d'un vigilant absent | Automàtica, en marcar l'absència | No: la mateixa hora ja compta per la seva fila de classe |
| `VIGILANCIA` | La classe d'un vigilant present que a aquella hora vigila un examen | Generació | No (el professor no falta) |
| `ENCADENADA` | L'activitat que deixa el substitut (és a prioritats i no a «No substituir») | Generació i tria a mà; un sol nivell | No (el professor no falta) |

Regles que hi intervenen:
- Si el vigilant és absent, la seva classe és `ABSENCIA` i l'examen, `VIGILANCIA_ABSENT`;
  `VIGILANCIA` només existeix si el vigilant és present. En marcar o treure l'absència,
  la mateixa fila canvia de tipus i conserva el substitut.
- L'hora d'absència compta **un sol cop** encara que hi hagi classe i vigilància.
- Cas límit acceptat: si a aquella hora només tenia vigilància, l'absència no surt com a
  absència, només la vigilància com a feina a cobrir.

## 4. El flux d'un dia

```
marcar absències ──► files ABSENCIA/SERVEI (+ VIGILANCIA_ABSENT)
                         │
«Genera pendents» / «Regenera tot» ──► motor (assignacio.py) tria substituts
                         │               per prioritats; crea VIGILANCIA i ENCADENADA
canvis del dia (alliberats, absències, absència coberta)
                         └─► NO assignen: treuen els substituts que ja no valen
                             (motius_substitut) i la fila queda pendent amb avís
```

## 5. Què compta cada sortida

**Quines files es veuen a la pantalla Substitucions** ho decideix una sola regla
(`substitucions/visibilitat.py`), que fan servir la pantalla i els recomptes:
- Les `VIGILANCIA_ABSENT` es veuen sempre (vegeu més avall per què).
- Les altres no es veuen si l'activitat és a «No substituir», tingui grup o no.
- Tampoc no es veuen si el professor està alliberat aquella hora (`sense_classe`: el
  grup sense classe o ell alliberat, també a les files sense grup).

Les files sense assignatura (hores sense activitat) no tenen cap condició especial: el
nom buit és un nom més de «No substituir» (regla dels noms, `nom_net`), i per això queden
amagades. Si un centre no té el buit a «No substituir», es veuen i compten: és la seva
configuració.

Les VIGILANCIA_ABSENT es veuen sempre a la pantalla Substitucions: no són una hora de
l'horari del professor, sinó un tipus de fila que crea el programa quan falta un vigilant
d'examen («VIGILÀNCIA» a la columna Assignatura n'és només l'etiqueta). «No substituir»
decideix quines hores de l'horari cal cobrir, i per això no s'hi aplica.

Les **absències i la cobertura** compten el que es veu a la pantalla Substitucions. Les
**substitucions fetes** compten totes les files amb substitut, sense cap filtre: si té
substitut, algú hi ha anat.

| | ABSENCIA | SERVEI | VIGILANCIA_ABSENT | VIGILANCIA | ENCADENADA |
|---|---|---|---|---|---|
| Pantalla Substitucions i PDF del dia | si es veu | si es veu | sempre | si es veu | si es veu (sota la seva) |
| **Absències i serveis**: informe de direcció, informe per professor; Estadístiques (per professor, top d'absents, classes, detall) | absència | servei | — | — | — |
| **Cobertura** (a cobrir, cobertes, %): portada, per mes, dia × hora, grups i nivells; Estadístiques (resum, temporals, classes) | sí | sí | — | — | — |
| **Substitucions fetes** (amb substitut, sense filtres): PDF de direcció (rànquing, professor × mes), PDF per professor; Estadístiques (top de substituts, taula per professor i balanç, detall, franges); «(n/total)» del desplegable de substituts | sí | sí | sí | sí | sí |
| **Vigilàncies cobertes** (Estadístiques, apartat propi, per resultat) | — | — | la vigilància és coberta si té substitut | — | — |
| **Vigilàncies fetes per professor** (Estadístiques) | — | — | — (el substitut ho té a les substitucions fetes) | — | — |

Les **substitucions fetes no són la cobertura**. La cobertura diu quantes absències i
serveis tenen substitut. Les fetes compten totes les files amb substitut, perquè mesuren
la feina de cada professor. Per això la suma de fetes pot ser més gran que les cobertes:
qui cobreix l'encadenada que deixa un substitut també en fa una. Les etiquetes de les
taules ho han de deixar clar.

Les vigilàncies d'examen es compten **per resultat**: una vigilància és coberta si hi va
el vigilant (assignat i no falta) o si la seva fila de vigilant absent té substitut,
perquè l'examen ha quedat vigilat; si no, és descoberta. Les **vigilàncies fetes per
professor** són només les de la pantalla Vigilàncies: el vigilant assignat que no falta.
Cada feina es compta en un sol lloc, segons la pantalla on surt: qui cobreix una
vigilància de vigilant absent des de Substitucions ho té a les substitucions fetes, no
a les vigilàncies fetes. L'informe no mostra les vigilàncies.

Al PDF de direcció, la columna «Total» de l'evolució mensual, la cobertura de cada mes,
la fila TOTAL i la portada fan la mateixa fórmula (cobertes / absències + serveis).

Cap franja té un tracte especial: una hora de pati compta com qualsevol altra. A
Estadístiques, un filtre per hores refà tots els recomptes amb les franges triades. Les
franges surten de l'horari, no del codi: la unió, pel nom, de les franges de les versions
de l'horari vigents a l'interval. Els informes PDF que es generen des d'Estadístiques
fan servir el mateix filtre, i la capçalera diu quines hores s'han triat. La targeta
«Absències cobertes» del PDF de direcció no hi entra: compta períodes, no hores.

Ordre: els rànquings van per comptador i els empats, per ordre alfabètic natural
(`noms.ordre_alfabetic`), a la web i al PDF; els selectors de professor, alfabètics.

## 6. Criteris decidits (29/10 i 30/10/2026)

Un vigilant que falta es pot resoldre de dues maneres: reassignant la vigilància
(pantalla Vigilàncies, sense cap substitució) o posant substitut a la fila
`VIGILANCIA_ABSENT`. Perquè les xifres no depenguin del camí, n'hi ha dues de diferents:
- **Absències i cobertura**: el que es veu a la pantalla Substitucions (la regla de
  l'apartat 5), i d'això només les hores marcades com a absència o servei
  (`ABSENCIA` i `SERVEI`). Cobertura = d'aquestes absències i serveis, quantes tenen
  substitut. Cap altre tipus no hi compta, ni a dalt ni a baix: la vigilància de
  vigilant absent no és una absència més (la mateixa hora ja compta per la seva fila de
  classe), i a les encadenades i les vigilàncies no falta ningú.
- **Absències**: compten les hores que s'han hagut de cobrir, no l'assistència del
  professor. Si falta a una activitat de «No substituir» (p. ex. una guàrdia que no es
  cobreix), aquella hora no compta; si l'activitat s'ha de cobrir, compta com una classe.
- **Substitucions fetes**: la feina de cada professor. Les files amb substitut, de
  qualsevol tipus (també `ENCADENADA`, `VIGILANCIA` i `VIGILANCIA_ABSENT`), sense els
  filtres de «No substituir» ni d'alliberats: si té substitut, algú hi ha anat (a les BD
  locals, cap fila amb substitut no és de «No substituir» ni d'un absent alliberat). Qui
  cobreix una absència en fa una, i qui cobreix l'encadenada que deixa també. El
  «(n/total)» del desplegable de substituts compta les mateixes, les del curs: n, a
  aquell dia de la setmana i hora; total, al curs.
- Una vigilància d'un absent resolta canviant el vigilant a Vigilàncies no surt a
  Substitucions i, per tant, no compta com a substitució feta (sí a l'apartat de
  vigilàncies: hi va el vigilant nou). És coherent: les fetes compten les files de
  Substitucions.
- **Balanç** per professor = substitucions fetes − absències (els serveis no resten,
  són feina per al centre). Sense categories normal/pati/altres ni ràtio.
- **Vigilàncies**: apartat propi, comptat per resultat (apartat 5). Coberta = hi va el
  vigilant, o la seva fila de vigilant absent té substitut; si no, descoberta.
- **Cada feina, en un sol lloc**, segons la pantalla on surt: les vigilàncies fetes per
  professor són les de la pantalla Vigilàncies (el vigilant assignat que no falta); qui
  cobreix una vigilància de vigilant absent des de Substitucions ho té a les
  substitucions fetes, no a les vigilàncies fetes.
- Els filtres («No substituir» i alliberats) són els de la pantalla Substitucions, i
  només valen per a les absències i la cobertura; les substitucions fetes no en tenen.
- A Prioritats, en afegir a «No substituir» una activitat que a l'horari vigent té grup,
  la pantalla avisa (sense impedir desar-la) que aquell grup quedarà sense professor quan
  qui la fa falti, perquè l'hora no sortirà a Substitucions.
- Els recomptes de la web i dels informes surten d'un sol lloc compartit i donen el
  mateix per al mateix interval.

## 7. Aplicat (30/10/2026) i pendent

Els criteris dels apartats 5 i 6 s'apliquen a la pantalla Estadístiques i als dos
informes PDF, amb els recomptes al mòdul comú `recomptes/` (vegeu `ARQUITECTURA.md`).
El filtre per hores també s'aplica als informes PDF (decidit el 30/10/2026). La regla de
quines files es veuen a Substitucions (apartat 5) la fan servir la pantalla (backend; el
frontend ja no filtra pel seu compte) i els recomptes.
