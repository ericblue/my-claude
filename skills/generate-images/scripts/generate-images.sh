#!/usr/bin/env bash
set -euo pipefail

# generate-images.sh
# Reads $ARGUMENTS (Clawdbot) or accepts a single argument string as $1.
# Generates images via OpenAI Images API (model: gpt-image-1.5) sequentially.

ARG_STRING="${1-${ARGUMENTS-}}"

need_cmd() { command -v "$1" >/dev/null 2>&1; }

if [[ -z "${OPENAI_API_KEY-}" ]]; then
  echo "ERROR: OPENAI_API_KEY is not set. Export it and try again." >&2
  exit 1
fi

if ! need_cmd jq; then
  echo "ERROR: jq is not installed. Install it (macOS): brew install jq" >&2
  exit 1
fi

PARSED_JSON="$({
  ARG_STRING="$ARG_STRING" python3 - <<'PY'
import json, os, re, shlex, sys
s = os.environ.get('ARG_STRING','')

tokens = shlex.split(s)
count = None
size = '1024x1024'
quality = 'high'
outdir = './'
prefix = 'image'
fmt = 'png'

rem = []
i = 0
while i < len(tokens):
    t = tokens[i]

    def take_value(key):
        global i
        if i+1 < len(tokens):
            v = tokens[i+1]
            i += 2
            return v
        i += 1
        return None

    if t == '--count':
        v = take_value('count')
        if v is not None: count = v
        continue
    if t.startswith('--count='):
        count = t.split('=',1)[1]; i += 1; continue

    if t == '--size':
        v = take_value('size')
        if v is not None: size = v
        continue
    if t.startswith('--size='):
        size = t.split('=',1)[1]; i += 1; continue

    if t == '--quality':
        v = take_value('quality')
        if v is not None: quality = v
        continue
    if t.startswith('--quality='):
        quality = t.split('=',1)[1]; i += 1; continue

    if t == '--output':
        v = take_value('output')
        if v is not None: outdir = v
        continue
    if t.startswith('--output='):
        outdir = t.split('=',1)[1]; i += 1; continue

    if t == '--prefix':
        v = take_value('prefix')
        if v is not None: prefix = v
        continue
    if t.startswith('--prefix='):
        prefix = t.split('=',1)[1]; i += 1; continue

    if t == '--format':
        v = take_value('format')
        if v is not None: fmt = v
        continue
    if t.startswith('--format='):
        fmt = t.split('=',1)[1]; i += 1; continue

    rem.append(t)
    i += 1

# Shorthand count only if no explicit --count.
if count is None and rem and re.fullmatch(r'\d{1,2}', rem[0]):
    count = rem[0]
    rem = rem[1:]

if count is None:
    count = 1

# Normalize/validate count
try:
    count_int = int(count)
except Exception:
    count_int = 1

clamped = False
if count_int < 1:
    count_int = 1; clamped = True
elif count_int > 10:
    count_int = 10; clamped = True

valid_sizes = {'1024x1024','1536x1024','1024x1536'}
if size not in valid_sizes:
    print(json.dumps({'error': f"Invalid --size '{size}'. Valid: 1024x1024, 1536x1024, 1024x1536"}))
    sys.exit(0)

quality = (quality or 'high').lower()
if quality not in {'low','medium','high'}:
    quality = 'high'

fmt = (fmt or 'png').lower()
if fmt not in {'png','jpg','jpeg'}:
    fmt = 'png'
if fmt == 'jpeg':
    fmt = 'jpg'

prompt = ' '.join(rem).strip()

print(json.dumps({
    'count': count_int,
    'size': size,
    'quality': quality,
    'output': outdir,
    'prefix': prefix,
    'format': fmt,
    'prompt': prompt,
    'clamped': clamped,
}))
PY
})"

if jq -e '.error? // empty' >/dev/null 2>&1 <<<"$PARSED_JSON"; then
  echo "ERROR: $(jq -r '.error' <<<"$PARSED_JSON")" >&2
  exit 1
fi

COUNT="$(jq -r '.count' <<<"$PARSED_JSON")"
SIZE="$(jq -r '.size' <<<"$PARSED_JSON")"
QUALITY="$(jq -r '.quality' <<<"$PARSED_JSON")"
OUTDIR="$(jq -r '.output' <<<"$PARSED_JSON")"
PREFIX="$(jq -r '.prefix' <<<"$PARSED_JSON")"
FMT="$(jq -r '.format' <<<"$PARSED_JSON")"
PROMPT="$(jq -r '.prompt' <<<"$PARSED_JSON")"
CLAMPED="$(jq -r '.clamped' <<<"$PARSED_JSON")"

if [[ "$CLAMPED" == "true" ]]; then
  echo "WARN: --count was out of range; clamped to $COUNT (valid 1-10)" >&2
fi

if [[ -z "$PROMPT" ]]; then
  echo "ERROR: No prompt provided. What do you want to generate?" >&2
  exit 1
fi

mkdir -p "$OUTDIR" || { echo "ERROR: Could not create output dir: $OUTDIR" >&2; exit 1; }

# Find next available index to avoid overwriting.
idx=1
while [[ -e "$OUTDIR/$PREFIX-$idx.$FMT" ]]; do
  idx=$((idx+1))
done

success=0
failed=0
declare -a outpaths=()

for ((k=1; k<=COUNT; k++)); do
  n=$((idx+k-1))
  outfile="$OUTDIR/$PREFIX-$n.$FMT"

  payload="$(jq -n \
    --arg model 'gpt-image-1.5' \
    --arg prompt "$PROMPT" \
    --arg size "$SIZE" \
    --arg quality "$QUALITY" \
    --arg output_format "$FMT" \
    '{model:$model,prompt:$prompt,size:$size,quality:$quality,output_format:$output_format}')"

  resp="$(curl -sS \
    --connect-timeout 10 \
    --max-time 180 \
    -X POST "https://api.openai.com/v1/images/generations" \
    -H "Authorization: Bearer $OPENAI_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$payload" || true)"

  if jq -e '.error' >/dev/null 2>&1 <<<"$resp"; then
    failed=$((failed+1))
    echo "Error generating image $k/$COUNT: $(jq -c '.error' <<<"$resp")" >&2
    continue
  fi

  b64="$(jq -r '.data[0].b64_json // empty' <<<"$resp")"
  if [[ -z "$b64" || "$b64" == "null" ]]; then
    failed=$((failed+1))
    echo "Error generating image $k/$COUNT: missing data[0].b64_json" >&2
    continue
  fi

  # macOS base64 supports --decode; also supports -D.
  if echo "$b64" | base64 --decode > "$outfile" 2>/dev/null; then
    :
  else
    echo "$b64" | base64 -D > "$outfile"
  fi

  revised="$(jq -r '.data[0].revised_prompt // empty' <<<"$resp")"
  if [[ -n "$revised" ]]; then
    echo "Generated: $outfile ($k/$COUNT) | revised_prompt: $revised"
  else
    echo "Generated: $outfile ($k/$COUNT)"
  fi

  success=$((success+1))
  outpaths+=("$outfile")
done

echo "----"
echo "Done. Success: $success | Failed: $failed"
if (( ${#outpaths[@]} > 0 )); then
  echo "Files:"
  for p in "${outpaths[@]}"; do
    # Print full path if possible
    if need_cmd python3; then
      python3 - <<PY
import os
print(os.path.abspath("$p"))
PY
    else
      echo "$p"
    fi
  done
fi

echo "Cost estimate: ~$0.04-0.19 per 1024x1024 image (low/medium/high); larger sizes ~1.5x."
