import { describe, it, expect } from "vitest";
import { PipeClient } from "../src/pipe-client.js";

describe("PipeClient", () => {
  it("throws on call before discovery", async () => {
    const client = new PipeClient();
    await expect(client.call("system.ping", {})).rejects.toThrow(/not discovered/);
  });

  it("isConnected returns false initially", () => {
    const client = new PipeClient();
    expect(client.isConnected()).toBe(false);
  });

  it("close marks disconnected", () => {
    const client = new PipeClient();
    client.close();
    expect(client.isConnected()).toBe(false);
  });

  it("rejects discovery when endpoint.json missing", async () => {
    const client = new PipeClient();
    await expect(client.discoverAndConnect("C:\\nonexistent\\mo2", 1000)).rejects.toThrow();
  });
});
