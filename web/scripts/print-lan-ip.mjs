#!/usr/bin/env node
/**
 * Prints likely LAN IPv4 addresses (skip loopback / link-local).
 * Use the one that matches your Wi‑Fi subnet (often 192.168.x.x or 10.x.x.x).
 */
import os from "node:os";

const nets = os.networkInterfaces();
const out = [];
for (const name of Object.keys(nets)) {
  for (const net of nets[name] ?? []) {
    if (net.family !== "IPv4" || net.internal) continue;
    if (net.address.startsWith("169.254.")) continue;
    out.push({ name, address: net.address });
  }
}

if (out.length === 0) {
  console.log("No non-internal IPv4 found. Check Wi‑Fi / Ethernet.");
  process.exit(1);
}

console.log("Try these URLs on the other computer (port 5173):\n");
for (const { name, address } of out) {
  console.log(`  http://${address}:5173   (${name})`);
}
console.log(
  "\nIf one fails, try another row. Ignore Docker / bridge / utun if listed.",
);
