/**
 * ByteToken — Model Context Protocol (MCP) TypeScript Middleware
 * ===============================================================
 * Automatically encodes large tool returns to non-merging ByteToken strings.
 */

import { encode, decode } from "./core.ts";

export interface ByteTokenWireResponse {
  _bytetoken_wire: true;
  encoding: string;
  original_bytes: number;
  wire_chars: number;
  payload: string;
}

/**
 * Wrap an async MCP tool handler function with ByteToken wire compression.
 */
export function mcpTool<T extends (...args: any[]) => Promise<any> | any>(
  fn: T,
  thresholdBytes: number = 1024
): (...args: Parameters<T>) => Promise<any> {
  return async (...args: Parameters<T>) => {
    const result = await fn(...args);

    let rawBuffer: Buffer;
    if (Buffer.isBuffer(result)) {
      rawBuffer = result;
    } else if (result instanceof Uint8Array) {
      rawBuffer = Buffer.from(result);
    } else if (typeof result === "object" || typeof result === "string") {
      const text = typeof result === "string" ? result : JSON.stringify(result);
      rawBuffer = Buffer.from(text, "utf-8");
    } else {
      return result;
    }

    if (rawBuffer.length < thresholdBytes) {
      return result;
    }

    const wirePayload = encode(rawBuffer);
    const wireResponse: ByteTokenWireResponse = {
      _bytetoken_wire: true,
      encoding: "bytetoken-15",
      original_bytes: rawBuffer.length,
      wire_chars: wirePayload.length,
      payload: wirePayload
    };

    return wireResponse;
  };
}

/**
 * Decode a ByteToken wire response back to a raw Buffer or parsed JSON.
 */
export function decodeMcpResponse(response: any): Uint8Array {
  if (!response || typeof response !== "object" || !response._bytetoken_wire) {
    throw new Error("Payload is not a valid ByteToken wire response.");
  }
  return decode(response.payload);
}
