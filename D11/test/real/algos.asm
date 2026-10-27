// Test programs for the Ghidra-Rare D11 module (written for Ghidra-Rare, Apache-2.0 like the module).
// Assembled with b43-asm (architecture 15). Three routines: a sum/xor checksum over 16 shared-memory
// words (offset register addressing), a bitwise CRC-16/CCITT over 16 words (jzx, sl, xor), and a bubble
// sort of 8 words (compare-and-jump, memory operands). Results are left in shared memory.
%arch 15
%start start

start:
	calls checksum
	calls crc16
	calls sort
	jmp done

// shm[0x00..0x0f] -> shm[0x80] = sum, shm[0x81] = xor
checksum:
	mov 0, r1
	mov 0, r2
	mov 0, off0
	mov 16, r3
cs_loop:
	add r1, [0x0,off0], r1
	xor r2, [0x0,off0], r2
	add off0, 1, off0
	sub r3, 1, r3
	jne r3, 0, cs_loop
	or r1, 0, [0x80]
	or r2, 0, [0x81]
	rets

// CRC-16/CCITT (poly 0x1021, init 0xffff) over the 16 words shm[0x00..0x0f], each XORed in whole:
// shm[0x82] = crc
crc16:
	sl 1, 12, r5
	or r5, 0x21, r5
	mov -1, r1
	mov 0, off0
	mov 16, r4
	mov 0, r6
crc_word:
	xor r1, [0x0,off0], r1
	mov 16, r3
crc_bit:
	jzx 0, 15, r1, r6, crc_nox
	sl r1, 1, r1
	xor r1, r5, r1
	jmp crc_next
crc_nox:
	sl r1, 1, r1
crc_next:
	sub r3, 1, r3
	jne r3, 0, crc_bit
	add off0, 1, off0
	sub r4, 1, r4
	jne r4, 0, crc_word
	or r1, 0, [0x82]
	rets

// bubble sort (unsigned, ascending) of the 8 words shm[0x40..0x47]
sort:
	mov 7, r10
sort_outer:
	mov 0x40, off0
	mov 7, r11
sort_inner:
	or [0x0,off0], 0, r1
	or [0x1,off0], 0, r2
	jle r1, r2, sort_noswap
	or r2, 0, [0x0,off0]
	or r1, 0, [0x1,off0]
sort_noswap:
	add off0, 1, off0
	sub r11, 1, r11
	jne r11, 0, sort_inner
	sub r10, 1, r10
	jne r10, 0, sort_outer
	rets

done:
	nap
	jmp done
