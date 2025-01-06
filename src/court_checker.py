import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Tuple
from .config import Config

logger = logging.getLogger(__name__)

class CourtChecker:
    def __init__(self):
        self.session = requests.Session()
        self.config = Config
        self._last_available = set()  # Pour éviter les notifications en double

    def login(self) -> bool:
        """
        Se connecte au site de réservation
        Returns:
            bool: True si la connexion réussit, False sinon
        """
        try:
            login_data = {
                'username': self.config.USERNAME,
                'password': self.config.PASSWORD
            }
            
            response = self.session.post(self.config.LOGIN_URL, data=login_data)
            response.raise_for_status()
            
            # Vérifier si la connexion a réussi (à adapter selon le site)
            if "Déconnexion" in response.text:
                logger.info("Connexion réussie")
                return True
            else:
                logger.error("Échec de la connexion")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors de la connexion: {str(e)}")
            return False

    def check_availability(self, target_time: str = None) -> List[Tuple[str, str, str]]:
        """
        Vérifie la disponibilité des terrains
        
        Args:
            target_time (str, optional): Heure cible (ex: "11:00"). 
                                       Si None, utilise la config
        
        Returns:
            List[Tuple[str, str, str]]: Liste de tuples (heure, numéro de terrain, date)
        """
        if target_time is None:
            target_time = self.config.TARGET_TIME

        try:
            response = self.session.get(self.config.PLANNING_URL)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            available_slots = []
            
            # Récupérer la date du planning
            date = self._extract_date(soup)
            
            # Trouver les créneaux disponibles
            slots = soup.select('tr')
            for slot in slots:
                time_cell = slot.select_one('th')
                if not time_cell:
                    continue
                    
                time = time_cell.text.strip()
                if time != target_time:
                    continue
                
                courts = slot.select('td')
                for i, court in enumerate(courts, 1):
                    if 'table-planning--type--libre' in court.get('class', []):
                        available_slots.append((time, f"Padel {i}", date))
            
            return available_slots
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des disponibilités: {str(e)}")
            return []

    def _extract_date(self, soup: BeautifulSoup) -> str:
        """Extrait la date du planning"""
        try:
            # À adapter selon la structure HTML
            date_element = soup.select_one('.planning--title')
            if date_element:
                date_text = date_element.text
                # Exemple: "PLANNING PADEL DU lundi 06 janvier 2025"
                return date_text.split('DU ')[-1].strip()
            return datetime.now().strftime("%d/%m/%Y")
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction de la date: {str(e)}")
            return datetime.now().strftime("%d/%m/%Y")
