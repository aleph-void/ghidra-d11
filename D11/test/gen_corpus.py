#!/usr/bin/env python3
"""Corpora of 64-bit D11 instruction words (top 13 bits zero, as in the module and in b43's
format): every 12-bit opcode with a number of random operand fields, in chunks of 8192 words (the
size of the 64 KB code space).
  gen_corpus.py <outdir> <seed> [per-opcode=8]    writes <outdir>/chunk<k>.bin and .pkl"""
import os, pickle, random, struct, sys
outd, seed = sys.argv[1], int(sys.argv[2])
per = int(sys.argv[3]) if len(sys.argv) > 3 else 8
rnd = random.Random(seed)
os.makedirs(outd, exist_ok=True)
words = []
# b43-dasm can only label jump targets inside the file it is given, so the target field of the jump
# opcodes (0x04 calls, 0x40/0x41/0x50/0x51/0x70/0x71/0x90-0x9d/0xd0-0xdd compare jumps, 0x4xx-0x7xx)
# stays below 16
JUMPS = set([4, 0x40, 0x41, 0x50, 0x51, 0x70, 0x71] + list(range(0x90, 0x9e)) + list(range(0xd0, 0xde)) +
            list(range(0x400, 0x800)))
for opc in range(4096):
    for _ in range(per):
        w = (opc << 39) | rnd.getrandbits(39)
        if opc in JUMPS:
            w = (w & ~0x1fff) | (w & 0xf)
        words.append(w)
k = 0
for i in range(0, len(words), 8192):
    ch = words[i:i + 8192]
    open(f'{outd}/chunk{k}.bin', 'wb').write(b''.join(struct.pack('<Q', w) for w in ch))
    pickle.dump(ch, open(f'{outd}/chunk{k}.pkl', 'wb'))
    k += 1
print(k, 'chunks', len(words), 'words')
