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

**Examples:**

```bash
./pdf2kindle.sh report.pdf
./pdf2kindle.sh --title "My Report" --author "Jane Doe" --keep-md report.pdf out.epub
./pdf2kindle.sh --no-pause --title "Quick Read" paper.pdf
```

## How It Works

1. `pdftotext -layout` extracts text preserving spatial layout
2. `extract.py` cleans up the output: strips repeated headers/footers, removes page numbers, collapses blank lines, detects likely headings, rejoins split paragraphs
3. You review and edit the Markdown (the part machines can't reliably automate)
4. `pandoc` converts to EPUB with a Kindle-optimized stylesheet and table of contents

Output files are written to the current working directory.

## Markdown Cleanup Tips

PDFs vary widely. After the script pauses, open the `.md` file and check:

- **Headings** — promote/demote `##`/`###` as needed
- **Paragraphs** — fix incorrectly joined or split lines
- **Callout boxes** — wrap in `>` blockquote syntax
- **Lists** — numbered/bulleted lists may need reformatting
- **Artifacts** — remove garbled characters or stray symbols
