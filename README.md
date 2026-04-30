# Debunk — X Thread Extractor

Outil Python local pour extraire un tweet X/Twitter et ses branches de réponses via Playwright.

## Installation
```bash
pip install -r requirements.txt
playwright install chromium
```

## Prérequis
- Google Chrome installé localement
- une session X/Twitter déjà enregistrée dans un profil persistant via `login_once.py`

## Usage
```bash
python x_thread_extractor.py https://x.com/USER/status/TWEET_ID
```

## Options utiles
```bash
python x_thread_extractor.py <url> --max-depth 3 --output sortie.json
python x_thread_extractor.py <url> --non-interactive
python x_thread_extractor.py <url> --headless
python x_thread_extractor.py <url> --verbose
python x_thread_extractor.py <url> --profile-dir ./chromium_profile
python x_thread_extractor.py <url> --chrome-exe "C:/Program Files/Google/Chrome/Application/chrome.exe"
```

| Option | Description |
|---|---|
| `--max-depth N` | Profondeur de récursion (défaut : 10) |
| `--output FILE` | Chemin de sortie JSON |
| `--non-interactive` | Échoue si la session est expirée au lieu d'attendre |
| `--headless` | Lance le navigateur sans fenêtre visible |
| `--verbose` | Affiche les erreurs internes détaillées (debug) |
| `--nav-wait N` | Secondes d'attente après navigation (défaut : 2.5) |
| `--scroll-passes N` | Nombre de scrolls par page (défaut : 8) |
| `--chrome-exe PATH` | Chemin vers l'exécutable Chrome |
| `--profile-dir PATH` | Répertoire du profil navigateur persistant |

## Comportement
- charge le tweet racine
- bascule les réponses sur le tri "Récents" quand possible
- scrolle et tente d'ouvrir les réponses supplémentaires
- explore récursivement les branches
- **sauvegarde intermédiaire** (`.partial.json`) après chaque branche de profondeur 1 pour éviter toute perte en cas de crash
- génère un fichier JSON horodaté par défaut et supprime le fichier partiel

## Fichier de sortie
Par défaut, la sortie est générée dans le dossier du script avec un nom de type :
- `fil_x_<tweet_id>_<timestamp>.json`

## Compatibilité
- **Windows** : détecte Chrome dans `C:\Program Files\Google\Chrome\Application\chrome.exe`
- **macOS** : détecte Chrome dans `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- **Linux** : cherche `google-chrome`, `chromium-browser` ou `chromium` dans le PATH

## Sécurité et limites
- le script réutilise un **profil navigateur persistant** : il contient potentiellement cookies et session authentifiée
- l'outil dépend fortement de l'interface de X/Twitter, donc il peut casser si le DOM change
- le mode `--non-interactive` échoue explicitement si la session est expirée
- ce projet est prévu pour un usage local expérimental, pas comme collecteur de production robuste

## Tests
```bash
python -m unittest discover -s tests
```
