#!/usr/bin/env python3
"""Run b43-dasm (b43-tools, GPL, used as a black box; architecture 15 = 64-bit D11 microcode) over a
file of 64-bit little-endian instruction words and print "<byte offset> <len> <text>" lines like
DumpSlots does. One process per word (b43-dasm stops at the first invalid word); each word is
followed by 20 NAP instructions so that jump targets 0-20 exist, and a jump target label is
replaced by the instruction number it names.
  ref_slots.py <corpus.bin> <out.txt>          ($B43DASM names the tool)
Jump targets of a word are taken modulo 16 for the run (the oracle can only label targets inside
the file); gen_corpus.py keeps the target field of jump opcodes below 16 for that reason."""
import os, re, struct, subprocess, sys, tempfile
from multiprocessing import Pool
tool = os.environ.get('B43DASM', 'b43-dasm')
NAP = (1 << 39) | (0x1780 << 26) | (0x1780 << 13)
src, outp = sys.argv[1:3]
data = open(src, 'rb').read()

def one(i):
    w = data[8 * i:8 * i + 8]
    with tempfile.TemporaryDirectory() as d:
        open(d + '/i.bin', 'wb').write(w + struct.pack('<Q', NAP) * 20)
        r = subprocess.run([tool, d + '/i.bin', d + '/o.txt', '-a', '15', '-f', 'raw-le32'], capture_output=True, text=True)
        if r.returncode:
            return i, None
        labels, first, n = {}, None, 0
        for l in open(d + '/o.txt'):
            s = l.strip()
            if not s or s.startswith('%') or s.startswith('entry'):
                continue
            if s.endswith(':'):
                labels[s[:-1]] = n
                continue
            if n == 0:
                first = s
            n += 1
        if first is None:
            return i, None
        first = first.replace('\t', ' ')
        first = re.sub(r'\bL\d+\b', lambda m: str(labels.get(m.group(0), m.group(0))), first)
        return i, first

if __name__ == '__main__':
    n = len(data) // 8
    with Pool(8) as p:
        res = p.map(one, range(n), chunksize=64)
    with open(outp, 'w') as f:
        for i, t in sorted(res):
            f.write('%08x %d %s\n' % (8 * i, 0 if t is None else 8, 'BAD' if t is None else t))
