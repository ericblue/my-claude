---
name: searxng-search
description: Use the locally-running SearXNG instance (http://127.0.0.1:8888) as a privacy-friendly meta-search engine and return concise results with titles, URLs, and snippets.
---

# SearXNG Search Skill

## Purpose

Run web searches via the **local SearXNG** instance that is set up in this workspace.

- Service URL: `http://127.0.0.1:8888`
- JSON endpoint: `/search?q=...&format=json`

## When to use

Trigger this skill when the user asks to:
- “search the web” / “look this up” / “find links about …”
- “use searxng” / “search with searxng”
- Anything that implies using a privacy-friendly search engine.

## Preconditions

1) SearXNG should be running.
   - Start it with:
     - `/Users/ericblue/clawd/services/searxng/start.sh`
   - If it’s not running, start it in the background.

2) Health check:
   - `curl -sS 'http://127.0.0.1:8888/search?q=test&format=json'` should return JSON.

## How to execute a search

Preferred method (stable formatting): run the helper script:

```bash
python3 /Users/ericblue/clawd/skills/public/searxng-search/scripts/searxng_search.py --q "YOUR QUERY" --n 5
```

Parameters:
- `--q` (required): query string
- `--n` (optional): number of results (default 5)
- `--categories` (optional): SearXNG categories, comma-separated (e.g. `general,science`)
- `--lang` (optional): language code (e.g. `en`)

## Output format (chat)

Return:
- A tight bullet list of the top results: **Title** + URL, then a short snippet line.
- If the user asked for “sources”, include 5–10 links.

## Notes / limitations

- This is a *meta-search*; results depend on upstream engines and may occasionally error.
- If SearXNG is down, restart it and retry once before asking the user.