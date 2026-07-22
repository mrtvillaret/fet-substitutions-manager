FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
# --only-binary=:all: instal·la només paquets ja compilats. Totes les
# dependències en publiquen, de manera que la imatge no necessita compilador ni
# capçaleres de desenvolupament. Si algun dia se n'afegeix una que no en tingui,
# la construcció s'aturarà aquí amb un error clar en lloc de fallar de forma
# críptica; aleshores caldrà tornar a instal·lar les eines de compilació (millor
# en una etapa a part, perquè no acabin a la imatge final).
RUN pip install --no-cache-dir --only-binary=:all: -r /app/requirements.txt

COPY . /app

ENV DATA_DIR=/app/data \
    AUTH_DB_PATH=/app/data/auth.db \
    APP_INSTITUCIO=exemple

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
