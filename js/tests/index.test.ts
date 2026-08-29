import test from "node:test";
import assert from "node:assert";
import { encode, decode, mcpTool, decodeMcpResponse } from "../src/index.ts";

test("ByteToken JS - Basic Lossless Roundtrip", () => {
  const original = Buffer.from("Hello ByteToken TypeScript SDK!");
  const encoded = encode(original);
  const decoded = decode(encoded);
  
  assert.deepStrictEqual(Buffer.from(decoded), original);
});

test("ByteToken JS - Binary Data Roundtrip", () => {
  const randomBytes = Buffer.alloc(512);
  for (let i = 0; i < 512; i++) {
    randomBytes[i] = (i * 37 + 13) % 256;
  }
  
  const encoded = encode(randomBytes);
  const decoded = decode(encoded);
  
  assert.deepStrictEqual(Buffer.from(decoded), randomBytes);
});

test("ByteToken JS - MCP Tool Wrapper", async () => {
  const mockTool = mcpTool(async () => {
    return { status: "ok", records: Array.from({ length: 50 }, (_, i) => ({ id: i, user: `user_${i}` })) };
  }, 100);

  const response = await mockTool();
  assert.strictEqual(response._bytetoken_wire, true);
  
  const restoredBytes = decodeMcpResponse(response);
  const restoredObj = JSON.parse(Buffer.from(restoredBytes).toString("utf-8"));
  assert.strictEqual(restoredObj.records.length, 50);
});
