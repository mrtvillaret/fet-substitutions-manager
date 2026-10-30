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

`real` = fila amb activitat que no és a «No substituir» i amb el professor que tenia
classe (no alliberat). Les files no reals no compten enlloc dels recomptes.

| | ABSENCIA | SERVEI | VIGILANCIA_ABSENT | VIGILANCIA | ENCADENADA |
|---|---|---|---|---|---|
| Pantalla i PDF del dia | surt | surt | surt | surt | surt (sota la seva) |
| Informe direcció: absències / serveis | absència | servei | — | — | — |
| Informe direcció: a cobrir, cobertura, per mes, dia×hora, grups | sí | sí | — (decidit 29/10) | — | — |
| Informe direcció: substitucions fetes (rànquing, professor × mes) | sí | sí | — (decidit 29/10) | — | — |
| Informe per professor: llista, cobertes i pendents de les seves absències | absència | servei | — (decidit 29/10) | — | — |
| Informe per professor: substitucions fetes | sí | sí | — (decidit 29/10) | — | — |
| Estadístiques: absències per professor | sí | sí («altres») | **sí** ⚠️ | — | — |
| Estadístiques: substitucions fetes | sí | sí | sí | — | **sí** ⚠️ |
| Estadístiques: resum de vigilàncies (taula `vigilancies`) | — | — | — | — | — |

Als dos informes, el filtre és el mateix: `compta_als_informes` (`backend/pdf/services.py`).
A l'informe de direcció, la columna «Total» de l'evolució mensual, la cobertura de cada
mes, la fila TOTAL i la portada fan la mateixa fórmula (cobertes / absències + serveis).

Les vigilàncies d'examen: la web en mostra el total, les assignades i les pendents
(de la taula `vigilancies`); l'informe no les mostra.

## 6. Criteri decidit: què compta (29/10/2026)

Un vigilant que falta es pot resoldre de dues maneres: reassignant la vigilància
(pantalla Vigilàncies, sense cap substitució) o posant substitut a la fila
`VIGILANCIA_ABSENT`. Perquè el recompte no depengui del camí:
- **Substitucions**: només compten les hores en què falta un professor amb classe
  (`ABSENCIA` i `SERVEI`). Les altres files són feina reorganitzada i no hi compten:
  `VIGILANCIA_ABSENT` (es pot resoldre sense substitució), `ENCADENADA` (no falta ningú:
  la tasca del substitut, p. ex. l'aula de guàrdia, la fa un altre) i `VIGILANCIA` (el
  vigilant hi és). Val per a l'informe i per a la web.
- **Substitucions fetes**: compten per a qui va a cobrir una absència o un servei. Qui hi va
  no té cap absència per això (la seva tasca, que és l'encadenada, no compta). Qui cobreix
  l'encadenada no fa cap substitució que compti.
- **Absències**: compten les hores que s'han hagut de cobrir, no l'assistència del
  professor. Si falta a una activitat de «No substituir» (p. ex. una guàrdia que no es
  cobreix), aquella hora no compta; si l'activitat s'ha de cobrir, compta com una classe.
- **Vigilàncies** (pendent, en migrar Estadístiques): apartat propi, comptat per resultat.
  Per a cada vigilància: hi va el vigilant (si no falta), el substitut de la seva fila de
  vigilant absent, o ningú (descoberta).
- Els recomptes de la web i de l'informe han de sortir d'un sol lloc compartit.

## 7. Discrepàncies detectades (29/10/2026, per resoldre en migrar Estadístiques)

1. **Estadístiques compta la vigilància absent com una absència més** (i com a
   substitució feta); l'informe, enlloc.
2. **Estadístiques compta les encadenades cobertes com a substitucions fetes**;
   l'informe no les compta.
3. **Estadístiques té «Pati» escrit al codi** per a la categoria de l'absència, i no tots
   els horaris tenen pati.

Les estadístiques (`routes/estadistiques.py`) encara no estan migrades.
