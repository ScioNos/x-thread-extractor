import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from thread_analysis import (
    DEFAULT_DEBUNK_SYSTEM_PROMPT,
    build_analysis_output_path,
    build_fallback_queries,
    build_thread_context,
    extract_json_payload,
    load_analysis_settings,
)


class AnalysisSettingsTest(unittest.TestCase):
    def test_load_analysis_settings_uses_routerlab_defaults(self):
        settings = load_analysis_settings({})
        self.assertEqual(settings.base_url, "https://routerlab.ch/v1")
        self.assertEqual(settings.search_region, "fr-fr")
        self.assertEqual(settings.search_max_results, 5)
        self.assertEqual(settings.system_prompt, DEFAULT_DEBUNK_SYSTEM_PROMPT)

    def test_load_analysis_settings_supports_model_overrides(self):
        settings = load_analysis_settings(
            {
                "OPENAI_API_KEY": "secret",
                "OPENAI_BASE_URL": "https://example.test/v1/",
                "OPENAI_ANALYSIS_MODEL": "analysis-model",
                "OPENAI_RESEARCH_MODEL": "research-model",
                "DEBUNK_FACT_CHECK_QUERIES": "6",
            }
        )
        self.assertEqual(settings.api_key, "secret")
        self.assertEqual(settings.base_url, "https://example.test/v1")
        self.assertEqual(settings.analysis_model, "analysis-model")
        self.assertEqual(settings.research_model, "research-model")
        self.assertEqual(settings.fact_check_queries, 6)


class AnalysisHelpersTest(unittest.TestCase):
    def test_build_analysis_output_path_switches_extension(self):
        path = build_analysis_output_path(Path("fil_x_123.json"))
        self.assertEqual(path, Path("fil_x_123.analysis.md"))

    def test_extract_json_payload_reads_embedded_json(self):
        payload = extract_json_payload('Réponse:\n{"queries":[{"claim":"A","query":"B"}]}')
        self.assertEqual(payload["queries"][0]["claim"], "A")

    def test_build_thread_context_contains_root_and_reply(self):
        payload = {
            "meta": {"url_racine": "https://x.com/user/status/1"},
            "tweet_racine": {"id": "1", "auteur": "Alice", "timestamp": "2026-05-01", "texte": "Tweet racine"},
            "reponses": [{"id": "2", "auteur": "Bob", "timestamp": "2026-05-01", "texte": "Réponse"}],
        }
        context = build_thread_context(payload)
        self.assertIn("Tweet racine", context)
        self.assertIn("Réponse", context)

    def test_build_fallback_queries_uses_root_text(self):
        queries = build_fallback_queries({"tweet_racine": {"texte": "Le vaccin X contient Y"}})
        self.assertEqual(len(queries), 1)
        self.assertIn("vaccin", queries[0]["query"])


if __name__ == "__main__":
    unittest.main()
