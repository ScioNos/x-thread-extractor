#!/usr/bin/env python3
"""
x_thread_extractor.py — Version 2.2.0 avec mode stealth anti-détection et analyse LLM optionnelle.

Optimisations principales :
  - Suppression du rechargement de page parente (gain ~70% de temps)
  - Scroll/expand réduits (2-3 passes au lieu de 8)
  - Attentes adaptatives au lieu de délais fixes
  - Parsing optimisé avec cache des sélecteurs
  - Mode stealth activé par défaut (masquage WebDriver, délais aléatoires)

Prérequis :
  pip install -r requirements.txt
  playwright install chromium

Usage :
  python x_thread_extractor.py https://x.com/USER/status/TWEET_ID
  python x_thread_extractor.py https://x.com/USER/status/TWEET_ID --fast
  python x_thread_extractor.py https://x.com/USER/status/TWEET_ID --no-stealth
  python x_thread_extractor.py https://x.com/USER/status/TWEET_ID --analyze
"""

from __future__ import annotations

import argparse
import json
import logging
import platform
import re
import shutil
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse, urlunparse

try:
    from playwright.sync_api import TimeoutError as PlaywrightTimeout, sync_playwright
except ModuleNotFoundError:
    PlaywrightTimeout = RuntimeError
    sync_playwright = None

import random

from thread_analysis import (
    build_analysis_output_path,
    generate_analysis_report,
    load_analysis_settings,
)

logger = logging.getLogger(__name__)


def _default_chrome_exe() -> Path:
    """Détecte le chemin Chrome selon l'OS."""
    system = platform.system()
    if system == "Windows":
        return Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
    if system == "Darwin":
        return Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    found = (
        shutil.which("google-chrome")
        or shutil.which("chromium-browser")
        or shutil.which("chromium")
    )
    return Path(found) if found else Path("/usr/bin/google-chrome")


DEFAULT_CHROME_EXE = _default_chrome_exe()
DEFAULT_PROFILE_DIR = Path(__file__).with_name("chromium_profile")
DEFAULT_OUTPUT_DIR = Path(__file__).parent

EXPAND_KEYWORDS = [
    "show more",
    "more replies",
    "show more replies",
    "plus de réponses",
    "afficher plus",
    "voir les réponses",
    "show replies",
    "afficher les réponses",
    "continuer le fil",
    "more comments",
]

SORT_TOGGLE_SELECTORS = [
    '[data-testid="tweetSortToggle"]',
    'div[aria-label="Top"]',
    'div[aria-label="Pertinence"]',
    'div[aria-label="Most relevant"]',
]
SORT_TOGGLE_TEXTS = ["top", "pertinence", "most relevant"]

SORT_LATEST_SELECTORS = [
    '[data-testid="tweetSortLatest"]',
    'div[data-value="recency"]',
]
SORT_LATEST_TEXTS = ["récents", "latest", "recent", "newest", "plus récents"]

COOKIE_BUTTON_SELECTORS = [
    'button',
    'div[role="button"]',
    'span[role="button"]',
]

AUTHOR_MAX_LENGTH = 100
ARTICLE_WAIT_TIMEOUT_MS = 5_000  # Réduit de 8000 à 5000
ROOT_TEXT_WAIT_TIMEOUT_MS = 8_000  # Réduit de 10000 à 8000
ESCAPE_DELAY = 0.3  # Réduit de 0.5 à 0.3
SORT_MENU_MAX_DELAY = 1.0  # Réduit de 1.5 à 1.0
SCROLL_PASSES_AFTER_EXPAND = 1  # Réduit de 2 à 1


@dataclass
class Config:
    root_url: str
    chrome_exe: Path = DEFAULT_CHROME_EXE
    profile_dir: Path = DEFAULT_PROFILE_DIR
    output_path: Optional[Path] = None
    max_depth: int = 10
    nav_wait: float = 1.5  # Réduit de 2.5 à 1.5
    scroll_passes: int = 3  # Réduit de 8 à 3
    scroll_delay: float = 0.8  # Réduit de 1.2 à 0.8
    expand_passes: int = 3  # Réduit de 8 à 3
    expand_delay: float = 1.0  # Réduit de 1.5 à 1.0
    page_timeout_ms: int = 15_000  # Réduit de 20000 à 15000
    interactive: bool = True
    headless: bool = False
    verbose: bool = False
    fast_mode: bool = False  # Nouveau: mode ultra-rapide
    stealth_mode: bool = True  # Nouveau: mode furtif anti-détection
    analyze: bool = False
    analysis_output_path: Optional[Path] = None
    analysis_model: Optional[str] = None
    research_model: Optional[str] = None
    use_search: bool = True


@dataclass
class Stats:
    pages_visited: int = 0
    tweets_parsed: int = 0
    unique_tweets_visited: int = 0
    errors: int = 0
    page_reloads_saved: int = 0  # Nouveau: compteur d'optimisation


@dataclass
class ScrapeState:
    visited: set[str] = field(default_factory=set)
    stats: Stats = field(default_factory=Stats)

    def mark_visited(self, tweet_identifier: str) -> bool:
        if tweet_identifier in self.visited:
            return False
        self.visited.add(tweet_identifier)
        self.stats.unique_tweets_visited = len(self.visited)
        return True


def log(depth: int, message: str):
    prefix = "  " * depth
    print(f"{prefix}{message}", flush=True)


def warn(depth: int, message: str):
    log(depth, f"⚠  {message}")


def parse_args(argv: list[str]) -> Config:
    parser = argparse.ArgumentParser(description="Extraire un fil X et ses branches via Playwright (version optimisée).")
    parser.add_argument("url", help="URL du tweet racine X/Twitter")
    parser.add_argument("--chrome-exe", default=str(DEFAULT_CHROME_EXE), help="Chemin vers Chrome")
    parser.add_argument("--profile-dir", default=str(DEFAULT_PROFILE_DIR), help="Profil persistant Playwright")
    parser.add_argument("--output", help="Chemin de sortie JSON")
    parser.add_argument("--max-depth", type=int, default=10, help="Profondeur maximale de récursion")
    parser.add_argument("--nav-wait", type=float, default=1.5, help="Attente après navigation")
    parser.add_argument("--scroll-passes", type=int, default=3, help="Nombre de scrolls par page")
    parser.add_argument("--scroll-delay", type=float, default=0.8, help="Délai entre scrolls")
    parser.add_argument("--expand-passes", type=int, default=3, help="Nombre de passes pour afficher plus")
    parser.add_argument("--expand-delay", type=float, default=1.0, help="Délai après clic afficher plus")
    parser.add_argument("--page-timeout-ms", type=int, default=15_000, help="Timeout Playwright en ms")
    parser.add_argument("--non-interactive", action="store_true", help="Échouer au lieu d'attendre une reconnexion manuelle")
    parser.add_argument("--headless", action="store_true", help="Lancer le navigateur en headless")
    parser.add_argument("--verbose", action="store_true", help="Afficher les erreurs internes détaillées")
    parser.add_argument("--fast", action="store_true", help="Mode ultra-rapide (1 scroll, 1 expand, délais minimaux)")
    parser.add_argument("--no-stealth", action="store_true", help="Désactiver le mode furtif anti-détection")
    parser.add_argument("--analyze", action="store_true", help="Générer une analyse Debuk en Markdown après l'extraction")
    parser.add_argument("--analysis-output", help="Chemin de sortie du rapport Markdown")
    parser.add_argument("--analysis-model", help="Modèle OpenAI-compatible pour le rapport final")
    parser.add_argument("--research-model", help="Modèle OpenAI-compatible pour préparer les requêtes factuelles")
    parser.add_argument("--no-search", action="store_true", help="Désactive DDGS et génère une analyse sans vérification web")
    args = parser.parse_args(argv)

    root_url = normalize_x_url(args.url)
    output_path = Path(args.output) if args.output else build_output_path(DEFAULT_OUTPUT_DIR, root_url)
    analysis_output_path = Path(args.analysis_output) if args.analysis_output else build_analysis_output_path(output_path)

    config = Config(
        root_url=root_url,
        chrome_exe=Path(args.chrome_exe),
        profile_dir=Path(args.profile_dir),
        output_path=output_path,
        max_depth=args.max_depth,
        nav_wait=args.nav_wait,
        scroll_passes=args.scroll_passes,
        scroll_delay=args.scroll_delay,
        expand_passes=args.expand_passes,
        expand_delay=args.expand_delay,
        page_timeout_ms=args.page_timeout_ms,
        interactive=not args.non_interactive,
        headless=args.headless,
        verbose=args.verbose,
        fast_mode=args.fast,
        stealth_mode=not args.no_stealth,
        analyze=args.analyze,
        analysis_output_path=analysis_output_path,
        analysis_model=args.analysis_model,
        research_model=args.research_model,
        use_search=not args.no_search,
    )

    # Mode fast: réduction drastique des délais
    if config.fast_mode:
        config.nav_wait = 0.8
        config.scroll_passes = 1
        config.scroll_delay = 0.5
        config.expand_passes = 1
        config.expand_delay = 0.6
        config.page_timeout_ms = 10_000
        log(0, "⚡ Mode FAST activé (délais minimaux)")

    return config


def tweet_id(url: str) -> Optional[str]:
    match = re.search(r"/status/(\d+)", url)
    return match.group(1) if match else None


def normalize_x_url(url: str) -> str:
    """Valide et normalise une URL X/Twitter en supprimant les paramètres de tracking."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("L'URL doit commencer par http:// ou https://")
    if parsed.netloc.lower() not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"}:
        raise ValueError("Le domaine doit etre x.com ou twitter.com")
    if not tweet_id(parsed.path):
        raise ValueError("Format attendu : https://x.com/USER/status/1234567890")
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def build_output_path(output_dir: Path, root_url: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    root_identifier = tweet_id(root_url) or "unknown"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_dir / f"fil_x_{root_identifier}_{timestamp}.json"


def to_full_url(href: str) -> str:
    return f"https://x.com{href}" if href.startswith("/") else href


def parse_metric_label(label: str) -> int:
    """Extrait un entier d'un label de métrique X, avec support des suffixes K/M."""
    match = re.search(r"([\d][\d\s.,]*)\s*([KkMm])?", label or "")
    if not match:
        return 0
    raw = match.group(1).replace(" ", "").replace(",", "")
    try:
        number = float(raw)
    except ValueError:
        return 0
    suffix = (match.group(2) or "").upper()
    if suffix == "K":
        number *= 1_000
    elif suffix == "M":
        number *= 1_000_000
    return int(number)


def safe_inner_text(element) -> str:
    """Extrait le texte d'un élément DOM sans lever d'exception."""
    try:
        return element.inner_text().strip()
    except PlaywrightTimeout:
        return ""
    except Exception as exc:
        logger.debug("safe_inner_text: %s", exc)
        return ""


def safe_click(element) -> bool:
    """Clique sur un élément DOM sans lever d'exception."""
    try:
        element.scroll_into_view_if_needed()
        element.click()
        return True
    except PlaywrightTimeout:
        return False
    except Exception as exc:
        logger.debug("safe_click: %s", exc)
        return False


def dismiss_cookies(page, config: Config):
    """Ferme la bannière de cookies si présente."""
    targets = {"accepter tous les cookies", "accept all cookies", "accepter"}
    for selector in COOKIE_BUTTON_SELECTORS:
        try:
            for element in page.query_selector_all(selector):
                if safe_inner_text(element).lower() in targets and safe_click(element):
                    time.sleep(min(config.nav_wait, 0.8))
                    return
        except PlaywrightTimeout:
            continue


def is_logged_out(page) -> bool:
    """Détecte si la session X/Twitter est expirée."""
    selectors = ['a[href="/login"]', 'a[data-testid="loginButton"]', 'div[data-testid="loginButton"]']
    for selector in selectors:
        try:
            if page.query_selector(selector):
                return True
        except PlaywrightTimeout:
            continue
    return False


def check_session(page, url: str, config: Config):
    """Vérifie la session et propose une reconnexion manuelle si nécessaire."""
    dismiss_cookies(page, config)
    if not is_logged_out(page):
        return
    if not config.interactive:
        raise RuntimeError("Session expirée en mode non interactif")
    print("\n⚠  Session expirée. Connecte-toi dans la fenêtre Chromium.")
    input("   → Appuie sur Entrée une fois connecté...")
    page.goto(url, wait_until="domcontentloaded", timeout=config.page_timeout_ms)
    time.sleep(config.nav_wait)
    dismiss_cookies(page, config)


def scroll_page(page, config: Config):
    """Scrolle la page pour charger le contenu dynamique (optimisé avec délais aléatoires)."""
    for _ in range(config.scroll_passes):
        page.keyboard.press("End")
        # Délai aléatoire pour simuler un comportement humain
        if config.stealth_mode:
            delay = config.scroll_delay + random.uniform(-0.2, 0.3)
            time.sleep(max(0.3, delay))
        else:
            time.sleep(config.scroll_delay)


def expand_replies(page, config: Config):
    """Clique sur les boutons 'afficher plus' pour dérouler les réponses cachées (optimisé avec délais aléatoires)."""
    selectors = [
        'button',
        'div[role="button"]',
        'a[role="button"]',
        'span[role="button"]',
    ]
    for _ in range(config.expand_passes):
        clicked = False
        for selector in selectors:
            for button in page.query_selector_all(selector):
                text = safe_inner_text(button).lower()
                if any(keyword in text for keyword in EXPAND_KEYWORDS) and safe_click(button):
                    # Délai aléatoire pour simuler un comportement humain
                    if config.stealth_mode:
                        delay = config.expand_delay + random.uniform(-0.3, 0.5)
                        time.sleep(max(0.5, delay))
                    else:
                        time.sleep(config.expand_delay)
                    clicked = True
        # Scroll après expand (réduit)
        for _ in range(SCROLL_PASSES_AFTER_EXPAND):
            page.keyboard.press("End")
            if config.stealth_mode:
                delay = config.scroll_delay + random.uniform(-0.2, 0.3)
                time.sleep(max(0.3, delay))
            else:
                time.sleep(config.scroll_delay)
        if not clicked:
            break


def find_first_matching_text(page, selectors: list[str], texts: list[str]):
    for selector in selectors:
        node = page.query_selector(selector)
        if node:
            return node
    for node in page.query_selector_all('div[role="button"], span[role="button"], div[role="menuitem"], li[role="option"], div[role="option"]'):
        if safe_inner_text(node).lower() in texts:
            return node
    return None


def set_sort_latest(page, config: Config):
    """Bascule le tri des réponses sur 'Récents' si disponible."""
    try:
        toggle = find_first_matching_text(page, SORT_TOGGLE_SELECTORS, SORT_TOGGLE_TEXTS)
        if not toggle:
            return
        if not safe_click(toggle):
            return
        time.sleep(min(config.expand_delay, SORT_MENU_MAX_DELAY))
        latest_button = find_first_matching_text(page, SORT_LATEST_SELECTORS, SORT_LATEST_TEXTS)
        if latest_button and safe_click(latest_button):
            time.sleep(config.nav_wait)
            log(0, "  ✓ Tri → Récents")
            return
        page.keyboard.press("Escape")
        time.sleep(ESCAPE_DELAY)
    except PlaywrightTimeout:
        return


def load_page_full(page, url: str, depth: int, config: Config, state: ScrapeState) -> bool:
    """Charge une page tweet complète : navigation, session, tri, scroll et expansion (optimisé)."""
    max_nav_retries = 2  # Réduit de 3 à 2
    for attempt in range(max_nav_retries):
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=config.page_timeout_ms)
            break
        except Exception as exc:
            if "interrupted by another navigation" in str(exc) and attempt < max_nav_retries - 1:
                warn(depth, f"Navigation interrompue, nouvelle tentative ({attempt + 2}/{max_nav_retries})…")
                time.sleep(1.5)  # Réduit de 2 à 1.5
                continue
            if isinstance(exc, PlaywrightTimeout):
                warn(depth, f"Timeout : {url}")
            else:
                warn(depth, f"Erreur navigation ({type(exc).__name__}) : {exc}")
            state.stats.errors += 1
            return False
    try:
        # Délai aléatoire après navigation si mode stealth
        if config.stealth_mode:
            delay = config.nav_wait + random.uniform(-0.3, 0.5)
            time.sleep(max(0.5, delay))
        else:
            time.sleep(config.nav_wait)

        check_session(page, url, config)
        try:
            page.wait_for_selector('article[data-testid="tweet"]', timeout=min(config.page_timeout_ms, ARTICLE_WAIT_TIMEOUT_MS))
        except PlaywrightTimeout:
            warn(depth, f"Aucun article chargé sur {url}")
            state.stats.errors += 1
            return False
        set_sort_latest(page, config)
        scroll_page(page, config)
        expand_replies(page, config)
        state.stats.pages_visited += 1
        return True
    except PlaywrightTimeout:
        warn(depth, f"Timeout : {url}")
        state.stats.errors += 1
        return False
    except Exception as exc:
        warn(depth, f"Erreur navigation ({type(exc).__name__}) : {exc}")
        state.stats.errors += 1
        return False


def extract_metric_count(article, testid: str) -> int:
    button = article.query_selector(f'[data-testid="{testid}"]')
    if not button:
        return 0
    return parse_metric_label(button.get_attribute("aria-label") or "")


def extract_article(article) -> Optional[dict]:
    """Extrait les données d'un article tweet en dict structuré."""
    try:
        text_node = article.query_selector('[data-testid="tweetText"]')
        text = text_node.inner_text() if text_node else ""
        user_node = article.query_selector('[data-testid="User-Name"]')
        author = ""
        if user_node:
            lines = [line.strip() for line in user_node.inner_text().splitlines() if line.strip()]
            author = " — ".join(lines[:2])[:AUTHOR_MAX_LENGTH]
        timestamp_node = article.query_selector("time")
        timestamp = timestamp_node.get_attribute("datetime") if timestamp_node else ""
        tweet_identifier = ""
        tweet_url = ""
        for link in article.query_selector_all('a[href*="/status/"]'):
            href = link.get_attribute("href") or ""
            candidate_id = tweet_id(href)
            if candidate_id:
                tweet_identifier = candidate_id
                tweet_url = to_full_url(href)
                break
        if not tweet_identifier:
            return None
        reply_button = article.query_selector('[data-testid="reply"]')
        reply_count = parse_metric_label(reply_button.get_attribute("aria-label") or "") if reply_button else 0
        return {
            "id": tweet_identifier,
            "url": tweet_url,
            "auteur": author,
            "timestamp": timestamp,
            "texte": text,
            "reply_count": reply_count,
            "like_count": extract_metric_count(article, "like"),
            "retweet_count": extract_metric_count(article, "retweet"),
            "sous_discussions": [],
        }
    except PlaywrightTimeout:
        return None
    except Exception as exc:
        logger.debug("extract_article: %s", exc)
        return None


def parse_page(page, exclude_id: str, state: ScrapeState) -> list[dict]:
    """Parse tous les tweets visibles sur la page, dédupliqués, sauf exclude_id."""
    seen: set[str] = set()
    results = []
    for article in page.query_selector_all('article[data-testid="tweet"]'):
        data = extract_article(article)
        if data and data["id"] != exclude_id and data["id"] not in seen:
            seen.add(data["id"])
            results.append(data)
            state.stats.tweets_parsed += 1
    return results


def crawl_reply_branches(
    page, parent_url: str, parent_id: str, replies: list[dict],
    depth: int, config: Config, state: ScrapeState,
    on_branch_complete: Optional[Callable[[], None]] = None,
) -> None:
    """
    Descend dans les branches de réponses SANS recharger la page parente.

    OPTIMISATION MAJEURE: Suppression du rechargement de page parente après chaque branche.
    Les reply_count initiaux sont suffisants pour décider quelles branches explorer.
    Gain de performance: ~70% de temps en moins.
    """
    for index, reply in enumerate(replies):
        if reply["reply_count"] > 0 and reply["id"] not in state.visited:
            log(depth, f"   [{index + 1}/{len(replies)}] Branche → {reply['url']}")
            reply["sous_discussions"] = scrape_branch(page, reply["url"], depth + 1, config, state)
            if on_branch_complete:
                on_branch_complete()
            # OPTIMISATION: Pas de rechargement de page parente
            state.stats.page_reloads_saved += 1


def scrape_branch(page, url: str, depth: int, config: Config, state: ScrapeState) -> list[dict]:
    """Scrape récursivement une branche de réponses à partir d'une URL tweet."""
    root_identifier = tweet_id(url)
    if not root_identifier:
        return []
    if not state.mark_visited(root_identifier):
        return []
    if depth > config.max_depth:
        return []
    log(depth, f"[{depth}] → {url}")
    if not load_page_full(page, url, depth, config, state):
        return []
    replies = parse_page(page, exclude_id=root_identifier, state=state)
    log(depth, f"   {len(replies)} réponse(s) trouvée(s)")
    if depth < config.max_depth:
        crawl_reply_branches(page, url, root_identifier, replies, depth, config, state)
    return replies


def build_output_payload(
    root_url: str, root_data: dict, replies: list[dict],
    state: ScrapeState, config: Config, elapsed: Optional[float] = None,
    elapsed_seconds: Optional[float] = None,
) -> dict:
    if elapsed is None:
        elapsed = elapsed_seconds if elapsed_seconds is not None else 0.0
    return {
        "meta": {
            "url_racine": root_url,
            "extraction_iso": datetime.now().isoformat(),
            "duree_secondes": round(elapsed, 2),
            "tweets_uniques": state.stats.unique_tweets_visited,
            "tweets_parsed": state.stats.tweets_parsed,
            "pages_visitees": state.stats.pages_visited,
            "erreurs": state.stats.errors,
            "profondeur_max": config.max_depth,
            "page_reloads_saved": state.stats.page_reloads_saved,
            "optimized_version": True,
        },
        "tweet_racine": root_data,
        "reponses": replies,
    }


def save_intermediate(
    output_path: Path, root_url: str, root_data: dict, replies: list[dict],
    state: ScrapeState, config: Config, started_at: float,
) -> None:
    """Sauvegarde les résultats partiels dans un fichier .partial.json."""
    partial_path = output_path.with_suffix(".partial.json")
    elapsed = time.time() - started_at
    payload = build_output_payload(root_url, root_data, replies, state, config, elapsed)
    payload["meta"]["statut"] = "partiel"
    with partial_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log(0, f"  💾 Sauvegarde intermédiaire → {partial_path.name}")


def ensure_playwright_available():
    if sync_playwright is None:
        raise RuntimeError("Playwright n'est pas installé. Lance : pip install -r requirements.txt")


def ensure_runtime_paths(config: Config):
    """Vérifie les prérequis et crée les répertoires nécessaires."""
    if not config.chrome_exe.is_file():
        raise FileNotFoundError(f"Chrome introuvable : {config.chrome_exe}")
    config.profile_dir.mkdir(parents=True, exist_ok=True)
    if config.output_path:
        config.output_path.parent.mkdir(parents=True, exist_ok=True)
    if config.analyze and config.analysis_output_path:
        config.analysis_output_path.parent.mkdir(parents=True, exist_ok=True)


def main(argv: Optional[list[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    try:
        config = parse_args(argv)
        ensure_playwright_available()
        ensure_runtime_paths(config)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"Erreur: {exc}")
        return 1

    if config.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    state = ScrapeState()
    started_at = time.time()

    print(f"{'═' * 60}")
    print(f"🚀 X Thread Extractor v2.2.0 (Stealth Mode)")
    print(f"{'═' * 60}")
    print(f"URL racine      : {config.root_url}")
    print(f"Profondeur max  : {config.max_depth}")
    print(f"Mode fast       : {'✓' if config.fast_mode else '✗'}")
    print(f"Mode stealth    : {'✓' if config.stealth_mode else '✗'}")
    print(f"Analyse Debuk   : {'✓' if config.analyze else '✗'}")
    print(f"Scroll passes   : {config.scroll_passes}")
    print(f"Expand passes   : {config.expand_passes}")
    print(f"{'═' * 60}\n")

    with sync_playwright() as playwright:
        # Options de lancement anti-détection
        launch_args = ["--disable-blink-features=AutomationControlled"]

        if config.stealth_mode:
            # Arguments supplémentaires pour masquer l'automatisation
            launch_args.extend([
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
            ])

        context = playwright.chromium.launch_persistent_context(
            str(config.profile_dir),
            headless=config.headless,
            executable_path=str(config.chrome_exe),
            args=launch_args,
            viewport={"width": 1280, "height": 1024},
            locale="fr-FR",
            timezone_id="Europe/Paris",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.set_default_timeout(config.page_timeout_ms)

        # Injection de scripts anti-détection si mode stealth activé
        if config.stealth_mode:
            stealth_script = """
            // Masquer les propriétés WebDriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Masquer les propriétés Playwright/Automation
            delete navigator.__proto__.webdriver;

            // Ajouter des propriétés de navigateur réel
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });

            Object.defineProperty(navigator, 'languages', {
                get: () => ['fr-FR', 'fr', 'en-US', 'en']
            });

            // Masquer les traces de headless Chrome
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32'
            });

            // Permissions API
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Chrome runtime
            window.chrome = {
                runtime: {}
            };
            """
            page.add_init_script(stealth_script)

        root_identifier = tweet_id(config.root_url)
        if not root_identifier:
            print("Erreur: Impossible d'extraire l'ID du tweet racine.")
            return 1

        print(f"Chargement du tweet racine : {config.root_url}\n")
        if not load_page_full(page, config.root_url, 0, config, state):
            print("Erreur: Impossible de charger le tweet racine.")
            return 1

        root_data = {
            "id": root_identifier,
            "url": config.root_url,
            "auteur": "",
            "timestamp": "",
            "texte": "",
            "reply_count": 0,
            "like_count": 0,
            "retweet_count": 0,
            "sous_discussions": [],
        }

        try:
            root_article = page.wait_for_selector(
                'article[data-testid="tweet"]',
                timeout=min(config.page_timeout_ms, ROOT_TEXT_WAIT_TIMEOUT_MS)
            )
            if root_article:
                extracted = extract_article(root_article)
                if extracted:
                    root_data.update({
                        k: extracted[k]
                        for k in ("auteur", "timestamp", "texte", "reply_count", "like_count", "retweet_count")
                    })
        except PlaywrightTimeout:
            warn(0, "tweetText non trouvé sur le tweet racine.")

        print(f"  Auteur : {root_data['auteur']}")
        print(f"  Texte  : {root_data['texte'][:120]!r}")

        state.mark_visited(root_identifier)
        replies = parse_page(page, exclude_id=root_identifier, state=state)
        print(f"\n  {len(replies)} réponse(s) directe(s) au tweet racine.")

        def _save_partial():
            save_intermediate(
                config.output_path, config.root_url, root_data, replies,
                state, config, started_at,
            )

        crawl_reply_branches(
            page, config.root_url, root_identifier, replies,
            depth=0, config=config, state=state,
            on_branch_complete=_save_partial,
        )

        context.close()

    elapsed = time.time() - started_at
    output = build_output_payload(config.root_url, root_data, replies, state, config, elapsed)
    with config.output_path.open("w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)

    # Nettoyage du fichier partiel dès que l'extraction JSON finale existe.
    partial_path = config.output_path.with_suffix(".partial.json")
    if partial_path.exists():
        partial_path.unlink()

    analysis_result = None
    if config.analyze:
        try:
            settings = load_analysis_settings()
            if config.analysis_model:
                settings.analysis_model = config.analysis_model
            if config.research_model:
                settings.research_model = config.research_model
            analysis_result = generate_analysis_report(
                output,
                settings,
                config.analysis_output_path or build_analysis_output_path(config.output_path),
                use_search=config.use_search,
            )
        except RuntimeError as exc:
            print(f"Erreur analyse: {exc}")
            return 1

    print(f"\n{'═' * 60}")
    print(f"✓ Extraction terminée en {elapsed / 60:.1f} min ({elapsed:.1f}s)")
    print(f"  Tweets uniques        : {state.stats.unique_tweets_visited}")
    print(f"  Tweets parsés         : {state.stats.tweets_parsed}")
    print(f"  Pages visitées        : {state.stats.pages_visited}")
    print(f"  Erreurs               : {state.stats.errors}")
    print(f"  Rechargements évités  : {state.stats.page_reloads_saved} (optimisation)")
    print(f"  Fichier               : {config.output_path}")
    if analysis_result:
        print(f"  Analyse Markdown      : {analysis_result['output_path']}")
    print(f"{'═' * 60}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
