import logging
import time
import schedule
from src.config import Config
from src.court_checker import CourtChecker
from src.email_notifier import EmailNotifier

# Configuration du logging
logging.basicConfig(
    level=logging.DEBUG,  # Changé en DEBUG pour plus de détails
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('padel_notifier.log')
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Point d'entrée principal"""
    try:
        logger.info("Démarrage du service de notification Padel...")
        
        # Initialisation
        config = Config()
        config.validate()
        
        checker = CourtChecker(config)
        notifier = EmailNotifier(config)
        
        # Connexion initiale
        logger.info("Tentative de connexion au site...")
        checker._login()
        
        # Première vérification immédiate
        logger.info("Lancement de la première vérification...")
        check_and_notify(checker, notifier)
        
        # Planification des vérifications suivantes
        schedule.every(config.CHECK_INTERVAL).minutes.do(
            check_and_notify, checker=checker, notifier=notifier
        )
        
        # Boucle principale
        while True:
            schedule.run_pending()
            time.sleep(1)
            
    except Exception as e:
        logger.error(f"Erreur dans la boucle principale: {str(e)}")
        if hasattr(e, 'response'):
            logger.error(f"Response status: {e.response.status_code}")
            logger.error(f"Response content: {e.response.text[:500]}...")

def check_and_notify(checker: CourtChecker, notifier: EmailNotifier):
    """Vérifie les disponibilités et envoie une notification si nécessaire"""
    try:
        # Vérifier toutes les dates disponibles
        available_slots, new_dates = checker.check_all_dates()
        
        if available_slots or new_dates:
            # Grouper les créneaux par date
            slots_by_date = {}
            for time, court, date in available_slots:
                if date not in slots_by_date:
                    slots_by_date[date] = []
                slots_by_date[date].append((time, court))
            
            # Construire le message
            message_parts = []
            
            # Annoncer les nouvelles dates en premier
            if new_dates:
                message_parts.append("🎉 NOUVELLES DATES DISPONIBLES ! 🎉")
                message_parts.append("Les dates suivantes viennent d'être ouvertes :")
                for date in new_dates:
                    message_parts.append(f"- {date}")
                message_parts.append("\nDétails des créneaux disponibles :")
            
            # Ajouter les créneaux disponibles
            if slots_by_date:
                if new_dates:
                    message_parts.append("\nCréneaux disponibles :")
                else:
                    message_parts.append("Nouveaux créneaux disponibles !")
                    
                for date, slots in slots_by_date.items():
                    message_parts.append(f"\nPour le {date} :")
                    for time, court in sorted(slots):
                        message_parts.append(f"- {court} à {time}")
            
            message = "\n".join(message_parts)
            
            # Envoyer la notification
            subject = "🎾 "
            if new_dates:
                subject += "NOUVELLES DATES "
            if slots_by_date:
                subject += "Créneaux Padel disponibles !"
            else:
                subject += "Planning Padel mis à jour !"
                
            notifier.send_notification(
                subject=subject,
                message=message
            )
    except Exception as e:
        logger.error(f"Erreur lors de la vérification : {str(e)}")

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,  
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    main()
