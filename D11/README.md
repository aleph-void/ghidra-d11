# Broadcom D11 for Ghidra

Ghidra processor module for the **Broadcom D11** micro-sequencer ("PSM"), the 802.11 MAC state machine
of Broadcom Wi-Fi chips, in the form of core revisions 15 and later: 64-bit instructions with three
13-bit operands (what the `b43-tools` assembler calls "architecture 15"). Language ID
`D11:LE:16:default`. This is not the PDP-11.

Original work by CUB3D (Apache-2.0, [CUB3D/ghidra-d11](https://github.com/CUB3D/ghidra-d11)). This fork
keeps the original commit and adds the Ghidra-Rare verification and fixes: `CREDITS.md` says who did
what, `GHIDRA-RARE.md` has the test results, known gaps and the notes on the reference tools. Prebuilt
zips for Ghidra 12.1.3, 12.1.4 and 12.2 are on the fork's Releases page.

## Install

*File > Install Extensions* with the zip for your Ghidra version. The module directory is `D11/`.
Load a microcode image (the raw `ucode` blob: 8 bytes per instruction, little endian, as `b43-asm
-f raw-le32` writes it) with the *Raw Binary* loader and the language `D11:LE:16:default`.

Address spaces: `code` (one address per instruction; jump targets are instruction numbers), `shm`
(the shared memory, 16-bit words addressed by word number), `callstack` (the hardware stack of `calls`
and `rets`). Registers `r0`-`r127`, the special registers `spr000`-`spr3ff` (`off0`-`off6` are
`spr0c0`-`spr0c6`, the offset registers of `[offset,offN]`), the carry bit `CF`.

## Known limitations of the original, and what became of them

The original README is two lines. These come from testing and from the comments in the specification:

| Limitation | Status |
|---|---|
| `mul` writes only the high half ("TODO: IHR") | fixed: the low half goes to `spr06d` |
| Immediate operands with the sign bit set decoded as the accumulator ("maskim") | fixed (signed 11-bit immediates) |
| `[offset,offN]`: the register field was read from the wrong bits and its number was added instead of the register | fixed |
| Special registers were dereferenced as pointers | fixed (they are registers) |
| `srx`, `orx`, `jzx`, `jnzx`: mask size and shift swapped | fixed |
| Code and shared memory were one address space (jump targets multiplied by 8) | fixed (separate spaces, instruction numbers) |
| Decompiler failed ("code may not be a global space") | fixed |
| `tkip` S-box lookup (pcodeop), external conditions `jext`/`jnext` (pcodeop), `nap` | remaining: hardware (see GHIDRA-RARE.md) |
| Opcodes the module accepts that no documentation or tool lists (the `0x09x` copies of the compare-and-jumps, `0x180`/`0x190` as add/sub) | kept, unverified |
