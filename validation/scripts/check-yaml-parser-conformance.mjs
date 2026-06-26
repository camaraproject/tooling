#!/usr/bin/env node

import fs from "node:fs";
import { load } from "js-yaml";

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
