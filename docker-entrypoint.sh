#!/bin/sh

# Initialiser les fichiers JSON s'ils n'existent pas
if [ ! -f /app/data/court_states.json ]; then
    echo "{}" > /app/data/court_states.json
    echo "Fichier court_states.json initialisé"
fi

if [ ! -f /app/data/known_dates.json ]; then
    echo "{}" > /app/data/known_dates.json
    echo "Fichier known_dates.json initialisé"
fi

# Exécuter la commande passée en argument
exec "$@"
