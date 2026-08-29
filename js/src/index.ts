/**
 * ByteToken — JavaScript / TypeScript SDK
 * ========================================
 * High-efficiency wire transport & context optimizer for AI agents and MCP servers.
 * 
 * GitHub: https://github.com/chandanpandeys/bytetoken
 */

export { encode, decode } from "./core.ts";
export { mcpTool, decodeMcpResponse } from "./mcp.ts";
export type { ByteTokenWireResponse } from "./mcp.ts";
