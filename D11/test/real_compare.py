#!/usr/bin/env python3
"""Compare the instructions Ghidra disassembled in a real D11 image (D11RealCheck.java listing,
"<instruction number> <bytes> <text>") with b43-dasm's disassembly of the same file.
  real_compare.py <listing.txt> <image.bin> <outdir>
Both are normalised like the decode differential (norm_slots.py); exit status 1 on any difference."""
import os, re, subprocess, sys
here = os.path.dirname(os.path.abspath(__file__))
lst, img, outd = sys.argv[1:4]
os.makedirs(outd, exist_ok=True)
tool = os.environ.get('B43DASM', 'b43-dasm')
subprocess.run([tool, img, outd + '/ref.s', '-a', '15', '-f', 'raw-le32', '-p'], check=True, capture_output=True)
labels, rows, n = {}, {}, 0
for l in open(outd + '/ref.s'):
    s = l.strip()
    if not s or s.startswith('%') or s.startswith('entry'):
        continue
    if s.endswith(':'):
        labels[s[:-1]] = n
        continue
    m = re.match(r'/\*\s*([0-9A-Fa-f]+)\s*\*/\s*(.*)', s)
    if m:
        n = int(m.group(1), 16)
        rows[n] = m.group(2).replace('\t', ' ')
        n += 1
with open(outd + '/gh.txt', 'w') as g, open(outd + '/ref_raw.txt', 'w') as o:
    for line in open(lst):
        a, b, t = line.rstrip('\n').split(' ', 2)
        i = int(a, 16)
        g.write('%08x 8 %s\n' % (8 * i, t))
        r = rows.get(i, 'BAD')
        r = re.sub(r'\b(L\d+|[a-z_][a-z_0-9]*)\b', lambda m: str(labels[m.group(1)]) if m.group(1) in labels else m.group(1), r)
        o.write('%08x 8 %s\n' % (8 * i, r))
for n_, tool_ in (('gh', 'ghidra'), ('ref_raw', 'b43')):
    subprocess.run([sys.executable, os.path.join(here, 'norm_slots.py'), tool_, outd + '/' + n_ + '.txt', outd + '/' + n_ + '_n.txt'], check=True)
open(outd + '/all.bin', 'wb').write(open(img, 'rb').read())
r = subprocess.run([sys.executable, os.path.join(here, 'd11_diff.py'), outd + '/gh_n.txt', outd + '/ref_raw_n.txt', outd + '/all.bin'], capture_output=True, text=True)
print(r.stdout.rstrip())
sys.exit(r.returncode)
