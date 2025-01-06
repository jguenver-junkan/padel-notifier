import os
from typing import List
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Site credentials
    USERNAME = os.getenv('PADEL_USERNAME')
    PASSWORD = os.getenv('PADEL_PASSWORD')

    # URLs
    SITE_URL = os.getenv('SITE_URL')
    LOGIN_URL = os.getenv('LOGIN_URL')
    PLANNING_URL = os.getenv('PLANNING_URL')

    # Notification settings
    EMAIL_TO = os.getenv('NOTIFICATION_EMAIL')
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    SMTP_USERNAME = os.getenv('SMTP_USERNAME')
    SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')

    # Monitoring settings
    TARGET_TIMES = [
        time.strip() 
        for time in os.getenv('TARGET_TIMES', '11H00').split(',')
    ]
    CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', 5))  # minutes

    @classmethod
    def validate(cls):
        required_vars = [
            'USERNAME', 'PASSWORD', 'SITE_URL', 'LOGIN_URL', 'PLANNING_URL',
            'EMAIL_TO', 'SMTP_USERNAME', 'SMTP_PASSWORD'
        ]
        
        missing = [var for var in required_vars if not getattr(cls, var)]
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
            
        # Valider le format des horaires
        for time in cls.TARGET_TIMES:
            if not time.endswith('H00'):
                raise ValueError(f"Invalid time format: {time}. Must end with 'H00'")
            try:
                hour = int(time[:-3])
                if not (0 <= hour <= 23):
                    raise ValueError(f"Invalid hour: {hour}. Must be between 0 and 23")
            except ValueError as e:
                raise ValueError(f"Invalid time format: {time}. {str(e)}")
