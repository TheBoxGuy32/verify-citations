# verify-citations

A read-only citation checker for Claude. Point it at a presentation, a Word document, a PDF or pasted text and it finds every citation, checks each scholarly reference against the public record, flags retracted papers, and reports what it found. It never edits the document.

Works in Claude chat, Claude Code, Cowork and the Word and PowerPoint add-ins. Any citation style: Harvard, APA, Chicago and MHRA footnotes, MLA, Vancouver, IEEE.

## What it checks against

Three free public databases, queried directly. No account, no key, no intermediary.

| Database | What it holds | Used for |
|---|---|---|
| [Crossref](https://www.crossref.org) | The DOI registry, with Retraction Watch data | Journal articles, chapters, most books with DOIs; retraction and correction notices |
| [OpenAlex](https://openalex.org) | Open index of about 250 million scholarly works (OurResearch, non-profit) | Second opinion on articles; works without DOIs |
| [Open Library](https://openlibrary.org) | The Internet Archive's book catalogue | Books whose publishers do not register DOIs (Polity, Routledge, many university presses) |

Non-scholarly sources (news, reports, websites, datasets) are checked by web search.

**Privacy.** The only data that leaves your machine is the text of each reference, sent to the three services above. Nothing is stored anywhere. There is no server of ours in the middle.

## Install

1. Download `verify-citations.zip` from the [latest release](../../releases/latest).
2. In the Claude desktop app: Cowork → Customize → + → Skills → upload the zip. On claude.ai: Settings → Capabilities → Skills. The skill then appears in chat, Cowork, Claude Code and the Office add-ins under the same account.
3. Open a document and ask: *"verify the citations"*.

You can also build the zip yourself with `./build_zip.sh`.

## What the report looks like

- **Summary line**: "18 citations checked: 12 verified, 3 discrepancies, 2 unverifiable, 1 attribution issue."
- **Needs attention**: retracted papers, unverifiable sources, wrong attributions, missing references.
- **Discrepancies**: real sources with the wrong year, pages, author or title, with the corrected reference as the record gives it.
- **Consistency**: inline cites without a reference entry and vice versa, mixed styles.
- **Verified**: each with the database that confirmed it.

Every finding names its basis (for example "Crossref: DOI 10.1177/1461444819854731, all fields match") so you can judge how strong the check is. "Could not find a record" is reported as exactly that, never as "fake".

## The lookup script on its own

`scripts/check_refs.py` is a standalone Python 3 script with no dependencies. Claude runs it where it can; where it cannot (the Office add-ins), the skill fetches the same database URLs itself.

```
python3 scripts/check_refs.py "Srnicek, N. (2017) Platform Capitalism. Polity."
python3 scripts/check_refs.py --file refs.txt        # one reference per line, any style
python3 scripts/check_refs.py --json --file refs.txt # machine-readable
```

Verdicts: `match`, `match, year differs`, `possible match`, `no match`. A `RETRACTED` status line is printed for withdrawn papers, with the date and the notice's DOI.

Optional environment variables:

- `VERIFY_MAILTO=you@example.org` puts your queries in Crossref's and OpenAlex's "polite pool" (faster, fewer rate limits).
- `OPENALEX_API_KEY=...` uses a free OpenAlex key. Without one, OpenAlex shares a daily budget among everyone on your network's IP address, which a university campus can exhaust. The script carries on with Crossref and Open Library when that happens, and says so.

## Tests

```
python3 tests/run_tests.py
```

Runs thirteen references in five styles, including two invented ones and one retracted paper, and compares the verdicts. Needs internet access.

## What it deliberately does not do

- It does not edit your document. Corrections are yours to apply.
- It does not judge journals. Predatory-journal lists are contested and a wrong verdict damages a real journal.
- It does not decide whether a source supports a claim on its own. It checks that the source exists and is described correctly; reading the source is still your job, and the skill helps by pointing at the abstract.

## Licence

Apache 2.0. Built by Mark Margaretten with Claude, September 2026.
