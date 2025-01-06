import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Tuple, Dict
import json
import os
import locale
from urllib.parse import urljoin
import re

# Configurer locale en français
locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')

logger = logging.getLogger(__name__)

class CourtChecker:
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.state_file = "court_states.json"
        self.dates_file = "known_dates.json"
        
        # Charger l'état précédent ou créer un nouveau dictionnaire
        self.previous_states = self._load_states()
        self.known_dates = self._load_known_dates()
        
        # Headers pour simuler un navigateur
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def _load_states(self) -> Dict:
        """
        Charge l'état précédent depuis le fichier JSON
        Format du dictionnaire:
        {
            "2025-01-06": {
                "11H00|Padel 1": "libre",
                "11H00|Padel 2": "occupé",
                ...
            },
            "2025-01-07": {
                ...
            }
        }
        """
        try:
            if not os.path.exists(self.state_file):
                logger.info("Fichier d'états non trouvé, création d'un nouveau fichier")
                with open(self.state_file, 'w') as f:
                    json.dump({}, f)
                return {}
                
            with open(self.state_file, 'r') as f:
                content = f.read().strip()
                if not content:  # Si le fichier est vide
                    logger.info("Fichier d'états vide, initialisation avec un dictionnaire vide")
                    return {}
                try:
                    saved_states = json.loads(content)
                    if not isinstance(saved_states, dict):
                        logger.warning("Le fichier d'états n'est pas au bon format, création d'un nouveau")
                        return {}
                    # Convertir les états pour chaque date
                    converted_states = {}
                    for date, states in saved_states.items():
                        if isinstance(states, dict):  # Vérifier que states est bien un dictionnaire
                            converted_states[date] = {
                                tuple(k.split('|')): v for k, v in states.items()
                            }
                    return converted_states
                except json.JSONDecodeError as e:
                    logger.error(f"Erreur de décodage JSON: {str(e)}")
                    return {}
            
        except Exception as e:
            logger.error(f"Erreur lors du chargement des états: {str(e)}")
            return {}

    def _save_states(self, states: Dict, date: str):
        """
        Sauvegarde l'état actuel dans le fichier JSON
        
        Args:
            states: Dict des états pour une date donnée
            date: Date du planning (format: "YYYY-MM-DD")
        """
        try:
            # Charger les états existants
            all_states = {}
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    content = f.read().strip()
                    if content:
                        try:
                            all_states = json.loads(content)
                        except json.JSONDecodeError:
                            logger.warning("Erreur lors du chargement du fichier existant, création d'un nouveau")
                            all_states = {}
            
            # Convertir les tuples en chaînes pour le JSON
            states_to_save = {f"{k[0]}|{k[1]}": v for k, v in states.items()}
            
            # Mettre à jour les états pour cette date
            all_states[date] = states_to_save
            
            # Supprimer les dates anciennes (garder seulement les 7 derniers jours)
            all_states = dict(sorted(all_states.items())[-7:])
            
            # Sauvegarder avec un backup
            backup_file = f"{self.state_file}.bak"
            if os.path.exists(self.state_file):
                os.replace(self.state_file, backup_file)
            
            with open(self.state_file, 'w') as f:
                json.dump(all_states, f, indent=2)
                
            # Si tout s'est bien passé, supprimer le backup
            if os.path.exists(backup_file):
                os.remove(backup_file)
                
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des états: {str(e)}")
            # En cas d'erreur, restaurer le backup si disponible
            if os.path.exists(backup_file):
                os.replace(backup_file, self.state_file)

    def _load_known_dates(self) -> Dict[str, List[str]]:
        """
        Charge les dates connues depuis le fichier JSON
        Format:
        {
            "2025-01": ["2025-01-06", "2025-01-07", ...],
            "2025-02": ["2025-02-01", ...],
            ...
        }
        """
        try:
            if not os.path.exists(self.dates_file):
                return {}
                
            with open(self.dates_file, 'r') as f:
                content = f.read().strip()
                if not content:
                    return {}
                return json.loads(content)
        except Exception as e:
            logger.error(f"Erreur lors du chargement des dates connues: {str(e)}")
            return {}

    def _save_known_dates(self, dates: List[str]):
        """
        Sauvegarde les dates connues dans le fichier JSON
        
        Args:
            dates: Liste des dates au format "YYYY-MM-DD"
        """
        try:
            # Organiser les dates par mois
            dates_by_month = {}
            for date in dates:
                month = date[:7]  # "YYYY-MM"
                if month not in dates_by_month:
                    dates_by_month[month] = []
                dates_by_month[month].append(date)
            
            # Trier les dates dans chaque mois
            for month in dates_by_month:
                dates_by_month[month].sort()
            
            # Sauvegarder avec backup
            backup_file = f"{self.dates_file}.bak"
            if os.path.exists(self.dates_file):
                os.replace(self.dates_file, backup_file)
            
            with open(self.dates_file, 'w') as f:
                json.dump(dates_by_month, f, indent=2)
                
            if os.path.exists(backup_file):
                os.remove(backup_file)
                
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des dates connues: {str(e)}")
            if os.path.exists(backup_file):
                os.replace(backup_file, self.dates_file)

    def _login(self) -> bool:
        """
        Se connecte au site web
        """
        try:
            # Si on est déjà sur la page d'accueil, on est déjà connecté
            response = self.session.get(self.config.LOGIN_URL)
            if "/membre/accueil" in response.url:
                logger.info("Déjà connecté")
                return True
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extraire l'URL du formulaire
            form = soup.find('form')
            if not form:
                logger.error("Formulaire de connexion non trouvé")
                return False
                
            login_url = form.get('action', '')
            if not login_url:
                login_url = self.config.LOGIN_URL
            elif not login_url.startswith('http'):
                login_url = urljoin(self.config.SITE_URL, login_url)
            
            # Préparer les données de connexion
            login_data = {
                '_username': self.config.USERNAME,
                '_password': self.config.PASSWORD
            }
            
            # Tentative de connexion
            logger.info(f"Tentative de connexion pour l'utilisateur {self.config.USERNAME}...")
            response = self.session.post(login_url, data=login_data)
            
            # Vérifier si la connexion a réussi
            if response.status_code == 200 or response.status_code == 302:
                if "/membre/accueil" in response.url:
                    logger.info("Connexion réussie")
                    return True
                else:
                    logger.error("Redirection inattendue après connexion")
                    return False
            else:
                logger.error(f"Échec de la connexion avec le code {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors de la connexion : {str(e)}")
            return False

    def check_all_dates(self, target_times: List[str] = None) -> Tuple[List[Tuple[str, str, str]], List[str]]:
        """
        Vérifie la disponibilité des terrains pour toutes les dates disponibles
        """
        all_available_slots = []
        new_dates_found = []
        
        try:
            # Récupérer la première page de planning
            response = self.session.get(self.config.PLANNING_URL)
            if "/membre/login" in response.url:
                logger.info("Session expirée, reconnexion...")
                if not self._login():
                    logger.error("Échec de la reconnexion")
                    return [], []
                response = self.session.get(self.config.PLANNING_URL)
            
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extraire toutes les URLs de planning disponibles
            planning_urls = self._get_planning_urls(soup)
            
            # Vérifier chaque date
            for url in planning_urls:
                response = self.session.get(url)
                if response.status_code != 200:
                    logger.error(f"Erreur lors de l'accès au planning : {response.status_code}")
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                date = self._extract_date(soup)
                if not date:
                    logger.error("Impossible de trouver la date du planning")
                    continue
                
                logger.info(f"Vérification du planning pour le {date}")
                
                # Vérifier les disponibilités pour cette date
                for target_time in (target_times or self.config.TARGET_TIMES):
                    available_slots = self.check_availability(target_time)
                    if available_slots:
                        all_available_slots.extend(available_slots)
                        if date not in self.known_dates:
                            new_dates_found.append(date)
                            self.known_dates.add(date)
            
            return all_available_slots, new_dates_found
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des dates : {str(e)}")
            return [], []

    def check_availability(self, target_time: str = None) -> List[Tuple[str, str, str]]:
        """
        Vérifie la disponibilité des terrains et ne retourne que les nouveaux créneaux disponibles
        
        Args:
            target_time (str, optional): Heure cible (ex: "11H00"). 
                                       Si None, utilise la config
        
        Returns:
            List[Tuple[str, str, str]]: Liste de tuples (heure, numéro de terrain, date)
                                       Ne contient que les terrains nouvellement disponibles
        """
        if target_time is None:
            target_time = self.config.TARGET_TIMES[0]
            
        target_time_site_format = target_time
        newly_available_slots = []
        current_states = {}

        try:
            logger.info(f"Vérification des disponibilités pour {target_time_site_format}...")
            
            # Vérifier si nous devons nous reconnecter
            response = self.session.get(self.config.PLANNING_URL)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Si on est redirigé vers la page de login
            if "/membre/login" in response.url:
                logger.info("Session expirée, reconnexion...")
                if not self._login():
                    logger.error("Échec de la reconnexion")
                    return []
                response = self.session.get(self.config.PLANNING_URL)
                soup = BeautifulSoup(response.text, 'html.parser')
            
            response.raise_for_status()
            
            # Chercher la table qui contient les créneaux
            planning_table = soup.find('table', {'class': 'table-planning'})
            if not planning_table:
                logger.error("Page de planning non trouvée")
                return []
            
            # Récupérer la date du planning
            date = self._extract_date(soup)
            if not date:
                logger.error("Impossible de trouver la date du planning")
                return []
                
            try:
                # Convertir la date française en format ISO
                date_obj = datetime.strptime(date, "%A %d %B %Y")
                date_iso = date_obj.strftime("%Y-%m-%d")
                logger.info(f"Date du planning : {date} ({date_iso})")
            except ValueError as e:
                logger.error(f"Erreur lors de la conversion de la date '{date}': {str(e)}")
                return []
            
            # Récupérer les états précédents pour cette date
            previous_states_for_date = self.previous_states.get(date_iso, {})
            
            slots = soup.select('tr')
            
            for slot in slots:
                time_cell = slot.select_one('th')
                if not time_cell:
                    continue
                    
                time = time_cell.text.strip()
                if time != target_time_site_format:
                    continue
                
                courts = slot.select('td')
                
                for i, court in enumerate(courts, 1):
                    court_classes = court.get('class', [])
                    court_id = (time, f"Padel {i}")
                    is_available = self._is_court_available(court_classes)
                    
                    # Enregistrer l'état actuel
                    current_states[court_id] = "libre" if is_available else "occupé"
                    
                    # Vérifier si le terrain était précédemment occupé et est maintenant libre
                    was_occupied = previous_states_for_date.get(court_id) == "occupé"
                    if is_available and was_occupied:
                        newly_available_slots.append((time, f"Padel {i}", date))
                        logger.info(f"Nouveau créneau disponible : Terrain {i} à {time}")
                    
            # Mettre à jour les états précédents et sauvegarder
            self.previous_states[date_iso] = current_states
            self._save_states(current_states, date_iso)
            
            if not newly_available_slots:
                logger.debug(f"Aucun nouveau créneau disponible pour {target_time_site_format}")
            
            return newly_available_slots
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des disponibilités: {str(e)}")
            return []

    def _is_court_available(self, court_classes):
        """Vérifie si un terrain est disponible en fonction de ses classes CSS"""
        return any('libre' in class_name for class_name in court_classes)

    def _extract_date(self, soup: BeautifulSoup) -> str:
        """Extrait la date du planning"""
        try:
            # Essayer différents sélecteurs possibles
            selectors = [
                '.table-planning--title',
                '.planning--title',
                'h2',  # Souvent utilisé pour les titres
                '.title'
            ]
            
            for selector in selectors:
                date_element = soup.select_one(selector)
                if date_element:
                    text = date_element.text.strip()
                    
                    # Si le texte contient "PLANNING" et une date, extraire la date
                    if "PLANNING" in text.upper() and any(month in text.lower() for month in ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]):
                        # Extraire la partie après "DU" ou juste prendre le texte si pas de "DU"
                        if "DU" in text.upper():
                            date_text = text.split("DU")[-1].strip()
                        else:
                            date_text = text.strip()
                        return date_text
            
            # Si aucun sélecteur n'a fonctionné, chercher dans tout le texte
            text = soup.get_text()
            
            # Chercher un motif de date (ex: "lundi 06 janvier 2025")
            import re
            date_pattern = r'(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4}'
            match = re.search(date_pattern, text, re.IGNORECASE)
            
            if match:
                date_text = match.group(0)
                return date_text
                
            logger.error("Aucune date trouvée dans la page")
            return ""
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction de la date: {str(e)}")
            return ""

    def _get_planning_urls(self, soup: BeautifulSoup) -> List[str]:
        """
        Extrait toutes les URLs de planning disponibles et les dates associées
        """
        urls = []
        try:
            # Toujours inclure l'URL principale en premier
            urls.append(self.config.PLANNING_URL)
            
            # Trouver tous les liens qui pourraient être des dates futures
            links = soup.find_all('a', href=True)
            latest_date = None
            
            for link in links:
                href = link.get('href', '')
                # Ne garder que les URLs de planning (pas les URLs de réservation)
                if '/membre/planning/6' in href and 'reserver' not in href:
                    full_url = urljoin(self.config.SITE_URL, href)
                    if full_url not in urls:
                        urls.append(full_url)
                        # Extraire la date pour trouver la plus récente
                        date_match = re.search(r'date=(\d{2}-\d{2}-\d{4})', href)
                        if date_match:
                            date_str = date_match.group(1)
                            try:
                                current_date = datetime.strptime(date_str, '%d-%m-%Y')
                                if not latest_date or current_date > latest_date:
                                    latest_date = current_date
                            except ValueError:
                                continue
            
            if not urls:
                logger.warning("Aucune URL de planning trouvée")
            else:
                if latest_date:
                    logger.info(f"URLs de planning trouvées : {len(urls)}, dernière date disponible : {latest_date.strftime('%d/%m/%Y')}")
                else:
                    logger.info(f"URLs de planning trouvées : {len(urls)}")
            
            return urls
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des URLs de planning : {str(e)}")
            return [self.config.PLANNING_URL]  # Toujours retourner au moins l'URL principale

    def _extract_date_from_url(self, url: str) -> str:
        """Extrait la date d'une URL de planning"""
        try:
            if "date=" in url:
                date_param = url.split("date=")[1].split("&")[0]
                # Convertir du format "DD-MM-YYYY" en "YYYY-MM-DD"
                day, month, year = date_param.split("-")
                return f"{year}-{month}-{day}"
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction de la date de l'URL {url}: {str(e)}")
        return None
