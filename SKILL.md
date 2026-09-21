---
name: "verify-citations"
description: "Read-only citation checker. Scans a presentation or any document (PowerPoint, PDF, Word, pasted text) for citations in any style, verifies scholarly references directly against the public record (Crossref, OpenAlex, Open Library; web search for non-scholarly sources), flags retracted papers, and reports in chat. Nothing goes through a third-party service. Never modifies the document. Use when asked to check, verify, fact-check, or audit citations, sources, or references."
---

## When to use

Use when the user asks to verify, check, fact-check, or audit the citations, references, or sources: "are these citations real?", "check my sources", "verify the references". Works on academic content (author-year, footnotes, reference lists) and business content (report and data attributions, quoted figures).

If the content has no citations at all, say so and stop. Do not invent things to check.

## This skill is READ-ONLY

This skill checks and verifies. It NEVER changes the document: no slide edits, no find-and-replace, no writing to the open deck or to any uploaded or connected file. Even if verification finds errors, do not fix them and do not offer to fix them as part of this skill. The only output is the verification report in step 5. If the user wants corrections applied afterward, that is a separate, explicitly requested task outside this skill.

## How verification works (say this once if the user asks)

Scholarly references are checked against three free, public databases, queried directly. No account, no key, no intermediary:

- **Crossref** (api.crossref.org): the DOI registry. Strongest check when a DOI is given.
- **OpenAlex** (api.openalex.org): open index of about 250 million scholarly works, run by the non-profit OurResearch.
- **Open Library** (openlibrary.org): the Internet Archive's book catalogue. Catches monographs from publishers such as Polity and Routledge that do not register DOIs.

The only data that leaves the machine is the text of each reference, sent to those three services. Non-scholarly sources (news, reports, websites, datasets) are checked by web search.

## OpenAlex key (optional, free)

OpenAlex shares a daily budget among everyone using it from the same network without a key, so on a university campus it can be used up by mid-morning. Crossref and Open Library still do the whole check when that happens; a key just makes OpenAlex reliable. A key is free: make an account at openalex.org (about 30 seconds) and copy the key from https://openalex.org/settings/api.

- **Where a script can run (Claude Code, Cowork, chat with code execution):** if the user gives you a key, save it once with `python3 scripts/check_refs.py --set-openalex-key THE_KEY`. It goes in a settings file in the user's home folder, readable only by them, and every later run picks it up. `--status` shows whether one is set. The user can also give a contact email for the polite pool with `--set-mailto`.
- **Where no script can run (Word and PowerPoint add-ins):** ask once per conversation whether the user has an OpenAlex key; if they paste one, add it to each OpenAlex request as an `Authorization: Bearer THE_KEY` header, or as `&api_key=THE_KEY` on the URL if headers are not possible. Do not store it anywhere.
- Never write a key into the skill files or the zip: those get shared.
- The report's summary line says whether OpenAlex was used, used with a key, or unavailable. If it was unavailable and there is no key, add one sentence telling the user a free key would fix it, with the link. Say it once, not per reference.

## Inputs: accept any document, on any surface

This skill runs in claude.ai chat, the PowerPoint add-in, Cowork and Claude Code. Work out WHERE the citations live and load the text with whatever read-only means the current surface offers:

- **Open PowerPoint deck (add-in)**: use the deck-outline or read-slide-text tools if present (e.g. `export_deck_outline`, or `list_slide_shapes` + `read_slide_text` per slide).
- **A .pptx, PDF, .docx or spreadsheet file** (uploaded, in a connected folder, or on Drive/SharePoint): read it with the file tools available: python-pptx for slides (include speaker notes and tables), pdfplumber for PDF, python-docx for Word, pandas/openpyxl for spreadsheets. In the chat sandbox, find uploads via `glob.glob(os.environ.get('INPUT_DIR','/files/input') + '/**/*', recursive=True)`. Read in place; do not copy or rewrite the file.
- **Pasted text in chat**: work directly from the message.
- **A document open in another connected app** (Word or Excel elsewhere): request its content read-only via the connected app.

If more than one source is present, ask the user which to verify, or confirm you should do all of them.
**Done when:** you have the full text of the target document loaded and know its type.

## Citation styles

Any style. The reading step recognises author-year (Harvard, APA), Chicago and MHRA footnotes, MLA, Vancouver and IEEE numbered lists. The checker script handles all of them too: it does not need the reference in a particular shape, only a title and a name somewhere in it. Footnote and endnote references are checked exactly like reference-list entries. If a footnote is a short form ("Latimer, 'Bio-Reproductive Futurism', 60"), match it to its full first citation or the bibliography entry before checking, and check the full form once.

**Word files:** footnotes and endnotes are not in the main body. python-docx's `doc.paragraphs` does not return them; read them from the package parts `word/footnotes.xml` and `word/endnotes.xml` (for example by opening the .docx as a zip and pulling the `<w:t>` text from those parts). In the Word add-in, ask the document tool for footnotes explicitly if the first read does not include them, and say in the report whether footnotes were read.

## What counts as a citation

- Author-year inline cites: `(Bird, 2024)`, `Smith & Jones (2019)`, `[3]`
- Footnote or endnote source lines
- Reference or bibliography sections
- Attributed quotes ("As X wrote, ...")
- Attributed data and figures ("per the 2023 WHO report", "Source: McKinsey 2022")

## Workflow

### 1. Collect every citation

From the loaded text, extract each distinct citation with its location (slide number, page or section) and the claim it supports. Build a working list: `{location, citation, claim_it_supports, kind}` where kind is **scholarly** (journal article, conference paper, thesis, academic book or chapter) or **non-scholarly** (news, report, website, dataset, industry source).
**Done when:** you have a deduplicated list of every citation and where it appears. Report the count to the user before verifying.

### 2. Verify each source exists and is correctly described

**Scholarly references: run the checker script.** Write the scholarly references to a text file, one per line, and run:

```
python3 scripts/check_refs.py --file refs.txt
```

(`--json` gives machine-readable output; single references can be passed as arguments instead of `--file`.) Standard library only; runs wherever Python 3 has internet access. Any citation style, one reference per line. Setting `VERIFY_MAILTO` to an email address puts the queries in Crossref and OpenAlex's polite pool, which is faster and rarely rate-limited; it is optional. It queries Crossref, OpenAlex and Open Library and returns, for each reference, a verdict and the best record found: canonical authors, title, venue, year, volume, issue, pages, DOI or ISBN, and an openable URL.

Verdicts the script gives:
- `match`: title and first author agree with a record; year agrees too.
- `match, year differs`: same work, but the record's year is different (common for books with print and online editions; report the record's year as the correction).
- `possible match`: partial title agreement with the right author, or full title with no author to check. Look at the record and decide.
- `no match`: nothing close enough, or the same title under a different author (a review, a chapter, or a different work with the same name). The best near-miss is shown so you can see what was found.

Compare every field of a `match` against what the document says, not just the verdict: wrong pages, wrong volume, misspelt author.

**Retractions and corrections.** The script also reports a `status` for each matched work, from Crossref's record (which carries Retraction Watch data) and OpenAlex. A line beginning `RETRACTED` means the publisher has withdrawn the paper; it goes at the top of Needs attention, with the date and the notice's DOI, whatever the rest of the reference looks like. A `correction`, `erratum` or `expression of concern` is reported under Discrepancies so the reader can check whether it touches the claim being cited. Citing a retracted paper is not automatically wrong (it may be cited as a retracted paper), so report it; do not judge it.

**If the script cannot run** (no Python or no network on the current surface), query the same three databases by fetching these URLs directly with the web-fetch tool, one reference at a time:
- DOI given: `https://api.crossref.org/works/<DOI>`
- No DOI given: `https://api.crossref.org/works?query.bibliographic=<reference text>&rows=3` (URL-encode the reference). A reference without a DOI is the one that most needs this query: it returns the DOI, and the document should be told what it is. Do not skip to a publisher page or web search for a DOI-less reference until this query has been tried.
- and: `https://api.openalex.org/works?search=<title>&per-page=3`
- Books: `https://openlibrary.org/search.json?title=<title>&author=<surname>&limit=3`

In the report, name the database as the basis ("Crossref: DOI 10.xxxx, all fields match"); a publisher page is a secondary confirmation, not the check itself.

Only if all three return nothing (common for grey literature, theses and older work) fall back to web search (publisher page, Google Scholar, library catalogue, DOI resolver) before labelling it unverifiable.

**Non-scholarly sources: use web search.** Confirm the report, article, dataset or page exists, with matching publisher, title and year.

Watch for hallucinated-citation signatures: plausible author, title and journal that return no real record; a real author who never wrote on that topic; a journal that does not exist.

Classify each as:
- **Verified**: real source, all details match the record
- **Discrepancy**: real source but wrong year, author, title, venue, pages or DOI (state the correction, taken from the record)
- **Unverifiable**: no record found in the three databases and 1-2 web searches (flag it; do not assert it is fake)
**Done when:** every citation has one of the three labels with a one-line basis naming what was checked (e.g. "Crossref: DOI matches, pages differ", "Open Library: ISBN 9781509504862", "web: publisher page found").

### 3. Check attribution accuracy

For citations that support a specific claim, figure or quote, verify the source actually says that, not just that it exists. The databases confirm a record, not content, so this step uses web search, the abstract, or the paper itself. Flag claims where the source exists but does not support the stated point, quotes that are altered, and figures that do not match the cited source.
Respect copyright: quote fewer than about 20 words from any source, in quotation marks.
**Done when:** each claim-bearing citation is marked as supported, not supported, or could not confirm.

### 4. Check internal consistency

- Every inline cite has a matching entry in the reference list, and vice versa (no orphan references)
- Author and year are spelled and dated consistently throughout
- Citation style is uniform (do not mix APA and numbered)
**Done when:** mismatches between inline cites and the reference list are listed, or confirmed none.

### 5. Deliver the verification report (only output)

Present a structured report on screen in chat. Do not modify the document. Structure it as:

- **Summary line**: e.g. "18 citations checked: 12 verified, 3 discrepancies, 2 unverifiable, 1 attribution issue. Databases: Crossref, Open Library; OpenAlex unavailable (no key)."
- **Needs attention**: retracted papers first, then fabricated or unverifiable sources, wrong attributions, missing references. One row each: location · citation · finding · basis.
- **Discrepancies**: real sources with wrong details, plus the corrected reference as the record gives it; and any published correction or expression of concern attached to a cited work.
- **Consistency**: style and format mismatches.
- **Verified**: list or count, with the verification basis (e.g. "Crossref: DOI 10.xxxx matches").

Use a clear table or grouped list so it reads at a glance on screen. If the user wants this report as a shareable file, offer to produce a Word document or send it to a connected docs app, but that is delivering the report, not editing the source document.
**Done when:** the report is on screen in chat and the user has seen the summary and per-citation findings.

## Notes

- Never fabricate a verification result. "Couldn't find a record" is a valid, useful finding. Do not upgrade it to "confirmed" or downgrade it to "fake".
- Always say which database verified each item (Crossref, OpenAlex, Open Library, or web search) so the user can judge the strength of the check.
- If web search is disabled, tell the user that non-scholarly sources and attribution checks need it, and do the scholarly checks plus internal consistency (steps 1, 2 and 4) only.
- Do not route references through any third-party checking service. The public databases are the record; an intermediary adds a party that sees the references and adds nothing to the check.
