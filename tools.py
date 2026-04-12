"""
Tools available to the Sheriff Jr. agent.

Each tool is a plain Python function. The TOOL_SCHEMAS list describes them
to the Claude API in the format required by Anthropic's tool-use feature.
TOOL_FUNCTIONS maps tool names to the callable so the agent loop can dispatch.
"""

import re
import pathlib
import requests
from bs4 import BeautifulSoup


# ---------------------------------------------------------------------------
# Local policy corpus
# ---------------------------------------------------------------------------
# Policy text lives in policies/<name>.md — one file per policy.
# This avoids brittle JS-heavy page fetches and makes the corpus auditable.

_POLICIES_DIR = pathlib.Path(__file__).parent / "policies"

POLICY_URLS = {
    "google-prohibited-content":
        "https://support.google.com/adspolicy/answer/6008942#con",
    "google-prohibited-practices":
        "https://support.google.com/adspolicy/answer/6008942#pra",
    "google-restricted-content":
        "https://support.google.com/adspolicy/answer/6008942#res",
    "google-editorial":
        "https://support.google.com/adspolicy/answer/6008942#ed",
    "microsoft-disallowed-content":
        "https://help.ads.microsoft.com/#apex/ads/en/60208/0-500",
    "microsoft-relevance-quality":
        "https://help.ads.microsoft.com/#apex/ads/en/60215/0-500",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_html(html: str, max_chars: int = 8000) -> str:
    """Strip scripts/styles and collapse whitespace; truncate for token safety."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars] + " [...truncated]"
    return text


def _http_get(url: str) -> str:
    headers = {"User-Agent": "SheriffJr/0.1 (+https://github.com/)"}
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.text


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def fetch_policy_page(policy_name: str) -> str:
    """Return the local policy summary for a named Google or Microsoft ad policy."""
    if policy_name not in POLICY_URLS:
        available = ", ".join(sorted(POLICY_URLS.keys()))
        return f"ERROR: Unknown policy '{policy_name}'. Available: {available}"
    path = _POLICIES_DIR / f"{policy_name}.md"
    return path.read_text(encoding="utf-8")


def fetch_url(url: str) -> str:
    """Fetch and extract readable text from any URL (e.g., a landing page)."""
    try:
        return _clean_html(_http_get(url))
    except Exception as e:
        return f"ERROR fetching {url}: {e}"


def web_search(query: str) -> str:
    """Placeholder — not yet implemented."""
    return "web_search not yet implemented in v1."


# ---------------------------------------------------------------------------
# Anthropic tool schemas
# ---------------------------------------------------------------------------
# These descriptions are what Claude reads to decide when to call each tool.
# Be specific: tell the model *when* to use it, not just what it does.

TOOL_SCHEMAS = [
    {
        "name": "fetch_policy_page",
        "description": (
            "Fetches the official text of a named Google Ads or Microsoft "
            "Advertising policy from a curated URL map. Call this BEFORE "
            "making any compliance judgment — do not rely on memory, because "
            "ad policies change frequently. Use this whenever you need to "
            "verify whether ad content violates a specific policy."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "policy_name": {
                    "type": "string",
                    "enum": sorted(POLICY_URLS.keys()),
                    "description": "Friendly name of the policy to fetch.",
                }
            },
            "required": ["policy_name"],
        },
    },
    {
        "name": "fetch_url",
        "description": (
            "Fetches and extracts readable text from any URL. Use this to "
            "review the content of a landing page the ad links to, or any "
            "other web page relevant to the compliance review."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL to fetch."}
            },
            "required": ["url"],
        },
    },
    {
        "name": "web_search",
        "description": (
            "General web search for broader context (e.g., checking whether "
            "a brand name is trademarked). Currently a placeholder."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."}
            },
            "required": ["query"],
        },
    },
]


TOOL_FUNCTIONS = {
    "fetch_policy_page": fetch_policy_page,
    "fetch_url": fetch_url,
    "web_search": web_search,
}
