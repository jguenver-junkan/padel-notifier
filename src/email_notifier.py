import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

class EmailNotifier:
    def __init__(self, config):
        self.config = config
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

    def send_notification(self, subject: str, message: str):
        """
        Envoie une notification par email
        
        Args:
            subject (str): Sujet de l'email
            message (str): Contenu de l'email
        """
        try:
            # Créer le message
            msg = MIMEText(message)
            msg['Subject'] = subject
            msg['From'] = self.config.SMTP_USERNAME
            msg['To'] = self.config.EMAIL_TO
            
            # Se connecter au serveur SMTP
            with smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT) as server:
                server.starttls()
                
                # Connexion
                server.login(self.config.SMTP_USERNAME, self.config.SMTP_PASSWORD)
                
                # Envoyer l'email
                server.send_message(msg)
                logger.info(f"Notification envoyée à {self.config.EMAIL_TO}")
                
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la notification: {str(e)}")
            raise
