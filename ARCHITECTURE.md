# Sheriff Jr. — Architecture

## Problem

Advertisers on Google Ads and Microsoft Advertising must comply with constantly evolving content policies. Manual review is slow, inconsistent, and doesn't scale. Sheriff Jr. is an agentic CLI tool that reviews ad copy, keywords, or landing pages and flags potential policy violations with citations and suggested rewrites.

## High-Level Design

Sheriff Jr. is a command-line agent built on the Anthropic API using Claude's tool-use capability. The user provides an ad, keyword, or landing page URL; the agent autonomously decides which policies to fetch, reads them, evaluates the input, and returns a structured compliance report.

## Components

### 1. Input Layer (CLI)
A Click-based Python CLI accepting:
- `--ad` — ad headline and/or body text
- `--keyword` — a search keyword being bid on
- `--landing-page` — URL of the destination page

Any combination of the three can be provided in a single run.

### 2. Agent Core
A Python loop that:
1. Sends the user input plus a system prompt to the Claude API with tool definitions attached.
2. If Claude responds with a tool-use request, executes the tool and sends the result back.
3. Repeats until Claude returns a final structured response.
4. Parses the response and hands it to the output layer.

This loop is the "agentic" heart of the project — Claude decides which tools to call and in what order, not the developer.

### 3. Tools
Functions exposed to Claude via the Anthropic tool-use schema:

- **`fetch_policy_page(policy_name)`** — Retrieves the latest official Google Ads or Microsoft Advertising policy page from a curated URL map. Ensures the agent reasons over current policy text rather than training data.
- **`fetch_url(url)`** — Fetches and extracts readable text from any web page (used for landing-page review).
- **`web_search(query)`** — General web search for cases where the agent needs broader context (e.g., trademark questions).

### 4. Output Layer
Formats Claude's final JSON response into a human-readable terminal report and optionally writes a JSON file for downstream use. Report fields per issue: policy name, offending text, severity (high/medium/low), explanation, suggested rewrite.

## Data Flow

```
User input (CLI)
      ↓
Agent core (system prompt + tools + user input)
      ↓
Claude API ⇄ Tool execution loop
      ↓
Structured JSON response
      ↓
Formatted terminal report
```

## Key Design Decisions

- **Always fetch fresh policies.** The system prompt instructs Claude to fetch policy pages on every run rather than rely on memory, because ad policies change frequently.
- **Tool use over RAG.** No vector database or pre-indexed corpus — the agent fetches what it needs at runtime. Simpler, more transparent, easier to demo.
- **JSON-structured output.** Forces the agent to return predictable fields, making the tool scriptable and testable.
- **Small tool surface.** Three tools only, to keep the agent's decision space narrow and reliable.

## Out of Scope (v1)

- Image and video ad review
- Bulk CSV processing
- Web UI
- Persistent storage of past reviews
- Support for ad platforms beyond Google and Microsoft

## Future Extensions

- Add Meta and TikTok ad policies
- Batch mode for reviewing campaign exports
- Web dashboard for non-technical users
- Integration with Google Ads API to pull live campaigns for review
