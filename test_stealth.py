#!/usr/bin/env python3
"""
Script de test pour vérifier l'efficacité du mode stealth.
Visite des sites de détection de bots et affiche les résultats.
"""

import sys
import unittest
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ModuleNotFoundError:
    sync_playwright = None


def test_stealth_mode():
    """Teste le mode stealth sur des sites de détection de bots."""

    print("=" * 70)
    print("🕵️  TEST DU MODE STEALTH - Détection de Bot")
    print("=" * 70)
    print()

    profile_dir = Path(__file__).with_name("chromium_profile")
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        # Configuration stealth
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--disable-site-isolation-trials",
        ]

        context = playwright.chromium.launch_persistent_context(
            str(profile_dir),
            headless=False,
            args=launch_args,
            viewport={"width": 1280, "height": 1024},
            locale="fr-FR",
            timezone_id="Europe/Paris",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )

        page = context.pages[0] if context.pages else context.new_page()

        # Injection du script anti-détection
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

        # Tests de détection
        tests = [
            {
                "name": "Sannysoft Bot Detector",
                "url": "https://bot.sannysoft.com/",
                "description": "Teste les propriétés WebDriver et autres indicateurs"
            },
            {
                "name": "Intoli WebDriver Test",
                "url": "https://intoli.com/blog/not-possible-to-block-chrome-headless/chrome-headless-test.html",
                "description": "Teste spécifiquement la détection de headless Chrome"
            },
            {
                "name": "BrowserLeaks WebRTC",
                "url": "https://browserleaks.com/webrtc",
                "description": "Teste les fuites WebRTC et l'empreinte réseau"
            }
        ]

        print("📋 Sites de test à visiter:")
        print()
        for i, test in enumerate(tests, 1):
            print(f"{i}. {test['name']}")
            print(f"   {test['description']}")
            print(f"   URL: {test['url']}")
            print()

        print("=" * 70)
        print()
        print("🌐 Ouverture du premier site de test...")
        print()

        # Ouvrir le premier site
        page.goto(tests[0]["url"], wait_until="domcontentloaded")

        print("✅ Navigateur ouvert avec le mode stealth activé")
        print()
        print("📊 Vérifications à faire manuellement:")
        print("   1. navigator.webdriver doit être 'undefined' (pas 'true')")
        print("   2. Les lignes rouges indiquent une détection")
        print("   3. Les lignes vertes indiquent que le test est passé")
        print()
        print("💡 Pour tester les autres sites, navigue manuellement vers:")
        for test in tests[1:]:
            print(f"   - {test['url']}")
        print()
        print("⏸️  Appuie sur Entrée pour fermer le navigateur...")

        input()

        context.close()

    print()
    print("=" * 70)
    print("✓ Test terminé")
    print("=" * 70)


class StealthModeTest(unittest.TestCase):
    @unittest.skipIf(sync_playwright is None, "Playwright n'est pas installé")
    def test_stealth_mode_manual(self):
        test_stealth_mode()


if __name__ == "__main__":
    if sync_playwright is None:
        print("Erreur: Playwright n'est pas installé.")
        print("Lance: pip install playwright && playwright install chromium")
        raise SystemExit(1)
    test_stealth_mode()
