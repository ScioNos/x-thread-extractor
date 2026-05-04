from __future__ import annotations

import json
import os
import textwrap
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional
from urllib import error, request

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args, **kwargs):  # type: ignore[no-redef]
        return False

try:
    from ddgs import DDGS
except ModuleNotFoundError:
    DDGS = None


DEFAULT_DEBUNK_SYSTEM_PROMPT = textwrap.dedent(
    """
    Tu es Debuk, analyste épistémique francophone pour fils X.com.

    Analyse le débat sans désigner de vainqueur. Évalue uniquement ce qui est observable et vérifiable.

    Règles :
    - Français uniquement.
    - Même exigence pour tous les camps.
    - Distingue faits, opinions, morale et rhétorique.
    - Vérifie les affirmations factuelles importantes avec sources fiables et croisées.
    - Indique le niveau de consensus : fort, débat actif, question ouverte, normatif.
    - Ne fais ni doxxing, ni psychologie sauvage, ni invention.
    - Si le fil est incomplet, signale les limites.

    Pour chaque argument important :
    - statut factuel ;
    - validité logique ;
    - pertinence ;
    - sophisme éventuel ;
    - cote : fort, mixte, faible, non évaluable.

    Structure :
    1. Question centrale
    2. État fiable des connaissances
    3. Tableau des arguments
    4. Vérifications factuelles sourcées
    5. Sophismes observés
    6. Participants influents
    7. Arguments solides/faibles
    8. Qualité globale du débat
    9. Limites
    """
).strip()


@dataclass
class AnalysisSettings:
    base_url: str = "https://routerlab.ch/v1"
    api_key: str = ""
    analysis_model: str = ""
    research_model: str = ""
    request_timeout: float = 120.0
    temperature: float = 0.2
    fact_check_queries: int = 4
    search_region: str = "fr-fr"
    search_safesearch: str = "moderate"
    search_max_results: int = 5
    extract_top_n: int = 2
    extract_max_chars: int = 1200
    system_prompt: str = DEFAULT_DEBUNK_SYSTEM_PROMPT


def _get_env_float(env: Mapping[str, str], key: str, default: float) -> float:
    raw = env.get(key)
    if raw is None or raw == "":
        return default
    return float(raw)


def _get_env_int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key)
    if raw is None or raw == "":
        return default
    return int(raw)


def load_analysis_settings(env: Optional[Mapping[str, str]] = None) -> AnalysisSettings:
    load_dotenv()
    source = env if env is not None else os.environ
    analysis_model = source.get("OPENAI_ANALYSIS_MODEL") or source.get("OPENAI_MODEL", "")
    research_model = source.get("OPENAI_RESEARCH_MODEL") or analysis_model
    return AnalysisSettings(
        base_url=(source.get("OPENAI_BASE_URL") or "https://routerlab.ch/v1").rstrip("/"),
        api_key=source.get("OPENAI_API_KEY", "").strip(),
        analysis_model=analysis_model.strip(),
        research_model=research_model.strip(),
        request_timeout=_get_env_float(source, "OPENAI_REQUEST_TIMEOUT", 120.0),
        temperature=_get_env_float(source, "OPENAI_TEMPERATURE", 0.2),
        fact_check_queries=_get_env_int(source, "DEBUNK_FACT_CHECK_QUERIES", 4),
        search_region=source.get("DEBUNK_SEARCH_REGION", "fr-fr").strip(),
        search_safesearch=source.get("DEBUNK_SEARCH_SAFESEARCH", "moderate").strip(),
        search_max_results=_get_env_int(source, "DEBUNK_SEARCH_MAX_RESULTS", 5),
        extract_top_n=_get_env_int(source, "DEBUNK_EXTRACT_TOP_N", 2),
        extract_max_chars=_get_env_int(source, "DEBUNK_EXTRACT_MAX_CHARS", 1200),
        system_prompt=(source.get("DEBUNK_SYSTEM_PROMPT") or DEFAULT_DEBUNK_SYSTEM_PROMPT).strip(),
    )


def validate_analysis_settings(settings: AnalysisSettings) -> None:
    missing = []
    if not settings.api_key:
        missing.append("OPENAI_API_KEY")
    if not settings.analysis_model:
        missing.append("OPENAI_ANALYSIS_MODEL")
    if missing:
        raise RuntimeError(
            "Configuration analyse incomplète dans .env : "
            + ", ".join(missing)
        )


def build_analysis_output_path(json_output_path: Path) -> Path:
    return json_output_path.with_suffix(".analysis.md")


def trim_text(value: str, limit: int) -> str:
    normalized = " ".join((value or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 1)].rstrip() + "…"


def _render_tweet_lines(tweet: dict[str, Any], depth: int, lines: list[str], stats: dict[str, int]) -> None:
    if stats["tweets"] >= stats["max_tweets"] or stats["chars"] >= stats["max_chars"]:
        return
    indent = "  " * depth
    text = trim_text(tweet.get("texte", ""), 420)
    author = trim_text(tweet.get("auteur", ""), 80) or "Auteur inconnu"
    timestamp = tweet.get("timestamp") or "horodatage inconnu"
    line = f"{indent}- id={tweet.get('id', '?')} | auteur={author} | date={timestamp} | texte={text}"
    if stats["chars"] + len(line) + 1 > stats["max_chars"]:
        return
    lines.append(line)
    stats["tweets"] += 1
    stats["chars"] += len(line) + 1
    for child in tweet.get("sous_discussions", []):
        _render_tweet_lines(child, depth + 1, lines, stats)


def build_thread_context(payload: Mapping[str, Any], max_tweets: int = 120, max_chars: int = 24000) -> str:
    root = payload.get("tweet_racine", {})
    replies = payload.get("reponses", [])
    lines = [f"URL racine: {payload.get('meta', {}).get('url_racine', '')}", "Fil extrait :"]
    stats = {"tweets": 0, "chars": sum(len(line) + 1 for line in lines), "max_tweets": max_tweets, "max_chars": max_chars}
    _render_tweet_lines(root, 0, lines, stats)
    for reply in replies:
        _render_tweet_lines(reply, 1, lines, stats)
    if stats["tweets"] >= max_tweets or stats["chars"] >= max_chars:
        lines.append("[Fil tronqué pour respecter le budget de contexte]")
    return "\n".join(lines)


def _extract_json_fragment(text: str) -> str:
    text = text.strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escaping = False
        for index in range(start, len(text)):
            char = text[index]
            if escaping:
                escaping = False
                continue
            if char == "\\":
                escaping = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]
    raise ValueError("Aucun JSON exploitable trouvé dans la réponse du modèle.")


def extract_json_payload(text: str) -> Any:
    return json.loads(_extract_json_fragment(text))


def _normalize_message_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        fragments = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    fragments.append(item.get("text", ""))
                elif "text" in item:
                    fragments.append(str(item["text"]))
            else:
                fragments.append(str(item))
        return "\n".join(fragment for fragment in fragments if fragment).strip()
    return str(content or "")


def _call_chat_completion(
    *,
    base_url: str,
    api_key: str,
    model: str,
    messages: list[dict[str, str]],
    timeout: float,
    temperature: float,
) -> str:
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    req = request.Request(endpoint, data=body, headers=headers, method="POST")
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with request.urlopen(req, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
            break
        except error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Erreur HTTP LLM {exc.code} sur {endpoint}: {details}") from exc
        except error.URLError as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(1.0)
                continue
            raise RuntimeError(f"Impossible de joindre l'API LLM {endpoint}: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Réponse LLM non JSON sur {endpoint}: {exc}") from exc
    else:
        raise RuntimeError(f"Impossible de joindre l'API LLM {endpoint}: {last_error}")

    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("Réponse LLM invalide: aucune choice trouvée.")
    message = choices[0].get("message") or {}
    return _normalize_message_content(message.get("content", ""))


def _build_query_planner_messages(thread_context: str, settings: AnalysisSettings) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "Tu identifies les affirmations factuelles prioritaires à vérifier dans un débat X. "
                "Réponds uniquement en JSON valide."
            ),
        },
        {
            "role": "user",
            "content": textwrap.dedent(
                f"""
                Retourne uniquement un objet JSON de la forme :
                {{
                  "queries": [
                    {{
                      "claim": "affirmation à vérifier",
                      "query": "requête web précise",
                      "why": "pourquoi cette vérification compte"
                    }}
                  ]
                }}

                Contraintes :
                - Entre 1 et {settings.fact_check_queries} requêtes.
                - Ne retiens que les affirmations factuelles importantes.
                - Évite les jugements moraux et les attaques personnelles.
                - Les requêtes doivent viser des sources fiables, idéalement primaires ou institutionnelles.
                - Français uniquement.

                Fil :
                {thread_context}
                """
            ).strip(),
        },
    ]


def build_fallback_queries(payload: Mapping[str, Any]) -> list[dict[str, str]]:
    root = payload.get("tweet_racine", {})
    root_text = trim_text(root.get("texte", ""), 180)
    if not root_text:
        return []
    return [
        {
            "claim": root_text,
            "query": root_text,
            "why": "Requête de secours construite à partir du tweet racine.",
        }
    ]


def request_fact_check_queries(payload: Mapping[str, Any], settings: AnalysisSettings) -> list[dict[str, str]]:
    thread_context = build_thread_context(payload, max_tweets=80, max_chars=12000)
    try:
        raw = _call_chat_completion(
            base_url=settings.base_url,
            api_key=settings.api_key,
            model=settings.research_model,
            messages=_build_query_planner_messages(thread_context, settings),
            timeout=settings.request_timeout,
            temperature=0.0,
        )
        parsed = extract_json_payload(raw)
    except Exception:
        return build_fallback_queries(payload)
    queries = parsed.get("queries", []) if isinstance(parsed, dict) else []
    normalized: list[dict[str, str]] = []
    for item in queries:
        if not isinstance(item, dict):
            continue
        claim = trim_text(str(item.get("claim", "")), 300)
        query = trim_text(str(item.get("query", "")), 300)
        why = trim_text(str(item.get("why", "")), 220)
        if claim and query:
            normalized.append({"claim": claim, "query": query, "why": why})
    return normalized[: settings.fact_check_queries] or build_fallback_queries(payload)


def ensure_ddgs_available() -> None:
    if DDGS is None:
        raise RuntimeError("Le package ddgs n'est pas installé. Lance : pip install -r requirements.txt")


def _extract_source_content(search_client: Any, url: str, max_chars: int) -> str:
    try:
        extracted = search_client.extract(url, fmt="text_markdown")
    except Exception:
        return ""
    if not isinstance(extracted, dict):
        return ""
    return trim_text(str(extracted.get("content", "")), max_chars)


def run_fact_check_searches(
    queries: list[dict[str, str]],
    settings: AnalysisSettings,
    *,
    include_extracts: bool = True,
) -> list[dict[str, Any]]:
    try:
        ensure_ddgs_available()
    except RuntimeError as exc:
        return [{"claim": item.get("claim", ""), "query": item.get("query", ""), "why": item.get("why", ""), "error": str(exc), "sources": []} for item in queries]
    bundles: list[dict[str, Any]] = []
    try:
        search_client = DDGS(timeout=int(settings.request_timeout))
    except Exception as exc:
        return [{"claim": item.get("claim", ""), "query": item.get("query", ""), "why": item.get("why", ""), "error": str(exc), "sources": []} for item in queries]
    for item in queries:
        try:
            results = search_client.text(
                item["query"],
                region=settings.search_region,
                safesearch=settings.search_safesearch,
                max_results=settings.search_max_results,
                backend="auto",
            )
        except Exception as exc:
            bundles.append(
                {
                    "claim": item["claim"],
                    "query": item["query"],
                    "why": item.get("why", ""),
                    "error": str(exc),
                    "sources": [],
                }
            )
            continue

        sources = []
        for index, result in enumerate(results or []):
            href = str(result.get("href", "")).strip()
            if not href:
                continue
            source = {
                "title": trim_text(str(result.get("title", "")), 180),
                "url": href,
                "snippet": trim_text(str(result.get("body", "")), 320),
            }
            if include_extracts and index < settings.extract_top_n:
                source["extract"] = _extract_source_content(search_client, href, settings.extract_max_chars)
            sources.append(source)

        bundles.append(
            {
                "claim": item["claim"],
                "query": item["query"],
                "why": item.get("why", ""),
                "sources": sources,
            }
        )
    return bundles


def format_search_context(searches: list[dict[str, Any]]) -> str:
    if not searches:
        return "Aucune recherche web disponible."
    lines = []
    for bundle_index, bundle in enumerate(searches, start=1):
        lines.append(f"Recherche {bundle_index}")
        lines.append(f"- Affirmation: {bundle.get('claim', '')}")
        lines.append(f"- Requête: {bundle.get('query', '')}")
        if bundle.get("why"):
            lines.append(f"- Pourquoi: {bundle['why']}")
        if bundle.get("error"):
            lines.append(f"- Erreur recherche: {bundle['error']}")
        if not bundle.get("sources"):
            lines.append("- Sources: aucune")
            continue
        for source_index, source in enumerate(bundle["sources"], start=1):
            lines.append(f"- Source {bundle_index}.{source_index}: {source.get('title', '')}")
            lines.append(f"  URL: {source.get('url', '')}")
            if source.get("snippet"):
                lines.append(f"  Résumé: {source['snippet']}")
            if source.get("extract"):
                lines.append(f"  Extrait: {source['extract']}")
    return "\n".join(lines)


def build_analysis_messages(
    payload: Mapping[str, Any],
    settings: AnalysisSettings,
    searches: list[dict[str, Any]],
) -> list[dict[str, str]]:
    thread_context = build_thread_context(payload)
    search_context = format_search_context(searches)
    return [
        {"role": "system", "content": settings.system_prompt},
        {
            "role": "user",
            "content": textwrap.dedent(
                f"""
                Contexte :
                - URL du fil: {payload.get('meta', {}).get('url_racine', '')}
                - Extraction: {payload.get('meta', {}).get('extraction_iso', '')}
                - Le fil peut être partiel, tronqué ou incomplet.

                Fil extrait :
                {thread_context}

                Vérifications factuelles sourcées :
                {search_context}

                Exigences supplémentaires :
                - Cite les sources utilisées directement dans les sections concernées, en Markdown.
                - Si les sources sont insuffisantes ou ambiguës, dis-le explicitement.
                - N'invente aucune information absente du fil ou des sources fournies.
                """
            ).strip(),
        },
    ]


def generate_analysis_report(
    payload: Mapping[str, Any],
    settings: AnalysisSettings,
    output_path: Path,
    *,
    use_search: bool = True,
) -> dict[str, Any]:
    validate_analysis_settings(settings)
    searches: list[dict[str, Any]] = []
    queries: list[dict[str, str]] = []
    if use_search:
        try:
            queries = request_fact_check_queries(payload, settings)
            searches = run_fact_check_searches(queries, settings)
        except Exception as exc:
            searches = [{"claim": "Recherche web", "query": "", "why": "Mode dégradé", "error": str(exc), "sources": []}]
    messages = build_analysis_messages(payload, settings, searches)
    report = _call_chat_completion(
        base_url=settings.base_url,
        api_key=settings.api_key,
        model=settings.analysis_model,
        messages=messages,
        timeout=settings.request_timeout,
        temperature=settings.temperature,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.strip() + "\n", encoding="utf-8")
    return {
        "output_path": output_path,
        "queries": queries,
        "searches": searches,
    }
