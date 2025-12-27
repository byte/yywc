# YYWC — Your Year With Chat

Generate a **shareable share card** + a deep-dive **HTML report** from your **ChatGPT** or **Claude** data export.

- Runs locally (no network required)
- Export-based (you control the input)
- Outputs `report.html`, `summary.json`, and `share.svg`
- Auto-detects export format (ChatGPT or Claude)

## Quickstart

### ChatGPT
1) Request a ChatGPT **Data Export** and download the `.zip`

2) From this repo directory:
```bash
python3 -m yywc --export /path/to/chatgpt-export.zip --out out --year 2025 --redact
open out/report.html
open out/share.svg
```

### Claude
1) Request your Claude **Data Export** from Settings → Account → Export Data

2) From this repo directory:
```bash
python3 -m yywc --export /path/to/claude-export.zip --out out --year 2025 --redact
open out/report.html
open out/share.svg
```

## Common options
```bash
# All time
python3 -m yywc --export chatgpt-export.zip --out out --redact

# Keep extracted files in a folder you control (otherwise it uses a temp dir)
python3 -m yywc --export chatgpt-export.zip --extract-dir ./extracted --out out

# Only include user+assistant messages (skip system/tool)
python3 -m yywc --export chatgpt-export.zip --out out --role-scope user,assistant
```

## Notes

- **Claude exports** don't include model information, so the "Top Models" section will be empty for Claude data.
- The tool auto-detects the export format based on the JSON structure.

## PNG export (optional)
If you want a PNG (for platforms that dislike SVG), with ImageMagick:
```bash
cd out
magick -density 144 share.svg -background none share.png
```

Or:
```bash
rsvg-convert -w 1200 -h 900 -o share.png share.svg
```

## Example input
There’s a tiny example export at `examples/sample_export/conversations.json`.
```bash
python3 -m yywc --export examples/sample_export --out out_example --year 2025
open out_example/report.html
```


