import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Tuple, Dict, Optional
import json
import os
import locale
from urllib.parse import urljoin
import re

# Configurer locale en français
try:
    locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
except locale.Error:
    try:
        # Fallback sur fr_FR
        locale.setlocale(locale.LC_TIME, 'fr_FR')
    except locale.Error:
        logger.warning("Impossible de configurer la locale française. Les dates pourraient ne pas être correctement détectées.")

logger = logging.getLogger(__name__)

class CourtChecker:
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.state_file = "court_states.json"
        self.dates_file = "known_dates.json"
        self.known_dates = set()
        
        # Charger l'état précédent ou créer un nouveau dictionnaire
        self.previous_states = self._load_states()
        
        # Charger les dates connues
        self._load_known_dates()
        
        # Headers pour simuler un navigateur moderne
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0'
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
        """Se connecte au site"""
        try:
            # Récupérer la page de login
            response = self.session.get(self.config.SITE_URL + "/membre", verify=True)
            response.raise_for_status()
            
            # Log du contenu HTML pour debug
            logger.info("Contenu de la page de login reçu")
            logger.debug(f"URL finale après redirection : {response.url}")
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Trouver le formulaire de login (qui n'a pas d'ID spécifique)
            login_form = soup.find('form')
            if not login_form:
                logger.error("Formulaire de login non trouvé")
                logger.debug("Contenu de la page :")
                logger.debug(soup.prettify()[:500])
                return False
            
            # Debug des champs du formulaire
            logger.debug("Champs du formulaire trouvés :")
            for input_field in login_form.find_all('input'):
                logger.debug(f"Input field: name={input_field.get('name', 'N/A')}, type={input_field.get('type', 'N/A')}")
            
            # Extraire l'URL de soumission du formulaire
            form_action = login_form.get('action', '')
            if not form_action:
                form_action = "/membre"
            login_url = urljoin(self.config.SITE_URL, form_action)
            logger.debug(f"URL de soumission du formulaire : {login_url}")
            
            # Préparer les données de login
            login_data = {}
            
            # Ajouter tous les champs cachés du formulaire
            for hidden_field in login_form.find_all('input', type='hidden'):
                login_data[hidden_field.get('name')] = hidden_field.get('value', '')
            
            # Ajouter les identifiants en utilisant les noms de champs exacts
            login_data['_username'] = self.config.USERNAME
            login_data['_password'] = self.config.PASSWORD
            
            logger.debug(f"Données de login préparées (sans le mot de passe) : {dict((k,v) for k,v in login_data.items() if k != '_password')}")
            
            # Ajouter le Referer pour plus d'authenticité
            headers = {
                'Origin': self.config.SITE_URL,
                'Referer': response.url,
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            # Envoyer le formulaire
            try:
                login_response = self.session.post(
                    login_url,
                    data=login_data,
                    headers=headers,
                    verify=True,
                    allow_redirects=True
                )
                login_response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                logger.error(f"Erreur HTTP lors du login : {str(e)}")
                logger.debug("Contenu de la réponse d'erreur :")
                logger.debug(e.response.text[:500])
                raise
            
            # Debug de la réponse
            logger.debug(f"Status code de la réponse : {login_response.status_code}")
            logger.debug(f"URL finale après login : {login_response.url}")
            
            # Vérifier si la connexion a réussi en essayant d'accéder au planning
            test_response = self.session.get(self.config.PLANNING_URL)
            if "/membre/planning" in test_response.url:
                logger.info("Connexion réussie")
                return True
            else:
                logger.error(f"Échec de la connexion. URL de redirection : {test_response.url}")
                logger.debug("Contenu de la réponse :")
                logger.debug(login_response.text[:500])
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
            logger.debug(f"URL finale du planning : {response.url}")
            logger.debug("Contenu de la page de planning reçu")
            
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
                    available_slots = self.check_availability(target_time, date)
                    if available_slots:
                        all_available_slots.extend(available_slots)
                        if date not in self.known_dates:
                            new_dates_found.append(date)
                            self.known_dates.add(date)
            
            return all_available_slots, new_dates_found
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des dates : {str(e)}")
            return [], []

    def check_availability(self, target_time: str = None, planning_date: Optional[str] = None) -> List[Tuple[str, str, str]]:
        """
        Vérifie la disponibilité des terrains et ne retourne que les nouveaux créneaux disponibles
        
        Args:
            target_time (str, optional): Heure cible (ex: "11H00"). 
                                       Si None, utilise la config
            planning_date (str, optional): Date du planning (format: "YYYY-MM-DD")
        
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
            
            # Construire l'URL avec la date si spécifiée
            url = self.config.PLANNING_URL
            if planning_date:
                # Convertir la date au format DD-MM-YYYY
                try:
                    date_obj = datetime.strptime(planning_date, "%A %d %B %Y")
                    formatted_date = date_obj.strftime("%d-%m-%Y")
                    url += f"?date={formatted_date}"
                except ValueError as e:
                    logger.error(f"Erreur lors de la conversion de la date '{planning_date}': {str(e)}")
                    return
            
            # Récupérer la page du planning
            response = self.session.get(url)
            response.raise_for_status()
            
            # Parser la page
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extraire la date du planning
            date_text = self._extract_date(soup)
            if not date_text:
                logger.error("Impossible de trouver la date du planning")
                return
            
            # Convertir la date en objet datetime
            try:
                date_obj = datetime.strptime(date_text, "%A %d %B %Y")
                logger.info(f"Date du planning : {date_text} ({date_obj.strftime('%Y-%m-%d')})")
            except ValueError as e:
                logger.error(f"Erreur lors de la conversion de la date '{date_text}': {str(e)}")
                return
            
            # Vérifier les disponibilités pour l'horaire demandé
            available_slots = self._find_available_slots(soup, target_time)
            
            # Si des créneaux sont disponibles, vérifier s'ils sont nouveaux
            if available_slots:
                state_key = f"{date_obj.strftime('%Y-%m-%d')}_{target_time}"
                if state_key not in self.previous_states:
                    self.previous_states[state_key] = []
                
                # Identifier les nouveaux créneaux
                new_slots = []
                for slot in available_slots:
                    if slot not in self.previous_states[state_key]:
                        new_slots.append(slot)
                        self.previous_states[state_key].append(slot)
                
                # Sauvegarder l'état
                self._save_states()
                
                # Si de nouveaux créneaux sont disponibles, envoyer une notification
                if new_slots:
                    message = f"Nouveaux créneaux disponibles pour {target_time} le {date_text} :\n"
                    message += "\n".join([f"- {slot}" for slot in new_slots])
                    logger.info(message)
                    self.notifier.send_notification("Créneaux Padel disponibles !", message)
                else:
                    logger.debug(f"Aucun nouveau créneau disponible pour {target_time}")
            else:
                logger.debug(f"Aucun nouveau créneau disponible pour {target_time}")
            
            return newly_available_slots
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des disponibilités : {str(e)}")
            return []

    def _is_court_available(self, court_classes):
        """Vérifie si un terrain est disponible en fonction de ses classes CSS"""
        return any('libre' in class_name for class_name in court_classes)

    def _extract_date(self, soup: BeautifulSoup) -> str:
        """Extrait la date du planning"""
        try:
            # Essayer différents sélecteurs possibles pour trouver le titre
            selectors = [
                '.planning--title',
                '.table-planning--title',
                'h2',
                '.title',
                '.table-planning thead th',
                'th.planning-title'
            ]
            
            # Liste des mois en français pour la détection
            mois_fr = [
                "janvier", "février", "mars", "avril", "mai", "juin",
                "juillet", "août", "septembre", "octobre", "novembre", "décembre",
                "fevrier", "aout"  # Variantes sans accents
            ]
            
            # D'abord, essayer les sélecteurs spécifiques
            for selector in selectors:
                elements = soup.select(selector)
                for element in elements:
                    text = element.get_text().strip().lower()
                    # Si le texte contient un mois français
                    if any(mois in text for mois in mois_fr):
                        # Extraire la partie après "planning padel du"
                        if "planning padel du" in text:
                            date_text = text.split("planning padel du")[1].strip()
                        else:
                            date_text = text.strip()
                        logger.debug(f"Date trouvée avec le sélecteur {selector}: {date_text}")
                        return date_text
            
            # Si rien n'a fonctionné, chercher dans tout le texte
            full_text = soup.get_text().lower()
            
            # Chercher un motif de date
            date_patterns = [
                r'planning padel du\s+(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+\d{1,2}\s+(?:' + '|'.join(mois_fr) + r')\s+\d{4}',
                r'(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+\d{1,2}\s+(?:' + '|'.join(mois_fr) + r')\s+\d{4}',
                r'\d{1,2}\s+(?:' + '|'.join(mois_fr) + r')\s+\d{4}'
            ]
            
            for pattern in date_patterns:
                match = re.search(pattern, full_text)
                if match:
                    date_text = match.group(0)
                    if "planning padel du" in date_text:
                        date_text = date_text.split("planning padel du")[1].strip()
                    logger.debug(f"Date trouvée avec pattern dans le texte: {date_text}")
                    return date_text
            
            # Si on arrive ici, aucune date n'a été trouvée
            logger.error("Aucune date trouvée dans la page")
            logger.debug("Contenu de la page :")
            logger.debug(full_text[:500])
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

    def _find_available_slots(self, soup: BeautifulSoup, target_time: str) -> List[str]:
        """
        Trouve les créneaux disponibles pour un horaire donné
        
        Args:
            soup (BeautifulSoup): Objet BeautifulSoup représentant la page du planning
            target_time (str): Heure cible (ex: "11H00")
        
        Returns:
            List[str]: Liste des créneaux disponibles pour l'horaire donné
        """
        available_slots = []
        
        # Chercher la table qui contient les créneaux
        planning_table = soup.find('table', {'class': 'table-planning'})
        if not planning_table:
            logger.error("Page de planning non trouvée")
            return []
        
        # Récupérer les lignes de la table
        rows = planning_table.find_all('tr')
        
        for row in rows:
            time_cell = row.select_one('th')
            if not time_cell:
                continue
            
            time = time_cell.text.strip()
            if time != target_time:
                continue
            
            courts = row.select('td')
            
            for i, court in enumerate(courts, 1):
                court_classes = court.get('class', [])
                if self._is_court_available(court_classes):
                    available_slots.append(f"Padel {i}")
        
        return available_slots
