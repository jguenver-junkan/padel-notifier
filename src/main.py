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
        
        # Ne notifier que s'il y a de NOUVEAUX créneaux disponibles
        if available_slots and any(slot[0] in config.TARGET_TIMES for slot in available_slots):
            logger.info(f"Nouveaux créneaux disponibles trouvés : {available_slots}")
            
            # Formater le message
            message = "Nouveaux créneaux disponibles :\n\n"
            # Grouper par date
            slots_by_date = {}
            for time, court, date in available_slots:
                # Ne notifier que pour les horaires ciblés
                if time not in config.TARGET_TIMES:
                    continue
                    
                if date not in slots_by_date:
                    slots_by_date[date] = []
                slots_by_date[date].append((time, court))
            
            # Ne rien envoyer si aucun créneau ne correspond aux horaires ciblés
            if not slots_by_date:
                logger.info("Aucun nouveau créneau disponible pour les horaires ciblés")
                return
            
            # Formater le message par date
            for date in sorted(slots_by_date.keys()):
                message += f"\nLe {date} :\n"
                # Grouper par heure
                slots_by_time = {}
                for time, court in slots_by_date[date]:
                    if time not in slots_by_time:
                        slots_by_time[time] = []
                    slots_by_time[time].append(court)
                
                # Ajouter les créneaux par heure
                for time in sorted(slots_by_time.keys()):
                    courts = sorted(slots_by_time[time])
                    message += f"- {time} : {', '.join(courts)}\n"
            
            # Envoyer la notification
            notifier.send_notification(
                subject="Nouveaux créneaux de Padel disponibles !",
                message=message
            )
            logger.info("Notification envoyée pour les nouveaux créneaux")
        else:
            logger.info("Aucun nouveau créneau disponible")

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
