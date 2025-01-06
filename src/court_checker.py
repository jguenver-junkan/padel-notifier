import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Tuple, Dict
import json
import os
import locale

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

    def login(self) -> bool:
        """
        Se connecte au site de réservation
        Returns:
            bool: True si la connexion réussit, False sinon
        """
        try:
            # Première requête pour obtenir le formulaire
            logger.info("Récupération de la page de connexion...")
            response = self.session.get(self.config.SITE_URL)
            response.raise_for_status()
            
            # Parse le formulaire de connexion
            soup = BeautifulSoup(response.text, 'html.parser')
            form = soup.find('form')
            
            if not form:
                logger.error("Formulaire de connexion non trouvé")
                return False
            
            # Récupère l'action du formulaire
            form_action = form.get('action', self.config.LOGIN_URL)
            if not form_action.startswith('http'):
                form_action = f"{self.config.SITE_URL.rstrip('/')}/{form_action.lstrip('/')}"
            
            logger.info(f"URL du formulaire : {form_action}")
            
            # Récupère tous les champs cachés du formulaire
            form_data = {}
            for hidden in form.find_all('input', type='hidden'):
                form_data[hidden['name']] = hidden.get('value', '')
                logger.info(f"Champ caché trouvé : {hidden['name']}")
            
            # Ajoute les identifiants
            form_data.update({
                '_username': self.config.USERNAME,  # Ajustez les noms des champs selon le formulaire
                '_password': self.config.PASSWORD
            })
            
            # Affiche les données qui seront envoyées (sans le mot de passe)
            safe_form_data = {k: v if k != '_password' else '****' for k, v in form_data.items()}
            logger.info(f"Données du formulaire : {safe_form_data}")
            
            # Envoie le formulaire
            logger.info(f"Tentative de connexion pour l'utilisateur {self.config.USERNAME}...")
            response = self.session.post(
                form_action,
                data=form_data,
                allow_redirects=True
            )
            
            # Log de la réponse pour debug
            logger.info(f"Status code: {response.status_code}")
            logger.info(f"URL finale: {response.url}")
            
            # Vérification du succès de la connexion
            if "Déconnexion" in response.text:
                logger.info("Connexion réussie")
                return True
            else:
                logger.error("Échec de la connexion - Déconnexion non trouvé dans la page")
                logger.debug(f"Contenu de la page : {response.text[:500]}...")
                return False
                
        except Exception as e:
            logger.error(f"Erreur lors de la connexion: {str(e)}")
            if hasattr(e, 'response'):
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response headers: {e.response.headers}")
                logger.error(f"Response content: {e.response.text[:500]}...")
            return False

    def _is_court_available(self, court_classes):
        """Vérifie si un terrain est disponible en fonction de ses classes CSS"""
        return any('libre' in class_name for class_name in court_classes)

    def check_all_dates(self, target_times: List[str] = None) -> Tuple[List[Tuple[str, str, str]], List[str]]:
        """
        Vérifie la disponibilité des terrains pour toutes les dates disponibles
        
        Args:
            target_times (List[str], optional): Liste des heures cibles (ex: ["11H00", "20H00"]). 
                                              Si None, utilise la config
        
        Returns:
            Tuple[List[Tuple[str, str, str]], List[str]]: 
                - Liste de tuples (heure, numéro de terrain, date)
                - Liste des nouvelles dates détectées
        """
        all_available_slots = []
        new_dates_found = []
        
        try:
            # Récupérer la première page de planning
            response = self.session.get(self.config.PLANNING_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extraire toutes les URLs de planning
            planning_urls = self._get_planning_urls(soup)
            logger.info(f"Vérification de {len(planning_urls)} dates")
            
            # Collecter toutes les dates disponibles
            current_dates = set()
            for url in planning_urls:
                date = self._extract_date_from_url(url)
                if date:
                    current_dates.add(date)
            
            # Vérifier les nouvelles dates
            known_dates = set()
            for month_dates in self.known_dates.values():
                known_dates.update(month_dates)
            
            new_dates = current_dates - known_dates
            if new_dates:
                logger.info(f"Nouvelles dates détectées : {sorted(new_dates)}")
                new_dates_found = sorted(new_dates)
            
            # Mettre à jour les dates connues
            self._save_known_dates(list(current_dates))
            
            # Utiliser les horaires de la config si non spécifiés
            if target_times is None:
                target_times = self.config.TARGET_TIMES
            
            # Vérifier chaque URL
            for url in planning_urls:
                logger.debug(f"Vérification de l'URL: {url}")
                date = self._extract_date_from_url(url)
                
                # Si c'est une nouvelle date, on la traite en priorité
                if date in new_dates:
                    logger.info(f"Vérification prioritaire de la nouvelle date : {date}")
                
                # Sauvegarder l'URL originale
                original_url = self.config.PLANNING_URL
                try:
                    # Remplacer temporairement l'URL
                    self.config.PLANNING_URL = url
                    
                    # Vérifier chaque horaire pour cette date
                    for target_time in target_times:
                        available_slots = self.check_availability(target_time)
                        if available_slots:
                            # Pour les nouvelles dates, on considère tous les créneaux comme "nouveaux"
                            if date in new_dates:
                                all_slots = []
                                soup = BeautifulSoup(response.text, 'html.parser')
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
                                        court_classes = court.get('class', [])
                                        if self._is_court_available(court_classes):
                                            all_slots.append((time, f"Padel {i}", date))
                                all_available_slots.extend(all_slots)
                            else:
                                all_available_slots.extend(available_slots)
                finally:
                    # Restaurer l'URL originale
                    self.config.PLANNING_URL = original_url
            
            return all_available_slots, new_dates_found
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de toutes les dates: {str(e)}")
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
            target_time = self.config.TARGET_TIMES[0]  # Utiliser le premier horaire par défaut
            
        target_time_site_format = target_time  # Le format est déjà bon maintenant (11H00)
        newly_available_slots = []
        current_states = {}

        try:
            logger.info(f"Vérification des disponibilités pour {target_time_site_format}...")
            response = self.session.get(self.config.PLANNING_URL)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
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
            logger.debug(f"Nombre de lignes trouvées : {len(slots)}")
            
            for slot in slots:
                time_cell = slot.select_one('th')
                if not time_cell:
                    continue
                    
                time = time_cell.text.strip()
                if time != target_time_site_format:
                    continue
                
                courts = slot.select('td')
                logger.debug(f"Nombre de terrains trouvés pour {time}: {len(courts)}")
                
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
                    
                    logger.debug(f"Terrain {i} à {time} - État actuel: {current_states[court_id]}, "
                               f"État précédent: {previous_states_for_date.get(court_id, 'inconnu')}")
            
            # Mettre à jour les états précédents et sauvegarder
            self.previous_states[date_iso] = current_states
            self._save_states(current_states, date_iso)
            
            if not newly_available_slots:
                logger.debug(f"Aucun nouveau créneau disponible pour {target_time_site_format}")
            
            return newly_available_slots
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des disponibilités: {str(e)}")
            if hasattr(e, 'response'):
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response content: {e.response.text[:500]}...")
            return []

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
            
            # Log le HTML pour debug
            logger.debug("HTML de la page :")
            logger.debug(soup.prettify()[:1000])  # Premiers 1000 caractères
            
            for selector in selectors:
                date_element = soup.select_one(selector)
                if date_element:
                    text = date_element.text.strip()
                    logger.debug(f"Trouvé avec le sélecteur {selector}: {text}")
                    
                    # Si le texte contient "PLANNING" et une date, extraire la date
                    if "PLANNING" in text.upper() and any(month in text.lower() for month in ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]):
                        # Extraire la partie après "DU" ou juste prendre le texte si pas de "DU"
                        if "DU" in text.upper():
                            date_text = text.split("DU")[-1].strip()
                        else:
                            date_text = text.strip()
                        logger.debug(f"Date extraite : {date_text}")
                        return date_text
            
            # Si aucun sélecteur n'a fonctionné, chercher dans tout le texte
            text = soup.get_text()
            logger.debug("Recherche dans tout le texte de la page...")
            
            # Chercher un motif de date (ex: "lundi 06 janvier 2025")
            import re
            date_pattern = r'(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+\d{1,2}\s+(?:janvier|février|mars|avril|mai|juin|juillet|août|septembre|octobre|novembre|décembre)\s+\d{4}'
            match = re.search(date_pattern, text, re.IGNORECASE)
            
            if match:
                date_text = match.group(0)
                logger.debug(f"Date trouvée par pattern matching : {date_text}")
                return date_text
                
            logger.error("Aucune date trouvée dans la page")
            return ""
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction de la date: {str(e)}")
            logger.debug("HTML causant l'erreur :")
            logger.debug(soup.prettify()[:500])  # Premiers 500 caractères
            return ""

    def _get_planning_urls(self, soup: BeautifulSoup) -> List[str]:
        """
        Extrait les URLs de tous les plannings disponibles
        
        Returns:
            List[str]: Liste des URLs des plannings
        """
        try:
            # Trouver tous les liens de planning
            planning_links = soup.select('a[href*="/membre/planning/"]')
            urls = []
            
            for link in planning_links:
                href = link.get('href')
                if href:
                    # Convertir en URL absolue si nécessaire
                    if href.startswith('/'):
                        href = f"{self.config.SITE_URL}{href}"
                    urls.append(href)
            
            # Dédupliquer et trier les URLs
            unique_urls = list(dict.fromkeys(urls))
            logger.debug(f"URLs de planning trouvées : {unique_urls}")
            return unique_urls
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des URLs de planning: {str(e)}")
            return [self.config.PLANNING_URL]  # Retourner au moins l'URL par défaut

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
