#!/usr/bin/env python3
"""Canonical spelling of D11 disassembly for compare.py:  norm_slots.py ghidra|b43 <in> <out>
Operands: [m] -> mem:m, [o,offN] -> memoff:o:N, rN -> r:N, sprHEX / offN -> spr:N, numbers -> numbers
(immediates modulo 2^16), jump targets are plain numbers (b43: label resolved to the instruction number,
Ghidra: the address operand, an instruction number). Mnemonic spellings are mapped: add. -> adds ..."""
import re, sys
tool, src, dst = sys.argv[1:4]
ALIAS = {'add.': 'adds', 'addc.': 'addcs', 'sub.': 'subs', 'subc.': 'subcs'}
def num(t):
    t = t.strip()
    neg = t.startswith('-')
    t = t.lstrip('-')
    v = int(t, 16) if t.lower().startswith('0x') else int(t, 10)
    return -v if neg else v
def operand(t, jump_target=False):
    t = t.strip()
    m = re.fullmatch(r'\[(0x[0-9a-fA-F]+|\d+),\s*off(\d)\]', t)
    if m: return 'memoff:%x:%s' % (num(m.group(1)), m.group(2))
    m = re.fullmatch(r'\[(0x[0-9a-fA-F]+|\d+)\]', t)
    if m: return 'mem:%x' % num(m.group(1))
    m = re.fullmatch(r'r(\d+)', t)
    if m: return 'r:%d' % int(m.group(1))
    m = re.fullmatch(r'spr([0-9a-fA-F]+)', t, re.I)
    if m: return 'spr:%x' % int(m.group(1), 16)
    m = re.fullmatch(r'off(\d)', t)
    if m: return 'spr:%x' % (0xc0 + int(m.group(1)))
    if re.fullmatch(r'-?(0x[0-9a-fA-F]+|\d+)', t):
        v = num(t)
        return 'n:%x' % (v & 0xffff)
    return 'raw:' + t
out = open(dst, 'w')
for line in open(src):
    off, n, text = line.rstrip('\n').split(' ', 2)
    if text == 'BAD':
        out.write('%s %s BAD\n' % (off, n)); continue
    text = text.strip()
    if text.startswith('@'):
        out.write('%s 0 BAD\n' % off); continue            # b43's raw (unknown) instruction
    mn, _, rest = text.partition(' ')
    mn = ALIAS.get(mn.lower(), mn.lower())
    ops = re.findall(r'\s*(\[[^\]]*\]|[^,\s][^,]*)', rest) if rest.strip() else []
    out.write('%s %s %s %s\n' % (off, n, mn, ','.join(operand(o) for o in ops)))
