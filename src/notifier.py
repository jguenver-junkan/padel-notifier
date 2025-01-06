import smtplib
import logging
from email.mime.text import MIMEText
from datetime import datetime
from .config import Config

logger = logging.getLogger(__name__)

class EmailNotifier:
    def __init__(self):
        self.config = Config

    def send_notification(self, slot_time: str, court_number: str, date: str):
        """
        Envoie une notification par email quand un créneau se libère
        
        Args:
            slot_time (str): L'heure du créneau (ex: "11:00")
            court_number (str): Le numéro du terrain
            date (str): La date du créneau
        """
        try:
            msg = self._create_message(slot_time, court_number, date)
            self._send_email(msg)
            logger.info(f"Notification envoyée pour le terrain {court_number} à {slot_time} le {date}")
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la notification: {str(e)}")
            raise

    def _create_message(self, slot_time: str, court_number: str, date: str) -> MIMEText:
        """Crée le message email"""
        current_time = datetime.now().strftime("%H:%M")
        
        body = f"""Un créneau s'est libéré !

Terrain: {court_number}
Date: {date}
Heure: {slot_time}

Détecté à: {current_time}

Lien de réservation: {Config.PLANNING_URL}
"""
        
        msg = MIMEText(body)
        msg['Subject'] = f'Créneau Padel Disponible - {court_number} - {slot_time}'
        msg['From'] = self.config.SMTP_USERNAME
        msg['To'] = self.config.EMAIL_TO
        
        return msg

    def _send_email(self, msg: MIMEText):
        """Envoie l'email via SMTP"""
        with smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT) as server:
            server.starttls()
            server.login(self.config.SMTP_USERNAME, self.config.SMTP_PASSWORD)
            server.send_message(msg)
