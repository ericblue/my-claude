Generate one or more images using OpenAI's gpt-image-1.5 model.

## Prerequisites

- `OPENAI_API_KEY` environment variable must be set
- `jq` must be available (for JSON parsing)

## Usage

- `/generate-images a sunset over the ocean` — Generate 1 image from the prompt
- `/generate-images 3 cats wearing hats` — Generate 3 images (number prefix)
- `/generate-images --count 5 --size 1536x1024 a mountain landscape` — Full options

## Arguments

The argument string is available as `$ARGUMENTS`. Parse it according to these rules:

### Flags (all optional, can appear in any order before or mixed with the prompt)

| Flag | Default | Description |
|------|---------|-------------|
| `--count N` | `1` | Number of images to generate (1-10) |
| `--size WxH` | `1024x1024` | Image dimensions. Valid: `1024x1024`, `1536x1024` (landscape), `1024x1536` (portrait) |
| `--quality Q` | `high` | `low`, `medium`, or `high` |
| `--output DIR` | `./` | Directory to save images to |
| `--prefix NAME` | `image` | Filename prefix (files will be `{prefix}-1.png`, `{prefix}-2.png`, etc.) |
| `--format FMT` | `png` | Output format: `png` or `jpg` |

### Shorthand count

If the prompt starts with a bare number followed by a space (e.g., `3 cats wearing hats`), treat the number as the count and the rest as the prompt. Only apply this if no `--count` flag is present.

### Everything else is the prompt

After extracting flags and optional leading count, join the remaining text as the image prompt.

## Steps

1. **Verify prerequisites**:
   - Check that `OPENAI_API_KEY` is set. If not, tell the user to set it and stop.
   - Check that `jq` is available. If not, tell the user to install it (`brew install jq` on macOS).

2. **Parse arguments**: Extract flags and prompt from `$ARGUMENTS` as described above.
   - If no prompt text is provided, ask the user what they want to generate and stop.
   - Validate `--count` is between 1 and 10.
   - Validate `--size` is one of the three accepted values.

3. **Ensure output directory exists**: Create the output directory if it doesn't already exist.

4. **Determine filenames**: Check existing files in the output directory to avoid overwriting. If `{prefix}-1.png` already exists, start numbering from the next available number.

5. **Generate images one at a time** for the requested count:

   - Call the OpenAI API using curl:

     ```bash
     curl -s -X POST "https://api.openai.com/v1/images/generations" \
       -H "Authorization: Bearer $OPENAI_API_KEY" \
       -H "Content-Type: application/json" \
       -d '{
         "model": "gpt-image-1.5",
         "prompt": "<the prompt>",
         "size": "<size>",
         "quality": "<quality>",
         "output_format": "<format>"
       }'
     ```

   - The response returns base64 image data in `data[0].b64_json`. Decode and save it:

     ```bash
     echo '<response>' | jq -r '.data[0].b64_json' | base64 --decode > <output_dir>/<prefix>-<n>.<format>
     ```

   - After each image, report progress: "Generated: {filename} ({n}/{total})"

   - If the API returns an error, report the error for that image and continue to the next one.

   - If the API returns a `revised_prompt` in the response (`data[0].revised_prompt`), note it in the progress output so the user can see what the model actually used.

6. **Summary**: After all images are processed, report:
   - How many images were successfully generated
   - How many failed (if any)
   - The full file paths of all generated images
   - Total estimated cost (~$0.04-0.19 per image depending on quality and size)

## Error Handling

- If `OPENAI_API_KEY` is not set, stop immediately with instructions
- If `jq` is not installed, stop immediately with install instructions
- If no prompt text is provided, stop and ask the user
- If the API returns an error for a specific image, log it and continue to the next
- If the output directory cannot be created, stop and report the error
- If count is out of range (< 1 or > 10), clamp to range and warn

## Notes

- Each API call generates one image; batch generation is done sequentially
- gpt-image-1.5 supports the three listed sizes — other sizes will be rejected by the API
- Cost varies by quality: low ~$0.04, medium ~$0.07, high ~$0.19 per image (1024x1024)
- Larger sizes cost more (~1.5x for landscape/portrait)

