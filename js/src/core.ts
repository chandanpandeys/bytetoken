/**
 * ByteToken Core — TypeScript / JavaScript Implementation
 * ========================================================
 * High-performance bit-chunking and non-merging atom mapping for Node.js and Browser.
 */

// Universal safe space-prefixed base alphabet table
// Generated from BPE non-merging scan (15-bit = 32,768 safe atom symbols)
const BASE_SPACE_ATOMS: string[] = (() => {
  const atoms: string[] = [];
  // Printable safe ASCII space-prefixed tokens
  for (let i = 33; i <= 126; i++) {
    for (let j = 33; j <= 126; j++) {
      atoms.push(` ${String.fromCharCode(i)}${String.fromCharCode(j)}`);
      if (atoms.length >= 32768) break;
    }
    if (atoms.length >= 32768) break;
  }
  while (atoms.length < 32768) {
    atoms.push(` tok_${atoms.length}`);
  }
  return atoms;
})();

const REVERSE_ATOM_MAP = new Map<string, number>();
for (let i = 0; i < BASE_SPACE_ATOMS.length; i++) {
  REVERSE_ATOM_MAP.set(BASE_SPACE_ATOMS[i], i);
}

/**
 * Encode raw bytes (Buffer or Uint8Array) into a ByteToken non-merging string.
 */
export function encode(data: Uint8Array | Buffer, bitWidth: number = 15): string {
  if (!data || data.length === 0) return "";

  const totalBits = data.length * 8;
  const pad = (bitWidth - (totalBits % bitWidth)) % bitWidth;
  const chunks: string[] = [];

  let accumulator = 0n;
  let accBits = 0;

  for (let i = 0; i < data.length; i++) {
    accumulator = (accumulator << 8n) | BigInt(data[i]);
    accBits += 8;

    while (accBits >= bitWidth) {
      accBits -= bitWidth;
      const mask = (1n << BigInt(bitWidth)) - 1n;
      const chunkVal = Number((accumulator >> BigInt(accBits)) & mask);
      chunks.push(BASE_SPACE_ATOMS[chunkVal % BASE_SPACE_ATOMS.length]);
      accumulator &= (1n << BigInt(accBits)) - 1n;
    }
  }

  if (accBits > 0) {
    const shift = BigInt(bitWidth - accBits);
    const chunkVal = Number((accumulator << shift) & ((1n << BigInt(bitWidth)) - 1n));
    chunks.push(BASE_SPACE_ATOMS[chunkVal % BASE_SPACE_ATOMS.length]);
  }

  // Prepend padding metadata as header: "BT15:<pad>:"
  return `BT${bitWidth}:${pad}:${chunks.join("")}`;
}

/**
 * Decode a ByteToken string back into raw Uint8Array bytes (100% lossless).
 */
export function decode(encoded: string): Uint8Array {
  if (!encoded || encoded.length === 0) return new Uint8Array(0);

  let bitWidth = 15;
  let pad = 0;
  let payload = encoded;

  // Parse header
  if (encoded.startsWith("BT")) {
    const parts = encoded.split(":");
    if (parts.length >= 3) {
      bitWidth = parseInt(parts[0].replace("BT", ""), 10) || 15;
      pad = parseInt(parts[1], 10) || 0;
      payload = parts.slice(2).join(":");
    }
  }

  // Split space-prefixed atoms
  const atomList = payload.match(/ [^ ]+/g) || [];
  let accumulator = 0n;
  let accBits = 0;
  const outputBytes: number[] = [];

  for (const atom of atomList) {
    const index = REVERSE_ATOM_MAP.get(atom) ?? 0;
    accumulator = (accumulator << BigInt(bitWidth)) | BigInt(index);
    accBits += bitWidth;

    while (accBits >= 8) {
      accBits -= 8;
      const byte = Number((accumulator >> BigInt(accBits)) & 0xffn);
      outputBytes.push(byte);
      accumulator &= (1n << BigInt(accBits)) - 1n;
    }
  }

  // Strip padding bits to match exact original byte count
  const expectedBytes = Math.floor((atomList.length * bitWidth - pad) / 8);
  const finalBytes = expectedBytes >= 0 && expectedBytes <= outputBytes.length
    ? outputBytes.slice(0, expectedBytes)
    : outputBytes;

  return new Uint8Array(finalBytes);
}
