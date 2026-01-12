FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    netcat-openbsd \
    dnsutils \
    curl \
    ca-certificates \
    wget \
    postgresql-client \
    && apt-get upgrade -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/
ENV PYTHONPATH=/app

# Создаем не-привилегированного пользователя
RUN groupadd -r appgroup && useradd -r -g appgroup appuser
RUN chown -R appuser:appgroup /app

USER appuser

ENTRYPOINT ["./entrypoint.sh"]