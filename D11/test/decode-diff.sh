#!/usr/bin/env bash
# Decode differential: test/decode-diff.sh <outdir>
# Every 12-bit opcode with random operand fields of every kind (test/gen_corpus.py, 8 words per opcode,
# two seeds: 65536 words) is decoded by Ghidra (D11:LE:16:default) and by b43-dasm (b43-tools,
# architecture 15, $B43DASM) and the two disassemblies are compared (test/norm_slots.py spelling).
# Every difference must fall in an explained class (test/d11_diff.py).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source "$HERE/env.sh"
OUTD=$(readlink -m "${1:-${TMPDIR:-/tmp}/d11-decode}")
mkdir -p "$OUTD"
rc=0
if ! command -v "${B43DASM:-b43-dasm}" >/dev/null; then echo "b43-dasm not found (set B43DASM): skipped"; exit 0; fi
for seed in 1 2; do
	D=$OUTD/s$seed
	python3 "$HERE/gen_corpus.py" "$D" $seed 8 >/dev/null
	n=$(ls "$D"/chunk*.bin | wc -l)
	for ((k = 0; k < n; k++)); do
		D11_GHIDRA_SETTINGS="${TMPDIR:-/tmp}/d11-settings-$seed-$k" \
			"$HERE/ghidra-slots.sh" D11:LE:16:default "$D/chunk$k.bin" 8 "$D/gh$k.txt" &
		python3 "$HERE/ref_slots.py" "$D/chunk$k.bin" "$D/ref$k.txt" &
	done
	wait
	: >"$D/all.bin"; : >"$D/gh_n.txt"; : >"$D/ref_n.txt"
	for ((k = 0; k < n; k++)); do
		cat "$D/chunk$k.bin" >>"$D/all.bin"
		python3 "$HERE/norm_slots.py" ghidra "$D/gh$k.txt" "$D/ghn$k.txt"; cat "$D/ghn$k.txt" >>"$D/gh_n.txt"
		python3 "$HERE/norm_slots.py" b43 "$D/ref$k.txt" "$D/refn$k.txt"; cat "$D/refn$k.txt" >>"$D/ref_n.txt"
	done
	echo "seed $seed: $(python3 "$HERE/d11_diff.py" "$D/gh_n.txt" "$D/ref_n.txt" "$D/all.bin" | head -1)"
	python3 "$HERE/d11_diff.py" "$D/gh_n.txt" "$D/ref_n.txt" "$D/all.bin" | tail -n +2 | sed 's/^/   /' || rc=1
done
exit $rc
