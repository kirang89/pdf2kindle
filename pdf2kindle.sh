#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CSS_FILE="$SCRIPT_DIR/kindle.css"

# Defaults
TITLE=""
AUTHOR=""
NO_PAUSE=false
KEEP_MD=false
USE_LAYOUT=false
USE_OCR=false

usage() {
    cat <<'EOF'
Usage: pdf2kindle.sh [options] input.pdf [output.epub]

Convert a PDF to a Kindle-optimized EPUB.

Options:
  --title TEXT      Set the book title (default: PDF filename)
  --author TEXT     Set the author name (default: "Unknown")
  --no-pause        Skip the manual review step
  --keep-md         Keep the intermediate Markdown file
  --layout          Use spatial layout mode (for single-column PDFs)
  --ocr             Force OCR via Tesseract (for scanned/garbled PDFs)
  -h, --help        Show this help message

Steps:
  1. Extracts text from the PDF
  2. Applies cleanup heuristics to produce a Markdown file
  3. Pauses for you to review/edit the Markdown (unless --no-pause)
  4. Converts Markdown to EPUB with Kindle-optimized CSS

Dependencies: pdftotext (poppler), pandoc, python3
EOF
    exit 0
}

# --- Parse arguments ---
POSITIONAL=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --title)   [[ $# -ge 2 ]] || { echo "Error: --title requires a value" >&2; exit 1; }; TITLE="$2"; shift 2 ;;
        --author)  [[ $# -ge 2 ]] || { echo "Error: --author requires a value" >&2; exit 1; }; AUTHOR="$2"; shift 2 ;;
        --no-pause) NO_PAUSE=true; shift ;;
        --keep-md)  KEEP_MD=true; shift ;;
        --layout)   USE_LAYOUT=true; shift ;;
        --ocr)      USE_OCR=true; shift ;;
        -h|--help)  usage ;;
        -*)         echo "Unknown option: $1" >&2; exit 1 ;;
        *)          POSITIONAL+=("$1"); shift ;;
    esac
done

if [[ ${#POSITIONAL[@]} -lt 1 ]]; then
    echo "Error: no input PDF specified." >&2
    echo "Run with --help for usage." >&2
    exit 1
fi

INPUT_PDF="${POSITIONAL[0]}"
BASENAME="$(basename "${INPUT_PDF%.pdf}")"

if [[ ${#POSITIONAL[@]} -ge 2 ]]; then
    OUTPUT_EPUB="${POSITIONAL[1]}"
else
    OUTPUT_EPUB="${BASENAME}.epub"
fi

MD_FILE="${BASENAME}.md"

# Default title to filename if not set
if [[ -z "$TITLE" ]]; then
    TITLE="$BASENAME"
fi
if [[ -z "$AUTHOR" ]]; then
    AUTHOR="Unknown"
fi

# --- Check dependencies ---
missing=()
brew_install=()
command -v pdftotext >/dev/null 2>&1 || { missing+=("pdftotext"); brew_install+=("poppler"); }
command -v pandoc    >/dev/null 2>&1 || { missing+=("pandoc"); brew_install+=("pandoc"); }
command -v python3   >/dev/null 2>&1 || missing+=("python3")

if [[ ${#missing[@]} -gt 0 ]]; then
    echo "Missing dependencies: ${missing[*]}" >&2
    if [[ ${#brew_install[@]} -gt 0 ]] && command -v brew >/dev/null 2>&1; then
        read -rp "Install via Homebrew (brew install ${brew_install[*]})? [Y/n] " answer
        if [[ -z "$answer" || "$answer" =~ ^[Yy] ]]; then
            if ! brew install "${brew_install[@]}"; then
                echo "Error: brew install failed." >&2
                exit 1
            fi
        else
            exit 1
        fi
    else
        echo "Install them manually:" >&2
        [[ " ${missing[*]} " == *" pdftotext "* ]] && echo "  brew install poppler" >&2
        [[ " ${missing[*]} " == *" pandoc "* ]]    && echo "  brew install pandoc" >&2
        [[ " ${missing[*]} " == *" python3 "* ]]   && echo "  python3 is required (ships with macOS or install via brew)" >&2
        exit 1
    fi
fi

if [[ ! -f "$INPUT_PDF" ]]; then
    echo "Error: file not found: $INPUT_PDF" >&2
    exit 1
fi

# --- Step 1: Extract and clean text ---
echo "==> Step 1: Extracting text from PDF..."
EXTRACT_ARGS=("$INPUT_PDF" -o "$MD_FILE" -t "$TITLE" -a "$AUTHOR")
[[ "$USE_LAYOUT" = true ]] && EXTRACT_ARGS+=(--layout)
[[ "$USE_OCR" = true ]]    && EXTRACT_ARGS+=(--ocr)
python3 "$SCRIPT_DIR/extract.py" "${EXTRACT_ARGS[@]}"

# --- Step 2: Manual review ---
if [[ "$NO_PAUSE" = false ]]; then
    echo ""
    echo "==> Step 2: Review the generated Markdown"
    echo "    File: $MD_FILE"
    echo ""
    echo "    Open it in your editor and fix any structural issues:"
    echo "    - Check heading levels (# / ## / ###)"
    echo "    - Fix paragraph breaks that were split incorrectly"
    echo "    - Wrap callout boxes in > blockquotes"
    echo "    - Remove any leftover artifacts"
    echo ""
    read -rp "    Press Enter when done editing (or Ctrl-C to abort)... "
fi

# --- Step 3: Convert to EPUB ---
echo ""
echo "==> Step 3: Converting Markdown to EPUB..."

pandoc "$MD_FILE" -o "$OUTPUT_EPUB" \
    --css="$CSS_FILE" \
    --split-level=1 \
    --toc \
    --toc-depth=3 \
    --metadata title="$TITLE" \
    --metadata creator="$AUTHOR" \
    --metadata lang="en"

echo ""
echo "Done! EPUB written to: $OUTPUT_EPUB"
echo "  Transfer to Kindle via USB or Send to Kindle."

# --- Cleanup ---
if [[ "$KEEP_MD" = true ]]; then
    echo "  Markdown file kept: $MD_FILE"
elif [[ "$NO_PAUSE" = true ]]; then
    rm -f "$MD_FILE"
else
    echo "  Markdown file kept: $MD_FILE"
fi
