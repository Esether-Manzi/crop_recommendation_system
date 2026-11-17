"""Client for the Gemini API, used by the chat assistant.

ask_gemini() sends the farmer's question, the last few chat messages and the
selected farm's details, with Google Search grounding switched on so answers
can draw on current Ugandan sources (news, MAAIF/NARO guidance, prices,
season forecasts). It returns None whenever Gemini can't answer, and the view
then falls back to the offline crop guide.

Google's terms for grounded answers require showing the returned search
suggestions (search_html) and source links alongside the answer, unchanged,
only to the farmer who asked. The chat template does that.
"""
import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Earlier messages sent along with each question so follow-ups like "and
# what about pests?" make sense.
HISTORY_MESSAGES = 6

# Searching the web makes a reply slower. Both stay under gunicorn's default
# 30s worker timeout, even when a refused search is retried without it.
SEARCH_TIMEOUT = 20
PLAIN_TIMEOUT = 15

SYSTEM_PROMPT = (
    "You are the CropAI Assistant, a friendly and knowledgeable crop advisor for smallholder "
    "farmers in Uganda. Give short, clear, practical advice in plain language, avoiding technical "
    "jargon a farmer without formal agricultural training wouldn't know. Format your answer in "
    "Markdown (bold, numbered or bulleted lists, no tables or headings).\n\n"
    "Use web search for anything recent or local: market prices, pest and disease outbreaks, "
    "season and weather forecasts, government programmes, input subsidies, and news. When you "
    "search, prefer Ugandan and East African sources: the Ministry of Agriculture, Animal "
    "Industry and Fisheries (MAAIF, agriculture.go.ug), the National Agricultural Research "
    "Organisation (NARO, naro.go.ug), NAADS and Operation Wealth Creation, the Uganda Coffee "
    "Development Authority, the Uganda National Meteorological Authority (unma.go.ug) for "
    "season forecasts, FAO Uganda, and the farming pages of the Daily Monitor and New Vision. "
    "Say how recent the information is when it matters, for example for prices.\n\n"
    "Only give planting distances or fertilizer rates that reflect widely accepted farming "
    "practice in Uganda, and don't invent numbers you're not confident about. For pesticides "
    "and other farm chemicals, only suggest products registered for use in Uganda, remind the "
    "farmer to follow the label and wear protective clothing, and suggest confirming with their "
    "local extension officer or agro-dealer. If you're not sure, say so and suggest the local "
    "extension officer. If the question is about the farmer's soil, use the farm details below."
)


def ask_gemini(question, history=(), farm_context=""):
    """Ask Gemini for a reply.

    Returns {"text", "sources": [{"title", "uri"}], "search_html", "web"},
    or None if no API key is set or Gemini couldn't answer.
    """
    if not settings.GEMINI_API_KEY:
        return None

    system_text = SYSTEM_PROMPT
    if farm_context:
        system_text += f"\n\nFarm details:\n{farm_context}"

    contents = []
    for message in list(history)[-HISTORY_MESSAGES:]:
        role = "user" if message.get("sender") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": message.get("text", "")}]})
    contents.append({"role": "user", "parts": [{"text": question}]})

    body = {
        "system_instruction": {"parts": [{"text": system_text}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 2048, "temperature": 0.3},
    }

    if settings.GEMINI_WEB_SEARCH:
        try:
            return _post({**body, "tools": [{"google_search": {}}]}, SEARCH_TIMEOUT)
        except urllib.error.HTTPError as error:
            # Google refused the request, e.g. a free-tier key, which can't
            # use search. Answer without searching rather than not at all.
            _log_http_error(error, "with web search")
        except Exception:
            logger.warning("Gemini request with web search failed", exc_info=True)
            return None

    try:
        return _post(body, PLAIN_TIMEOUT)
    except urllib.error.HTTPError as error:
        _log_http_error(error, "without web search")
    except Exception:
        logger.warning("Gemini request failed", exc_info=True)
    return None


def _post(body, timeout):
    request = urllib.request.Request(
        API_URL.format(model=settings.GEMINI_MODEL),
        data=json.dumps(body).encode("utf-8"),
        # The key goes in a header, not the URL, so it can't leak into logs
        # or error messages.
        headers={"Content-Type": "application/json", "x-goog-api-key": settings.GEMINI_API_KEY},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return parse_response(json.loads(response.read().decode("utf-8")))


def parse_response(data):
    """Pull the answer text and grounding details out of a generateContent response."""
    candidates = data.get("candidates") or []
    if not candidates:
        logger.warning(f"Gemini returned no answer: {data.get('promptFeedback')}")
        return None
    candidate = candidates[0]

    parts = (candidate.get("content") or {}).get("parts") or []
    text = "".join(part.get("text", "") for part in parts if not part.get("thought")).strip()
    if not text:
        logger.warning(f"Gemini returned an empty answer (finishReason={candidate.get('finishReason')})")
        return None

    grounding = candidate.get("groundingMetadata") or {}
    sources = []
    seen = set()
    for chunk in grounding.get("groundingChunks") or []:
        web = chunk.get("web") or {}
        uri = web.get("uri", "")
        if uri.startswith("https://") and uri not in seen:
            seen.add(uri)
            sources.append({"title": web.get("title") or uri, "uri": uri})

    search_html = (grounding.get("searchEntryPoint") or {}).get("renderedContent", "")

    return {
        "text": text,
        "sources": sources,
        "search_html": search_html,
        "web": bool(sources or search_html),
    }


def _log_http_error(error, attempt):
    try:
        detail = error.read().decode("utf-8", "replace")[:300]
    except Exception:
        detail = ""
    logger.warning(f"Gemini request {attempt} failed: HTTP {error.code} {detail}")
