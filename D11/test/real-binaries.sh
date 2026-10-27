#!/usr/bin/env bash
# Real code for the D11 module: test/real-binaries.sh <workdir>
# test/real/algos.asm (a sum/xor checksum with offset-register addressing, a bitwise CRC-16 with jzx,
# a bubble sort with compare-and-jumps) is assembled with b43-asm, run in the p-code emulator against
# results computed in Python, imported with auto-analysis (instructions, functions, bookmarks, decompile
# failures) and compared with b43-dasm's disassembly of the same file.
# No freely licensed D11 firmware was found (Broadcom's microcode is not redistributable for analysis).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source "$HERE/env.sh"
W=$(readlink -m "${1:?workdir}")
mkdir -p "$W"
rc=0
python3 "$HERE/real/algos.py" "$W" | sed 's/^/   /'
"$HERE/real-emu.sh" "$W/algos-cases.txt" "$W" | tail -n 8 | sed 's/^/   /' || rc=1
P=$(mktemp -d "${TMPDIR:-/tmp}/d11-real.XXXXXX")
"$GHIDRA_INSTALL_DIR/support/analyzeHeadless" "$P" p -import "$W/algos.bin" -loader BinaryLoader \
	-processor D11:LE:16:default -scriptPath "$HERE" \
	-postScript D11RealCheck.java "$W/algos.sum" "$W/algos.lst" "$W/algos.dec" 120 -deleteProject >"$P/log.txt" 2>&1 \
	|| { tail -30 "$P/log.txt"; rc=1; }
rm -rf "$P"
grep -E "^functions:|^instructions:|bad-instruction|error bookmarks|^decompile:" "$W/algos.sum" | sed 's/  (.*//; s/^/   /'
grep -q "bad-instruction bookmarks: 0" "$W/algos.sum" || rc=1
grep -q "error bookmarks: 0" "$W/algos.sum" || rc=1
grep -q " 0 failed, 0 timed out" "$W/algos.sum" || rc=1
python3 "$HERE/real_compare.py" "$W/algos.lst" "$W/algos.bin" "$W/cmp" | sed 's/^/   b43-dasm: /' || rc=1
exit $rc
