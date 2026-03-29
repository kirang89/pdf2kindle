# Conversion QA Checklist (Run for Every Conversion)

Use this checklist as a mandatory **go/no-go gate** before sharing any EPUB.

- Mark each item as: `[PASS]`, `[FAIL]`, or `[N/A]`.
- Any `[FAIL]` must be recorded in **Failed Items for User Review**.
- Do not mark a conversion complete until all required items pass.

---

## 1) Preflight

- [ ] PDF type identified (text-based vs scanned/garbled)
- [ ] First pass mode chosen correctly (`--keep-md` for unknown/non-trivial PDFs)
- [ ] OCR policy followed (normal extraction first, OCR only if needed)

## 2) Extraction Output Sanity

- [ ] Intermediate output exists for non-trivial conversion
- [ ] No catastrophic extraction failure (empty or unreadable body)
- [ ] Chapter/section boundaries are recoverable

## 3) Structural Quality (Priority)

- [ ] Heading hierarchy is logical (`h1 > h2 > h3`, no random jumps)
- [ ] Section titles are not split/merged incorrectly
- [ ] TOC/front matter leakage removed from body
- [ ] Spurious headings from figures/tables removed
- [ ] Lists/callouts normalized and readable

## 4) Artifact Cleanup Sweep

- [ ] Wrapped URLs and broken inline text repaired
- [ ] Accidental line joins/splits fixed
- [ ] Repeated page headers/footers/page numbers removed
- [ ] OCR artifacts spot-cleaned (if OCR used)
- [ ] Paragraph flow is smooth for e-ink reading

## 5) Navigation & TOC Validation

- [ ] Navigation/TOC opens and is readable
- [ ] TOC links resolve to real targets
- [ ] Heading anchors/targets exist where needed
- [ ] TOC hierarchy depth is sensible
- [ ] Reading order is correct

## 6) Metadata Finalization

- [ ] Title is correct
- [ ] Author is correct
- [ ] Language is correct
- [ ] Metadata verified after final build

## 7) Technical EPUB Validity

- [ ] EPUB opens cleanly without archive/format errors
- [ ] Required files present (`mimetype`, `META-INF/container.xml`, OPF, nav)
- [ ] Manifest/spine references are consistent
- [ ] Stylesheets are linked and loading
- [ ] No broken internal references/images in sampled chapters

## 8) Reading Quality Spot-Check

Spot-check at least: beginning, middle, end, plus 2 complex sections.

- [ ] Chapter starts are clean (no junk blocks)
- [ ] Heading presentation is consistent
- [ ] Paragraphs are coherent and not fragmented
- [ ] No obvious extraction/OCR defects in sampled sections
- [ ] Kindle navigation experience is usable

---

## Failed Items for User Review (Mandatory)

After every conversion, provide the user a concise list of all failed checks.

Use this format:

```text
Conversion QA - Failed Items
1. [Section] <line item>
   - Evidence: <file/chapter/brief example>
   - Impact: <navigation/readability/technical>
   - Suggested fix: <short action>
```

If no failures:

```text
Conversion QA - Failed Items
None. All required checks passed.
```

---

## Final Go/No-Go Decision

- [ ] GO: All required checks passed
- [ ] NO-GO: One or more required checks failed (share failed-item list with user)
