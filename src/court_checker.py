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
        
        # Déterminer le répertoire de données selon l'environnement
        if os.environ.get('DOCKER_ENV'):
            data_dir = "/app/data"
        else:
            # En local, utiliser le répertoire courant
            data_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            
        # Créer le répertoire data en local si nécessaire
        if not os.environ.get('DOCKER_ENV'):
            os.makedirs(os.path.join(data_dir, "data"), exist_ok=True)
            data_dir = os.path.join(data_dir, "data")
        
        # Configurer les chemins des fichiers
        self.state_file = os.path.join(data_dir, "court_states.json")
        self.dates_file = os.path.join(data_dir, "known_dates.json")
        self.known_dates = set()
        
        # S'assurer que les fichiers existent
        self._ensure_files_exist()
        
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

    def _ensure_files_exist(self):
        """S'assure que les fichiers d'état existent avec une structure valide"""
        # Créer le fichier d'états s'il n'existe pas
        if not os.path.exists(self.state_file):
            logger.info("Création du fichier d'états")
            with open(self.state_file, 'w') as f:
                json.dump({}, f)
        else:
            # Vérifier que le contenu est valide
            try:
                with open(self.state_file, 'r') as f:
                    content = f.read().strip()
                    if content:  # Si le fichier n'est pas vide
                        json.loads(content)  # Tester si c'est du JSON valide
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Fichier d'états corrompu, création d'un nouveau : {str(e)}")
                with open(self.state_file, 'w') as f:
                    json.dump({}, f)
        
        # Créer le fichier des dates connues s'il n'existe pas
        if not os.path.exists(self.dates_file):
            logger.info("Création du fichier des dates connues")
            with open(self.dates_file, 'w') as f:
                json.dump({}, f)
        else:
            # Vérifier que le contenu est valide
            try:
                with open(self.dates_file, 'r') as f:
                    content = f.read().strip()
                    if content:  # Si le fichier n'est pas vide
                        json.loads(content)  # Tester si c'est du JSON valide
            except (json.JSONDecodeError, Exception) as e:
                logger.warning(f"Fichier des dates corrompu, création d'un nouveau : {str(e)}")
                with open(self.dates_file, 'w') as f:
                    json.dump({}, f)

    def _load_states(self) -> Dict[str, Dict[str, str]]:
        """
        Charge l'état des créneaux depuis le fichier JSON
        
        Returns:
            Dict[str, Dict[str, str]]: État des créneaux
        """
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Erreur lors du chargement des états : {str(e)}")
            return {}

    def _save_states(self, states: Dict, state_key: str):
        """
        Sauvegarde l'état actuel dans le fichier JSON
        
        Args:
            states: Dict des états pour une date donnée
            state_key: Clé d'état (format: "HH:MM|YYYY-MM-DD")
        """
        backup_file = f"{self.state_file}.bak"
        try:
            # Mettre à jour les états pour cette clé
            self.previous_states[state_key] = states
            
            # Nettoyer les anciennes clés qui ne sont pas au format "HH:MM|YYYY-MM-DD"
            self.previous_states = {k: v for k, v in self.previous_states.items() if '|' in k}
            
            # Supprimer les états anciens (garder seulement les dates futures)
            today = datetime.now().strftime('%Y-%m-%d')
            
            # Garder seulement les états des dates futures ou d'aujourd'hui
            self.previous_states = {
                k: v for k, v in self.previous_states.items()
                if k.split('|')[1] >= today  # Comparer les dates au format YYYY-MM-DD
            }
            
            # Sauvegarder avec un backup
            if os.path.exists(self.state_file):
                os.replace(self.state_file, backup_file)
            
            with open(self.state_file, 'w') as f:
                json.dump(self.previous_states, f, indent=2)
                
            # Si tout s'est bien passé, supprimer le backup
            if os.path.exists(backup_file):
                os.remove(backup_file)
                
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des états : {str(e)}")
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
                dates_by_month = json.loads(content)
                # Mettre à jour self.known_dates avec toutes les dates
                self.known_dates = set()
                for month_dates in dates_by_month.values():
                    self.known_dates.update(month_dates)
                return dates_by_month
        except Exception as e:
            logger.error(f"Erreur lors du chargement des dates connues : {str(e)}")
            return {}

    def _save_known_dates(self, dates: List[str]):
        """
        Sauvegarde les dates connues dans le fichier JSON
        
        Args:
            dates: Liste des dates au format "YYYY-MM-DD"
        """
        try:
            # Mettre à jour self.known_dates
            self.known_dates.update(dates)
            
            # Organiser les dates par mois
            dates_by_month = {}
            for date in self.known_dates:  # Utiliser toutes les dates connues
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
                
            # Si tout s'est bien passé, supprimer le backup
            if os.path.exists(backup_file):
                os.remove(backup_file)
                
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde des dates connues : {str(e)}")
            # En cas d'erreur, restaurer le backup si disponible
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
        if target_times is None:
            target_times = self.config.TARGET_TIMES
            
        all_available_slots = []
        new_dates_found = []
        all_dates = set()  # Pour stocker toutes les dates trouvées
        
        try:
            # Recharger les dates connues depuis le fichier
            known_dates = self._load_known_dates()
            self.known_dates = set()
            for month_dates in known_dates.values():
                self.known_dates.update(month_dates)
            logger.info(f"Dates connues rechargées : {sorted(list(self.known_dates))}")
            
            # Se connecter si nécessaire
            self._login()
            
            # Obtenir la page principale du planning
            response = self.session.get(self.config.PLANNING_URL)
            response.raise_for_status()
            
            # Parser la page
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extraire la date du jour depuis la page principale
            today_text = self._extract_date(soup)
            if today_text:
                today_date = self._convert_date_to_iso(today_text)
                if today_date:
                    all_dates.add(today_date)
                    logger.info(f"Date du jour : {today_date}")
                    
                    # Vérifier si c'est une nouvelle date
                    if today_date not in self.known_dates:
                        new_dates_found.append(today_date)
                        logger.info(f"Nouvelle date trouvée : {today_date}")
                    
                    # Vérifier les disponibilités pour la date du jour
                    for target_time in target_times:
                        logger.info(f"Vérification des disponibilités pour {target_time}...")
                        available_slots = self.check_availability(target_time, today_date)
                        if available_slots:
                            all_available_slots.extend(available_slots)
            
            # Obtenir toutes les URLs de planning disponibles
            planning_urls = self._get_planning_urls(soup)
            
            # Pour chaque URL de planning
            for url in planning_urls:
                # Extraire la date de l'URL
                date = self._extract_date_from_url(url)
                if not date:
                    continue
                
                # Ne pas revérifier la date du jour
                if date == today_date:
                    continue
                
                logger.info(f"Vérification du planning pour le {date}")
                all_dates.add(date)  # Ajouter la date à l'ensemble des dates trouvées
                
                # Vérifier si c'est une nouvelle date
                if date not in self.known_dates:
                    new_dates_found.append(date)
                    logger.info(f"Nouvelle date trouvée : {date}")
                
                # Pour chaque horaire cible
                for target_time in target_times:
                    logger.info(f"Vérification des disponibilités pour {target_time}...")
                    available_slots = self.check_availability(target_time, date)
                    if available_slots:
                        all_available_slots.extend(available_slots)
            
            # Sauvegarder toutes les dates trouvées
            if all_dates:
                logger.info(f"Dates trouvées : {sorted(list(all_dates))}")
                self._save_known_dates(list(all_dates))  # Sauvegarder toutes les dates
                self.known_dates.update(all_dates)  # Mettre à jour self.known_dates avec toutes les dates
            
            return all_available_slots, new_dates_found
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des dates : {str(e)}")
            return [], []

    def _get_all_times(self, soup: BeautifulSoup) -> List[str]:
        """Retourne la liste de tous les horaires du planning"""
        times = []
        planning_table = soup.find('table', {'class': 'table-planning'})
        if not planning_table:
            return times
            
        # Récupérer toutes les cellules d'horaire
        for row in planning_table.find_all('tr'):
            time_cell = row.select_one('th')
            if not time_cell:
                continue
                
            time = time_cell.text.strip()
            if time and time != "Horaires":  # Ignorer l'en-tête
                times.append(time)
                
        return times

    def _find_available_slots_for_time(self, row) -> Tuple[List[str], Dict[str, str]]:
        """
        Trouve les créneaux disponibles pour une ligne donnée
        
        Returns:
            Tuple[List[str], Dict[str, str]]: (créneaux disponibles, état de tous les terrains)
        """
        available_slots = []
        current_state = {}
        
        courts = row.select('td')
        for i, court in enumerate(courts, 1):
            court_name = f"Padel {i}"
            court_classes = court.get('class', [])
            is_available = self._is_court_available(court_classes)
            
            current_state[court_name] = "libre" if is_available else "occupé"
            if is_available:
                available_slots.append(court_name)
                
        return available_slots, current_state

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
        try:
            # Recharger l'état depuis le fichier
            self.previous_states = self._load_states()
            
            # Construire l'URL avec la date si fournie
            url = self.config.PLANNING_URL
            if planning_date:
                # Convertir la date au format DD-MM-YYYY pour l'URL
                date_obj = datetime.strptime(planning_date, '%Y-%m-%d')
                formatted_date = date_obj.strftime('%d-%m-%Y')
                url = f"{url}?date={formatted_date}"

            # Faire la requête
            response = self.session.get(url)
            
            # Vérifier si on a été redirigé vers la page de connexion
            if "/membre" in response.url and "planning" not in response.url:
                logger.info("Session expirée, reconnexion...")
                self._login()
                # Réessayer la requête après la reconnexion
                response = self.session.get(url)
            
            # Vérifier le code de statut
            response.raise_for_status()
            
            # Parser le HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Si la date n'est pas fournie, l'extraire du HTML
            if not planning_date:
                date_text = self._extract_date(soup)
                if not date_text:
                    logger.error("Impossible de trouver la date du planning")
                    return []
                planning_date = self._convert_date_to_iso(date_text)
                if not planning_date:
                    return []
            
            logger.info(f"Vérification du planning pour le {planning_date}")
            
            # Si aucun horaire n'est spécifié, utiliser celui de la config
            if not target_time:
                target_time = self.config.TARGET_TIME
            
            # Trouver la table qui contient les créneaux
            planning_table = soup.find('table', {'class': 'table-planning'})
            if not planning_table:
                logger.error("Page de planning non trouvée")
                return []
            
            # Parcourir toutes les lignes pour sauvegarder tous les états
            new_slots = []
            rows = planning_table.find_all('tr')
            
            # Stocker tous les états du site web
            web_states = {}
            
            # Première passe : récupérer tous les états du site web
            for row in rows:
                time_cell = row.select_one('th')
                if not time_cell:
                    continue
                    
                current_time = time_cell.text.strip()
                if not current_time or current_time == "Horaires":
                    continue
                
                # Trouver les créneaux disponibles et l'état actuel pour cet horaire
                available_slots, current_state = self._find_available_slots_for_time(row)
                state_key = f"{current_time}|{planning_date}"
                web_states[state_key] = current_state
            
            # Deuxième passe : comparer avec les états précédents et mettre à jour
            for state_key, web_state in web_states.items():
                current_time = state_key.split('|')[0]
                
                # Si c'est l'horaire cible, vérifier les créneaux qui passent de occupé à libre
                if current_time == target_time:
                    # Si nous avons un état précédent
                    if state_key in self.previous_states:
                        for court, web_status in web_state.items():
                            # Si le créneau est libre sur le site web
                            if web_status == "libre":
                                # Et qu'il était occupé dans l'état précédent
                                if (
                                    court in self.previous_states[state_key] and
                                    self.previous_states[state_key][court] == "occupé"
                                ):
                                    new_slots.append((target_time, court, planning_date))
                                    logger.info(f"Créneau libéré : {court} à {target_time} le {planning_date}")
                                    logger.info(f"État précédent : {self.previous_states[state_key][court]}")
                                    logger.info(f"Nouvel état : {web_status}")
                
                # Mettre à jour l'état avec celui du site web
                if state_key not in self.previous_states:
                    self.previous_states[state_key] = {}
                self.previous_states[state_key] = web_state
                self._save_states(web_state, state_key)
            
            if new_slots:
                logger.info(f"Créneaux libérés pour {target_time} : {new_slots}")
            else:
                logger.debug(f"Aucun créneau libéré pour {target_time}")
            
            return new_slots
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des disponibilités : {str(e)}")
            return []

    def _is_court_available(self, court_classes):
        """Vérifie si un terrain est disponible en fonction de ses classes CSS"""
        return any('libre' in class_name for class_name in court_classes)

    def _extract_date(self, soup: BeautifulSoup) -> str:
        """Extrait la date du planning"""
        try:
            # Log du contenu HTML pour le debug
            logger.debug("Contenu HTML de la page :")
            logger.debug(str(soup)[:1000])  # Les 1000 premiers caractères
            
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
                logger.debug(f"Recherche avec le sélecteur {selector} : {len(elements)} éléments trouvés")
                for element in elements:
                    text = element.get_text().strip().lower()
                    logger.debug(f"Texte trouvé : {text}")
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
            logger.debug("Texte complet de la page :")
            logger.debug(full_text[:1000])  # Les 1000 premiers caractères
            
            # Chercher un motif de date
            date_patterns = [
                r'planning padel du\s+(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+\d{1,2}\s+(?:' + '|'.join(mois_fr) + r')\s+\d{4}',
                r'(?:lundi|mardi|mercredi|jeudi|vendredi|samedi|dimanche)\s+\d{1,2}\s+(?:' + '|'.join(mois_fr) + r')\s+\d{4}',
                r'\d{1,2}\s+(?:' + '|'.join(mois_fr) + r')\s+\d{4}'
            ]
            
            for pattern in date_patterns:
                logger.debug(f"Essai du pattern : {pattern}")
                match = re.search(pattern, full_text)
                if match:
                    date_text = match.group(0)
                    if "planning padel du" in date_text:
                        date_text = date_text.split("planning padel du")[1].strip()
                    logger.debug(f"Date trouvée avec pattern dans le texte: {date_text}")
                    return date_text
            
            # Si on arrive ici, aucune date n'a été trouvée
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
            # Trouver la liste des dates
            dates_list = soup.find('ul', class_='planning--dates')
            if not dates_list:
                logger.warning("Liste des dates non trouvée")
                return [self.config.PLANNING_URL]

            # Trouver tous les liens de dates
            date_links = dates_list.find_all('a', class_='planning--header--date')
            
            # Log pour le debug
            logger.debug(f"Nombre de liens de dates trouvés : {len(date_links)}")
            
            for link in date_links:
                href = link.get('href', '')
                logger.debug(f"Analyse du lien de date : {href}")
                
                # Construire l'URL complète
                full_url = urljoin(self.config.SITE_URL, href)
                if full_url not in urls:
                    urls.append(full_url)
                    # Extraire la date pour le logging
                    date_match = re.search(r'date=(\d{2}-\d{2}-\d{4})', href)
                    if date_match:
                        date_str = date_match.group(1)
                        logger.debug(f"Date trouvée dans l'URL : {date_str}")
            
            if not urls:
                logger.warning("Aucune URL de planning trouvée")
                return [self.config.PLANNING_URL]
            
            logger.info(f"URLs de planning trouvées : {len(urls)}")
            return urls
            
        except Exception as e:
            logger.error(f"Erreur lors de l'extraction des URLs de planning : {str(e)}")
            return [self.config.PLANNING_URL]  # Retourner au moins l'URL principale en cas d'erreur

    def _extract_date_from_url(self, url: str) -> str:
        """Extrait la date d'une URL de planning"""
        try:
            # Extraire la date de l'URL (format: DD-MM-YYYY)
            date_match = re.search(r'date=(\d{2}-\d{2}-\d{4})', url)
            if date_match:
                date_str = date_match.group(1)
                # Convertir en format YYYY-MM-DD
                date_obj = datetime.strptime(date_str, '%d-%m-%Y')
                return date_obj.strftime('%Y-%m-%d')
            else:
                # Si pas de date dans l'URL, c'est la date du jour
                return datetime.now().strftime('%Y-%m-%d')
        except ValueError as e:
            logger.error(f"Erreur lors de l'extraction de la date de l'URL '{url}': {str(e)}")
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

    def _convert_date_to_iso(self, date_text: str) -> str:
        """Convertit une date au format texte en date ISO"""
        try:
            date_obj = datetime.strptime(date_text, "%A %d %B %Y")
            return date_obj.strftime("%Y-%m-%d")
        except ValueError as e:
            logger.error(f"Erreur lors de la conversion de la date '{date_text}': {str(e)}")
        return None

    def _get_all_slots(self) -> List[str]:
        """Retourne la liste de tous les terrains possibles"""
        return [f"Padel {i}" for i in range(1, 5)]  # Padel 1 à 4
