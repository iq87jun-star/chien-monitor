// RiskGuard — license key generator
//
// Generates buy-once perpetual keys of the form RG-XXXX-XXXX-XXXX using a
// crypto-strong RNG over a Crockford-style base32 alphabet (no ambiguous
// chars: no I, L, O, U). No secrets involved — the key is an opaque token;
// validity lives in the license store, not in the key itself.

import { randomBytes } from "node:crypto";

const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"; // 32 chars, no I L O U

function group(len) {
  const bytes = randomBytes(len);
  let out = "";
  for (let i = 0; i < len; i++) out += ALPHABET[bytes[i] % ALPHABET.length];
  return out;
}

export function generateKey(prefix = "RG") {
  return `${prefix}-${group(4)}-${group(4)}-${group(4)}`;
}

// CLI: `node keygen.js` prints one key
if (import.meta.url === `file://${process.argv[1]}`) {
  console.log(generateKey());
}
