# pdf2kindle

> **Note:** This tool was AI-generated. It applies best-effort heuristics that
> won't work perfectly on every PDF. Review the intermediate Markdown before
> converting. Use at your own risk.

Convert PDFs to Kindle-optimized EPUBs.

## Prerequisites

```bash
brew install poppler pandoc uv
```

Python 3.11+ is also required (ships with macOS). If `pdftotext` or `pandoc`
are missing, the script will offer to install them via Homebrew.

For PDFs with custom font encodings (garbled text output), Tesseract OCR is
used as an automatic fallback:

```bash
brew install tesseract
```

Install the Python dependencies (includes `epubcheck` for EPUB validation):

```bash
uv sync
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
5. `qa_epub.py` runs deterministic validation checks against the final EPUB and
   reports any issues before you transfer to Kindle

If the extracted text looks garbled (common with PDFs that use custom font
encodings), the script automatically falls back to Tesseract OCR. You can also
force OCR with `--ocr`.

Output files are written to the current working directory.

## Tools

### `pdf2kindle.sh`

Main conversion script. Orchestrates extraction → review → EPUB build →
validation. See the [Usage](#usage) section for options.

### `extract.py`

Standalone text extraction and cleanup script. Called by `pdf2kindle.sh` but
can be run directly:

```bash
python3 extract.py [--layout] [--ocr] [-t TITLE] [-a AUTHOR] [-o output.md] input.pdf
```

Heuristics applied: soft-hyphen removal, dehyphenation, repeated line
(header/footer) detection, page-number stripping, TOC dot-leader removal,
heading detection (numbered headings + ALL CAPS), paragraph rejoining.

### `build_hybrid_markdown.py`

Advanced builder for visual-heavy PDFs (annual reports, data-rich documents).
Produces a hybrid Markdown file that combines reflowable text with embedded
rendered page images for pages that are primarily charts, maps, or tables.

```bash
python3 build_hybrid_markdown.py \
  --title "My Report" --author "Jane Doe" \
  --image-dir images --image-prefix page \
  [--section PAGE:TITLE ...] \
  [--skip-pages RANGE ...] \
  [--toc-pages RANGE ...] \
  -o output.md input.pdf
```

| Option | Description |
|--------|-------------|
| `--image-dir DIR` | Relative path (used in Markdown) to pre-rendered page images |
| `--image-prefix PREFIX` | Filename prefix for page images (default: `page`) |
| `--section PAGE:TITLE` | Insert a `# TITLE` heading before the given page number |
| `--skip-pages RANGE` | Pages or ranges to omit entirely (e.g. `1-3,7`) |
| `--toc-pages RANGE` | Pages where TOC dot-leader lines should be dropped |

Pages are classified automatically as *visual-heavy* based on alpha/digit
ratios, line-length distribution, and chart/map markers. Visual-heavy pages are
replaced by embedded `<img>` tags pointing to pre-rendered JPEGs; text pages
are reflowed normally.

Typical workflow for visual PDFs:

```bash
# 1. Pre-render all pages to JPEG (requires pdftoppm from poppler)
mkdir -p images
pdftoppm -jpeg -r 150 report.pdf images/page

# 2. Build hybrid Markdown
python3 build_hybrid_markdown.py \
  --title "Annual Report 2024" --author "ASER" \
  --image-dir images --image-prefix page \
  --section 5:"Introduction" --section 12:"Results" \
  --toc-pages 2-4 --skip-pages 1 \
  -o report.md report.pdf

# 3. Convert to EPUB
pandoc report.md -o report.epub \
  --css=kindle.css --split-level=1 --toc --toc-depth=3 \
  --metadata title="Annual Report 2024" \
  --metadata creator="ASER" --metadata lang="en"
```

### `qa_epub.py`

Deterministic EPUB quality-assurance checker. Run automatically by
`pdf2kindle.sh` after every build, or invoke directly:

```bash
uv run python qa_epub.py output.epub [--source-md output.md]
```

Checks performed:

| Check | Description |
|-------|-------------|
| EPUBCheck validation | W3C schema conformance via the `epubcheck` Python package |
| Archive integrity | ZIP validity, `mimetype`, `META-INF/container.xml` present |
| Package/manifest | Spine itemrefs resolve to manifest items |
| Navigation | Nav document exists, is parseable, contains links |
| Internal links | All `href` targets and fragment anchors resolve |
| Images | All `<img src>` targets exist in the archive |
| Stylesheets | CSS files are linked and present in the archive |
| Placeholder text | Fallback marker strings are not left in final output |
| Split URLs | URLs broken across lines are flagged |

Output follows the `CONVERSION_QA_CHECKLIST.md` format: failed items only,
with evidence, impact, and suggested fix. Exit code `0` = all clear;
`1` = issues found.

### `kindle.css`

Stylesheet embedded in every generated EPUB. Optimised for e-ink readability:
`font-size`, `line-height`, `margin` tuning, and `.visual-page` rules that
constrain preserved page images to fit Kindle screen widths.

## Markdown Cleanup Tips

PDFs vary widely. After the script pauses, open the `.md` file and check:

- **Headings** — promote/demote `##`/`###` as needed
- **Paragraphs** — fix incorrectly joined or split lines
- **Callout boxes** — wrap in `>` blockquote syntax
- **Lists** — numbered/bulleted lists may need reformatting
- **Artifacts** — remove garbled characters or stray symbols

## QA Checklist

`CONVERSION_QA_CHECKLIST.md` is the mandatory go/no-go gate used by the agent
for every conversion. It covers preflight, extraction sanity, structural
quality, artifact cleanup, navigation, metadata, technical validity, and
reading-quality spot-checks. `qa_epub.py` automates the deterministic subset;
the structural and reading-quality sections require human review.
