#!/usr/bin/env python3
"""
check_refs.py — look up scholarly references in the public record.

Sources (all free, no account, no key):
  Crossref      https://api.crossref.org   the DOI registry
  OpenAlex      https://api.openalex.org   open index of ~250m scholarly works
  Open Library  https://openlibrary.org    Internet Archive's book catalogue (for books without DOIs)

Any citation style: author-year (Harvard, APA), Chicago footnotes, MLA, Vancouver, IEEE.

Usage:
  python3 check_refs.py "Srnicek, N. (2017) Platform Capitalism. Polity."
  python3 check_refs.py --file refs.txt          # one reference per line
  python3 check_refs.py --json --file refs.txt   # machine-readable output

Nothing is stored; each reference is sent only to the three public APIs above.
Set VERIFY_MAILTO=you@example.org to join Crossref and OpenAlex's polite pool (faster, fewer rate limits).
Standard library only, so it runs anywhere Python 3 does.
"""
import json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from difflib import SequenceMatcher

MAILTO = os.environ.get("VERIFY_MAILTO", "")          # optional: puts you in Crossref/OpenAlex's polite pool
OPENALEX_KEY = os.environ.get("OPENALEX_API_KEY", "")  # optional: OpenAlex free key; without one, a daily budget is shared by everyone on your network
UA = "verify-citations-skill/2.2 (personal citation checker; stdlib urllib" + (f"; mailto:{MAILTO}" if MAILTO else "") + ")"
TIMEOUT = 20

def get(url):
    if "openalex.org" in url:
        if OPENALEX_KEY: url += ("&" if "?" in url else "?") + "api_key=" + urllib.parse.quote(OPENALEX_KEY)
        elif MAILTO:     url += ("&" if "?" in url else "?") + "mailto=" + urllib.parse.quote(MAILTO)
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(2 * (attempt + 1)); continue
            raise

def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", (s or "").lower()).strip()

def sim(a, b):
    return SequenceMatcher(None, norm(a), norm(b)).ratio()

STOP = {"and", "the", "eds", "ed", "et", "al", "in", "new", "york", "london", "press", "university"}

def clean(ref):
    """Reference text with DOI/URL, list numbers and bracket notes removed, the dots taken out of
    initials (so 'T.' does not split the text) and each year turned into a separator (so the
    authors and the title fall into different pieces)."""
    body = re.sub(r"\b(doi|https?):\S+", " ", ref, flags=re.I)
    body = re.sub(r"^\s*(\[\d+\]|\d+\.)\s*", "", body)                # leading [4] or 1.
    body = re.sub(r"\s*\[[^\]]*\]\s*", " ", body)                        # [online], [Blog]
    for _ in range(3):                                                     # T., B.E., C. (2016), S. and
        body = re.sub(r"\b([A-Z])\.(?=,|\s*[A-Z]\.|\s*\(|\s+(and|&)\b|\s*$)", r"\1", body)
    body = re.sub(r"\(?\b(19|20)\d{2}[a-z]?\)?", " . ", body)            # years become separators
    return re.sub(r"\s+", " ", body).strip()

def pieces_of(body):
    return [c.strip(" ,'\"“”‘’()") for c in re.split(r"[.;\"“”‘’]", body)]

def looks_like_authors(piece):
    """'Poell, T, Nieborg, D and Duffy, BE' / 'S Cunningham and D Craig' / 'Srnicek, Nick'."""
    if ":" in piece: return False
    words = [w for w in piece.split() if w.lower() not in ("and", "&")]
    caps = sum(1 for w in words if re.match(r"[A-Z]", w))
    return bool(words) and caps / len(words) > 0.8 and (re.search(r"\b[A-Z]{1,2}\b", piece) or "," in piece) and len(words) <= 8

def chunks_of(ref):
    """Pieces of the reference that could be a title, under several splitting rules,
    so author-year, Chicago footnotes, Vancouver, MLA and IEEE all yield the title as one piece."""
    body = clean(ref)
    out = set()
    for pat in (r"[.;\"“”‘’]", r"[.;:\"“”‘’]", r"[.;:,\"“”‘’]", r"[\"“”]"):
        for c in re.split(pat, body):
            c = c.strip(" ,'\"“”‘’()")
            if len(c) > 8: out.add(c)
    pieces = pieces_of(body)
    for a, b in zip(pieces, pieces[1:]):                                   # "Title: Subtitle" split by a colon
        if len(a) > 3 and len(b) > 3: out.add(f"{a}: {b}")
    return out

def parse(ref):
    """Pull out what we can search with: DOI, years, an author hint, a title guess, all chunks."""
    doi = re.search(r"10\.\d{4,9}/[^\s\"<>]+", ref)
    years = [int(y[:4]) for y in re.findall(r"\b(?:19|20)\d{2}", ref)]
    body = clean(ref)
    quoted = re.search(r"[\"“]([^\"”]{8,})[\"”]", body)
    if quoted:                                                             # Chicago / MLA article titles
        title = quoted.group(1).strip(" ,")
    else:
        cands = [c for c in pieces_of(body) if len(c) > 8 and not looks_like_authors(c)]
        title = cands[0] if cands else body                                 # the title follows the authors
    before = body.split(title, 1)[0] if title in body else ""
    names = [w for w in re.findall(r"[A-Z][A-Za-z'\-]{2,}", before) if w.lower() not in STOP]
    if not names:                                                          # title-first styles
        after = body.split(title, 1)[1] if title in body else body
        names = [w for w in re.findall(r"[A-Z][A-Za-z'\-]{2,}", after) if w.lower() not in STOP][:2]
    return {
        "doi": doi.group(0).rstrip(".,;") if doi else None,
        "year": years[0] if years else None,
        "years": years,
        "author_hint": " ".join(names[:4]),
        "title": title,
        "chunks": chunks_of(ref),
    }

def from_crossref(item):
    au = item.get("author") or []
    yr = None
    for k in ("published-print", "published-online", "issued", "created"):
        dp = (item.get(k) or {}).get("date-parts") or [[None]]
        if dp and dp[0] and dp[0][0]:
            yr = dp[0][0]; break
    notices = []
    for u in item.get("updated-by") or []:
        when = ((u.get("updated") or {}).get("date-parts") or [[None]])[0]
        notices.append({"type": u.get("type", "update"), "date": "-".join(str(x) for x in when if x),
                        "doi": u.get("DOI"), "source": u.get("source", "Crossref")})
    return {
        "source": "Crossref",
        "notices": notices,
        "title": (item.get("title") or [""])[0],
        "authors": [f"{a.get('family','')}, {a.get('given','')}".strip(", ") for a in au] or [a.get("name","") for a in au],
        "year": yr,
        "venue": (item.get("container-title") or [""])[0] or item.get("publisher"),
        "type": item.get("type"),
        "volume": item.get("volume"), "issue": item.get("issue"), "pages": item.get("page"),
        "doi": item.get("DOI"),
        "url": f"https://doi.org/{item['DOI']}" if item.get("DOI") else None,
    }

def from_openalex(w):
    au = [a.get("author", {}).get("display_name", "") for a in w.get("authorships") or []]
    loc = (w.get("primary_location") or {}).get("source") or {}
    bib = w.get("biblio") or {}
    pages = None
    if bib.get("first_page"):
        pages = bib["first_page"] + (f"-{bib['last_page']}" if bib.get("last_page") else "")
    return {
        "source": "OpenAlex",
        "notices": [{"type": "retraction", "date": None, "doi": None, "source": "OpenAlex"}] if w.get("is_retracted") else [],
        "title": w.get("title") or w.get("display_name"),
        "authors": au,
        "year": w.get("publication_year"),
        "venue": loc.get("display_name"),
        "type": w.get("type"),
        "volume": bib.get("volume"), "issue": bib.get("issue"), "pages": pages,
        "doi": (w.get("doi") or "").replace("https://doi.org/", "") or None,
        "url": w.get("doi") or w.get("id"),
    }

def split_name(name):
    """Return (surname, given) from 'Family, Given' or 'Given Family'."""
    if "," in name:
        fam, giv = [x.strip() for x in name.split(",", 1)]
    else:
        parts = name.split()
        fam, giv = (parts[-1], " ".join(parts[:-1])) if parts else ("", "")
    return fam, giv

def author_agrees(ref, first_author):
    """The record's first-author surname must appear in the reference (any style);
    if the reference gives an initial beside it, the record's given name must start with it."""
    if not first_author: return False
    fam, giv = split_name(first_author)
    if not fam or not re.search(r"\b" + re.escape(norm(fam)) + r"\b", norm(ref)): return False
    m = (re.search(re.escape(fam) + r",?\s+([A-Z])", ref) or
         re.search(r"\b([A-Z])\.?\s*(?:[A-Z]\.?\s*)?" + re.escape(fam), ref))
    if m and giv and not norm(giv).startswith(m.group(1).lower()):
        return False
    return True

def from_open_library(d):
    isbns = d.get("isbn") or []
    return {
        "source": "Open Library",
        "notices": [],
        "title": d.get("title", ""),
        "authors": d.get("author_name", []),
        "year": d.get("first_publish_year"),
        "venue": ", ".join(dict.fromkeys(d.get("publisher", [])[:2])),
        "type": "book",
        "volume": None, "issue": None, "pages": None,
        "doi": None,
        "url": "https://openlibrary.org" + d["key"] if d.get("key") else None,
        "isbn": next((i for i in isbns if len(i) == 13), isbns[0] if isbns else None),
    }

def lookup(ref):
    p = parse(ref)
    candidates = []
    # 1. DOI given: resolve it directly (strongest check)
    if p["doi"]:
        try:
            candidates.append(from_crossref(get(f"https://api.crossref.org/works/{urllib.parse.quote(p['doi'])}")["message"]))
        except Exception as e:
            candidates.append({"source": "Crossref", "error": f"Crossref: DOI did not resolve: {e}"})
    # 2. Bibliographic search on both indexes
    q = urllib.parse.quote(ref[:300])
    try:
        for it in get(f"https://api.crossref.org/works?query.bibliographic={q}&rows=3")["message"]["items"]:
            candidates.append(from_crossref(it))
    except Exception as e:
        candidates.append({"source": "Crossref", "error": f"Crossref: {e}"})
    try:
        for it in get(f"https://api.crossref.org/works?query.title={urllib.parse.quote(p['title'][:200])}&rows=3")["message"]["items"]:
            candidates.append(from_crossref(it))
    except Exception as e:
        candidates.append({"source": "Crossref", "error": f"Crossref: {e}"})
    tq = urllib.parse.quote(p["title"][:200])
    oa_urls = [f"https://api.openalex.org/works?search={tq}&per-page=3"]
    if p["author_hint"]:
        oa_urls.append(f"https://api.openalex.org/works?search={tq}&filter=raw_author_name.search:{urllib.parse.quote(p['author_hint'])}&per-page=3")
        try:
            for it in get(f"https://api.crossref.org/works?query.title={tq}&query.author={urllib.parse.quote(p['author_hint'])}&rows=3")["message"]["items"]:
                candidates.append(from_crossref(it))
        except Exception as e:
            candidates.append({"source": "Crossref", "error": f"Crossref: {e}"})
    for u in oa_urls:
        try:
            for w in get(u)["results"]:
                candidates.append(from_openalex(w))
        except Exception as e:
            candidates.append({"source": "OpenAlex", "error": f"OpenAlex: {e}"})

    # Open Library (Internet Archive): books from publishers that do not register DOIs (Polity, Routledge...)
    try:
        ol = f"https://openlibrary.org/search.json?title={urllib.parse.quote(p['title'].split(':')[0][:120])}"
        if p["author_hint"]: ol += f"&author={urllib.parse.quote(p['author_hint'])}"
        ol += "&limit=3&fields=title,author_name,first_publish_year,publisher,isbn,key"
        for d in get(ol).get("docs", []):
            candidates.append(from_open_library(d))
    except Exception as e:
        candidates.append({"source": "Open Library", "error": f"Open Library: {e}"})

    # Score on the title. A short-title-only hit (before the colon) is never more than "possible".
    # The first author decides between "match" and "possible": a title match with a different
    # author is usually a review, a chapter, or a different work with the same name.
    best, best_key, flags = None, (False, 0, False, False), []
    for c in candidates:
        if "error" in c: continue
        ct = re.sub(r"^\s*(RETRACTED|WITHDRAWN|RETRACTED ARTICLE)\s*:\s*", "", c["title"] or "", flags=re.I)
        t_full = max((sim(ch, ct) for ch in p["chunks"]), default=0)
        t_short = max((sim(ch.split(":")[0], ct.split(":")[0]) for ch in p["chunks"]), default=0)
        t = t_full if t_full >= 0.88 else min(t_short, 0.87)
        if p["doi"] and c.get("doi") and c["doi"].lower() == p["doi"].lower(): t = 1.0
        au_ok = author_agrees(ref, c["authors"][0] if c["authors"] else "")
        yr_ok = bool(c["year"] and c["year"] in p["years"])
        key = (t >= 0.88 and au_ok, t if t >= 0.65 else 0, au_ok, yr_ok)
        if key > best_key: best, best_key = c, key
    _, t, au_ok, yr_ok = best_key
    best_score = t
    if best and p["years"] and best["year"] and not yr_ok:
        flags.append(f"year differs: reference says {p['year']}, record says {best['year']}")
    if best and best["authors"] and not au_ok:
        flags.append(f"first author differs: record says {best['authors'][0]}, not found in the reference"
                     " (same title, different author: likely a review, a chapter, or a different work)")
    if not best or t < 0.65:
        verdict = "no match"
    elif t >= 0.88 and au_ok:
        verdict = "match" if yr_ok or not p["years"] else "match, year differs"
    elif au_ok or (t >= 0.88 and not best["authors"]):
        verdict = "possible match"
    else:
        verdict = "no match"
    status = []
    if best:
        same = [c for c in candidates if "error" not in c and (c is best or (c.get("doi") and c.get("doi") == best.get("doi")))]
        seen = set()
        for c in same:
            for n in c.get("notices", []):
                key = (n["type"], n["doi"])
                if key in seen: continue
                seen.add(key)
                if n["type"] in ("retraction", "withdrawal", "removal"):
                    status.append(f"RETRACTED ({n['source']}{', ' + n['date'] if n['date'] else ''}"
                                  f"{'; notice https://doi.org/' + n['doi'] if n['doi'] else ''})")
                elif n["type"] in ("correction", "erratum", "corrigendum", "expression_of_concern"):
                    status.append(f"{n['type'].replace('_', ' ')} published{' ' + n['date'] if n['date'] else ''}"
                                  f"{': https://doi.org/' + n['doi'] if n['doi'] else ''}")
        if best.get("title", "").upper().startswith("RETRACTED") and not any(x.startswith("RETRACTED") for x in status):
            status.append("RETRACTED (title marked by publisher)")
    errors = []
    for c in candidates:
        if "error" in c and c["error"] not in errors: errors.append(c["error"])
    p = {k: v for k, v in p.items() if k != "chunks"}
    return {"reference": ref, "parsed": p, "verdict": verdict, "status": status, "score": round(best_score, 2),
            "best": best, "flags": flags, "errors": errors}

def show(r):
    print(f"\n{r['verdict'].upper():<15} (score {r['score']})  {r['reference']}")
    b = r["best"]
    if b:
        au = "; ".join(b["authors"][:4]) + (" et al." if len(b["authors"]) > 4 else "")
        print(f"  {b['source']}: {au} ({b['year']}). {b['title']}. {b['venue'] or ''}"
              f"{', ' + b['volume'] if b.get('volume') else ''}{'(' + b['issue'] + ')' if b.get('issue') else ''}"
              f"{', ' + b['pages'] if b.get('pages') else ''}")
        print(f"  {b['url'] or '(no DOI)'}" + (f"  ISBN {b['isbn']}" if b.get("isbn") else ""))
    for st in r["status"]:
        print(f"  !! {st}")
    for f in r["flags"]:
        print(f"  ! {f}")
    for e in r["errors"]:
        print(f"  note: {e}")

if __name__ == "__main__":
    args = sys.argv[1:]
    as_json = "--json" in args
    if "--file" in args:
        refs = [l.strip() for l in open(args[args.index("--file") + 1], encoding="utf-8") if l.strip()]
    else:
        refs = [a for a in args if not a.startswith("--")]
    if not refs:
        print(__doc__); sys.exit(1)
    out = []
    for ref in refs:
        out.append(lookup(ref)); time.sleep(1.0)
    if as_json:
        print(json.dumps(out, indent=1, ensure_ascii=False))
    else:
        for r in out: show(r)
        from collections import Counter
        c = Counter(r["verdict"] for r in out)
        line = f"\n{len(out)} checked: " + ", ".join(f"{v} {k}" for k, v in c.items())
        retracted = sum(any(x.startswith("RETRACTED") for x in r["status"]) for r in out)
        if retracted: line += f"; {retracted} RETRACTED"
        print(line)
        if any("OpenAlex" in e for r in out for e in r["errors"]):
            print("note: OpenAlex was unavailable (rate limit or daily budget); Crossref and Open Library were used. "
                  "A free OpenAlex key in OPENALEX_API_KEY removes the shared daily limit.")
