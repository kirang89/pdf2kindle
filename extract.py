#!/usr/bin/env python3
"""
extract.py — PDF text extraction + cleanup heuristics.

Extracts text from a PDF using pdftotext -layout, then applies heuristics
to produce a Markdown file ready for quick manual review before EPUB conversion.
"""

import argparse
import os
import re
import subprocess
import sys
from collections import Counter


def extract_text(pdf_path):
    """Run pdftotext -layout and return raw text."""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", "-enc", "UTF-8", pdf_path, "-"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout
    except FileNotFoundError:
        print("Error: pdftotext not found. Install poppler:", file=sys.stderr)
        print("  brew install poppler", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Error running pdftotext: {e.stderr}", file=sys.stderr)
        sys.exit(1)


def dehyphenate(text):
    """Rejoin words split across lines with a trailing hyphen.

    "infra-\\nstructure" → "infrastructure"
    Conservative: preserves hyphens in compound words (self-service,
    co-operate) and never touches URLs.
    """
    # Common compound-word prefixes — keep the hyphen for these
    COMPOUND_PREFIXES = {
        "anti", "co", "counter", "cross", "e", "ex", "multi", "non",
        "post", "pre", "re", "self", "semi", "sub", "well", "world",
    }

    def _rejoin(m):
        prefix = m.group(1)
        suffix = m.group(2)
        full_line_before = text[max(0, m.start() - 200):m.start()]

        # Never dehyphenate inside URLs
        if re.search(r"https?://\S*$", full_line_before):
            return m.group(0)

        # Keep hyphen for known compound-word prefixes
        if prefix.lower() in COMPOUND_PREFIXES:
            return prefix + "-" + suffix

        # Only remove hyphen if both parts are lowercase (syllable break)
        if prefix[-1:].islower() and suffix[0:1].islower():
            return prefix + suffix

        return prefix + "-" + suffix

    return re.sub(r"(\w+)-\s*\n\s*(\w+)", _rejoin, text)


def strip_soft_hyphens(text):
    """Remove Unicode soft hyphens (U+00AD) that break display/search."""
    return text.replace("\u00ad", "")


def is_toc_line(line):
    """Detect table-of-contents lines with dot leaders (e.g. 'Chapter 1 ...... 5')."""
    return bool(re.match(r"^.{3,}\s*[.·]{4,}\s*\d+\s*$", line.strip()))


def split_pages(raw_text):
    """Split raw text into pages (pdftotext uses form-feed characters)."""
    return raw_text.split("\f")


def detect_repeated_lines(pages, threshold=0.4):
    """
    Find lines that repeat across many pages — likely headers/footers.
    A line appearing on more than `threshold` fraction of pages is flagged.
    """
    if len(pages) < 3:
        return set()

    line_counts = Counter()
    for page in pages:
        # Use a set so each line counts once per page
        unique_lines = set()
        for line in page.strip().splitlines():
            stripped = line.strip()
            if stripped:
                unique_lines.add(stripped)
        for line in unique_lines:
            line_counts[line] += 1

    min_count = max(3, int(len(pages) * threshold))
    return {line for line, count in line_counts.items() if count >= min_count}


def is_page_number(line):
    """Check if a line is just a standalone page number."""
    # Strip whitespace and common PDF font artifacts:
    #   U+F07C = Wingdings vertical bar, U+F0A7 = Wingdings bullet,
    #   U+F0B7 = Wingdings filled bullet — often used as page decorations.
    stripped = re.sub(r"[\s\uf07c\uf0a7\uf0b7]", "", line)
    if re.match(r"^\d{1,4}$", stripped):
        return True
    stripped = line.strip()
    # Patterns like "Page 5" or "- 5 -" or "| 5"
    if re.match(r"^[-|]?\s*(page\s*)?\d{1,4}\s*[-|]?$", stripped, re.IGNORECASE):
        return True
    return False


def is_likely_heading(line, prev_blank, next_blank):
    """
    Heuristic: a line is likely a heading if it's:
    - Short (under 80 chars)
    - Surrounded by blank lines (or at start)
    - Optionally numbered like "1 Title" or "1.2 Title"
    - Not ending with typical sentence punctuation
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 80:
        return False, 0

    if not (prev_blank or next_blank):
        return False, 0

    # Numbered heading: "1 Title" or "1.2.3 Title"
    # Require the text after the number to start with an uppercase letter,
    # which avoids false positives like "3 January 2024" or "100 people attended".
    num_match = re.match(r"^(\d+(?:\.\d+)*)\s+([A-Z].+)$", stripped)
    if num_match:
        number = num_match.group(1)
        text_part = num_match.group(2)
        depth = number.count(".") + 1
        # Skip if it looks like a sentence (ends with punctuation) or is too long
        if (
            depth <= 3
            and len(text_part) <= 60
            and not stripped.endswith((".", ",", ";", ":"))
        ):
            return True, min(depth, 3)

    # ALL CAPS short line (common heading style in PDFs)
    if stripped.isupper() and len(stripped) > 3 and prev_blank:
        return True, 1

    return False, 0


def cleanup_text(raw_text):
    """
    Apply cleanup heuristics to raw pdftotext output.
    Returns cleaned Markdown text.
    """
    # Pre-processing: fix encoding artifacts before splitting
    raw_text = strip_soft_hyphens(raw_text)
    raw_text = dehyphenate(raw_text)

    pages = split_pages(raw_text)
    repeated = detect_repeated_lines(pages)

    # Flatten all pages into lines, stripping headers/footers/page numbers/TOC
    all_lines = []
    for page in pages:
        for line in page.splitlines():
            stripped = line.strip()
            if stripped in repeated:
                continue
            if is_page_number(line):
                continue
            if is_toc_line(line):
                continue
            all_lines.append(line)
        # Add a blank line at page boundaries
        all_lines.append("")

    # Second pass: detect headings, collapse blanks, build markdown
    md_lines = []
    i = 0
    consecutive_blanks = 0

    while i < len(all_lines):
        line = all_lines[i]
        stripped = line.strip()

        # Handle blank lines — collapse runs of 3+ into 2
        if not stripped:
            consecutive_blanks += 1
            if consecutive_blanks <= 2:
                md_lines.append("")
            i += 1
            continue

        prev_blank = consecutive_blanks > 0 or i == 0
        next_blank = (i + 1 >= len(all_lines)) or not all_lines[i + 1].strip()
        consecutive_blanks = 0

        # Try heading detection
        is_heading, depth = is_likely_heading(line, prev_blank, next_blank)
        if is_heading:
            prefix = "#" * (depth + 1)  # h2 for depth=1, h3 for depth=2, etc.
            # Remove the numbering prefix for cleaner headings
            text = re.sub(r"^\d+(?:\.\d+)*\s+", "", stripped)
            if text.isupper():
                text = text.title()
            md_lines.append(f"\n{prefix} {text}\n")
            i += 1
            continue

        # Rejoin lines that look like they're part of the same paragraph.
        # Guard against merging lines that start new items: bullets, numbered
        # items, lettered lists like "a)", or lines with significant indentation.
        looks_like_new_item = (
            stripped.startswith(("-", "*", "\u2022"))
            or re.match(r"^\d+[.)]\s", stripped)
            or re.match(r"^[a-z][.)]\s", stripped)
        )
        prev_is_joinable = (
            md_lines
            and md_lines[-1].strip()
            and not md_lines[-1].strip().startswith("#")
        )
        if (
            not prev_blank
            and prev_is_joinable
            and not looks_like_new_item
        ):
            # Check if previous line ended mid-sentence (no terminal punctuation)
            prev = md_lines[-1].rstrip()
            if prev and not prev.endswith((".", "!", "?", ":", '"', "'", ")")):
                md_lines[-1] = prev + " " + stripped
                i += 1
                continue

        md_lines.append(stripped)
        i += 1

    return "\n".join(md_lines)


def yaml_escape(value):
    """Escape a string for safe inclusion in YAML double-quoted scalars."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


def build_markdown(cleaned_text, title="Untitled", author="Unknown"):
    """Wrap cleaned text in Markdown with YAML front matter."""
    front_matter = f"""---
title: "{yaml_escape(title)}"
author: "{yaml_escape(author)}"
lang: en
---

"""
    return front_matter + cleaned_text


def main():
    parser = argparse.ArgumentParser(
        description="Extract text from a PDF and produce a cleaned Markdown file."
    )
    parser.add_argument("pdf", help="Input PDF file path")
    parser.add_argument("-o", "--output", help="Output Markdown file path")
    parser.add_argument("-t", "--title", default="Untitled", help="Document title")
    parser.add_argument("-a", "--author", default="Unknown", help="Document author")

    args = parser.parse_args()

    if not os.path.isfile(args.pdf):
        print(f"Error: file not found: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    # Default output name: same as PDF but .md
    if args.output:
        out_path = args.output
    else:
        base = os.path.splitext(os.path.basename(args.pdf))[0]
        out_path = base + ".md"

    print(f"Extracting text from: {args.pdf}")
    raw = extract_text(args.pdf)

    print("Applying cleanup heuristics...")
    cleaned = cleanup_text(raw)

    md = build_markdown(cleaned, title=args.title, author=args.author)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"Markdown written to: {out_path}")
    line_count = md.count("\n") + 1
    print(f"  ({line_count} lines — review and edit before converting to EPUB)")


if __name__ == "__main__":
    main()
