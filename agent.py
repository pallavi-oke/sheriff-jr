"""
Sheriff Jr. — agent loop.

Entry point: review(ad, keyword, landing_page) -> dict
"""

import json
import os
from typing import Optional

import anthropic
from dotenv import load_dotenv

from tools import TOOL_SCHEMAS, TOOL_FUNCTIONS


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are Sheriff, an expert ad compliance reviewer for Google Ads and Microsoft Advertising.

Your job: given ad copy, a keyword, and/or a landing page URL, identify potential policy violations and return a structured compliance report.

## Non-negotiable rules

1. **Always call `fetch_policy_page`** for every policy that could be relevant before making any compliance judgment. Do NOT rely on your training data — ad policies change frequently and your knowledge may be out of date.

2. **If a landing page URL is provided, always call `fetch_url`** on it before drawing conclusions. The landing page content is as important as the ad copy itself.

3. **Cover all six policy areas** on every run by calling `fetch_policy_page` for each:
   - google-prohibited-content
   - google-prohibited-practices
   - google-restricted-content
   - google-editorial
   - microsoft-disallowed-content
   - microsoft-relevance-quality

4. After reading the policies and (if applicable) the landing page, produce your final answer as a **single JSON object** matching this exact schema — no markdown fences, no extra keys, no prose outside the JSON:

{
  "overall_verdict": "clean" | "at_risk" | "likely_violation",
  "summary": "<one-sentence plain-English verdict>",
  "issues": [
    {
      "policy": "<policy name from the curated list>",
      "offending_text": "<the specific text that is problematic>",
      "severity": "high" | "medium" | "low",
      "explanation": "<one sentence>",
      "suggested_rewrite": "<a compliant alternative>"
    }
  ]
}

5. If there are no issues, return `"overall_verdict": "clean"` and an empty `"issues"` list.

6. Set `overall_verdict` based on the worst issue found:
   - "likely_violation" if any issue is high severity
   - "at_risk" if the worst issue is medium severity
   - "clean" if there are no issues or only informational ones

7. Be precise: quote the exact offending text rather than paraphrasing. Suggested rewrites must be concrete and ready to paste.
"""


# ---------------------------------------------------------------------------
# Agent loop
# ---------------------------------------------------------------------------

MAX_ITERATIONS = 10


def _extract_json(text: str) -> str:
    """
    Best-effort extraction of a JSON object from a model response that may
    contain prose, markdown fences, or both.

    Priority:
    1. Content inside a ```json … ``` or ``` … ``` block.
    2. Substring from the first '{' to the last '}'.
    3. The original text unchanged.
    """
    import re as _re

    # Strategy 1: fenced code block.
    fence_match = _re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, _re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    # Strategy 2: first '{' … last '}'.
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1].strip()

    # Strategy 3: give up and let the caller raise a clear error.
    return text


def review(
    ad: Optional[str],
    keyword: Optional[str],
    landing_page: Optional[str],
) -> dict:
    """
    Run the Sheriff compliance review agent.

    Parameters
    ----------
    ad          : ad headline and/or body text, or None
    keyword     : search keyword being bid on, or None
    landing_page: URL of the destination page, or None

    Returns
    -------
    Parsed JSON dict matching the compliance report schema.
    """
    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "ANTHROPIC_API_KEY not found. Add it to a .env file or export it."
        )

    client = anthropic.Anthropic(api_key=api_key)

    # Build the initial user message from whichever inputs were provided.
    parts: list[str] = []
    if ad:
        parts.append(f"**Ad copy:**\n{ad}")
    if keyword:
        parts.append(f"**Keyword:**\n{keyword}")
    if landing_page:
        parts.append(f"**Landing page URL:**\n{landing_page}")

    if not parts:
        raise ValueError("At least one of ad, keyword, or landing_page must be provided.")

    user_message = "\n\n".join(parts)

    messages: list[dict] = [{"role": "user", "content": user_message}]

    for iteration in range(MAX_ITERATIONS):
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )

        # Collect all tool-use blocks and the text block (if any).
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        if response.stop_reason == "tool_use" and tool_use_blocks:
            # Append the assistant turn (may contain both text and tool_use blocks).
            messages.append({"role": "assistant", "content": response.content})

            # Execute every tool the model requested and collect results.
            tool_results = []
            for block in tool_use_blocks:
                tool_name = block.name
                tool_input = block.input

                # Pretty-print the call so the user can watch the agent reason.
                args_repr = ", ".join(
                    f"{k}={v!r}" for k, v in tool_input.items()
                )
                print(f"[tool] {tool_name}({args_repr})")

                if tool_name not in TOOL_FUNCTIONS:
                    result_content = f"ERROR: Unknown tool '{tool_name}'."
                else:
                    result_content = TOOL_FUNCTIONS[tool_name](**tool_input)

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_content,
                    }
                )

            messages.append({"role": "user", "content": tool_results})
            continue  # next iteration

        if response.stop_reason == "end_turn":
            if not text_blocks:
                raise ValueError(
                    "Agent returned end_turn with no text content. "
                    f"Full response: {response}"
                )
            raw = text_blocks[-1].text.strip()

            # Extract JSON from the response using a cascade of strategies:
            # 1. Pull content out of a ```json ... ``` or ``` ... ``` fence block.
            # 2. Grab the substring from the first '{' to the last '}'.
            # 3. Try the raw text as-is.
            candidate = _extract_json(raw)

            try:
                return json.loads(candidate)
            except json.JSONDecodeError as exc:
                print("[debug] Raw response that failed to parse:")
                print(raw)
                raise ValueError(
                    f"Agent returned non-JSON text (parse error: {exc}).\n"
                    "Raw response printed above."
                ) from exc

        # Unexpected stop reason — treat remaining text as a partial response.
        raise ValueError(
            f"Unexpected stop_reason='{response.stop_reason}' at iteration {iteration}. "
            f"Response: {response}"
        )

    raise RuntimeError(
        f"Agent loop exceeded {MAX_ITERATIONS} iterations without a final answer. "
        "This likely means the model is stuck in a tool-call cycle."
    )
