# Changelog

All notable changes to X Thread Extractor will be documented in this file.

## [2.2.1] - 2026-05-04

### 🛡️ Robustness, Guardrails & Portable Tests

#### Fixed
- Fixed Linux/macOS portability issue in unit tests caused by the hardcoded `C:\tmp` temporary directory.
- Fixed `test_stealth.py` so missing Playwright no longer breaks unittest discovery at import time.
- Added clean unittest skip behavior for the stealth test when Playwright is unavailable.

#### Added
- Added global crawl guardrails to avoid uncontrolled extraction runs:
  - `--max-pages` with default `200`
  - `--max-tweets` with default `1000`
  - `--crawl-timeout-s` with default `1800`
- Added extraction metadata for guarded exits:
  - `stopped_by_limit`
  - `stop_reason`

#### Improved
- Improved Debuk analysis robustness with retry/fallback behavior around LLM calls.
- Improved fact-check query planning fallback when the research model returns invalid or unusable JSON.
- Improved DDGS failure handling so analysis can continue in degraded mode when search is unavailable.
- Hardened `.gitignore` for sensitive and generated files: `.a0proj/secrets.env`, `.a0proj/variables.env`, `*.partial.json`, `*.analysis.md`.

#### Testing
- `python -m py_compile x_thread_extractor.py thread_analysis.py test_stealth.py tests/*.py` passes.
- `python -m unittest discover -s tests -v` passes with 37 tests.
- `python -m unittest test_stealth -v` now reports a clean skip when Playwright is not installed.

## [2.2.0] - 2026-05-01

### 🤖 Debuk Analysis Mode

#### Added
- Optional `--analyze` mode to generate a Markdown debate analysis after thread extraction
- `.env`-driven configuration for any OpenAI-compatible API
- Support for configurable `OPENAI_BASE_URL`, `OPENAI_API_KEY`, `OPENAI_ANALYSIS_MODEL`, and `OPENAI_RESEARCH_MODEL`
- New `thread_analysis.py` module for LLM orchestration, fact-check query planning, and report generation
- `ddgs` integration for web search and source extraction before final analysis
- `.env.example` with RouterLab-compatible defaults
- CLI flags:
  - `--analyze`
  - `--analysis-output`
  - `--analysis-model`
  - `--research-model`
  - `--no-search`

#### Changed
- `build_output_payload()` now accepts `elapsed_seconds` as a backward-compatible keyword alias for tests
- README updated with `.env` setup and analysis workflow
- Requirements now include `ddgs` and `python-dotenv`
- Documentation now recommends reproducing older behavior with CLI flags instead of a duplicate backup script

#### Output
- JSON extraction output remains unchanged
- New optional Markdown report output: `*.analysis.md`

#### Removed
- `x_thread_extractor_backup.py`, replaced by documented runtime flags and Git history

## [2.1.0] - 2026-05-01

### 🥷 Anti-Detection & Stealth Mode

#### Major Changes
- **Stealth mode enabled by default**: Advanced anti-detection techniques to bypass bot detection systems
- **WebDriver property masking**: Hides automation traces from X/Twitter's detection algorithms
- **Randomized human-like delays**: Variable timing to simulate natural user behavior
- **Realistic browser fingerprint**: Mimics genuine Chrome browser characteristics

#### Stealth Features
- **WebDriver masking**: `navigator.webdriver` set to `undefined` instead of `true`
- **Browser properties simulation**:
  - `navigator.plugins`: Simulated plugin array
  - `navigator.languages`: `['fr-FR', 'fr', 'en-US', 'en']`
  - `navigator.platform`: `'Win32'`
  - `window.chrome.runtime`: Chrome native object injection
- **Realistic User-Agent**: Chrome 131.0.0.0 on Windows 10
- **Locale & Timezone**: `fr-FR` locale with `Europe/Paris` timezone
- **Permissions API patching**: Simulates native browser permissions behavior

#### Randomized Delays (Human Behavior Simulation)
- **Scroll delays**: ±0.2-0.3s variation (e.g., 0.6s-1.1s instead of fixed 0.8s)
- **Expand delays**: ±0.3-0.5s variation
- **Navigation delays**: ±0.3-0.5s variation
- Only active when stealth mode is enabled

#### Chrome Arguments
- `--disable-blink-features=AutomationControlled`
- `--disable-dev-shm-usage`
- `--disable-web-security`
- `--disable-features=IsolateOrigins,site-per-process`
- `--disable-site-isolation-trials`

### Added
- `--no-stealth` flag to disable stealth mode (not recommended)
- `stealth_mode: bool = True` parameter in Config dataclass
- `test_stealth.py`: Testing script for bot detection sites
- `STEALTH_FEATURES.md`: Comprehensive stealth mode documentation
- `random` module import for delay randomization

### Changed
- Default behavior now includes stealth mode (can be disabled with `--no-stealth`)
- All delays now have random variations when stealth mode is active
- Browser context includes realistic locale, timezone, and user-agent
- Page initialization includes anti-detection script injection

### Documentation
- Updated `README.md` with stealth mode section
- Added comparison table: Playwright standard vs Stealth mode
- Added legal disclaimer about X/Twitter ToS
- Added DrissionPage migration recommendation if blocking persists

### Technical Details
- Stealth script injected via `page.add_init_script()` on every page load
- Random delays use `random.uniform()` with configurable ranges
- Stealth mode check in `scroll_page()`, `expand_replies()`, and `load_page_full()`
- Browser context configuration includes `locale`, `timezone_id`, and `user_agent` parameters

### Testing
```bash
# Test stealth mode on bot detection sites
python test_stealth.py

# Normal usage (stealth enabled by default)
python x_thread_extractor.py <url>

# Disable stealth if needed
python x_thread_extractor.py <url> --no-stealth
```

### Limitations
- Stealth mode reduces detectability but doesn't guarantee 100% invisibility
- Advanced ML-based detection systems may still identify automation
- Mouse movement simulation not implemented (Playwright limitation)
- Canvas fingerprinting not randomized in this version

### Migration to DrissionPage
If you still encounter frequent blocking despite stealth mode, consider migrating to DrissionPage which uses Chrome DevTools Protocol (CDP) instead of WebDriver for even better stealth capabilities.

---

## [2.0.0] - 2026-05-01

### 🚀 Performance Optimizations (70-85% faster)

#### Major Changes
- **Removed parent page reloading**: Eliminated systematic page reload after each branch exploration, resulting in ~70% performance improvement
- **Reduced scroll/expand passes**: Decreased from 8 to 3 passes by default (configurable)
- **Optimized delays**: Reduced navigation waits and interaction delays across the board
- **Added fast mode**: New `--fast` flag for ultra-rapid extraction with minimal delays

#### Detailed Improvements
- `nav_wait`: 2.5s → 1.5s (0.8s in fast mode)
- `scroll_passes`: 8 → 3 (1 in fast mode)
- `scroll_delay`: 1.2s → 0.8s (0.5s in fast mode)
- `expand_passes`: 8 → 3 (1 in fast mode)
- `expand_delay`: 1.5s → 1.0s (0.6s in fast mode)
- `page_timeout`: 20s → 15s (10s in fast mode)
- `max_nav_retries`: 3 → 2
- `ARTICLE_WAIT_TIMEOUT_MS`: 8000 → 5000
- `ROOT_TEXT_WAIT_TIMEOUT_MS`: 10000 → 8000
- `ESCAPE_DELAY`: 0.5s → 0.3s
- `SORT_MENU_MAX_DELAY`: 1.5s → 1.0s
- `SCROLL_PASSES_AFTER_EXPAND`: 2 → 1

### Added
- `--fast` flag for ultra-rapid extraction mode
- `page_reloads_saved` metric in output JSON and statistics
- `optimized_version: true` flag in output metadata
- Enhanced progress display with optimization metrics
- Execution time now shown in both minutes and seconds

### Changed
- **Breaking**: Default behavior is now optimized (faster but may miss some deeply nested replies)
- Output JSON now includes `page_reloads_saved` and `optimized_version` fields in metadata
- Improved console output with clearer performance metrics

### Technical Details
- Removed `crawl_reply_branches()` page reload logic (lines 477-484 in old version)
- Removed redundant `parse_page()` call after branch completion
- Removed `fresh_map` reply count update mechanism
- Optimized `load_page_full()` retry logic

### Migration Guide
If you need the old behavior (slower but more exhaustive):
```bash
python x_thread_extractor.py URL \
  --nav-wait 2.5 \
  --scroll-passes 8 \
  --scroll-delay 1.2 \
  --expand-passes 8 \
  --expand-delay 1.5 \
  --page-timeout-ms 20000
```

### Performance Benchmarks
- **Standard mode**: ~70-75% faster than v1.0.0
- **Fast mode**: ~80-85% faster than v1.0.0
- **Page reloads eliminated**: Typically saves 50-200+ page loads per extraction

### Backward Compatibility
- All CLI arguments remain compatible
- Output JSON structure unchanged (only added fields)
- Profile directory and authentication mechanism unchanged

---

## [1.0.0] - 2025-01-XX

### Initial Release
- Recursive X/Twitter thread extraction with Playwright
- Persistent browser profile for authentication
- Configurable depth limits and timeouts
- Intermediate save functionality
- Support for multiple languages (French/English UI)
- Comprehensive error handling and retry logic
