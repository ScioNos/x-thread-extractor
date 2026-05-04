import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from x_thread_extractor import (
    Config,
    ScrapeState,
    build_output_path,
    build_output_payload,
    normalize_x_url,
    parse_metric_label,
    to_full_url,
    tweet_id,
)


class UrlHelpersTest(unittest.TestCase):
    def test_tweet_id_extracts_status_identifier(self):
        self.assertEqual(tweet_id("https://x.com/user/status/1234567890"), "1234567890")

    def test_tweet_id_returns_none_without_status(self):
        self.assertIsNone(tweet_id("https://x.com/user/likes"))

    def test_normalize_x_url_accepts_x_and_twitter_domains(self):
        self.assertEqual(
            normalize_x_url("https://x.com/user/status/1234567890"),
            "https://x.com/user/status/1234567890",
        )
        self.assertEqual(
            normalize_x_url("https://twitter.com/user/status/1234567890"),
            "https://twitter.com/user/status/1234567890",
        )

    def test_normalize_x_url_rejects_invalid_domain(self):
        with self.assertRaises(ValueError):
            normalize_x_url("https://example.com/user/status/1234567890")

    def test_normalize_x_url_rejects_invalid_status_path(self):
        with self.assertRaises(ValueError):
            normalize_x_url("https://x.com/user/1234567890")

    def test_normalize_x_url_strips_query_params(self):
        result = normalize_x_url("https://x.com/user/status/123?s=20&t=abc")
        self.assertEqual(result, "https://x.com/user/status/123")

    def test_normalize_x_url_strips_fragment(self):
        result = normalize_x_url("https://x.com/user/status/123#section")
        self.assertEqual(result, "https://x.com/user/status/123")

    def test_normalize_x_url_rejects_non_http_scheme(self):
        with self.assertRaises(ValueError):
            normalize_x_url("ftp://x.com/user/status/123")

    def test_to_full_url_prepends_domain_for_relative(self):
        self.assertEqual(to_full_url("/user/status/123"), "https://x.com/user/status/123")

    def test_to_full_url_keeps_absolute_url(self):
        self.assertEqual(
            to_full_url("https://x.com/user/status/123"),
            "https://x.com/user/status/123",
        )


class MetricsHelpersTest(unittest.TestCase):
    def test_parse_metric_label_reads_space_separated_digits(self):
        self.assertEqual(parse_metric_label("1 234 réponses"), 1234)

    def test_parse_metric_label_returns_zero_without_digits(self):
        self.assertEqual(parse_metric_label("aucune réponse"), 0)

    def test_parse_metric_label_returns_zero_for_empty(self):
        self.assertEqual(parse_metric_label(""), 0)

    def test_parse_metric_label_returns_zero_for_none(self):
        self.assertEqual(parse_metric_label(None), 0)

    def test_parse_metric_label_handles_k_suffix(self):
        self.assertEqual(parse_metric_label("1.2K replies"), 1200)

    def test_parse_metric_label_handles_uppercase_k(self):
        self.assertEqual(parse_metric_label("5K likes"), 5000)

    def test_parse_metric_label_handles_m_suffix(self):
        self.assertEqual(parse_metric_label("3.5M likes"), 3500000)

    def test_parse_metric_label_handles_plain_number(self):
        self.assertEqual(parse_metric_label("42 replies"), 42)

    def test_parse_metric_label_handles_comma_separator(self):
        self.assertEqual(parse_metric_label("1,234 replies"), 1234)


class ScrapeStateTest(unittest.TestCase):
    def test_mark_visited_returns_true_first_time(self):
        state = ScrapeState()
        self.assertTrue(state.mark_visited("123"))

    def test_mark_visited_returns_false_second_time(self):
        state = ScrapeState()
        state.mark_visited("123")
        self.assertFalse(state.mark_visited("123"))

    def test_mark_visited_updates_stats(self):
        state = ScrapeState()
        state.mark_visited("111")
        state.mark_visited("222")
        self.assertEqual(state.stats.unique_tweets_visited, 2)

    def test_mark_visited_idempotent_stats(self):
        state = ScrapeState()
        state.mark_visited("111")
        state.mark_visited("111")
        self.assertEqual(state.stats.unique_tweets_visited, 1)


class OutputHelpersTest(unittest.TestCase):
    def test_build_output_path_includes_tweet_id_and_json_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = build_output_path(Path(tmp), "https://x.com/user/status/987654321")
            self.assertTrue(path.name.startswith("fil_x_987654321_"))
            self.assertEqual(path.suffix, ".json")
            self.assertEqual(path.parent, Path(tmp))

    def test_build_output_payload_exposes_metrics(self):
        state = ScrapeState()
        state.mark_visited("111")
        state.stats.tweets_parsed = 4
        state.stats.pages_visited = 2
        state.stats.errors = 1
        payload = build_output_payload(
            "https://x.com/user/status/111",
            {"id": "111", "texte": "root"},
            [{"id": "222"}],
            state,
            Config(root_url="https://x.com/user/status/111"),
            elapsed_seconds=12,
        )
        self.assertEqual(payload["meta"]["tweets_uniques"], 1)
        self.assertEqual(payload["meta"]["tweets_parsed"], 4)
        self.assertEqual(payload["meta"]["pages_visitees"], 2)
        self.assertEqual(payload["meta"]["erreurs"], 1)
        self.assertEqual(payload["meta"]["duree_secondes"], 12)

    def test_build_output_payload_contains_root_and_replies(self):
        state = ScrapeState()
        root = {"id": "111", "texte": "root"}
        replies = [{"id": "222"}, {"id": "333"}]
        payload = build_output_payload(
            "https://x.com/user/status/111",
            root,
            replies,
            state,
            Config(root_url="https://x.com/user/status/111"),
            elapsed_seconds=5,
        )
        self.assertEqual(payload["tweet_racine"], root)
        self.assertEqual(len(payload["reponses"]), 2)


class ParseArgsTest(unittest.TestCase):
    def test_default_max_depth(self):
        from x_thread_extractor import parse_args
        config = parse_args(["https://x.com/user/status/123"])
        self.assertEqual(config.max_depth, 10)

    def test_custom_max_depth(self):
        from x_thread_extractor import parse_args
        config = parse_args(["https://x.com/user/status/123", "--max-depth", "3"])
        self.assertEqual(config.max_depth, 3)

    def test_non_interactive_flag(self):
        from x_thread_extractor import parse_args
        config = parse_args(["https://x.com/user/status/123", "--non-interactive"])
        self.assertFalse(config.interactive)

    def test_verbose_flag(self):
        from x_thread_extractor import parse_args
        config = parse_args(["https://x.com/user/status/123", "--verbose"])
        self.assertTrue(config.verbose)

    def test_headless_flag(self):
        from x_thread_extractor import parse_args
        config = parse_args(["https://x.com/user/status/123", "--headless"])
        self.assertTrue(config.headless)


if __name__ == "__main__":
    unittest.main()
