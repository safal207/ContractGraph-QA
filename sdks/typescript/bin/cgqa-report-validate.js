#!/usr/bin/env node
import {readFile, stat} from "node:fs/promises";
import {validateConformanceReportJson} from "../src/index.js";

const MAX_BYTES = 1_048_576;

async function input() {
  const path = process.argv[2];
  if (process.argv.length > 3 || path === "--help" || path === "-h") {
    console.log("usage: cgqa-report-validate [report.json]\nReads stdin when no file is supplied.");
    process.exit(path === "--help" || path === "-h" ? 0 : 2);
  }
  if (path) {
    const metadata = await stat(path);
    if (!metadata.isFile()) throw new Error("input must be a regular file");
    if (metadata.size > MAX_BYTES) throw new Error(`input exceeds ${MAX_BYTES} bytes`);
    return readFile(path, "utf8");
  }
  const chunks = [];
  let size = 0;
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > MAX_BYTES) throw new Error(`input exceeds ${MAX_BYTES} bytes`);
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
}

try {
  const summary = validateConformanceReportJson(await input());
  process.stdout.write(`${JSON.stringify(summary)}\n`);
} catch (error) {
  process.stderr.write(`cgqa-report-validate: ${error.message}\n`);
  process.exitCode = 2;
}
