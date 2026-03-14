---
name: generate-images
description: Generate one or more images from a text prompt using OpenAI's Images API (model gpt-image-1.5). Use when the user asks to “generate images”, “create an image”, “make a thumbnail”, or similar; especially when they provide a prompt plus options like count/size/quality/output directory.
---

# Generate Images (gpt-image-1.5)

Generate images via the OpenAI Images API using a deterministic helper script.

## Prerequisites

- `OPENAI_API_KEY` environment variable must be set
- `jq` must be available (used to parse API JSON)

## Usage

- `/generate-images a sunset over the ocean` — generate 1 image
- `/generate-images 3 cats wearing hats` — generate 3 images (shorthand count)
- `/generate-images --count 5 --size 1536x1024 a mountain landscape` — full options

## Arguments

The argument string is available as `$ARGUMENTS`.

### Flags (all optional)

- `--count N` (default `1`) — number of images (1–10)
- `--size WxH` (default `1024x1024`) — one of: `1024x1024`, `1536x1024`, `1024x1536`
- `--quality Q` (default `high`) — `low`, `medium`, `high`
- `--output DIR` (default `./`) — directory to save images
- `--prefix NAME` (default `image`) — filenames like `{prefix}-1.png`, `{prefix}-2.png`, ...
- `--format FMT` (default `png`) — `png` or `jpg`

Flags can appear in any order and may be mixed with prompt tokens.

### Shorthand count

If the prompt starts with a bare number + space (e.g. `3 cats wearing hats`), treat the number as the count **only if** no `--count` flag is present.

### Everything else is the prompt

After extracting flags and optional leading count, join the remaining text as the prompt.

## Procedure

Prefer running the bundled script (it handles parsing, file naming, progress, and errors):

```bash
bash /Users/ericblue/clawd/skills/public/generate-images/scripts/generate-images.sh
```

The script reads `$ARGUMENTS` (or you can pass a single argument string as `$1`).

## Notes

- Each API call generates one image; multiple images are generated sequentially.
- Cost varies by quality and size (rough estimates per 1024×1024 image): low ~$0.04, medium ~$0.07, high ~$0.19. Larger sizes are ~1.5×.
