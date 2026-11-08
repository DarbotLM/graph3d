import childProcess from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const localVenvPython = process.platform === "win32"
  ? path.join(root, ".venv", "Scripts", "python.exe")
  : path.join(root, ".venv", "bin", "python");

function run(command, args, options = {}) {
  const result = childProcess.spawnSync(command, args, {
    cwd: options.cwd || root,
    env: {
      ...process.env,
      ...(process.env.GRAPH3D_PYTHON || !fs.existsSync(localVenvPython)
        ? {}
        : { GRAPH3D_PYTHON: localVenvPython })
    },
    stdio: options.stdio || "pipe",
    encoding: "utf8",
    shell: false,
    windowsHide: true
  });
  if (result.status !== 0) {
    if (result.stdout) process.stdout.write(result.stdout);
    if (result.stderr) process.stderr.write(result.stderr);
    process.exit(result.status || 1);
  }
  return result;
}

function quoteForCmd(value) {
  const text = String(value);
  if (/^[A-Za-z0-9_./:=@-]+$/.test(text)) {
    return text;
  }
  return `"${text.replace(/"/g, '\\"')}"`;
}

function runNpm(args, options = {}) {
  if (process.platform !== "win32") {
    return run("npm", args, options);
  }
  const commandLine = ["npm", ...args.map(quoteForCmd)].join(" ");
  return run(process.env.ComSpec || "cmd.exe", ["/d", "/s", "/c", commandLine], options);
}

const pack = runNpm(["pack", "--json"]);
const packed = JSON.parse(pack.stdout);
const tarball = packed[0]?.filename;

if (!tarball) {
  console.error("ERROR: npm pack did not produce a tarball.");
  process.exit(1);
}

const corpus = fs.mkdtempSync(path.join(os.tmpdir(), "graph3d-npx-"));
try {
  runNpm(["exec", "--yes", "--package", `./${tarball}`, "--", "graph3d", "--version"], {
    stdio: "inherit"
  });
  fs.writeFileSync(path.join(corpus, "example.py"), "def smoke_example():\n    return 1\n");
  runNpm(["exec", "--yes", "--package", path.join(root, tarball), "--", "graph3d", "update"], {
    cwd: corpus
  });
  if (!fs.existsSync(path.join(corpus, "graph3d-out", "graph.json"))) {
    console.error("ERROR: npm launcher did not update the caller's working directory.");
    process.exitCode = 1;
  }
  console.log(`npx smoke passed for ${tarball}.`);
} finally {
  fs.rmSync(path.join(root, tarball), { force: true });
  fs.rmSync(corpus, { recursive: true, force: true });
}
