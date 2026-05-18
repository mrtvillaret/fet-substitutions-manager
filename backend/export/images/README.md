# Imatges per PDFs

Aquesta carpeta conté les imatges SVG que substitueixen els emojis als PDFs generats pel sistema.

## Imatges disponibles:

- **clock.svg** (🕐) - Icona de rellotge per indicar hores
- **building.svg** (🏫) - Icona d'edifici per indicar aules  
- **warning.svg** (⚠️) - Icona d'advertència per avisos
- **error.svg** (❌) - Icona d'error per conflictes crítics

## Avantatges de les imatges vs emojis:

1. **Compatibilitat**: Les imatges es mostren correctament a tots els visors PDF
2. **Consistència**: Mateix aspecte independentment del sistema operatiu
3. **Qualitat**: Icones vectorials escalables
4. **Professionalitat**: Aspecte més formal i consistent

## Ús automàtic:

Les imatges s'usen automàticament a través del mòdul `pdf_images.py`:
- Els conflictes als PDFs mostren icones en lloc d'emojis
- Fallback automàtic a text si les imatges no es poden carregar
- Mida optimitzada per alinear amb el text (0.15 inch)

## Colors utilitzats:

- **Hora**: Blau (#2E86C1)
- **Aula**: Violeta (#8E44AD) 
- **Avís**: Taronja (#F39C12)
- **Error**: Vermell (#E74C3C)