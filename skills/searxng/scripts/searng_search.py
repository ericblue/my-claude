#!/usr/bin/env python3
"""Query the local SearXNG instance and print concise results.

Designed for Clawdbot skills: deterministic, low-dependency, markdown-ish output.
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
import urllib.parse
import urllib.request


DEFAULT_BASE = "http://127.0.0.1:8888"


def fetch_json(url: str, timeout: float = 20.0) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "clawdbot-searxng-skill/1.0",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    return json.loads(data.decode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", required=True, help="query")
    ap.add_argument("--n", type=int, default=5, help="max results")
    ap.add_argument(
        "--base",
        default=DEFAULT_BASE,
        help=f"SearXNG base URL (default: {DEFAULT_BASE})",
    )
    ap.add_argument("--categories", default="", help="comma-separated categories")
    ap.add_argument("--lang", default="", help="language code")

    args = ap.parse_args()

    params = {
        "q": args.q,
        "format": "json",
    }
    if args.categories:
        params["categories"] = args.categories
    if args.lang:
        params["language"] = args.lang

    url = args.base.rstrip("/") + "/search?" + urllib.parse.urlencode(params)

    try:
        payload = fetch_json(url)
    except Exception as e:
        print(f"ERROR: failed to query SearXNG at {args.base}: {e}", file=sys.stderr)
        return 2

    results = payload.get("results") or []
    results = results[: max(0, args.n)]

    if not results:
        print("No results.")
        return 0

    for r in results:
        title = (r.get("title") or "").strip() or "(no title)"
        link = (r.get("url") or "").strip()
        content = (r.get("content") or "").strip()
        # Keep snippets short.
        content = " ".join(content.split())
        if len(content) > 240:
            content = content[:237].rstrip() + "..."

        print(f"- **{title}**\n  {link}")
        if content:
            wrapped = textwrap.fill(content, width=92)
            wrapped = textwrap.indent(wrapped, prefix="  ")
            print(wrapped)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())