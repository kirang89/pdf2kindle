#!/usr/bin/env python3
"""
Build a reflow-friendly Markdown file from a PDF and append a visual appendix
that embeds rendered page images.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from typing import Iterable

from extract import dehyphenate, detect_repeated_lines, is_page_number, is_toc_line, strip_soft_hyphens


HEADER_RE = re.compile(
    r"^(?:Annual Status of Education Report 2024(?: \| \d+\|?)?|\d+ \| Annual Status of Education Report 2024(?: \|)?)$"
)


def parse_page_set(specs: list[str]) -> set[int]:
    pages: set[int] = set()
    for spec in specs:
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                start_s, end_s = part.split("-", 1)
                start = int(start_s)
                end = int(end_s)
                if end < start:
                    start, end = end, start
                pages.update(range(start, end + 1))
            else:
                pages.add(int(part))
    return pages


def parse_sections(specs: list[str]) -> dict[int, str]:
    sections: dict[int, str] = {}
    for spec in specs:
        if ":" not in spec:
            raise ValueError(f"Invalid --section value: {spec!r}")
        page_s, title = spec.split(":", 1)
        sections[int(page_s)] = title.strip()
    return sections


def extract_pages(pdf_path: str) -> list[str]:
    cmd = ["pdftotext", "-enc", "UTF-8", pdf_path, "-"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    raw = strip_soft_hyphens(dehyphenate(result.stdout))
    pages = raw.split("\f")
    while pages and not pages[-1].strip():
        pages.pop()
    return pages


def normalize_line(line: str) -> str:
    line = line.replace("\x02", "fi")
    line = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", line)
    return re.sub(r"\s+", " ", line.strip())


def normalize_title_key(line: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", line.lower()).strip()


def clean_page_lines(
    page_text: str,
    repeated_lines: set[str],
    drop_toc_lines: bool,
) -> list[str]:
    cleaned: list[str] = []
    for raw_line in page_text.splitlines():
        line = normalize_line(raw_line)
        if not line:
            cleaned.append("")
            continue
        if line in repeated_lines:
            continue
        if HEADER_RE.match(line):
            continue
        if is_page_number(line):
            continue
        if drop_toc_lines and is_toc_line(line):
            continue
        if re.fullmatch(r"[%\d.,()\-–—/*+ ]+", line):
            continue
        if len(line.split()) <= 2 and sum(ch.isdigit() for ch in line) >= 2 and sum(ch.isalpha() for ch in line) <= 2:
            continue
        cleaned.append(line)
    return collapse_blank_lines(cleaned)


def collapse_blank_lines(lines: Iterable[str]) -> list[str]:
    out: list[str] = []
    blank = False
    for line in lines:
        if line:
            out.append(line)
            blank = False
        elif not blank:
            out.append("")
            blank = True
    while out and not out[0]:
        out.pop(0)
    while out and not out[-1]:
        out.pop()
    return out


def is_display_line(line: str) -> bool:
    words = line.split()
    if not words or len(words) > 8:
        return False
    if line.endswith((".", "!", "?", ";")):
        return False
    if "http://" in line or "https://" in line:
        return False
    if sum(ch.isalpha() for ch in line) < 3:
        return False
    return line[:1].isupper() or line.isupper()


def is_reference_line(line: str) -> bool:
    return bool(
        "http://" in line
        or "https://" in line
        or re.match(r"^[A-Z][^.]{0,120}\(\d{4}\)", line)
        or re.match(r"^\d+\s*$", line)
    )


def is_prose_line(line: str) -> bool:
    words = line.split()
    if len(words) < 6:
        return False
    if is_reference_line(line):
        return False
    if line.isupper():
        return False
    return sum(ch.isalpha() for ch in line) >= 20


def paragraphize_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        if not line:
            if out and out[-1]:
                out.append("")
            continue

        if out and out[-1]:
            prev = out[-1]
            paragraph_break = (
                is_prose_line(prev)
                and is_prose_line(line)
                and prev.endswith((".", "!", "?", '."', "!”", "?”", ":"))
                and line[:1].isupper()
                and not re.match(r"^(?:and|but|or|so|because|however|therefore)\b", line, re.I)
            )
            if paragraph_break:
                out.append("")
            elif is_display_line(prev) and is_prose_line(line):
                out.append("")
            elif is_reference_line(line) and prev:
                out.append("")

        out.append(line)

    return collapse_blank_lines(out)


def repair_split_urls(lines: list[str]) -> list[str]:
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line:
            out.append(line)
            i += 1
            continue

        line = re.sub(r"(https?://)\s+", r"\1", line)
        line = re.sub(r"(https?://\S+?)(Walker,\s)", r"\1\n\n\2", line)
        line = re.sub(r"(https?://\S+?)(ICAN is\b)", r"\1\n\n\2", line)
        line = re.sub(r"(https?://\S+?)(Fiszbein,\s)", r"\1\n\n\2", line)
        line = re.sub(r"(https?://\S+?)(Goal 4 \|)", r"\1\n\n\2", line)
        line = re.sub(r"(https?://\S+?)(Learning Progression Explorer:)", r"\1\n\n\2", line)
        line = re.sub(r"(https?://\S+?)(ASER Survey -)", r"\1\n\n\2", line)

        if i + 1 < len(lines):
            nxt = lines[i + 1]
            if line.rstrip().endswith("/") and nxt and re.match(r"^[A-Za-z0-9%_.#?=&/-]+$", nxt):
                out.append(line + nxt)
                i += 2
                continue
            if "http://" in line or "https://" in line:
                joined = f"{line} {nxt}".strip()
                joined = re.sub(r"(https?://)\s+", r"\1", joined)
                joined = re.sub(r"(https?://\S+)\s+([A-Za-z0-9%_.#?=&/-]+(?:/[A-Za-z0-9%_.#?=&/-]*)*)", r"\1\2", joined)
                if joined != f"{line} {nxt}".strip():
                    out.append(joined)
                    i += 2
                    continue

        out.append(line)
        i += 1

    return out


def is_heading_candidate(line: str) -> bool:
    if len(line) > 90 or len(line.split()) > 12:
        return False
    if line.endswith((".", ",", ";")):
        return False
    if re.search(r"\d \| ", line):
        return False
    if sum(ch.isalpha() for ch in line) < 4:
        return False
    return True


def join_paragraphs(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        if not line:
            if out and out[-1]:
                out.append("")
            continue
        if out and out[-1]:
            prev = out[-1]
            new_item = bool(
                line.startswith(("-", "*", "•", "■"))
                or re.match(r"^\d+[.)]\s", line)
                or re.match(r"^[A-Za-z][.)]\s", line)
            )
            short_heading = is_heading_candidate(line) and prev == ""
            if (
                not new_item
                and not short_heading
                and not is_display_line(prev)
                and not is_display_line(line)
                and not is_reference_line(prev)
                and not is_reference_line(line)
                and not prev.endswith((".", "!", "?", ":", ";", '"', "'", ")"))
            ):
                out[-1] = f"{prev} {line}"
                continue
        out.append(line)
    return collapse_blank_lines(out)


def is_visual_heavy(lines: list[str]) -> bool:
    nonblank = [line for line in lines if line]
    if not nonblank:
        return True
    alpha = sum(sum(ch.isalpha() for ch in line) for line in nonblank)
    digits = sum(sum(ch.isdigit() for ch in line) for line in nonblank)
    chars = sum(len(line.replace(" ", "")) for line in nonblank)
    long_lines = sum(1 for line in nonblank if len(line.split()) >= 6)
    short_lines = sum(1 for line in nonblank if len(line.split()) <= 2)
    very_short_lines = sum(1 for line in nonblank if len(line.split()) <= 4)
    table_or_chart_lines = sum(
        1
        for line in nonblank
        if line.startswith("Table ") or line.startswith("Chart ")
    )
    rural_marker_lines = sum(1 for line in nonblank if line.endswith(" RURAL"))
    url_lines = sum(1 for line in nonblank if "http://" in line or "https://" in line)
    alpha_ratio = alpha / max(chars, 1)
    digit_ratio = digits / max(chars, 1)
    return (
        alpha_ratio < 0.45
        or (digit_ratio > 0.25 and long_lines < 8)
        or (short_lines > long_lines * 2 and long_lines < 10)
        or (digit_ratio > 0.12 and very_short_lines > 18 and long_lines < 18)
        or (table_or_chart_lines >= 1 and digit_ratio > 0.02)
        or (table_or_chart_lines >= 1 and long_lines < 28)
        or (rural_marker_lines >= 1 and digit_ratio > 0.08 and long_lines < 22)
        or (url_lines >= 2 and long_lines < 28)
    )


def has_url_content(lines: list[str]) -> bool:
    return any("http://" in line or "https://" in line for line in lines)


def extract_image_page_stats(pdf_path: str) -> dict[int, tuple[int, int]]:
    cmd = ["pdfimages", "-list", pdf_path]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    stats: dict[int, tuple[int, int]] = {}
    for raw_line in result.stdout.splitlines()[2:]:
        parts = raw_line.split()
        if len(parts) < 6 or not parts[0].isdigit() or not parts[3].isdigit() or not parts[4].isdigit():
            continue
        page = int(parts[0])
        width = int(parts[3])
        height = int(parts[4])
        area = width * height
        total_area, max_area = stats.get(page, (0, 0))
        stats[page] = (total_area + area, max(max_area, area))
    return stats


def is_image_dominant_page(lines: list[str], image_stats: dict[int, tuple[int, int]], page_number: int) -> bool:
    total_area, max_area = image_stats.get(page_number, (0, 0))
    if max_area < 900000:
        return False

    nonblank = [line for line in lines if line]
    alpha = sum(sum(ch.isalpha() for ch in line) for line in nonblank)
    long_lines = sum(1 for line in nonblank if len(line.split()) >= 6)
    total_words = sum(len(line.split()) for line in nonblank)

    return (
        len(nonblank) <= 3
        and long_lines <= 1
        and total_words <= 12
        and (alpha <= 160 or (alpha <= 220 and total_area > 1300000))
    )


TABULAR_MARKER_RE = re.compile(
    r"(?:% children|year|govt\+?pvt|govt|pvt|std\b|no schooling|above std|i-v|vi-viii|\b2018\b|\b2022\b|\b2024\b)",
    re.I,
)


def is_map_like_page(lines: list[str]) -> bool:
    nonblank = [line for line in lines if line]
    if len(nonblank) < 40:
        return False

    long_lines = sum(1 for line in nonblank if len(line.split()) >= 6)
    short_lines = sum(1 for line in nonblank if len(line.split()) <= 3)
    alpha = sum(sum(ch.isalpha() for ch in line) for line in nonblank)
    tabular_markers = sum(1 for line in nonblank if TABULAR_MARKER_RE.search(line))
    short_ratio = short_lines / max(len(nonblank), 1)

    return (
        alpha >= 1500
        and long_lines <= 8
        and short_ratio >= 0.82
        and tabular_markers <= 4
    )


def make_yaml(title: str, author: str, lang: str) -> str:
    def esc(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    return (
        "---\n"
        f'title: "{esc(title)}"\n'
        f'author: "{esc(author)}"\n'
        f'lang: {lang}\n'
        "---\n\n"
    )


def has_large_rendered_page(image_dir: str, image_prefix: str, page_number: int, min_size: int = 150_000) -> bool:
    path = os.path.join(image_dir, f"{image_prefix}-{page_number:03d}.jpg")
    try:
        return os.path.getsize(path) >= min_size
    except OSError:
        return False


def build_markdown(
    pdf_path: str,
    pages: list[str],
    sections: dict[int, str],
    skip_pages: set[int],
    toc_pages: set[int],
    image_dir: str,
    image_prefix: str,
) -> str:
    repeated = detect_repeated_lines(pages)
    image_page_stats = extract_image_page_stats(pdf_path)
    out: list[str] = []

    def add_page_image(page_number: int) -> None:
        rel_path = os.path.join(image_dir, f"{image_prefix}-{page_number:03d}.jpg")
        out.append(
            f'<div class="visual-page"><p><strong>Original PDF page {page_number}</strong></p><img src="{rel_path}" alt="Original PDF page {page_number}" /></div>'
        )
        out.append("")

    for index, page_text in enumerate(pages, start=1):
        if index in skip_pages:
            continue

        title = sections.get(index)
        if title:
            out.append(f"# {title}")
            out.append("")

        cleaned = clean_page_lines(
            page_text=page_text,
            repeated_lines=repeated,
            drop_toc_lines=index in toc_pages,
        )
        cleaned = repair_split_urls(cleaned)
        cleaned = join_paragraphs(cleaned)
        cleaned = paragraphize_lines(cleaned)
        if title and cleaned and normalize_title_key(cleaned[0]) == normalize_title_key(title):
            cleaned = collapse_blank_lines(cleaned[1:])

        if not cleaned:
            if has_large_rendered_page(image_dir, image_prefix, index):
                add_page_image(index)
            continue

        if is_image_dominant_page(cleaned, image_page_stats, index) or is_map_like_page(cleaned):
            add_page_image(index)
            continue

        out.extend(cleaned)
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build hybrid markdown with a visual appendix.")
    parser.add_argument("pdf", help="Input PDF path")
    parser.add_argument("-o", "--output", required=True, help="Output Markdown path")
    parser.add_argument("--title", required=True, help="Document title")
    parser.add_argument("--author", required=True, help="Document author")
    parser.add_argument("--lang", default="en", help="Document language")
    parser.add_argument("--image-dir", required=True, help="Relative image directory used in Markdown")
    parser.add_argument("--image-prefix", default="page", help="Rendered image file prefix")
    parser.add_argument("--section", action="append", default=[], help="Section marker in PAGE:TITLE form")
    parser.add_argument("--skip-pages", action="append", default=[], help="Pages or page ranges to omit from reflow text")
    parser.add_argument("--toc-pages", action="append", default=[], help="Pages or page ranges where TOC dot-leader lines should be dropped")
    args = parser.parse_args()

    if not os.path.isfile(args.pdf):
        print(f"Error: file not found: {args.pdf}", file=sys.stderr)
        return 1

    try:
        sections = parse_sections(args.section)
        skip_pages = parse_page_set(args.skip_pages)
        toc_pages = parse_page_set(args.toc_pages)
        pages = extract_pages(args.pdf)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    markdown = make_yaml(args.title, args.author, args.lang) + build_markdown(
        pdf_path=args.pdf,
        pages=pages,
        sections=sections,
        skip_pages=skip_pages,
        toc_pages=toc_pages,
        image_dir=args.image_dir,
        image_prefix=args.image_prefix,
    )

    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(markdown)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
