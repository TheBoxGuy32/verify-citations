#!/usr/bin/env python3
"""Run every reference in tests/refs.txt through check_refs.py and compare with the expected verdict.
Needs internet access. OpenAlex being rate-limited is reported but is not a failure."""
import json, os, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
script = os.path.join(here, "..", "scripts", "check_refs.py")
cases = []
for line in open(os.path.join(here, "refs.txt"), encoding="utf-8"):
    line = line.strip()
    if not line or line.startswith("#"): continue
    verdict, status, ref = [x.strip() for x in line.split("|", 2)]
    cases.append((verdict, status, ref))
out = json.loads(subprocess.run([sys.executable, script, "--json"] + [c[2] for c in cases],
                                capture_output=True, text=True, check=True).stdout)
failed = 0
for (want_v, want_s, ref), r in zip(cases, out):
    got_v = r["verdict"].replace(", ", "-").replace(" ", "-")
    got_s = "retracted" if any(x.startswith("RETRACTED") for x in r["status"]) else "-"
    ok = got_v == want_v and got_s == want_s
    failed += not ok
    print(f"{'ok  ' if ok else 'FAIL'} want {want_v}/{want_s:9} got {got_v}/{got_s:9} {ref[:70]}")
oa = any("OpenAlex" in e for r in out for e in r["errors"])
print(f"\n{len(cases) - failed}/{len(cases)} passed" + ("  (OpenAlex unavailable during this run)" if oa else ""))
sys.exit(1 if failed else 0)
