// P-code semantics check for the D11 module. Reads a cases file (test/emu/cases.txt), writes the code at
// code:0 (one instruction per address), sets registers and memory, emulates with Ghidra's
// EmulatorHelper until the PC reaches the end address, and compares registers and memory with the
// expected values (worked out by hand from the microcode documentation, bcm-v4.sipsolutions.net).
//
// Case file lines: case <name> / code <hex 64-bit words, 16 digits> / end <hex instruction number> /
//   steps <n> / set <reg> <value> | set shm:<hexaddr>[/<n>] <value> /
//   expect <reg> <value> | expect shm:<addr>[/<n>] <value> | expect callstack:<entry> <value> / end
// Script args: <cases.txt> <outfile> [<trace file>]
//@category Testing

import java.io.BufferedReader;
import java.io.FileReader;
import java.io.PrintStream;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import ghidra.app.emulator.EmulatorHelper;
import ghidra.app.script.GhidraScript;
import ghidra.pcode.emulate.BreakCallBack;
import ghidra.pcode.pcoderaw.PcodeOpRaw;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;

public class D11EmuTest extends GhidraScript {

	private static final long START = 0;
	private int pcodeops;
	private PrintStream trace;
	private static final Map<String, Integer> FLAGS = Map.of();

	private static class Case {
		String name;
		byte[] code;
		long endWord = -1;
		int mainLen = -1;
		int steps = 2000;
		Map<String, Long> set = new LinkedHashMap<>();
		Map<String, Long> expect = new LinkedHashMap<>();
	}

	private List<Case> load(String path) throws Exception {
		List<Case> cases = new ArrayList<>();
		Case c = null;
		try (BufferedReader r = new BufferedReader(new FileReader(path))) {
			String line;
			while ((line = r.readLine()) != null) {
				line = line.trim();
				if (line.isEmpty() || line.startsWith("#")) {
					continue;
				}
				String[] f = line.split("\\s+");
				switch (f[0]) {
					case "case":
						c = new Case();
						c.name = f[1];
						break;
					case "code":
						c.code = new byte[8 * (f.length - 1)];
						for (int i = 1; i < f.length; i++) {
							long w = Long.parseUnsignedLong(f[i], 16);
							for (int b = 0; b < 8; b++) {
								c.code[8 * (i - 1) + b] = (byte) (w >> (8 * b));
							}
						}
						break;
					case "steps":
						c.steps = Integer.decode(f[1]);
						break;
					case "main":
						c.mainLen = Integer.decode(f[1]);
						break;
					case "end":
						if (f.length > 1) {
							c.endWord = Long.parseLong(f[1], 16);
						}
						else {
							cases.add(c);
						}
						break;
					case "set":
						c.set.put(f[1], num(f[2]));
						break;
					case "expect":
						c.expect.put(f[1], num(f[2]));
						break;
					default:
						throw new IllegalArgumentException("bad line: " + line);
				}
			}
		}
		return cases;
	}

	private static long num(String t) {
		return t.startsWith("0x") ? new java.math.BigInteger(t.substring(2), 16).longValue() : Long.decode(t);
	}

	private Address addr(String loc) {
		String[] p = loc.split("[:/]");
		// Address offsets count bytes; "CODE:100" is the instruction at word address 0x100
		ghidra.program.model.address.AddressSpace sp = currentProgram.getAddressFactory().getAddressSpace(p[0]);
		return sp.getAddress(Long.parseLong(p[1], 16) * sp.getAddressableUnitSize());
	}

	private int size(String loc) {
		String[] p = loc.split("/");
		return p.length > 1 ? Integer.parseInt(p[1]) : 1;
	}

	private String runCase(Case c) throws Exception {
		Address start = addr("code:" + Long.toHexString(START));
		Address end = c.endWord >= 0 ? addr("code:" + Long.toHexString(c.endWord))
				: start.add(8 * (c.mainLen >= 0 ? c.mainLen : c.code.length / 8));
		AddressSet body = new AddressSet(start, start.add(c.code.length + 64));
		clearListing(new AddressSet(start, start.add(8 * 1024 - 1)));
		setBytes(start, new byte[8 * 1024]);      // empty program memory (0 = unknown instruction)
		setBytes(start, c.code);
		final EmulatorHelper emu = new EmulatorHelper(currentProgram);
		// hardware operations modelled as pcodeops (CLRWDT, SLEEP, RESET, OPTION): count them and go on
		emu.registerDefaultCallOtherCallback(new BreakCallBack() {
			@Override
			public boolean pcodeCallback(PcodeOpRaw op) {
				pcodeops++;
				return true;
			}
		});
		pcodeops = 0;
		try {
			// registers and memory
			for (Map.Entry<String, Long> e : c.set.entrySet()) {
				String k = e.getKey();
				if (k.contains(":")) {
					int n = size(k);
					byte[] b = new byte[n];
					final boolean big = currentProgram.getLanguage().isBigEndian();
					for (int i = 0; i < n; i++) {
						b[i] = (byte) (e.getValue() >> (8 * (big ? n - 1 - i : i)));
					}
					emu.writeMemory(addr(k), b);
				}
				else if (!FLAGS.containsKey(k)) {
					emu.writeRegister(k, e.getValue());
				}
			}
			for (Map.Entry<String, Long> e : c.set.entrySet()) {
				if (FLAGS.containsKey(e.getKey())) {
					long st = emu.readRegister("STATUS").longValue();
					int bit = FLAGS.get(e.getKey());
					st = (st & ~(1L << bit)) | (e.getValue() << bit);
					emu.writeRegister("STATUS", st);
				}
			}
			emu.writeRegister(emu.getPCRegister(), START);
			int steps = 0;
			java.util.ArrayDeque<String> lastPcs = new java.util.ArrayDeque<>();
			while (!emu.getExecutionAddress().equals(end)) {
				lastPcs.add(Long.toHexString(emu.getExecutionAddress().getAddressableWordOffset()));
				if (trace != null) {
					trace.println(Long.toHexString(emu.getExecutionAddress().getAddressableWordOffset()));
				}
				if (lastPcs.size() > 12) {
					lastPcs.remove();
				}
				if (++steps > c.steps) {
					return "did not reach the end (pc " + emu.getExecutionAddress() + "; last pcs " + lastPcs + ")";
				}
				if (!emu.step(monitor)) {
					return "emulation error at " + emu.getExecutionAddress() + ": " +
						emu.getLastError();
				}
			}
			StringBuilder bad = new StringBuilder();
			for (Map.Entry<String, Long> e : c.expect.entrySet()) {
				String k = e.getKey();
				long got;
				if (k.contains(":")) {
					int n = size(k);
					byte[] b = emu.readMemory(addr(k), n);
					got = 0;
					final boolean big = currentProgram.getLanguage().isBigEndian();
					for (int i = 0; i < n; i++) {
						got |= (long) (b[i] & 0xff) << (8 * (big ? n - 1 - i : i));
					}
				}
				else if (FLAGS.containsKey(k)) {
					got = (emu.readRegister("STATUS").longValue() >> FLAGS.get(k)) & 1;
				}
				else if (k.equals("PCODEOPS")) {
					got = pcodeops;
				}
				else if (k.equals("PCnext")) {
					got = emu.getExecutionAddress().getAddressableWordOffset();
				}
				else {
					got = emu.readRegister(k).longValue();
				}
				if (got != e.getValue()) {
					bad.append(String.format(" %s=0x%x (expected 0x%x)", k, got, e.getValue()));
				}
			}
			return bad.length() == 0 ? null : bad.toString().trim();
		}
		finally {
			emu.dispose();
		}
	}

	@Override
	protected void run() throws Exception {
		String[] args = getScriptArgs();
		List<Case> cases = load(args[0]);
		PrintStream out = new PrintStream(args[1]);
		if (args.length > 2) {
			trace = new PrintStream(args[2]);      // optional: every executed address (debugging)
		}
		int pass = 0, fail = 0;
		for (Case c : cases) {
			String err = runCase(c);
			if (err == null) {
				pass++;
				out.println("PASS " + c.name);
			}
			else {
				fail++;
				out.println("FAIL " + c.name + ": " + err);
			}
		}
		out.printf("emulation (%s): %d passed, %d failed%n", currentProgram.getLanguageID(), pass,
			fail);
		out.close();
	}
}
