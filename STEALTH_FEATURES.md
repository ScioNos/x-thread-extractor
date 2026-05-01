# 🥷 Fonctionnalités Anti-Détection (Stealth Mode)

## Vue d'ensemble

Le mode stealth a été ajouté pour rendre Playwright plus furtif face aux systèmes anti-bot de X/Twitter. Il est **activé par défaut** et peut être désactivé avec `--no-stealth`.

## Techniques Implémentées

### 1. Masquage des Propriétés WebDriver

**Problème** : Les sites détectent `navigator.webdriver === true`

**Solution** : Injection de script au démarrage de chaque page pour :
- Supprimer `navigator.webdriver`
- Masquer `navigator.__proto__.webdriver`
- Définir `navigator.webdriver` comme `undefined`

```javascript
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined
});
```

### 2. Simulation de Navigateur Réel

**Propriétés ajoutées** :
- `navigator.plugins` : Liste de plugins simulés
- `navigator.languages` : `['fr-FR', 'fr', 'en-US', 'en']`
- `navigator.platform` : `'Win32'`
- `window.chrome.runtime` : Objet Chrome natif

### 3. User-Agent Réaliste

User-Agent configuré pour correspondre à Chrome 131 sur Windows 10 :
```
Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36
```

### 4. Locale et Timezone

- **Locale** : `fr-FR`
- **Timezone** : `Europe/Paris`

Cela évite les incohérences entre l'IP et les paramètres du navigateur.

### 5. Arguments de Lancement Chrome

Arguments supplémentaires pour masquer l'automatisation :
```python
--disable-blink-features=AutomationControlled
--disable-dev-shm-usage
--disable-web-security
--disable-features=IsolateOrigins,site-per-process
--disable-site-isolation-trials
```

### 6. Délais Aléatoires (Comportement Humain)

**Avant** : Délais fixes et prévisibles
```python
time.sleep(0.8)  # Toujours 0.8s
```

**Après** : Délais aléatoires pour simuler un humain
```python
delay = config.scroll_delay + random.uniform(-0.2, 0.3)
time.sleep(max(0.3, delay))  # Entre 0.6s et 1.1s
```

**Zones concernées** :
- Scroll de page : ±0.2-0.3s de variation
- Expansion de réponses : ±0.3-0.5s de variation
- Navigation : ±0.3-0.5s de variation

### 7. Permissions API

Simulation de la Permissions API pour éviter les détections :
```javascript
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);
```

## Utilisation

### Mode Stealth Activé (par défaut)
```bash
python x_thread_extractor.py https://x.com/USER/status/TWEET_ID
```

### Désactiver le Mode Stealth
```bash
python x_thread_extractor.py https://x.com/USER/status/TWEET_ID --no-stealth
```

### Combiner avec Mode Fast
```bash
python x_thread_extractor.py https://x.com/USER/status/TWEET_ID --fast
# Le mode stealth reste actif même en mode fast
```

## Comparaison Avant/Après

| Propriété | Avant (Playwright standard) | Après (Stealth Mode) |
|-----------|----------------------------|----------------------|
| `navigator.webdriver` | `true` | `undefined` |
| `navigator.plugins` | `[]` | `[1, 2, 3, 4, 5]` |
| `navigator.languages` | `['en-US']` | `['fr-FR', 'fr', 'en-US', 'en']` |
| User-Agent | Playwright/1.x | Chrome/131.0.0.0 |
| Délais | Fixes | Aléatoires ±20-40% |
| Timezone | Système | `Europe/Paris` |
| `window.chrome` | `undefined` | `{ runtime: {} }` |

## Tests de Détection

Pour vérifier l'efficacité du mode stealth, vous pouvez tester sur :

1. **Bot Detection Test** : https://bot.sannysoft.com/
2. **Fingerprint Test** : https://abrahamjuliot.github.io/creepjs/
3. **WebDriver Test** : https://intoli.com/blog/not-possible-to-block-chrome-headless/chrome-headless-test.html

## Limitations

⚠️ **Important** : Ces techniques réduisent la détectabilité mais ne garantissent pas l'invisibilité totale.

**Ce qui reste détectable** :
- Patterns de navigation trop rapides ou trop réguliers
- Absence de mouvements de souris (Playwright ne simule pas les mouvements naturels)
- Empreinte du profil Chrome (si nouveau profil sans historique)
- Analyse comportementale avancée (ML-based detection)

**Recommandations** :
- Utiliser un profil Chrome avec historique réel
- Éviter de scraper trop rapidement (respecter les délais)
- Se connecter manuellement au moins une fois
- Ne pas utiliser en mode headless pour les premières connexions

## Prochaines Améliorations Possibles

Si les blocages persistent, envisager :

1. **Playwright Stealth Plugin** : Bibliothèque dédiée avec plus de patches
2. **Rotation de User-Agents** : Changer le UA entre les sessions
3. **Simulation de mouvements de souris** : Ajouter des mouvements aléatoires
4. **Gestion de Canvas Fingerprinting** : Randomiser les empreintes canvas
5. **Migration vers DrissionPage** : Si Playwright reste trop détectable

## Ressources

- [Playwright Stealth](https://github.com/AtuboDad/playwright_stealth)
- [Undetected ChromeDriver](https://github.com/ultrafunkamsterdam/undetected-chromedriver)
- [Bot Detection Evasion](https://intoli.com/blog/not-possible-to-block-chrome-headless/)
