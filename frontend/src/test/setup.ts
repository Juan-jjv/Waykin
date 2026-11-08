// Vitest setup. Node 18 has WebCrypto but not as a global, so lib/crypto's tests fail without this.
// Node 20+ already provides globalThis.crypto, and then this does nothing.
import { webcrypto } from "node:crypto";

if (!globalThis.crypto?.subtle) {
  Object.defineProperty(globalThis, "crypto", { value: webcrypto, configurable: true });
}
