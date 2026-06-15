#!/usr/bin/env node
"use strict";

const childProcess = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const packageRoot = path.resolve(__dirname, "..");
const packageJson = JSON.parse(fs.readFileSync(path.join(packageRoot, "package.json"), "utf8"));
const packageVersion = packageJson.version;

function pythonCandidates() {
  if (process.env.GRAPH3D_PYTHON) {
    return [{ command: process.env.GRAPH3D_PYTHON, args: [] }];
  }

  if (process.platform === "win32") {
    return [
      { command: "py", args: ["-3"] },
      { command: "python", args: [] },
      { command: "python3", args: [] }
    ];
  }

  return [
    { command: "python3", args: [] },
    { command: "python", args: [] }
  ];
}

function run(candidate, args, options = {}) {
  return childProcess.spawnSync(candidate.command, [...candidate.args, ...args], {
    cwd: packageRoot,
    env: pythonEnv(options.env),
    stdio: options.stdio || "inherit",
    windowsHide: true
  });
}

function pythonEnv(extraEnv = {}) {
  const pythonPath = [packageRoot, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);
  return {
    ...process.env,
    PYTHONPATH: pythonPath,
    ...extraEnv
  };
}

function hasSupportedPython(candidate) {
  const probe = run(candidate, [
    "-c",
    "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
  ], { stdio: "ignore" });
  return probe.status === 0;
}

function hasMatchingGraph3d(candidate) {
  const probe = run(candidate, [
    "-c",
    `import importlib.metadata as md; raise SystemExit(0 if md.version("graph3d") == "${packageVersion}" else 1)`
  ], { stdio: "ignore" });
  return probe.status === 0;
}

function findBasePython() {
  for (const candidate of pythonCandidates()) {
    if (hasSupportedPython(candidate)) {
      return candidate;
    }
  }
  return null;
}

function findInstalledGraph3d() {
  for (const candidate of pythonCandidates()) {
    if (hasSupportedPython(candidate) && hasMatchingGraph3d(candidate)) {
      return candidate;
    }
  }
  return null;
}

function defaultVenvDir() {
  if (process.env.GRAPH3D_NPM_VENV) {
    return process.env.GRAPH3D_NPM_VENV;
  }
  return path.join(os.homedir(), ".graph3d", "npm-python", packageVersion);
}

function venvPython(venvDir) {
  return process.platform === "win32"
    ? path.join(venvDir, "Scripts", "python.exe")
    : path.join(venvDir, "bin", "python");
}

function ensureManagedPython(basePython) {
  const venvDir = defaultVenvDir();
  const pythonPath = venvPython(venvDir);
  const managed = { command: pythonPath, args: [] };

  if (fs.existsSync(pythonPath) && hasSupportedPython(managed) && hasMatchingGraph3d(managed)) {
    return managed;
  }

  fs.mkdirSync(venvDir, { recursive: true });

  console.error(`graph3d npm launcher: preparing Python environment at ${venvDir}`);
  let result = run(basePython, ["-m", "venv", venvDir]);
  if (result.status !== 0) {
    fail("could not create a Python virtual environment", result.status);
  }

  result = run(managed, ["-m", "pip", "install", "--upgrade", "pip"]);
  if (result.status !== 0) {
    fail("could not upgrade pip in the managed Python environment", result.status);
  }

  result = run(managed, ["-m", "pip", "install", packageRoot]);
  if (result.status !== 0) {
    fail("could not install the bundled graph3d Python package", result.status);
  }

  return managed;
}

function fail(message, status = 1) {
  console.error(`ERROR: ${message}.`);
  console.error("Install Python 3.10+ and ensure pip can install graph3d dependencies, or set GRAPH3D_PYTHON to a Python executable with graph3d installed.");
  process.exit(status || 1);
}

function main() {
  const args = process.argv.slice(2);
  let python = findInstalledGraph3d();

  if (!python) {
    const basePython = findBasePython();
    if (!basePython) {
      fail("no supported Python 3.10+ interpreter was found on PATH");
    }
    python = ensureManagedPython(basePython);
  }

  const result = run(python, ["-m", "graph3d", ...args]);
  if (result.error) {
    fail(result.error.message);
  }
  process.exit(result.status === null ? 1 : result.status);
}

main();
