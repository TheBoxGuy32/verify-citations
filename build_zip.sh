#!/bin/sh
# Build verify-citations.zip for upload to Claude (Cowork → Customize → Skills).
set -e
cd "$(dirname "$0")"
rm -rf /tmp/vc-build verify-citations.zip
mkdir -p /tmp/vc-build/verify-citations/scripts
cp SKILL.md README.md LICENSE /tmp/vc-build/verify-citations/
cp scripts/check_refs.py /tmp/vc-build/verify-citations/scripts/
(cd /tmp/vc-build && zip -r -q "$OLDPWD/verify-citations.zip" verify-citations)
rm -rf /tmp/vc-build
echo "built verify-citations.zip"
