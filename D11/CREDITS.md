# Credits

## Upstream

- Source: [CUB3D/ghidra-d11](https://github.com/CUB3D/ghidra-d11), commit `2ecdbe8` ("Instruction fixes",
  2026-05-13), the only commit of the repository's history we received; the module directory is `D11/`.
- Author: CUB3D (GitHub `@CUB3D`; commit author "CUB3D").
- License: Apache-2.0 (the text is in `LICENSE`).
- The module was written for the Broadcom D11 microcode of recent Wi-Fi chips. The instruction set is
  described by the reverse-engineering work of the b43 project.

## Other sources used

- bcm-v4.sipsolutions.net, page "802.11/Microcode" (the microcode instruction format and the meaning of the
  instructions; the Broadcom 43xx reverse-engineering wiki), and the instruction summary in the README of
  b43-tools' assembler: used as the specification.
- b43-tools (Michael Buesch, GPL, https://git.bues.ch/cgit/b43-tools.git, commit
  `36284a5731daae15d345c67248c3205e59f780a7`): `b43-dasm` and `b43-asm` (architecture 15) run as black boxes
  (no source read) for the decode differential and to assemble the test programs.

## What Ghidra-Rare changed

Commits on top of the original, branch `ghidra-rare`:

1. Stand-alone extension build: `build.gradle`, `extension.properties`, `.gitignore`, `LICENSE` in `D11/`.
2. Specification rework (`d11.slaspec`, `spr.sinc`, `d11.cspec`, `d11.pspec`, `d11.ldefs`):
   - operand decoding: signed 11-bit immediates (the `maskim` operand), the offset-register form
     `[offset,offN]` (register field position, value of the register instead of its number, `off6` valid),
     special registers as registers, 13-bit register numbers checked against the format;
   - `srx`/`orx`/`jzx`/`jnzx`: the mask size `M` and shift `S` were swapped; `orx` rotates the mask;
   - code addressed by instruction number in its own space (`wordsize=8`), shared memory in its own space
     of 16-bit words, a `callstack` space; `jmp` (= `jext 0x7f`, always true) is unconditional; `mul`
     writes `spr06d`; the carry flag is the register `CF`; `calls`/`rets` use the call stack;
   - the cspec declares the code space global (the decompiler refused every function) and a stack pointer;
   - `spr.sinc` is the plain register list (the upstream list contained non-register names and a
     register file size that did not match).
3. `README.md`, `GHIDRA-RARE.md`, this file, `test/`.
