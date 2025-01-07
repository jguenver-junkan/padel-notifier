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

# Créer le répertoire pour les données persistantes
RUN mkdir -p /app/data

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Déplacer les fichiers d'état dans le volume
RUN mv court_states.json data/ || true
RUN mv known_dates.json data/ || true

# Créer des liens symboliques vers le volume
RUN ln -sf /app/data/court_states.json /app/court_states.json
RUN ln -sf /app/data/known_dates.json /app/known_dates.json

# Exécuter le script depuis le répertoire src
CMD ["python", "-m", "src.main"]
