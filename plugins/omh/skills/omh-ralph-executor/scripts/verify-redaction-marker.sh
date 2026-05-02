#!/usr/bin/env bash
# verify-redaction-marker.sh — confirm whether a verifier's "literal redaction
# marker" strike reflects actual file bytes or is a display-layer artifact.
#
# Usage:
#   verify-redaction-marker.sh <file> <line-number> [pattern]
#
# Prints the raw bytes of the cited line in three forms — od -c, repr() of
# the line as bytes, and `git show HEAD:<file>` for the same line — so the
# orchestrator (or a fresh executor) can decide whether to retry.
#
# Exit codes:
#   0 — bytes inspected, output emitted (interpret manually)
#   1 — bad arguments or file/line doesn't exist
#
# Typical signal:
#   - od/repr show `{token}` / `${var}` / `%s` / actual interpolation token
#     → display-layer mangled it; verifier strike is a FALSE POSITIVE.
#   - od/repr show the literal mask sigil (`***`, `<redacted>`, etc.)
#     → strike is REAL; proceed with the implementation fix.

set -euo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
    echo "usage: $0 <file> <line-number> [grep-pattern]" >&2
    exit 1
fi

FILE="$1"
LINE="$2"
PATTERN="${3:-}"

if [[ ! -f "$FILE" ]]; then
    echo "error: file not found: $FILE" >&2
    exit 1
fi

TOTAL_LINES=$(wc -l < "$FILE")
if (( LINE < 1 || LINE > TOTAL_LINES )); then
    echo "error: line $LINE out of range (file has $TOTAL_LINES lines)" >&2
    exit 1
fi

echo "=== File: $FILE  Line: $LINE ==="
echo

echo "--- 1) sed -n '${LINE}p' (rendered, may be mangled by display layer) ---"
sed -n "${LINE}p" "$FILE"
echo

echo "--- 2) sed -n '${LINE}p' | od -c (raw bytes) ---"
sed -n "${LINE}p" "$FILE" | od -c
echo

echo "--- 3) python3 repr() of the line as bytes ---"
python3 -c "
import sys
with open(sys.argv[1], 'rb') as f:
    lines = f.read().splitlines()
print(repr(lines[int(sys.argv[2]) - 1]))
" "$FILE" "$LINE"
echo

if git -C "$(dirname "$FILE")" rev-parse --git-dir >/dev/null 2>&1; then
    REL=$(git -C "$(dirname "$FILE")" ls-files --full-name "$(basename "$FILE")" 2>/dev/null || true)
    if [[ -n "$REL" ]]; then
        echo "--- 4) git show HEAD:${REL} | sed -n '${LINE}p' | od -c (committed bytes) ---"
        if git -C "$(dirname "$FILE")" show "HEAD:$REL" 2>/dev/null | sed -n "${LINE}p" | od -c; then
            :
        else
            echo "(file not in HEAD or path differs from working tree)"
        fi
        echo
    fi
fi

if [[ -n "$PATTERN" ]]; then
    echo "--- 5) byte-level pattern check: does the line contain '$PATTERN'? ---"
    if python3 -c "
import sys
with open(sys.argv[1], 'rb') as f:
    line = f.read().splitlines()[int(sys.argv[2]) - 1]
target = sys.argv[3].encode()
if target in line:
    print(f'YES — bytes contain {target!r}')
    sys.exit(0)
else:
    print(f'NO — bytes do not contain {target!r}')
    sys.exit(2)
" "$FILE" "$LINE" "$PATTERN"; then
        :
    fi
    echo
fi

echo "=== Interpretation ==="
echo "If section 2/3 shows interpolation tokens ({var}, \${var}, %s, etc.):"
echo "  → display layer mangled the rendering; verifier strike is FALSE POSITIVE."
echo "  → do NOT retry the implementation; add a regression test pinning the bytes."
echo "If section 2/3 shows the literal mask sigil:"
echo "  → strike is REAL; proceed with the implementation fix."
