# Ghidra-Rare notes: D11

Verification of the Broadcom D11 module (CUB3D/ghidra-d11) to the Ghidra-Rare bar
([docs/VERIFICATION.md](https://github.com/aleph-void/Ghidra-Rare/blob/main/docs/VERIFICATION.md)).
`CREDITS.md` has the provenance and the list of changes, `README.md` the memory model and the
limitation table.

- Language ID: `D11:LE:16:default` (upstream's). No collision with Ghidra's languages or other modules.
- Tested with Ghidra 12.1.3, 12.1.4 and 12.2; `d11.sla` is about 22 KB.
- **The module is not about the DEC PDP-11 nor the Texas Instruments T11**: D11 is Broadcom's Wi-Fi MAC
  micro-sequencer (core revisions 15 and later, 64-bit instructions).

## Running the tests

```
GHIDRA_INSTALL_DIR=<ghidra with this directory in Ghidra/Processors/D11> B43DASM=<b43-dasm> B43ASM=<b43-asm> test/run-tests.sh [--real <workdir>] [outdir]
```

`b43-dasm` and `b43-asm` come from b43-tools (https://git.bues.ch/cgit/b43-tools.git; `make` in `disassembler`
and `assembler`; the `b43-asm` shell wrapper preprocesses with `gcc -E` and calls `b43-asm.bin`). Without
`B43DASM` the differential steps are skipped.

## Results

| Area | Result |
|---|---|
| Decode | 65536 words (every 12-bit opcode, 8 random operand fills each, two seeds) against `b43-dasm -a 15`: both-undefined 39952, identical about 25 000, **0 unexplained**; the 5 explained classes are listed below (`test/d11_diff.py`). `reached/total` constructors: **65/65**. |
| Semantics | 65 emulator cases (`test/emu/cases.txt`; assembled by `b43-asm`, expectations worked out by hand from the microcode documentation: add/sub with carry use and carry setting, 32-bit carry chains, mul high/low halves, all shifts and rotates, logic, `srx`/`orx` mask and shift (including across the register pair and the rotated mask), every compare-and-jump in both directions with signed/unsigned and the signed-difference jumps, `jzx`/`jnzx`, `jand`/`js` families, shared memory direct, `[offset,offN]` read and write, special registers, `calls`/`rets` and nested calls with the return stack contents); one wrong expectation is reported by the "broken expectation" run. |
| Real code | `test/real/algos.asm` (self-written, assembled by `b43-asm`): sum/xor checksum with offset-register addressing, bitwise CRC-16/CCITT with `jzx`, bubble sort with compare-and-jump; 6 random/edge input vectors each match results computed in Python; imported with auto-analysis: 52 instructions, 5 functions, 0 bad-instruction bookmarks, 0 error bookmarks, 0 decompile failures; the disassembly equals `b43-dasm`'s at every address. No freely licensed D11 microcode exists (Broadcom's images are not redistributable), so no third-party code was run. |
| Spec files | `d11.cspec` (code and shm global, stack pointer), `d11.pspec` (program counter, entry), no ELF/DWARF/loader. |

Explained decode differences (all in `test/d11_diff.py`):

- opcodes `0x090`-`0x09d` (copies of the compare-and-jumps `0x0d0`-`0x0dd`) and `0x180`-`0x183`/`0x190`-`0x193`
  (copies of add/sub): the module (upstream) decodes them, neither b43 nor the documentation lists them
  (kept, unverified; the upstream author may have found them in newer firmware);
- opcode `0x003` (`ret lrX,lrY`, the link-register return of cores 5-14): b43 decodes it, the module does not
  (the call stack of core 15 is `calls`/`rets`);
- `tkip` with an operand B outside the flags 0-3: b43 requires an immediate 0-3;
- `jext 0x7f` is shown as the assembler's virtual `jmp`;
- b43-dasm prints no operand for a jump to instruction 0.

### Doesn't work

- **TKIP S-box** (`tkip`): the 256-entry table is data, not p-code; the instruction is a pcodeop.
- **External conditions** (`jext`/`jnext` and every condition register bit): hardware state, a pcodeop;
  `jext 0x7f` (= `jmp`) is exact.
- **`nap`** waits for a hardware event (a pcodeop).
- **Shift counts of 16 or more** (`sl`, `sr`, `sra`, `rl`, `rr`) follow the documentation's formulas (shifts
  by 16 and more give 0); what the hardware does with the high bits of the count is not documented.
- **Carry after a subtraction** is modelled as the borrow (A < B + carry); the documentation says only
  "set carry".
- **Decompiler output** shows the hardware return stack as memory writes to a pointer around each
  `calls` (return address pushes).
- Link-register instructions of the older cores (`call lrX` = opcode 002, `ret lrX,lrY` = 003).
- Special register numbers above `0x3ff` and general registers above `r127` do not exist (13-bit operands).

### Unverified

- Real firmware: none under a free license was available, so no real image was disassembled or decompiled
  (the algorithm programs are self-written). Behaviours that the documentation leaves open (carry after
  subtraction, large shift counts, memory addressing wrap-around, SPR side effects) are unverified.
- The copies of the compare/add/sub opcodes listed above.
- Core revisions below 15 (48-bit instructions, link registers) are a different format and are not covered.

### Reference tool notes

- `b43-asm` reports "Using offset register 6. This register is broken on certain devices"; `b43-dasm`
  accepts `[o,off6]`.
- `b43-dasm` stops at the first invalid instruction and needs jump targets inside the file; the differential
  runs it once per word on a file padded with `nap` instructions.
- `b43-dasm` prints a jump to instruction 0 without its target operand.
- The wiki's operand table lists `0b10111 0.......` as "does not exist?"; the tools accept it (`off6`).
- `b43-asm` limits the general registers to `r0`-`r63`; `b43-dasm` decodes `r0`-`r127`.
