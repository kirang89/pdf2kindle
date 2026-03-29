# AGENTS.md

For repository purpose, workflow, commands, options, dependencies, and core script descriptions, **read the README**.

## Mandatory QA Enforcement (Every Conversion)

For **every** conversion, run `CONVERSION_QA_CHECKLIST.md` as a required verification gate.

Also run `qa_epub.py` for deterministic checks whenever an EPUB has been built.

- Verify each checklist line item and record status (`PASS` / `FAIL` / `N/A`) internally.
- In user-facing output, show **only failed checklist items** (do not print full PASS/FAIL/N/A status for every line item).
- Before handing over output, prepare a **Failed Items for User Review** list containing all failed checks.
- Present failed checklist items in a **tabular format** for easy reading (e.g., item, failure reason, suggested fix/status).
- If any required check fails, treat the conversion as **NO-GO** until failures are resolved or explicitly accepted by the user.

---

## General Learnings for Smooth Future Conversions

### 1) Treat conversion as a two-pass process
For anything beyond a very simple PDF, expect:
- Pass 1: automated extraction/conversion
- Pass 2: structural cleanup + rebuild

Trying to force “perfect in one pass” usually costs more time than a quick cleanup cycle.

### 2) Keep intermediate Markdown for non-trivial PDFs
Preserving Markdown gives you a stable editing surface for:
- heading hierarchy fixes,
- paragraph/line-break cleanup,
- list and callout normalization,
- removing PDF artifacts.

### 3) Prioritize structure over cosmetic edits
Readability and Kindle navigation improve most when you fix:
- heading levels,
- section boundaries,
- broken or merged subsection titles,
- noisy front matter/body leakage.

Typography polish matters, but structure yields bigger gains first.

### 4) Watch for common PDF extraction artifacts
Typical problems to scan for:
- table-of-contents text leaking into chapter body,
- spurious headings from figure labels,
- split section numbers/titles,
- wrapped URLs and broken inline text,
- accidental line joins/splits.

A quick targeted sweep for these catches most readability regressions.

### 5) Prefer deterministic cleanup steps
When possible, use repeatable cleanup logic (scriptable transforms + minimal manual edits). This helps:
- re-run conversions reliably,
- apply fixes consistently across similar documents,
- reduce drift between builds.

### 6) Validate navigation explicitly
Always confirm generated TOC/navigation files are internally consistent:
- links resolve to existing targets,
- heading anchors are present,
- hierarchy is sensible for Kindle navigation.

A technically valid EPUB can still have poor reading navigation.

### 7) Set metadata intentionally near finalization
Apply title/author/language metadata in the final build step, after content cleanup. This avoids accidental overrides from intermediate files and keeps library display clean on Kindle.

### 8) Use OCR strategically, not by default
OCR is valuable for scanned or garbled PDFs, but can add noise. Use it when text extraction quality is clearly poor, and then do a stronger cleanup pass.

### 9) Optimize for reader flow on e-ink
A “good” conversion is not just valid EPUB syntax. It should read smoothly on Kindle:
- predictable section progression,
- no junk blocks at chapter starts,
- coherent paragraphs,
- usable TOC.

Focus on reading experience, not just conversion success.

### 10) Maintain a reusable QA checklist
Before sharing any EPUB, run a short final checklist:
- structural headings look right,
- no obvious extraction artifacts,
- TOC links work,
- metadata is correct,
- file opens cleanly on target reader/device.

### 11) Separate **technical validity** from **reading quality**
Run both checks explicitly:
- **Technical validity**: EPUB archive opens cleanly, required files exist (`mimetype`, `META-INF/container.xml`, OPF/nav), CSS is linked.
- **Reading quality**: spot-check chapter text for OCR/extraction artifacts (e.g., broken small-caps, split words, malformed headings, duplicated page headers).

A file can be technically valid and still unpleasant to read.

### 12) Prefer `--keep-md` during first build for unknown PDFs
For unfamiliar PDFs, do **not** start with a fully disposable run.
Recommended first pass:
- keep Markdown (`--keep-md`),
- optionally skip pause only if you will immediately inspect the `.md`.

Use `--no-pause` without `--keep-md` only when you are confident extraction quality is already good.

### 13) OCR fallback policy
Use this sequence:
1. Try normal extraction.
2. If text is garbled/encoded badly, rerun with `--ocr --keep-md`.
3. Perform targeted cleanup in Markdown, then rebuild EPUB.

OCR often fixes encoding failures but can introduce recognition noise; expect cleanup.

### 14) Treat visual-heavy pages as a separate content class
Annual reports, survey documents, and data-rich PDFs often contain pages that are technically text-based but not meaningfully reflowable.
Examples:
- charts and maps with many short labels,
- dense statistical tables,
- figure-heavy spreads,
- citation/reference pages with wrapped URLs.

For these pages:
- do **not** force low-quality reflow text into the main reading flow,
- prefer preserving **image assets** (figures, charts, maps, diagrams) rather than entire page screenshots,
- do **not** keep full-page facsimiles for text pages unless explicitly requested by the user,
- if visual preservation is used, prefer inserting only the non-text visual content inline at the original location rather than only in an appendix.

Appendix-only preservation is a weaker fallback because it keeps the information but harms reader flow. Full-page preservation should be treated as an exception path, not the default.

### 15) Add deterministic QA checks for known failure modes
If a failure can be checked by code, check it automatically instead of relying only on spot review.

At minimum, add deterministic checks for:
- broken internal EPUB links/anchors,
- missing image targets,
- required EPUB container/package/navigation files,
- placeholder/fallback markers left in final output,
- wrapped or split URLs in the final text layer,
- CSS presence for preserved visual pages when page images are used.

If any of these checks fail, treat the output as **NO-GO** until fixed or explicitly accepted.

### 16) Validate preserved visual coverage when using page-image fallback
When the conversion strategy includes rendered PDF pages:
- confirm that the number of preserved pages/images matches expectations,
- confirm the final EPUB references real image assets,
- confirm images are sized for Kindle rather than forced to full-width distortion.

It is not enough for images to exist; they must be reachable and readable on e-ink.

### 17) Watch for “technically valid but semantically degraded” output
Common examples:
- placeholder sentences replacing real content,
- appendix-only visual preservation with no inline context,
- chart/table pages converted into unreadable fragments,
- references turning into malformed prose because URLs were split.

These should be treated as reading-quality failures even if the EPUB archive itself is valid.

---

## Suggested Operating Principle

Aim for **fast automation + lightweight human QA**.  
This consistently produces better Kindle outcomes than either full manual work or fully unattended conversion.
