FROM python:3.11-slim

# Installation des dépendances système
RUN apt-get update && apt-get install -y \
    locales \
    ca-certificates \
    curl \
    && sed -i '/fr_FR/s/^# //g' /etc/locale.gen \
    && locale-gen \
    && update-locale LANG=fr_FR.UTF-8 \
    && rm -rf /var/lib/apt/lists/*

# Configuration des locales
ENV LANG=fr_FR.UTF-8
ENV LANGUAGE=fr_FR:fr
ENV LC_ALL=fr_FR.UTF-8

# Configuration des certificats SSL
RUN update-ca-certificates

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Exécuter le script depuis le répertoire src
CMD ["python", "-m", "src.main"]
