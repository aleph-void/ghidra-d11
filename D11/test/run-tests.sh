#!/usr/bin/env bash
# D11 module tests:
#   1. d11.slaspec compiles
#   2. p-code emulator cases (test/emu/cases.txt, hand-computed from the microcode documentation) on
#      D11:LE:16:default, and a copy with one deliberately wrong expectation, which must be the only failure
#   3. every-entry decode test (CoverageCheck.java, two seeds)
#   4. decode differential against b43-dasm (b43-tools, architecture 15): every opcode with random operands
#   5. with --real <workdir>: test/real-binaries.sh (self-built programs assembled with b43-asm)
#
#   test/run-tests.sh [--real <workdir>] [outdir]
#
# Environment: GHIDRA_INSTALL_DIR (Ghidra 12.1.x/12.2 whose Ghidra/Processors/D11 is, or links to, this
# module directory), JAVA_HOME (JDK 21+; 25 for 12.2), B43DASM (b43-dasm built from b43-tools,
# https://git.bues.ch/cgit/b43-tools.git; steps 4-5 are skipped without it) and B43ASM (the b43-asm
# wrapper script that preprocesses with `gcc -E`, next to b43-asm.bin; needed by --real and when the
# emulator cases are regenerated). TMPDIR must not contain a path component starting with a dot.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
MOD=$(cd "$HERE/.." && pwd)
source "$HERE/env.sh"
REAL=
if [[ ${1:-} == --real ]]; then
	REAL=$(readlink -m "$2")
	shift 2
fi
OUT=$(readlink -m "${1:-${TMPDIR:-/tmp}/d11-tests}")
mkdir -p "$OUT"
rc=0

echo "== 1. compile"
"$GHIDRA_INSTALL_DIR/support/sleigh" "$MOD/data/languages/d11.slaspec" >"$OUT/sleigh.log" 2>&1 || { tail -20 "$OUT/sleigh.log"; rc=1; }
grep -E "ERROR" "$OUT/sleigh.log" && rc=1
ls -l "$MOD"/data/languages/*.sla | awk '{print "   " $5, $9}'

echo "== 2. emulator"
"$HERE/emu-test.sh" "$OUT/emu" || rc=1
"$HERE/emu-test.sh" --broken "$OUT/emu" || rc=1
grep -h -E "emulation \(" "$OUT/emu/emu.txt" | sed 's/^/   /'

echo "== 3. every-entry decode test"
head -c 64 /dev/zero >"$OUT/zero.bin"
for seed in 1 2; do
	D11_GHIDRA_SETTINGS="${TMPDIR:-/tmp}/d11-settings-cov$seed" \
		"$HERE/ghidra-script.sh" raw D11:LE:16:default "$OUT/zero.bin" CoverageCheck.java "$OUT/cov_$seed.txt" 256 "$seed" &
done
wait
tot=$(sed -n 's/^coverage: \([0-9]*\) constructors.*/\1/p' "$OUT/cov_1.txt")
un=$( (cat "$OUT"/cov_*.txt | grep '^unreached' || true) | sort | uniq -c | awk '$1==2' | wc -l)
echo "   $((tot - un))/$tot constructors reached"
(cat "$OUT"/cov_*.txt | grep '^unreached' || true) | sort | uniq -c | awk '$1==2 {print "   " $0}'
((un == 0)) || rc=1

echo "== 4. decode differential"
"$HERE/decode-diff.sh" "$OUT/decode" || rc=1

if [[ -n $REAL ]]; then
	echo "== 5. real code"
	"$HERE/real-binaries.sh" "$REAL" || rc=1
fi
((rc == 0)) && echo "all tests passed" || echo "FAILURES"
exit $rc
