# ByteToken (TypeScript / JavaScript SDK)

[![npm version](https://img.shields.io/npm/v/bytetoken.svg)](https://www.npmjs.com/package/bytetoken)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

High-efficiency wire transport and context optimization for AI agents, TypeScript MCP servers, and full-stack LLM applications.

- **15–17 bits per token** vs Base64's ~5.6 bits per token.
- **Zero BPE string fragmentation** across LLM context boundaries.
- **Zero native dependencies** (pure TypeScript/JavaScript, runs on Node.js, Bun, Deno, and Browser).

---

## Installation

```bash
npm install bytetoken
```

---

## Quick Start

### 1. Direct Wire Encode & Decode

```typescript
import { encode, decode } from "bytetoken";

// 1. Encode Buffer or Uint8Array to non-merging BPE token string
const original = Buffer.from("arbitrary binary, JSON, or tensor data");
const wireString = encode(original);

// 2. Decode on the receiving agent or backend
const restoredBytes = decode(wireString);
console.log(Buffer.from(restoredBytes).toString("utf-8"));
```

### 2. Model Context Protocol (MCP) Tool Wrapper

```typescript
import { mcpTool, decodeMcpResponse } from "bytetoken";

// Server side: Wrap any MCP tool returning database rows, diffs, or images
export const fetchUserRecords = mcpTool(async (limit: number) => {
  return await db.users.findMany({ take: limit });
}, 512);

// Client / Agent side: Decode tool responses automatically
const toolResult = await fetchUserRecords(100);
if (toolResult._bytetoken_wire) {
  const cleanBytes = decodeMcpResponse(toolResult);
  const data = JSON.parse(Buffer.from(cleanBytes).toString("utf-8"));
}
```

---

## License

MIT © Chandan Pandey (https://github.com/chandanpandeys/bytetoken)
