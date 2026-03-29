#!/usr/bin/env python3
"""
Deterministic EPUB QA checks for the pdf2kindle workflow.

Runs two layers of validation:
  1. epubcheck — W3C schema and spec conformance (fatals, errors, warnings).
  2. Local heuristic checks — broken links, placeholder text, split URLs,
     missing images, CSS presence, etc.
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import xml.etree.ElementTree as ET

try:
    from epubcheck import EpubCheck
    _EPUBCHECK_AVAILABLE = True
except ImportError:
    _EPUBCHECK_AVAILABLE = False


NCX_NS = {"opf": "http://www.idpf.org/2007/opf", "xhtml": "http://www.w3.org/1999/xhtml"}
CONTAINER_NS = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}

PLACEHOLDER_RE = re.compile(r"Page \d+ is mainly graphical/tabular in the source PDF", re.I)
SPLIT_URL_RE = re.compile(
    r"https?://\S+\s+(?:www\.|[a-z0-9%_.-]+\.[a-z]{2,}\S*|[a-z0-9%_.-]+/[A-Za-z0-9%_.#?=&/-]+)",
    re.I,
)
SPACE_AFTER_SCHEME_RE = re.compile(r"https?://\s+\S+", re.I)


@dataclass
class Finding:
    section: str
    item: str
    evidence: str
    impact: str
    suggested_fix: str


def add_finding(findings: list[Finding], section: str, item: str, evidence: str, impact: str, suggested_fix: str) -> None:
    findings.append(Finding(section, item, evidence, impact, suggested_fix))


def read_zip_text(zf: zipfile.ZipFile, name: str) -> str:
    return zf.read(name).decode("utf-8")


def strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1]


def parse_xml(data: str) -> ET.Element:
    return ET.fromstring(data)


def normalize_zip_path(base: PurePosixPath, href: str) -> str:
    path = PurePosixPath(href)
    if not path.is_absolute():
        path = base.joinpath(path)
    parts: list[str] = []
    for part in path.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def check_archive(zf: zipfile.ZipFile, findings: list[Finding]) -> None:
    bad_file = zf.testzip()
    if bad_file is not None:
        add_finding(
            findings,
            "Technical EPUB Validity",
            "EPUB opens cleanly without archive/format errors",
            f"Corrupt ZIP member: {bad_file}",
            "technical",
            "Rebuild the EPUB and re-run archive validation.",
        )

    names = set(zf.namelist())
    required = ["mimetype", "META-INF/container.xml"]
    for required_name in required:
        if required_name not in names:
            add_finding(
                findings,
                "Technical EPUB Validity",
                "Required files present (`mimetype`, `META-INF/container.xml`, OPF, nav)",
                f"Missing archive entry: {required_name}",
                "technical",
                "Ensure the EPUB builder emits the standard container files.",
            )


def locate_package(zf: zipfile.ZipFile, findings: list[Finding]) -> tuple[str | None, ET.Element | None]:
    try:
        container_xml = read_zip_text(zf, "META-INF/container.xml")
        container_root = parse_xml(container_xml)
    except Exception as exc:
        add_finding(
            findings,
            "Technical EPUB Validity",
            "Required files present (`mimetype`, `META-INF/container.xml`, OPF, nav)",
            f"Unable to parse META-INF/container.xml: {exc}",
            "technical",
            "Rebuild the EPUB with a valid container.xml file.",
        )
        return None, None

    rootfile = container_root.find(".//c:rootfile", CONTAINER_NS)
    if rootfile is None or not rootfile.get("full-path"):
        add_finding(
            findings,
            "Technical EPUB Validity",
            "Required files present (`mimetype`, `META-INF/container.xml`, OPF, nav)",
            "No package document path found in META-INF/container.xml",
            "technical",
            "Ensure the EPUB container points to a valid OPF package document.",
        )
        return None, None

    opf_path = rootfile.get("full-path")
    try:
        opf_root = parse_xml(read_zip_text(zf, opf_path))
    except Exception as exc:
        add_finding(
            findings,
            "Technical EPUB Validity",
            "Required files present (`mimetype`, `META-INF/container.xml`, OPF, nav)",
            f"Unable to parse OPF package document {opf_path}: {exc}",
            "technical",
            "Rebuild the EPUB with a valid OPF package document.",
        )
        return opf_path, None

    return opf_path, opf_root


def check_package(zf: zipfile.ZipFile, opf_path: str, opf_root: ET.Element, findings: list[Finding]) -> tuple[list[str], str | None]:
    manifest_by_id: dict[str, str] = {}
    nav_href: str | None = None

    for item in opf_root.findall(".//opf:manifest/opf:item", NCX_NS):
        item_id = item.get("id")
        href = item.get("href")
        if item_id and href:
            manifest_by_id[item_id] = href
        if item.get("properties") == "nav" and href:
            nav_href = href

    spine_hrefs: list[str] = []
    for itemref in opf_root.findall(".//opf:spine/opf:itemref", NCX_NS):
        idref = itemref.get("idref")
        if not idref or idref not in manifest_by_id:
            add_finding(
                findings,
                "Technical EPUB Validity",
                "Manifest/spine references are consistent",
                f"Spine itemref points to missing manifest id: {idref}",
                "technical",
                "Ensure all spine entries refer to valid manifest items.",
            )
            continue
        spine_hrefs.append(manifest_by_id[idref])

    if not nav_href:
        add_finding(
            findings,
            "Navigation & TOC Validation",
            "Navigation/TOC opens and is readable",
            "No manifest item with nav property found in OPF.",
            "navigation",
            "Emit an EPUB3 nav document and include it in the manifest.",
        )
        return spine_hrefs, None

    nav_path = normalize_zip_path(PurePosixPath(opf_path).parent, nav_href)
    if nav_path not in zf.namelist():
        add_finding(
            findings,
            "Navigation & TOC Validation",
            "Navigation/TOC opens and is readable",
            f"Nav document missing from archive: {nav_path}",
            "navigation",
            "Ensure the OPF nav item points to a real file in the EPUB.",
        )
        return spine_hrefs, None

    return spine_hrefs, nav_path


def collect_ids(root: ET.Element) -> set[str]:
    ids: set[str] = set()
    for element in root.iter():
        element_id = element.get("id")
        if element_id:
            ids.add(element_id)
    return ids


def check_xhtml_documents(zf: zipfile.ZipFile, opf_path: str, spine_hrefs: list[str], findings: list[Finding]) -> None:
    all_names = set(zf.namelist())
    opf_dir = PurePosixPath(opf_path).parent
    xhtml_docs = [normalize_zip_path(opf_dir, href) for href in spine_hrefs if href.endswith((".xhtml", ".html", ".htm"))]
    doc_ids: dict[str, set[str]] = {}

    css_link_count = 0
    visual_css_seen = False

    for doc_name in xhtml_docs:
        try:
            root = parse_xml(read_zip_text(zf, doc_name))
        except Exception as exc:
            add_finding(
                findings,
                "Technical EPUB Validity",
                "EPUB opens cleanly without archive/format errors",
                f"Unable to parse XHTML content {doc_name}: {exc}",
                "technical",
                "Ensure content documents are well-formed XHTML.",
            )
            continue

        doc_ids[doc_name] = collect_ids(root)
        text = "".join(root.itertext())

        if PLACEHOLDER_RE.search(text):
            add_finding(
                findings,
                "Reading Quality Spot-Check",
                "No obvious extraction/OCR defects in sampled sections",
                f"Placeholder marker left in final content: {doc_name}",
                "readability",
                "Replace fallback placeholder text with real content or inline preserved page images.",
            )

        if SPLIT_URL_RE.search(text) or SPACE_AFTER_SCHEME_RE.search(text):
            add_finding(
                findings,
                "Artifact Cleanup Sweep",
                "Wrapped URLs and broken inline text repaired",
                f"Split URL detected in final text layer: {doc_name}",
                "readability",
                "Normalize wrapped URLs before EPUB generation or preserve the page visually.",
            )

        base_dir = PurePosixPath(doc_name).parent
        for element in root.iter():
            tag = strip_ns(element.tag)
            if tag == "link" and element.get("rel") == "stylesheet":
                css_link_count += 1
                href = element.get("href")
                if href:
                    css_path = normalize_zip_path(base_dir, href)
                    if css_path in all_names:
                        css_text = read_zip_text(zf, css_path)
                        if ".visual-page" in css_text:
                            visual_css_seen = True
                    else:
                        add_finding(
                            findings,
                            "Technical EPUB Validity",
                            "Stylesheets are linked and loading",
                            f"Missing linked stylesheet {href} from {doc_name}",
                            "technical",
                            "Ensure linked CSS files are packaged and correctly referenced.",
                        )

            if tag == "img":
                src = element.get("src")
                if src:
                    img_path = normalize_zip_path(base_dir, src)
                    if img_path not in all_names:
                        add_finding(
                            findings,
                            "Technical EPUB Validity",
                            "No broken internal references/images in sampled chapters",
                            f"Missing image target {src} referenced from {doc_name}",
                            "technical",
                            "Ensure every referenced image asset is packaged in the EPUB.",
                        )

            if tag == "a":
                href = element.get("href")
                if not href or href.startswith(("http://", "https://", "mailto:")):
                    continue
                target, _, frag = href.partition("#")
                target_doc = doc_name if not target else normalize_zip_path(base_dir, target)
                if target_doc not in all_names:
                    add_finding(
                        findings,
                        "Navigation & TOC Validation",
                        "TOC links resolve to real targets",
                        f"Broken internal link {href} referenced from {doc_name}",
                        "navigation",
                        "Ensure all internal href targets exist in the EPUB.",
                    )
                    continue
                if frag:
                    target_ids = doc_ids.get(target_doc)
                    if target_ids is None:
                        try:
                            target_root = parse_xml(read_zip_text(zf, target_doc))
                        except Exception:
                            target_ids = set()
                        else:
                            target_ids = collect_ids(target_root)
                        doc_ids[target_doc] = target_ids
                    if frag not in target_ids:
                        add_finding(
                            findings,
                            "Navigation & TOC Validation",
                            "Heading anchors/targets exist where needed",
                            f"Missing fragment target #{frag} in {target_doc} (linked from {doc_name})",
                            "navigation",
                            "Ensure internal fragment links point to real ids in the target document.",
                        )

    if css_link_count == 0:
        add_finding(
            findings,
            "Technical EPUB Validity",
            "Stylesheets are linked and loading",
            "No stylesheet links found in spine XHTML documents.",
            "technical",
            "Ensure the EPUB content documents link to packaged CSS files.",
        )

    if not visual_css_seen:
        add_finding(
            findings,
            "Technical EPUB Validity",
            "Stylesheets are linked and loading",
            "No `.visual-page` styling found in linked CSS while preserved page images may be present.",
            "readability",
            "Add dedicated CSS for preserved page images so Kindle scales them predictably.",
        )


def check_nav(zf: zipfile.ZipFile, nav_path: str, findings: list[Finding]) -> None:
    try:
        nav_root = parse_xml(read_zip_text(zf, nav_path))
    except Exception as exc:
        add_finding(
            findings,
            "Navigation & TOC Validation",
            "Navigation/TOC opens and is readable",
            f"Unable to parse nav document {nav_path}: {exc}",
            "navigation",
            "Emit a valid EPUB3 nav document.",
        )
        return

    links = [
        element.get("href")
        for element in nav_root.iter()
        if strip_ns(element.tag) == "a" and element.get("href")
    ]
    if not links:
        add_finding(
            findings,
            "Navigation & TOC Validation",
            "Navigation/TOC opens and is readable",
            f"No navigation links found in {nav_path}",
            "navigation",
            "Ensure the nav document contains a usable table of contents.",
        )


def validate_epub(epub_path: Path, findings: list[Finding]) -> None:
    """Run epubcheck and map any fatals/errors/warnings into findings."""
    if not _EPUBCHECK_AVAILABLE:
        add_finding(
            findings,
            "Technical EPUB Validity",
            "EPUBCheck schema validation",
            "epubcheck Python package not installed — run `uv sync` to install it.",
            "technical",
            "Run `uv sync` in the project directory to install epubcheck.",
        )
        return

    result = EpubCheck(str(epub_path))

    # Fatal and error level messages are hard failures; warnings are surfaced too.
    for msg in result.messages:
        if msg.level in ("FATAL", "ERROR", "WARNING"):
            add_finding(
                findings,
                "Technical EPUB Validity",
                f"EPUBCheck: {msg.id}",
                f"[{msg.level}] {msg.message} — {msg.location}",
                "technical" if msg.level in ("FATAL", "ERROR") else "readability",
                msg.suggestion or "Refer to the EPUB specification for details.",
            )


def check_source_markdown(source_md: Path, findings: list[Finding]) -> None:
    if not source_md.exists():
        add_finding(
            findings,
            "Extraction Output Sanity",
            "Intermediate output exists for non-trivial conversion",
            f"Markdown file not found: {source_md}",
            "workflow",
            "Keep the intermediate Markdown for QA on non-trivial conversions.",
        )
        return

    text = source_md.read_text(encoding="utf-8")
    if PLACEHOLDER_RE.search(text):
        add_finding(
            findings,
            "Reading Quality Spot-Check",
            "No obvious extraction/OCR defects in sampled sections",
            f"Placeholder marker present in source markdown: {source_md}",
            "readability",
            "Replace placeholders with real content or inline preserved page images before final build.",
        )

    if SPLIT_URL_RE.search(text) or SPACE_AFTER_SCHEME_RE.search(text):
        add_finding(
            findings,
            "Artifact Cleanup Sweep",
            "Wrapped URLs and broken inline text repaired",
            f"Split URL detected in source markdown: {source_md}",
            "readability",
            "Normalize wrapped URLs before final build.",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic EPUB QA checks.")
    parser.add_argument("epub", help="Path to EPUB file")
    parser.add_argument("--source-md", help="Optional source Markdown used to build the EPUB")
    args = parser.parse_args()

    epub_path = Path(args.epub)
    if not epub_path.is_file():
        print(f"Error: EPUB not found: {epub_path}", file=sys.stderr)
        return 2

    findings: list[Finding] = []

    validate_epub(epub_path, findings)

    with zipfile.ZipFile(epub_path) as zf:
        check_archive(zf, findings)
        opf_path, opf_root = locate_package(zf, findings)
        if opf_path and opf_root is not None:
            spine_hrefs, nav_path = check_package(zf, opf_path, opf_root, findings)
            if nav_path:
                check_nav(zf, nav_path, findings)
            check_xhtml_documents(zf, opf_path, spine_hrefs, findings)

    if args.source_md:
        check_source_markdown(Path(args.source_md), findings)

    if findings:
        print("Conversion QA - Failed Items")
        for idx, finding in enumerate(findings, start=1):
            print(f"{idx}. [{finding.section}] {finding.item}")
            print(f"   - Evidence: {finding.evidence}")
            print(f"   - Impact: {finding.impact}")
            print(f"   - Suggested fix: {finding.suggested_fix}")
        return 1

    print("Conversion QA - Failed Items")
    print("None. All deterministic checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
