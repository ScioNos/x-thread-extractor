# Changelog

All notable changes to X Thread Extractor will be documented in this file.

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
# Use the backup file
python x_thread_extractor_backup.py URL

# Or adjust parameters to match old behavior
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
