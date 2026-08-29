FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /srv

# las deps primero: si solo cambia el codigo, esta capa se reusa
COPY pyproject.toml ./
RUN mkdir -p app sim && touch app/__init__.py sim/__init__.py \
    && pip install --no-cache-dir . \
    && rm -rf app sim

COPY app ./app
COPY sim ./sim

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
