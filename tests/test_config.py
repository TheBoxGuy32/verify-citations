#!/usr/bin/env python3
"""Settings-file test: no network needed. Uses a temporary home folder so your real settings are untouched."""
import json, os, subprocess, sys, tempfile
here = os.path.dirname(os.path.abspath(__file__))
script = os.path.join(here, "..", "scripts", "check_refs.py")
with tempfile.TemporaryDirectory() as home:
    env = {**os.environ, "HOME": home}
    env.pop("OPENALEX_API_KEY", None); env.pop("VERIFY_MAILTO", None)
    run = lambda *a: subprocess.run([sys.executable, script, *a], capture_output=True, text=True, env=env).stdout
    assert "not set" in run("--status"), run("--status")
    run("--set-openalex-key", "test-key-123")
    run("--set-mailto", "someone@example.org")
    cfg = json.load(open(os.path.join(home, ".config", "verify-citations", "config.json")))
    assert cfg == {"openalex_api_key": "test-key-123", "mailto": "someone@example.org"}, cfg
    mode = oct(os.stat(os.path.join(home, ".config", "verify-citations", "config.json")).st_mode)[-3:]
    assert mode == "600", mode
    st = run("--status")
    assert "OpenAlex key:  set" in st and "someone@example.org" in st, st
    env["OPENALEX_API_KEY"] = ""      # empty env var must not hide the file's key
    assert "OpenAlex key:  set" in run("--status")
print("config test passed")
