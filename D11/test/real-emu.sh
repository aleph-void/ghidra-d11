#!/usr/bin/env bash
# Run a D11EmuTest case file in the p-code emulator:  test/real-emu.sh <cases.txt> [outdir] [language-id]
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source "$HERE/env.sh"
CASES=$(readlink -f "$1")
OUTD=$(readlink -m "${2:-${TMPDIR:-/tmp}/d11-real}")
LANG_ID=${3:-D11:LE:16:default}
mkdir -p "$OUTD"
PROJ=$(mktemp -d "${TMPDIR:-/tmp}/d11-real.XXXXXX")
trap 'rm -rf "$PROJ"' EXIT
head -c 16384 /dev/zero > "$PROJ/zero.bin"
out=$OUTD/$(basename "$CASES" .txt).out
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$PROJ" p -import "$PROJ/zero.bin" \
	-loader BinaryLoader -processor "$LANG_ID" -noanalysis -scriptPath "$HERE" \
	-postScript D11EmuTest.java "$CASES" "$out" -deleteProject >"$PROJ/log.txt" 2>&1 \
	|| { tail -40 "$PROJ/log.txt" >&2; exit 1; }
[[ -s $out ]] || { grep -E "ERROR|Exception" "$PROJ/log.txt" | head -20 >&2; exit 1; }
cat "$out"
grep -q " 0 failed" "$out"
