# ETL runtime para ar-acc
FROM python:3.12-slim

WORKDIR /app

# Instala el paquete aracc_etl y su CLI `aracc-etl`.
COPY pyproject.toml ./
COPY aracc_etl ./aracc_etl
RUN pip install --no-cache-dir .

# Los datos crudos y el esquema se montan como volúmenes en runtime.
ENV PYTHONUNBUFFERED=1 \
    DATA_DIR=/data

ENTRYPOINT ["aracc-etl"]
CMD ["list"]
