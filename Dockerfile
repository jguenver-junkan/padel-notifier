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

# Créer les fichiers d'état vides dans le volume
RUN echo "{}" > /app/data/court_states.json
RUN echo "{}" > /app/data/known_dates.json

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Créer des liens symboliques vers le volume
RUN ln -sf /app/data/court_states.json /app/court_states.json
RUN ln -sf /app/data/known_dates.json /app/known_dates.json

# Définir le volume
VOLUME /app/data

# Exécuter le script depuis le répertoire src
CMD ["python", "-m", "src.main"]
