# этап 1: ставим зависимости в отдельную папку
FROM python:3.12-slim AS build
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# этап 2: чистый образ без pip-кеша и временных файлов
FROM python:3.12-slim
RUN useradd -r -u 10001 app
WORKDIR /app
COPY --from=build /install /usr/local
COPY worker.py .
USER app
CMD ["python", "worker.py"]