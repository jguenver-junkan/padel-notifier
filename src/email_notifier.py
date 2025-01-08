import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)

class EmailNotifier:
    def __init__(self, config):
        """
        Initialise le notifieur avec la configuration
        
        Args:
            config (Config): Configuration contenant les paramètres SMTP
        """
        self.config = config
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

    def send_notification(self, subject: str, message: str):
        """
        Envoie une notification par email
        
        Args:
            subject (str): Sujet de l'email
            message (str): Corps du message
        """
        try:
            # Créer le message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.config.SMTP_USERNAME
            msg['To'] = self.config.EMAIL_TO
            
            # Convertir le message texte en HTML
            html = message.replace('\n', '<br>')
            
            # Ajouter les parties texte et HTML
            text_part = MIMEText(message, 'plain')
            html_part = MIMEText(html, 'html')
            
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Se connecter au serveur SMTP
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                
                # Connexion
                server.login(self.config.SMTP_USERNAME, self.config.SMTP_PASSWORD)
                
                # Envoyer l'email
                server.send_message(msg)
                logger.info(f"Notification envoyée à {self.config.EMAIL_TO}")
                
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de la notification: {str(e)}")
            raise
