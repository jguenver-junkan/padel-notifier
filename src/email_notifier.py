import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging

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
        
        # Log la liste des destinataires au démarrage
        logger.info(f"Liste des destinataires configurés : {self.config.EMAIL_TO}")
    
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
                
                # Convertir le message en string
                msg_str = msg.as_string()
                
                # Envoyer l'email à chaque destinataire
                for to_email in self.config.EMAIL_TO:
                    to_email = to_email.strip()  # Nettoyer l'email au cas où
                    logger.info(f"Tentative d'envoi à {to_email}")
                    
                    # Mettre à jour le destinataire
                    msg['To'] = to_email
                    
                    # Envoyer avec sendmail
                    server.sendmail(
                        from_addr=self.config.SMTP_USERNAME,
                        to_addrs=[to_email],
                        msg=msg_str
                    )
                    logger.info(f"✓ Email envoyé avec succès à {to_email}")
                
        except Exception as e:
            error_msg = f"Erreur lors de l'envoi de l'email : {str(e)}"
            logger.error(error_msg)
            raise Exception(error_msg)
