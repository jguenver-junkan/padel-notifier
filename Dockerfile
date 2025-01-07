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

# Définir la variable d'environnement pour Docker
ENV DOCKER_ENV=1

WORKDIR /app

# Créer le répertoire pour les données persistantes
RUN mkdir -p /app/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Définir le volume
VOLUME /app/data

# Script d'entrée pour initialiser les fichiers si nécessaire
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Utiliser le script d'entrée
ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["python", "-m", "src.main"]
