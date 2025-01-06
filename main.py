import logging
import schedule
import time
from src.config import Config
from src.court_checker import CourtChecker
from src.notifier import EmailNotifier

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('padel_notifier.log')
    ]
)

logger = logging.getLogger(__name__)

class PadelNotifier:
    def __init__(self):
        self.checker = CourtChecker()
        self.notifier = EmailNotifier()
        self.config = Config
        
    def check_and_notify(self):
        """Vérifie les disponibilités et envoie des notifications si nécessaire"""
        try:
            # Vérifier les créneaux disponibles
            available_slots = self.checker.check_availability()
            
            # Envoyer une notification pour chaque créneau disponible
            for time, court, date in available_slots:
                self.notifier.send_notification(time, court, date)
                
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des créneaux: {str(e)}")
    
    def run(self):
        """Lance le service de notification"""
        try:
            # Valider la configuration
            self.config.validate()
            
            # Se connecter au site
            if not self.checker.login():
                raise Exception("Impossible de se connecter au site")
            
            # Programmer les vérifications périodiques
            schedule.every(self.config.CHECK_INTERVAL).minutes.do(self.check_and_notify)
            
            # Première vérification immédiate
            self.check_and_notify()
            
            logger.info(f"Service démarré - Vérification toutes les {self.config.CHECK_INTERVAL} minutes")
            
            # Boucle principale
            while True:
                schedule.run_pending()
                time.sleep(60)
                
        except Exception as e:
            logger.error(f"Erreur fatale: {str(e)}")
            raise

if __name__ == "__main__":
    try:
        notifier = PadelNotifier()
        notifier.run()
    except Exception as e:
        logger.error(f"Le service s'est arrêté: {str(e)}")
        raise
