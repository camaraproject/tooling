#!/usr/bin/env node

import fs from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Load the pinned js-yaml from the validation install (CAMARA_NODE_MODULES or
// validation/node_modules) by its explicit path, never from a node_modules
// higher up the tree. The install may be a symlink.
const nodeModules = path.resolve(
  process.env.CAMARA_NODE_MODULES?.trim() ||
    path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "node_modules"),
);
const jsYamlDir = path.join(nodeModules, "js-yaml");
if (!fs.existsSync(path.join(jsYamlDir, "package.json"))) {
  process.stderr.write(`js-yaml not installed in ${nodeModules}\n`);
  process.exit(2);
}
const { load } = createRequire(import.meta.url)(jsYamlDir);

function toPositiveInt(value, fallback) {
  return Number.isInteger(value) && value >= 0 ? value + 1 : fallback;
}

function findingFor(path, error) {
  const reason = error.reason || error.message || "YAML parser error";
  const line = toPositiveInt(error.mark?.line, 1);
  const column = toPositiveInt(error.mark?.column, 1);

  return {
    path,
    line,
    column,
    reason,
    message: `YAML parser rejected the document: ${reason}`,
  };
}

const findings = [];

for (const path of process.argv.slice(2)) {
  try {
    load(fs.readFileSync(path, "utf8"));
  } catch (error) {
    findings.push(findingFor(path, error));
  }
}

process.stdout.write(`${JSON.stringify(findings, null, 2)}\n`);
