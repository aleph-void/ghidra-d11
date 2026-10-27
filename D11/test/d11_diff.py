#!/usr/bin/env python3
"""Bucket the differences between Ghidra's D11 decoding and b43-dasm's (both through norm_slots.py).
  d11_diff.py <ghidra_n.txt> <ref_n.txt> <corpus.bin> [--show N]
Every difference must fall in an explained class (printed); exit status 1 if any is unexplained."""
import collections, struct, sys
g = [l.rstrip('\n').split(' ', 3) for l in open(sys.argv[1])]
r = [l.rstrip('\n').split(' ', 3) for l in open(sys.argv[2])]
words = open(sys.argv[3], 'rb').read()
show = int(sys.argv[sys.argv.index('--show') + 1]) if '--show' in sys.argv else 2
EXTRA = set(range(0x90, 0x9e)) | set(range(0x180, 0x184)) | set(range(0x190, 0x194))   # accepted by the module, unknown to b43

def explain(i, ga, rb, ta, tb, mn):
    w = struct.unpack('<Q', words[8 * i:8 * i + 8])[0]
    opc = (w >> 39) & 0xfff
    if rb and not ga and opc in EXTRA:
        return 'opcode 0x09x / 0x18x / 0x19x (copies of the 0x0Dx compare-and-jumps and of add/sub): in the module, not known to b43'
    if rb and not ga and opc == 0x1e0:
        return 'TKIP lookup: b43 only accepts the immediate flags 0-3 as operand B'
    if ga and not rb and opc == 0x003:
        return 'opcode 0x003 "ret lrX,lrY" (link-register return of the rev 5-14 cores): not decoded'
    if not ga and not rb and ta.rstrip(',') .endswith('n:0') and tb == ta.rsplit(',', 1)[0].rstrip(',') :
        return 'b43-dasm prints no operand for a jump target of 0'
    if mn == 'jmp' and tb == 'jext n:7f,' + ta.split(' ', 1)[1]:
        return 'jext 0x7f (condition always true) is shown as the assembler\'s virtual instruction jmp'
    return None

cnt = collections.Counter(); ex = collections.defaultdict(list); expl = collections.Counter()
for i, (a, b) in enumerate(zip(g, r)):
    ga, rb = a[2] == 'BAD', b[2] == 'BAD'
    ta = ' '.join(a[2:]).strip(); tb = ' '.join(b[2:]).strip()
    if ga and rb: k = ('both-undefined',)
    elif ta == tb: k = ('same',)
    else:
        why = explain(i, ga, rb, ta, tb, a[2])
        if why:
            expl[why] += 1
            continue
        k = ('ghidra-undefined', b[2]) if ga else ('ref-undefined', a[2]) if rb else ('diff', a[2], b[2])
    cnt[k] += 1
    if len(ex[k]) < show: ex[k].append((i, ta, tb))
tot = len(g)
same = cnt[('same',)]; both = cnt[('both-undefined',)]
un = sum(v for k, v in cnt.items() if k[0] not in ('same', 'both-undefined'))
print('words %d  identical %d  both-undefined %d  explained %d  unexplained %d' % (tot, same, both, sum(expl.values()), un))
for why, n in expl.most_common():
    print('  explained %6d  %s' % (n, why))
for k, v in sorted(cnt.items(), key=lambda x: -x[1]):
    if k[0] in ('same', 'both-undefined'): continue
    print('  DIFF %6d  %s' % (v, k))
    for e in ex[k]: print('      %d: ghidra [%s]  ref [%s]' % e)
sys.exit(1 if un else 0)
