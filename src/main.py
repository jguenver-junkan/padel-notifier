import logging
import schedule
import time
from datetime import datetime
from src.config import Config
from src.court_checker import CourtChecker
from src.email_notifier import EmailNotifier

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_and_notify():
    """
    Fonction principale qui vérifie les disponibilités et envoie les notifications
    """
    try:
        config = Config()
        checker = CourtChecker(config)
        notifier = EmailNotifier(config)

        # Vérifier les disponibilités
        available_slots, new_dates = checker.check_all_dates()
        
        # Si des créneaux sont disponibles, envoyer une notification
        if available_slots:
            logger.info(f"Créneaux disponibles trouvés : {available_slots}")
            notifier.send_notification(available_slots)
        else:
            logger.info("Aucun créneau disponible")

    except Exception as e:
        logger.error(f"Erreur lors de la vérification : {str(e)}")

def main():
    """
    Point d'entrée principal du script
    """
    logger.info("Démarrage du service de notification Padel")
    
    # Exécuter une première fois au démarrage
    check_and_notify()
    
    # Planifier les vérifications selon l'intervalle configuré
    schedule.every(int(Config().CHECK_INTERVAL)).minutes.do(check_and_notify)
    
    # Boucle principale
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    main()
