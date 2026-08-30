FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /srv
RUN pip install --no-cache-dir fastapi "uvicorn[standard]"
COPY main.py .
EXPOSE 8100
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8100"]
