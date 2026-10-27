#!/usr/bin/env python3
"""Emulator cases for the D11 module. Each case is assembly (assembled once with b43-asm, architecture
15, from b43-tools (GPL, used as a black box); the machine code is kept in cases.txt so the test needs
no tools), initial registers/memory, and results worked out by hand from the microcode documentation
(bcm-v4.sipsolutions.net/802.11/Microcode and the b43-tools README).

  cases.py --assemble        regenerate cases.txt (needs b43-asm: set B43ASM)
  cases.py --broken          print cases.txt with one expectation made wrong
Programs start at code:0. The main part ends in "jmp done"; the last instruction of every program is
"nap" at label "done", and the emulation stops when the PC reaches it."""
import os, struct, subprocess, sys, tempfile

CASES = [
 # (name, asm, set, expect)
 ('add', 'add r1, r2, r3', {'r1': 0x7fff, 'r2': 1}, {'r3': 0x8000}),
 ('add_wraps', 'add r1, r2, r3', {'r1': 0xffff, 'r2': 2}, {'r3': 1}),
 ('add_immediate_negative', 'add r1, -2, r3', {'r1': 5}, {'r3': 3}),
 ('add_carry_chain', 'add. r0, r2, r4\n addc r1, r3, r5', {'r0': 0xffff, 'r1': 0, 'r2': 1, 'r3': 0}, {'r4': 0, 'r5': 1, 'CF': 1}),
 ('addc_uses_old_carry', 'add. r0, r2, r4\n addc r6, r7, r5', {'r0': 0xffff, 'r2': 1, 'r6': 0x10, 'r7': 0x20}, {'r4': 0, 'r5': 0x31}),
 ('add_dot_no_carry_clears', 'add. r0, r2, r4', {'r0': 5, 'r2': 6, 'CF': 1}, {'r4': 11, 'CF': 0}),
 ('sub', 'sub r1, r2, r3', {'r1': 5, 'r2': 7}, {'r3': 0xfffe}),
 ('sub_dot_borrow', 'sub. r1, r2, r3', {'r1': 5, 'r2': 7}, {'r3': 0xfffe, 'CF': 1}),
 ('sub_dot_no_borrow', 'sub. r1, r2, r3', {'r1': 7, 'r2': 7, 'CF': 1}, {'r3': 0, 'CF': 0}),
 ('subc_takes_borrow', 'sub. r1, r2, r3\n subc r5, r6, r4', {'r1': 5, 'r2': 7, 'r5': 0x20, 'r6': 0x10}, {'r4': 0x0f}),
 ('subc_dot_chain', 'sub. r0, r2, r4\n subc. r1, r3, r5', {'r0': 0, 'r1': 1, 'r2': 1, 'r3': 0}, {'r4': 0xffff, 'r5': 0, 'CF': 0}),
 ('mul_high_and_low', 'mul r1, r2, r3', {'r1': 0x1234, 'r2': 0x100}, {'r3': 0x12, 'spr06d': 0x3400}),
 ('mul_big', 'mul r1, r2, r3', {'r1': 0xffff, 'r2': 0xffff}, {'r3': 0xfffe, 'spr06d': 1}),
 ('sl', 'sl r1, 4, r3', {'r1': 0x8001}, {'r3': 0x0010}),
 ('sr', 'sr r1, 4, r3', {'r1': 0x8001}, {'r3': 0x0800}),
 ('sra', 'sra r1, 4, r3', {'r1': 0x8000}, {'r3': 0xf800}),
 ('sra_positive', 'sra r1, 4, r3', {'r1': 0x7000}, {'r3': 0x0700}),
 ('rl', 'rl r1, 4, r3', {'r1': 0x8001}, {'r3': 0x0018}),
 ('rr', 'rr r1, 4, r3', {'r1': 0x8001}, {'r3': 0x1800}),
 ('rl_zero', 'rl r1, 0, r3', {'r1': 0x1234}, {'r3': 0x1234}),
 ('or', 'or r1, r2, r3', {'r1': 0xf0f0, 'r2': 0x0ff0}, {'r3': 0xfff0}),
 ('and', 'and r1, r2, r3', {'r1': 0xf0f0, 'r2': 0x0ff0}, {'r3': 0x00f0}),
 ('xor', 'xor r1, r2, r3', {'r1': 0xf0f0, 'r2': 0x0ff0}, {'r3': 0xff00}),
 ('nand_clears_bits', 'nand r1, r2, r3', {'r1': 0xf0f0, 'r2': 0x0ff0}, {'r3': 0xf000}),
 ('mov', 'mov r1, r3', {'r1': 0xbeef}, {'r3': 0xbeef}),
 ('mov_immediate_negative', 'mov -1, r3', {}, {'r3': 0xffff}),
 ('srx_mask_shift', 'srx 7, 4, r1, r2, r3', {'r1': 0xabcd, 'r2': 0x1234}, {'r3': 0xbc}),
 ('srx_across_registers', 'srx 3, 12, r1, r2, r3', {'r1': 0xabcd, 'r2': 0x1234}, {'r3': 0xa}),
 ('orx_merge', 'orx 3, 4, r1, r2, r3', {'r1': 0x00a5, 'r2': 0x1234}, {'r3': 0x1254}),
 ('orx_rotated_mask', 'orx 3, 14, r1, r2, r3', {'r1': 0x000f, 'r2': 0}, {'r3': 0xc003}),
 ('shm_direct_store_load', 'add r1, r2, [0x20]\n or [0x20], 0, r4', {'r1': 0x100, 'r2': 0x23}, {'shm:20/2': 0x123, 'r4': 0x123}),
 ('shm_offset_register', 'mov 0x10, off0\n add r1, 0, [0x5,off0]\n or [0x15], 0, r4', {'r1': 0xa5a5}, {'shm:15/2': 0xa5a5, 'r4': 0xa5a5}),
 ('shm_offset_register_read', 'mov 0x30, off3\n or [0x2,off3], 0, r4', {'shm:32/2': 0x4321}, {'r4': 0x4321}),
 ('spr_access', 'mov r1, spr100\n or spr100, 0, r2', {'r1': 0x77}, {'spr100': 0x77, 'r2': 0x77}),
 ('jmp_skips', 'jmp L1\n mov 1, r1\nL1: mov 2, r2', {}, {'r1': 0, 'r2': 2}),
 ('je_taken', 'je r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 5, 'r2': 5}, {'r3': 0, 'r4': 2}),
 ('je_not_taken', 'je r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 5, 'r2': 6}, {'r3': 1, 'r4': 2}),
 ('jne_taken', 'jne r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 5, 'r2': 6}, {'r3': 0, 'r4': 2}),
 ('jls_signed', 'jls r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 0xffff, 'r2': 1}, {'r3': 0}),
 ('jl_unsigned_not_taken', 'jl r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 0xffff, 'r2': 1}, {'r3': 1}),
 ('jges_equal', 'jges r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 4, 'r2': 4}, {'r3': 0}),
 ('jgs_signed', 'jgs r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 1, 'r2': 0xffff}, {'r3': 0}),
 ('jles_signed', 'jles r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 0x8000, 'r2': 0}, {'r3': 0}),
 ('jg_unsigned', 'jg r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 0x8000, 'r2': 0}, {'r3': 0}),
 ('jge_unsigned_equal', 'jge r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 3, 'r2': 3}, {'r3': 0}),
 ('jle_unsigned', 'jle r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 4, 'r2': 3}, {'r3': 1}),
 ('jdn_taken', 'jdn r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 3, 'r2': 5}, {'r3': 0}),
 ('jdn_overflow_ignored', 'jdn r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 0x7fff, 'r2': 0xffff}, {'r3': 0}),
 ('jdpz_zero', 'jdpz r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 5, 'r2': 5}, {'r3': 0}),
 ('jdp_zero_not_taken', 'jdp r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 5, 'r2': 5}, {'r3': 1}),
 ('jdnz_zero_taken', 'jdnz r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 5, 'r2': 5}, {'r3': 0}),
 ('jand_taken', 'jand r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 0x12, 'r2': 0x10}, {'r3': 0}),
 ('jand_not_taken', 'jand r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 0xf0, 'r2': 0x0f}, {'r3': 1}),
 ('jnand_taken', 'jnand r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 0xf0, 'r2': 0x0f}, {'r3': 0}),
 ('js_all_bits', 'js r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 0x0c, 'r2': 0x1f}, {'r3': 0}),
 ('js_not_all_bits', 'js r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 0x0c, 'r2': 0x14}, {'r3': 1}),
 ('jns_taken', 'jns r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 0x0c, 'r2': 0x14}, {'r3': 0}),
 ('jzx_bit_clear', 'jzx 0, 3, r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 0x00f7}, {'r3': 0}),
 ('jzx_bit_set', 'jzx 0, 3, r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 0x0008}, {'r3': 1}),
 ('jnzx_high_register', 'jnzx 0, 0, r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 0, 'r2': 1}, {'r3': 1}),
 ('jnzx_across_registers', 'jnzx 3, 14, r1, r2, L1\n mov 1, r3\nL1: mov 2, r4', {'r1': 0, 'r2': 1}, {'r3': 0}),
 ('calls_rets', 'calls fn1\n add r1, 1, r2\n jmp done\nfn1: add r1, 10, r1\n rets', {'r1': 1}, {'r1': 11, 'r2': 12, 'SP': 0}),
 ('calls_pushes_return_address', 'calls fn1\n nop_marker: mov 5, r5\n jmp done\nfn1: mov 4, r4\n rets', {}, {'callstack:0': 1, 'SP': 0, 'r4': 4, 'r5': 5}),
 ('nested_calls', 'calls fa\n jmp done\nfa: add r1, 1, r1\n calls fb\n add r1, 100, r1\n rets\nfb: add r1, 10, r1\n rets', {'r1': 0}, {'r1': 111, 'SP': 0}),
 ('register_copy_loop', 'mov 5, r1\n mov 0, r2\nL1: add r2, r1, r2\n sub r1, 1, r1\n jne r1, 0, L1', {}, {'r2': 15, 'r1': 0}),
]

def assemble(asm):
    prog = '%arch 15\n%start start\nstart:\n' + '\n'.join('\t' + l.strip() if not l.strip().endswith(':') and ':' not in l.split()[0] else l.strip() for l in asm.split('\n')) + '\n\tjmp done\n' \
        if False else None
    lines = []
    for l in asm.split('\n'):
        l = l.strip()
        lines.append(l if (l.split(' ')[0].endswith(':')) else '\t' + l)
    body = '\n'.join(lines)
    # the main part ends with "jmp done"; subroutines (after the first jmp done) follow
    if 'jmp done' in body:
        pre, post = body.split('jmp done', 1)
        body = pre + 'jmp done' + post
    else:
        body += '\n\tjmp done'
    prog = '%arch 15\n%start start\nstart:\n' + body + '\ndone:\n\tnap\n'
    with tempfile.TemporaryDirectory() as d:
        open(d + '/a.asm', 'w').write(prog)
        r = subprocess.run([os.environ.get('B43ASM', 'b43-asm'), d + '/a.asm', d + '/a.bin', '-f', 'raw-le32'],
                           capture_output=True, text=True)
        if r.returncode:
            raise SystemExit('b43-asm failed for %r:\n%s' % (asm, r.stdout + r.stderr))
        data = open(d + '/a.bin', 'rb').read()
    n = len(data) // 8
    return [struct.unpack('<Q', data[8 * i:8 * i + 8])[0] for i in range(n)]

def render(broken=False):
    out = ['# generated by test/emu/cases.py; do not edit']
    first = True
    for name, asm, st, ex in CASES:
        words = assemble(asm)
        out.append('case ' + name)
        out.append('#   ' + asm.replace('\n', ' ; '))
        out.append('code ' + ' '.join('%016x' % w for w in words))
        out.append('end %x' % (len(words) - 1))
        out.append('steps 3000')
        for k, v in st.items():
            out.append('set %s 0x%x' % (k, v))
        for k, v in ex.items():
            out.append('expect %s 0x%x' % (k, v))
        out.append('end')
    return '\n'.join(out) + '\n'

if __name__ == '__main__':
    here = os.path.dirname(os.path.abspath(__file__))
    if '--assemble' in sys.argv:
        open(here + '/cases.txt', 'w').write(render())
    elif '--broken' in sys.argv:
        txt = open(here + '/cases.txt').read().split('\n')
        for i, l in enumerate(txt):
            if l.startswith('expect '):
                p = l.split()
                txt[i] = 'expect %s %s' % (p[1], hex(int(p[2], 0) ^ 1))
                break
        sys.stdout.write('\n'.join(txt))
