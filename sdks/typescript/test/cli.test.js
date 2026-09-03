import assert from "node:assert/strict";
import {mkdtemp, rm, symlink} from "node:fs/promises";
import {tmpdir} from "node:os";
import {join} from "node:path";
import {fileURLToPath} from "node:url";
import {spawnSync} from "node:child_process";
import test from "node:test";

const cli = fileURLToPath(new URL("../bin/cgqa-report-validate.js", import.meta.url));
const fixture = fileURLToPath(new URL("../../testdata/pass-report.json", import.meta.url));

test("CLI validates a regular pinned report", () => {
  const result = spawnSync(process.execPath, [cli, fixture], {encoding: "utf8"});
  assert.equal(result.status, 0, result.stderr);
  assert.equal(JSON.parse(result.stdout).mayAuthorizeAction, false);
});

test("CLI rejects input over 1 MiB before JSON parsing", () => {
  const result = spawnSync(process.execPath, [cli], {
    input: Buffer.alloc(1_048_577, 0x20),
    encoding: "utf8",
  });
  assert.equal(result.status, 2);
  assert.match(result.stderr, /input exceeds 1048576 bytes/);
});

test("CLI rejects symbolic-link input", {skip: process.platform === "win32"}, async () => {
  const directory = await mkdtemp(join(tmpdir(), "cgqa-sdk-"));
  const link = join(directory, "report.json");
  try {
    await symlink(fixture, link);
    const result = spawnSync(process.execPath, [cli, link], {encoding: "utf8"});
    assert.equal(result.status, 2);
    assert.match(result.stderr, /non-symlink regular file/);
  } finally {
    await rm(directory, {recursive: true});
  }
});
