#!/usr/bin/env python3
"""Which 12-bit opcodes does b43-dasm (arch 15) accept, and as which mnemonic? For every opcode a few
random operand fills (all operand kinds); the word is followed by 20 `nap` so that jump targets < 20
exist. Prints the accepted opcodes grouped by mnemonic; pickles {opcode: [(word, text)...]}.
  opcode_scan.py <out.pkl>      ($B43DASM names the tool)"""
import collections, os, pickle, random, struct, subprocess, sys, tempfile
from multiprocessing import Pool
B = os.environ.get('B43DASM', 'b43-dasm')
NAP = (1 << 39) | (0x1780 << 26) | (0x1780 << 13)

def operand(rnd):
    k = rnd.randrange(6)
    if k == 0: return rnd.getrandbits(12)
    if k == 1: return 0x1000 | rnd.getrandbits(10)
    if k == 2: return 0x1400 | (rnd.randrange(7) << 7) | rnd.getrandbits(7)
    if k == 3: return 0x1780 | rnd.getrandbits(6)
    if k == 4: return 0x1800 | rnd.getrandbits(11)
    return 0x1780 | rnd.getrandbits(7)

def run(args):
    opc, seed = args
    rnd = random.Random(opc * 131 + seed)
    w = (opc << 39) | (operand(rnd) << 26) | (operand(rnd) << 13) | rnd.randrange(16)
    data = struct.pack('<Q', w) + b''.join(struct.pack('<Q', NAP) for _ in range(20))
    with tempfile.TemporaryDirectory() as d:
        open(d + '/i.bin', 'wb').write(data)
        r = subprocess.run([B, d + '/i.bin', d + '/o.txt', '-a', '15', '-f', 'raw-le32'], capture_output=True, text=True)
        if r.returncode:
            return opc, w, None
        lines = [l.strip() for l in open(d + '/o.txt').read().split('\n') if l.strip() and not l.startswith('%') and not l.startswith('entry')]
        lines = [l for l in lines if not l.endswith(':')]
        return opc, w, lines[0] if lines else None

if __name__ == '__main__':
    with Pool(8) as p:
        res = p.map(run, [(o, s) for o in range(4096) for s in range(6)], chunksize=32)
    valid = collections.defaultdict(list)
    for opc, w, t in res:
        if t:
            valid[opc].append((w, t))
    names = collections.OrderedDict()
    for opc in sorted(valid):
        names.setdefault(valid[opc][0][1].split()[0], []).append(opc)
    print(len(valid), 'opcodes accepted')
    for m, l in names.items():
        print(m, ' '.join('%03x' % x for x in l[:24]), len(l))
    pickle.dump(dict(valid), open(sys.argv[1], 'wb'))
