# Sheriff Jr.

An agentic CLI tool that reviews Google Ads and Microsoft Advertising copy, keywords, and landing pages for policy violations. Powered by Claude's tool-use capability — the agent fetches the actual policy documents at review time rather than relying on static knowledge.

## Features

- Reviews ad copy, keywords, and landing page URLs — any combination
- Fetches all six Google and Microsoft ad policies on every run
- Returns structured JSON: verdict, per-issue severity, offending text, and a suggested rewrite
- Color-coded terminal output via `rich`
- **Batch mode**: review an entire CSV campaign export in one command

## Setup

```bash
# 1. Clone and enter the repo
git clone https://github.com/your-org/sheriff-jr.git
cd sheriff-jr

# 2. Install dependencies
pip install -r requirements.txt

# 3. Add your Anthropic API key
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

## Single-ad review (`check`)

```bash
python main.py check --ad "Affordable car insurance quotes in your area"

python main.py check \
  --keyword "payday loans" \
  --landing-page https://example.com

python main.py check \
  --ad "Best deals on prescription meds" \
  --keyword "buy xanax" \
  --landing-page https://example.com

# Raw JSON output (pipe-friendly)
python main.py check --ad "Lose 30 lbs in 30 days, guaranteed!" --json-out
```

The agent prints each tool call as it runs so you can watch it reason:

```
Running compliance review…

[tool] fetch_policy_page(policy_name='google-prohibited-content')
[tool] fetch_policy_page(policy_name='google-prohibited-practices')
[tool] fetch_policy_page(policy_name='google-restricted-content')
[tool] fetch_policy_page(policy_name='google-editorial')
[tool] fetch_policy_page(policy_name='microsoft-disallowed-content')
[tool] fetch_policy_page(policy_name='microsoft-relevance-quality')

╭────────────────── Sheriff Jr. Compliance Report ──────────────────╮
│ LIKELY VIOLATION                                                   │
│ Ad makes an unrealistic weight-loss claim with an unsubstantiated  │
│ guarantee, violating Google editorial and Microsoft quality rules. │
╰────────────────────────────────────────────────────────────────────╯
```

## Batch review (`batch`)

Process a CSV file containing multiple ads in one command. Input columns: `ad`, `keyword`, `landing_page` (any may be empty per row).

```bash
python main.py batch \
  --input examples/sample_ads.csv \
  --output results.csv

# Dry-run with just the first 3 rows
python main.py batch \
  --input examples/sample_ads.csv \
  --output results.csv \
  --limit 3
```

A progress bar tracks each review in real time. When complete, Sheriff prints a summary:

```
╭───────────────── Batch Complete ─────────────────╮
│ Processed 10 ad(s):                              │
│   4 CLEAN                                        │
│   3 AT RISK                                      │
│   3 LIKELY VIOLATION                             │
│                                                  │
│ Results written to results.csv                   │
╰──────────────────────────────────────────────────╯
```

### Output CSV columns

| Column | Description |
|---|---|
| `ad` | Original ad text |
| `keyword` | Original keyword |
| `landing_page` | Original URL |
| `verdict` | `clean` / `at_risk` / `likely_violation` |
| `summary` | One-sentence plain-English verdict |
| `issue_count` | Number of issues found |
| `issues_json` | Full issues list serialized as JSON |
| `error` | Error message if the review call failed; empty otherwise |

### Sample input

See [`examples/sample_ads.csv`](examples/sample_ads.csv) for a starter set that covers the full verdict range:

| Ad | Expected verdict |
|---|---|
| Affordable car insurance quotes in your area | at_risk |
| Try ProjectFlow — project management for modern teams | clean |
| Lose 30 pounds in 30 days, guaranteed! | likely_violation |
| Best weight loss supplement — doctors hate this trick | likely_violation |
| Low-rate personal loans, apply in minutes | at_risk |
| Buy cheap Xanax without a prescription — shipped overnight | likely_violation |
| Get authentic designer handbags at 90% off — limited stock | likely_violation |
| Open a high-yield savings account today — 5% APY, FDIC insured | clean |
| Earn $5,000 a week from home — guaranteed, no experience needed | likely_violation |
| Cloud storage for your business — 1 TB free, no credit card required | clean |

## Output schema

```json
{
  "overall_verdict": "clean" | "at_risk" | "likely_violation",
  "summary": "One-sentence plain-English verdict.",
  "issues": [
    {
      "policy": "google-editorial",
      "offending_text": "the exact problematic text",
      "severity": "high" | "medium" | "low",
      "explanation": "One sentence.",
      "suggested_rewrite": "A compliant alternative ready to paste."
    }
  ]
}
```

## Policies covered

| ID | Platform | Topic |
|---|---|---|
| `google-prohibited-content` | Google | Counterfeit goods, dangerous products, adult content |
| `google-prohibited-practices` | Google | Data collection, misrepresentation, malicious software |
| `google-restricted-content` | Google | Healthcare, alcohol, gambling, financial services |
| `google-editorial` | Google | Grammar, superlatives, punctuation, capitalisation |
| `microsoft-disallowed-content` | Microsoft | Illegal products, misleading claims, offensive content |
| `microsoft-relevance-quality` | Microsoft | Ad relevance, landing-page quality, deceptive tactics |

## Architecture

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the full design document.
