# pdf2kindle

> **Note:** This tool was AI-generated. It applies best-effort heuristics that
> won't work perfectly on every PDF. Review the intermediate Markdown before
> converting. Use at your own risk.

Convert PDFs to Kindle-optimized EPUBs.

## Prerequisites

```bash
brew install poppler pandoc
```

Python 3 is also required (ships with macOS). If dependencies are missing, the
script will offer to install them via Homebrew.

For PDFs with custom font encodings (garbled text output), Tesseract OCR is
used as an automatic fallback:

```bash
brew install tesseract
```

## Usage

```bash
chmod +x pdf2kindle.sh
./pdf2kindle.sh [options] input.pdf [output.epub]
```

**Options:**

| Flag | Description |
|------|-------------|
| `--title TEXT` | Book title (default: filename) |
| `--author TEXT` | Author name |
| `--no-pause` | Skip the manual review step |
| `--keep-md` | Keep the intermediate Markdown file |
| `--layout` | Use spatial layout mode (for single-column PDFs) |
| `--ocr` | Force OCR extraction via Tesseract |

**Examples:**

```bash
# Basic conversion with manual review step
./pdf2kindle.sh report.pdf

# Set metadata, keep the markdown, custom output name
./pdf2kindle.sh --title "My Report" --author "Jane Doe" --keep-md report.pdf out.epub

# Fully automated (skip review)
./pdf2kindle.sh --no-pause --title "Quick Read" paper.pdf

# Force OCR for a scanned or garbled PDF
./pdf2kindle.sh --ocr --title "Scanned Doc" scan.pdf
```

## How It Works

1. `pdftotext` extracts text in reading order (handles multi-column layouts)
2. `extract.py` cleans up the output: strips repeated headers/footers, removes
   page numbers and TOC lines, collapses blank lines, detects likely headings,
   rejoins split paragraphs, dehyphenates broken words
3. You review and edit the Markdown (the part machines can't reliably automate)
4. `pandoc` converts to EPUB with a Kindle-optimized stylesheet and table of
   contents

If the extracted text looks garbled (common with PDFs that use custom font
encodings), the script automatically falls back to Tesseract OCR. You can also
force OCR with `--ocr`.

Output files are written to the current working directory.

## Markdown Cleanup Tips

PDFs vary widely. After the script pauses, open the `.md` file and check:

- **Headings** — promote/demote `##`/`###` as needed
- **Paragraphs** — fix incorrectly joined or split lines
- **Callout boxes** — wrap in `>` blockquote syntax
- **Lists** — numbered/bulleted lists may need reformatting
- **Artifacts** — remove garbled characters or stray symbols
