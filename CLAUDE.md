# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
pip install -r requirements.txt
playwright install chromium
```

```bash
python x_thread_extractor.py https://x.com/USER/status/TWEET_ID
python x_thread_extractor.py <url> --max-depth 3 --output sortie.json
python x_thread_extractor.py <url> --non-interactive
python x_thread_extractor.py <url> --profile-dir ./chromium_profile
python x_thread_extractor.py <url> --chrome-exe "C:/Program Files/Google/Chrome/Application/chrome.exe"
```

```bash
python -m unittest discover -s tests
python -m unittest tests.test_extracteur_fil_x
```

## Architecture

- `x_thread_extractor.py` is the full application entry point and orchestration layer. `main()` parses CLI args, validates runtime dependencies, launches Playwright with a persistent Chromium context, extracts the root tweet plus nested replies, then writes the JSON payload.
- Runtime configuration and traversal state are kept in the `Config`, `Stats`, and `ScrapeState` dataclasses. `ScrapeState.visited` is the guard against revisiting the same tweet branch during recursion.
- URL and output preparation live in small helpers such as `normalize_x_url()`, `tweet_id()`, and `build_output_path()`. These are also the main units covered by tests.
- Page loading follows a fixed sequence: `load_page_full()` opens the tweet page, checks the authenticated session, switches sorting to latest when possible, scrolls, and expands hidden replies before parsing.
- Tweet extraction is split between `extract_article()` and `parse_page()`. `extract_article()` reads a single tweet card into the JSON shape, while `parse_page()` deduplicates tweet cards found on the current page and updates traversal stats.
- Recursive branch traversal happens in `scrape_branch()`. It only descends into replies whose `reply_count` is greater than zero, and after each nested branch it reloads the parent page to refresh the remaining reply state before continuing.
- Final output assembly is centralized in `build_output_payload()`, which combines extraction metadata, root tweet information, and the nested reply tree.

## Project-specific constraints

- The script expects a local Chrome installation and a persistent authenticated browser profile at `chromium_profile`. `ensure_runtime_paths()` fails fast if either the Chrome executable or the profile directory is missing.
- The automation depends on X/Twitter DOM structure and visible labels such as reply-expansion text and sort controls, so selector breakage is a normal failure mode when the site UI changes.
- `--non-interactive` is intended for runs where the saved session must already be valid; otherwise the script exits instead of waiting for manual re-login.
- Current tests only cover pure helpers and payload construction. They do not exercise Playwright navigation or live X/Twitter behavior, so browser-facing changes should be validated manually.
