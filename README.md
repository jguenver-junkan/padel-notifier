# Padel Court Notifier

Un service de notification pour les créneaux disponibles de Padel.

## Description

Ce service surveille la disponibilité des terrains de padel et envoie des notifications par email lorsqu'un créneau souhaité se libère.

## Installation

### Prérequis

- Python 3.11+
- Docker (pour le déploiement)
- Un compte email pour l'envoi des notifications

### Configuration

1. Créez un fichier `.env` à partir du modèle :

```bash
cp .env.example .env
```

2. Remplissez les variables d'environnement dans `.env` :

```env
PADEL_USERNAME=votre_username
PADEL_PASSWORD=votre_password
NOTIFICATION_EMAIL=votre_email
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=votre_email_gmail
SMTP_PASSWORD=votre_mot_de_passe_app
TARGET_TIME=11:00
CHECK_INTERVAL=5
```

### Déploiement avec Dokku

1. Créez une application sur votre serveur Dokku :

```bash
dokku apps:create padel-notifier
```

2. Configurez les variables d'environnement :

```bash
dokku config:set padel-notifier PADEL_USERNAME=xxx PADEL_PASSWORD=xxx ...
```

3. Déployez l'application :

```bash
git push dokku main
```

## Développement local

1. Installez les dépendances :

```bash
pip install -r requirements.txt
```

2. Lancez l'application :

```bash
python main.py
```

## License

MIT
