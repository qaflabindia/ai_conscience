#!/bin/zsh
# Builds the ResearchGate-ready PDF of the v2 paper.
# Needs: pandoc 3.x, Google Chrome (headless printing), swift (Xcode command-line tools).
set -e
B=${0:A:h}
SRC="$B/../Agentic_AI_Trust_and_Conscience_v2.md"
OUT="$B/../Santhanam_2026_Evidence-Gated_Delegation_for_Agentic_AI_v2.1.pdf"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
cp "$B/paper.css" "$TMP/"

pandoc "$SRC" \
  -f markdown+tex_math_single_backslash+autolink_bare_uris -t html5 -s \
  --template="$B/template.html" --css=paper.css --mathml --toc --toc-depth=1 \
  --syntax-highlighting=pygments -o "$TMP/paper.html"

# Let the browser size table columns from their content.
python3 -c "
import re, sys; p = sys.argv[1]; s = open(p).read()
open(p, 'w').write(re.sub(r'<colgroup>.*?</colgroup>', '', s, flags=re.S))" "$TMP/paper.html"

"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer \
  --generate-pdf-document-outline --user-data-dir="$TMP/profile" \
  --print-to-pdf="$TMP/paper.pdf" "file://$TMP/paper.html" >/dev/null 2>&1

swift "$B/set_metadata.swift" "$TMP/paper.pdf" "$OUT"
echo "Wrote $OUT"
