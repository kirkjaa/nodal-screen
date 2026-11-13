FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --shell /usr/sbin/nologin screen

COPY server/ server/
COPY web/ web/
COPY data/samples/ data/samples/
COPY data/cohort.json data/cohort.json
COPY data/sources.json data/sources.json
COPY data/norms.csv data/norms.csv
COPY data/cutoffs.csv data/cutoffs.csv

USER screen
ENV PORT=8080
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn server.main:app --host 0.0.0.0 --port ${PORT}"]
