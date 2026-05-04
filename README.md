# Debunk — X Thread Extractor

Outil Python local pour extraire un tweet X/Twitter et ses branches de réponses via Playwright.

**Version 2.3.0** — Optimisations performance adaptatives + mode stealth anti-détection + analyse Debuk via API OpenAI-compatible + garde-fous de crawl.

**Nouveau v2.3.0** : extraction plus rapide avec scroll/expand adaptatifs, mode `--fast` renforcé, tri récence désactivable et sauvegardes partielles espacées.

## Installation
```bash
conda activate test
pip install -r requirements.txt
playwright install chromium
```

## Configuration `.env`

Copie `.env.example` vers `.env`, puis renseigne au minimum :

```env
OPENAI_BASE_URL=https://routerlab.ch/v1
OPENAI_API_KEY=your-api-key
OPENAI_ANALYSIS_MODEL=your-analysis-model
OPENAI_RESEARCH_MODEL=your-research-model
```

Variables disponibles :

| Variable | Description | Défaut |
|---|---|---|
| `OPENAI_BASE_URL` | Base URL de l'API OpenAI-compatible | `https://routerlab.ch/v1` |
| `OPENAI_API_KEY` | Clé API | vide |
| `OPENAI_ANALYSIS_MODEL` | Modèle pour le rapport final Debuk | vide |
| `OPENAI_RESEARCH_MODEL` | Modèle pour générer les requêtes de vérification | identique au modèle d'analyse |
| `OPENAI_REQUEST_TIMEOUT` | Timeout HTTP en secondes | `120` |
| `OPENAI_TEMPERATURE` | Température du rapport final | `0.2` |
| `DEBUNK_FACT_CHECK_QUERIES` | Nombre max de requêtes factuelles | `4` |
| `DEBUNK_SEARCH_REGION` | Région DDGS | `fr-fr` |
| `DEBUNK_SEARCH_SAFESEARCH` | SafeSearch DDGS | `moderate` |
| `DEBUNK_SEARCH_MAX_RESULTS` | Résultats DDGS par requête | `5` |
| `DEBUNK_EXTRACT_TOP_N` | Sources enrichies avec extraction de contenu | `2` |
| `DEBUNK_EXTRACT_MAX_CHARS` | Taille max des extraits DDGS | `1200` |

## Prérequis
- Google Chrome installé localement
- Au premier lancement, le script crée automatiquement un profil navigateur (`chromium_profile/`) et te demande de te connecter à X/Twitter dans la fenêtre qui s'ouvre

## Usage

### Mode standard (optimisé + stealth)
```bash
conda activate test
python x_thread_extractor.py https://x.com/USER/status/TWEET_ID
```

### Mode ultra-rapide (recommandé pour les gros fils)
```bash
conda activate test
python x_thread_extractor.py https://x.com/USER/status/TWEET_ID --fast
```

### Extraction + analyse Debuk
```bash
conda activate test
python x_thread_extractor.py https://x.com/USER/status/TWEET_ID --analyze
```

Le mode `--analyze` :
- utilise une API compatible OpenAI configurable dans `.env`
- prépare des requêtes factuelles avec le modèle `OPENAI_RESEARCH_MODEL`
- interroge le moteur de recherche `ddgs`
- génère un rapport Markdown `*.analysis.md` avec le prompt système Debuk

### Exemples avancés
```bash
# Extraction rapide avec profondeur limitée
python x_thread_extractor.py <url> --fast --max-depth 3

# Extraction complète avec sortie personnalisée
python x_thread_extractor.py <url> --max-depth 5 --output sortie.json

# Mode headless pour automatisation
python x_thread_extractor.py <url> --fast --headless --non-interactive

# Désactiver le mode stealth (non recommandé)
python x_thread_extractor.py <url> --no-stealth

# Extraction bornée pour éviter les runs trop longs
python x_thread_extractor.py <url> --max-pages 50 --max-tweets 300 --crawl-timeout-s 900
```

## Options

| Option | Description | Défaut |
|---|---|---|
| `--fast` | **Mode ultra-rapide** (1 scroll, 1 expand, délais minimaux, tri récence désactivé) | Désactivé |
| `--no-stealth` | **Désactive le mode furtif** anti-détection | Activé |
| `--no-sort-latest` | Ne tente pas le tri des réponses par récence, pour gagner du temps | Désactivé |
| `--max-depth N` | Profondeur de récursion | 10 |
| `--max-pages N` | Nombre maximal de pages tweet à visiter avant arrêt propre | 200 |
| `--max-tweets N` | Nombre maximal de tweets à collecter/parser avant arrêt propre | 1000 |
| `--crawl-timeout-s N` | Timeout global du crawl en secondes | 1800 |
| `--output FILE` | Chemin de sortie JSON | Auto-généré |
| `--non-interactive` | Échoue si la session est expirée au lieu d'attendre | Désactivé |
| `--headless` | Lance le navigateur sans fenêtre visible | Désactivé |
| `--verbose` | Affiche les erreurs internes détaillées (debug) | Désactivé |
| `--analyze` | Génère un rapport Markdown Debuk après extraction | Désactivé |
| `--analysis-output FILE` | Chemin du rapport Markdown | `*.analysis.md` |
| `--analysis-model MODEL` | Surcharge du modèle de rapport final | `.env` |
| `--research-model MODEL` | Surcharge du modèle de recherche factuelle | `.env` |
| `--no-search` | Analyse sans DDGS ni vérification web | Désactivé |
| `--partial-save-every N` | Sauvegarde partielle toutes les N branches, 0 pour désactiver | 5 |
| `--partial-save-interval-s N` | Délai minimal entre deux sauvegardes partielles | 20 |
| `--nav-wait N` | Secondes d'attente après navigation | 1.5 (0.5 en fast) |
| `--scroll-passes N` | Nombre de scrolls par page | 3 (1 en fast) |
| `--scroll-delay N` | Délai entre scrolls (secondes) | 0.8 (0.25 en fast) |
| `--expand-passes N` | Nombre de passes "afficher plus" | 3 (1 en fast) |
| `--expand-delay N` | Délai après clic "afficher plus" | 1.0 (0.3 en fast) |
| `--chrome-exe PATH` | Chemin vers l'exécutable Chrome | Auto-détecté |
| `--profile-dir PATH` | Répertoire du profil navigateur persistant | `./chromium_profile` |

## Mode Stealth Anti-Détection 🥷

Le mode stealth est **activé par défaut** et implémente plusieurs techniques pour éviter la détection par les systèmes anti-bot :

### Techniques implémentées
- ✅ Masquage de `navigator.webdriver`
- ✅ Simulation de propriétés de navigateur réel (`plugins`, `languages`, `platform`)
- ✅ User-Agent réaliste (Chrome 131 sur Windows 10)
- ✅ Locale et timezone cohérents (`fr-FR`, `Europe/Paris`)
- ✅ Délais aléatoires pour simuler un comportement humain
- ✅ Arguments Chrome anti-détection (`--disable-blink-features=AutomationControlled`)
- ✅ Injection de `window.chrome.runtime`
- ✅ Simulation de Permissions API

### Tester le mode stealth
```bash
python test_stealth.py
```

Ce script ouvre un navigateur avec le mode stealth et te permet de tester sur des sites de détection de bots.

📖 **Documentation complète** : Voir [STEALTH_FEATURES.md](STEALTH_FEATURES.md) pour tous les détails techniques.

## Comportement

### Nouveautés v2.3.0
- **Mode `--fast` renforcé** : délais réduits, timeout abaissé et tri par récence désactivé automatiquement
- **Scroll adaptatif** : arrêt anticipé quand la hauteur de page ne progresse plus
- **Expansion adaptative** : arrêt si aucun nouveau tweet n'apparaît après les clics "afficher plus"
- **Limite de clics expand** : plafonne les clics par passe pour éviter les boucles lentes sur les gros fils
- **Tri désactivable** : nouvelle option `--no-sort-latest` pour éviter une étape coûteuse
- **Sauvegardes partielles optimisées** : nouvelles options `--partial-save-every` et `--partial-save-interval-s`, écriture compacte et atomique

### Nouveautés v2.2.1
- **Garde-fous de crawl** : arrêt propre via `--max-pages`, `--max-tweets` et `--crawl-timeout-s`
- **Métadonnées d'arrêt** : ajout de `stopped_by_limit` et `stop_reason` dans la sortie JSON
- **Tests portables** : suppression du chemin Windows hardcodé dans les tests unitaires
- **Test stealth robuste** : Playwright manquant déclenche maintenant un skip `unittest` propre
- **Analyse Debuk plus tolérante** : fallbacks en cas d'erreur LLM, JSON invalide ou DDGS indisponible

### Nouveautés v2.2.0
- **Analyse Debuk optionnelle** : génération d'un rapport Markdown via API OpenAI-compatible
- **Configuration `.env`** : `OPENAI_BASE_URL`, modèles, clé API, paramètres de recherche
- **Recherche factuelle DDGS** : préparation des requêtes puis enrichissement avec sources web

### Nouveautés v2.1.0
- **Mode stealth anti-détection** : Masquage WebDriver, délais aléatoires, empreinte navigateur réaliste
- **Activé par défaut** : Protection contre les systèmes anti-bot de X/Twitter
- **Délais aléatoires** : Variation de ±20-40% pour simuler un comportement humain

### Optimisations v2.0.0
- **Suppression du rechargement de page parente** : gain de ~70% de performance en éliminant les rechargements inutiles après chaque branche
- **Scroll/expand réduits** : 3 passes au lieu de 8 (1 en mode `--fast`)
- **Arrêt anticipé intelligent** : stoppe scroll/expand quand la page ne progresse plus
- **Délais optimisés** : attentes réduites tout en maintenant la fiabilité
- **Sauvegardes partielles espacées** : moins de réécritures JSON complètes pendant le crawl
- **Délais aléatoires** : variation de ±20-40% pour simuler un comportement humain (mode stealth)
- **Métriques de performance** : affiche le nombre de rechargements évités

### Processus d'extraction
- Charge le tweet racine
- Bascule les réponses sur le tri "Récents" quand possible, sauf `--fast` ou `--no-sort-latest`
- Scrolle et tente d'ouvrir les réponses supplémentaires
- Explore récursivement les branches **sans recharger la page parente** (optimisation majeure)
- **Sauvegarde intermédiaire** (`.partial.json`) toutes les 5 branches et au minimum toutes les 20s par défaut, pour limiter les écritures coûteuses
- Génère un fichier JSON horodaté par défaut et supprime le fichier partiel

## Fichier de sortie

Par défaut, la sortie est générée dans le dossier du script avec un nom de type :
- `fil_x_<tweet_id>_<timestamp>.json`
- `fil_x_<tweet_id>_<timestamp>.analysis.md` si `--analyze` est activé

### Structure JSON
```json
{
  "meta": {
    "url_racine": "https://x.com/user/status/123",
    "extraction_iso": "2026-05-01T14:30:00",
    "duree_secondes": 45.2,
    "tweets_uniques": 150,
    "tweets_parsed": 155,
    "pages_visitees": 80,
    "erreurs": 2,
    "profondeur_max": 10,
    "page_reloads_saved": 75,
    "optimized_version": true,
    "stopped_by_limit": false,
    "stop_reason": ""
  },
  "tweet_racine": { ... },
  "reponses": [ ... ]
}
```

## Performance

| Mode | Vitesse | Usage recommandé |
|---|---|---|
| **Standard** | ~70% plus rapide que v1.0 | Extraction complète et fiable |
| **Fast (`--fast`)** | ~85-90% plus rapide que v1.0 | Gros fils, tests rapides |

**Exemple** : Un fil qui prenait 20 minutes en v1.0 prend maintenant ~6 minutes en mode standard, ou ~3 minutes en mode `--fast`.

## Compatibilité
- **Windows** : détecte Chrome dans `C:\Program Files\Google\Chrome\Application\chrome.exe`
- **macOS** : détecte Chrome dans `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`
- **Linux** : cherche `google-chrome`, `chromium-browser` ou `chromium` dans le PATH

## Sécurité et limites
- Le script réutilise un **profil navigateur persistant** : il contient potentiellement cookies et session authentifiée
- L'outil dépend fortement de l'interface de X/Twitter, donc il peut casser si le DOM change
- Le mode `--non-interactive` échoue explicitement si la session est expirée
- **Mode stealth** : Réduit la détectabilité mais ne garantit pas l'invisibilité totale face aux systèmes anti-bot avancés
- Les fichiers `.env`, `chromium_profile/`, `*.partial.json`, `*.analysis.md` et les secrets `.a0proj/` ne doivent pas être commités
- Les garde-fous `--max-pages`, `--max-tweets` et `--crawl-timeout-s` limitent les extractions trop longues, mais ne garantissent pas l'exhaustivité
- Ce projet est prévu pour un usage local expérimental, pas comme collecteur de production robuste
- ⚠️ **Légalité** : Le scraping de X/Twitter peut violer leurs conditions d'utilisation. Utilise cet outil de manière responsable.

## Anti-Détection : Playwright vs DrissionPage

Le mode stealth de Playwright implémente les techniques suivantes :
- Masquage des propriétés WebDriver
- User-Agent et locale réalistes
- Délais aléatoires pour simuler un comportement humain
- Arguments Chrome anti-détection

**Si tu rencontres des blocages fréquents**, envisage de migrer vers **DrissionPage** qui utilise le Chrome DevTools Protocol (CDP) au lieu de WebDriver, le rendant encore plus furtif.

📖 Voir [STEALTH_FEATURES.md](STEALTH_FEATURES.md) pour une comparaison détaillée.

## Reproduire l'ancien comportement

Si tu as besoin d'un comportement plus lent mais plus exhaustif, ajuste simplement les paramètres :
```bash
python x_thread_extractor.py <url> \
  --nav-wait 2.5 \
  --scroll-passes 8 \
  --scroll-delay 1.2 \
  --expand-passes 8 \
  --expand-delay 1.5
```

Voir [CHANGELOG.md](CHANGELOG.md) pour tous les détails.

## Historique des Versions

- **v2.3.0** (2026-05-04) : Optimisations performance adaptatives, fast mode renforcé, sauvegardes partielles espacées
- **v2.2.1** (2026-05-04) : Garde-fous de crawl, tests portables, robustesse LLM/DDGS
- **v2.2.0** (2026-05-01) : Analyse Debuk, config `.env`, API OpenAI-compatible, recherche DDGS
- **v2.1.0** (2026-05-01) : Mode stealth anti-détection, délais aléatoires, masquage WebDriver
- **v2.0.0** (2026-05-01) : Optimisations majeures de performance (70-85% plus rapide)
- **v1.0.0** (2025-01-XX) : Version initiale

## Tests
```bash
conda activate test
python -m py_compile x_thread_extractor.py thread_analysis.py test_stealth.py tests/*.py
python -m unittest discover -s tests -v
python -m unittest test_stealth -v
```

Sans Playwright installé, `test_stealth.py` est ignoré proprement par `unittest`.
