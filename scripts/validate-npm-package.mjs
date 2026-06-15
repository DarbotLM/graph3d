import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const packagePath = path.join(root, "package.json");
const pyprojectPath = path.join(root, "pyproject.toml");
const binPath = path.join(root, "bin", "graph3d.js");

const pkg = JSON.parse(fs.readFileSync(packagePath, "utf8"));
const pyproject = fs.readFileSync(pyprojectPath, "utf8");
const pyVersion = pyproject.match(/^version = "([^"]+)"/m)?.[1];

const required = [
  ["name", pkg.name === "graph3d"],
  ["version matches pyproject.toml", pkg.version === pyVersion],
  ["bin.graph3d", pkg.bin?.graph3d === "./bin/graph3d.js"],
  ["files includes graph3d Python modules", pkg.files?.includes("graph3d/*.py")],
  ["files includes graph3d skill files", pkg.files?.includes("graph3d/skill*.md")],
  ["files includes pyproject.toml", pkg.files?.includes("pyproject.toml")],
  ["build script", Boolean(pkg.scripts?.build)],
  ["npx smoke script", Boolean(pkg.scripts?.["npx:smoke"])],
  ["node engine", Boolean(pkg.engines?.node)]
];

const missing = required.filter(([, ok]) => !ok).map(([name]) => name);
if (missing.length) {
  console.error(`ERROR: npm package validation failed: ${missing.join(", ")}`);
  process.exit(1);
}

const launcher = fs.readFileSync(binPath, "utf8");
if (!launcher.startsWith("#!/usr/bin/env node")) {
  console.error("ERROR: bin/graph3d.js must start with a node shebang.");
  process.exit(1);
}

console.log(`npm package graph3d@${pkg.version} is valid.`);
