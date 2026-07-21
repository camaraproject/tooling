// CAMARA Project - support function for Spectral linter
// Extends Spectral's unused-component detection with discriminator mappings.

const COMPONENT_TYPES = [
  "schemas",
  "responses",
  "parameters",
  "examples",
  "requestBodies",
  "headers",
  "links",
  "callbacks",
];

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function decodePointer(value) {
  let decoded;
  try {
    decoded = decodeURIComponent(value);
  } catch {
    decoded = value;
  }
  return decoded.replaceAll("~1", "/").replaceAll("~0", "~");
}

function mappingTargetPath(target, documentSource, schemas) {
  if (typeof target !== "string") return null;

  const decodedTarget = decodePointer(target.trim());
  if (decodedTarget.startsWith("#/components/schemas/")) {
    return `${documentSource}${decodedTarget}`;
  }

  if (
    !decodedTarget.includes("/") &&
    !decodedTarget.includes("#") &&
    Object.hasOwn(schemas, decodedTarget)
  ) {
    return `${documentSource}#/components/schemas/${decodedTarget}`;
  }

  return null;
}

function collectDiscriminatorTargets(document, documentSource, schemas) {
  const targets = new Set();
  const visited = new WeakSet();

  function walk(value) {
    if (value === null || typeof value !== "object" || visited.has(value)) return;
    visited.add(value);

    if (isObject(value.discriminator?.mapping)) {
      for (const target of Object.values(value.discriminator.mapping)) {
        const targetPath = mappingTargetPath(target, documentSource, schemas);
        if (targetPath !== null) targets.add(targetPath);
      }
    }

    for (const child of Object.values(value)) walk(child);
  }

  walk(document);
  return targets;
}

export default (document, _options, context) => {
  const graph = context.documentInventory.graph;
  if (graph === null) {
    throw new Error(
      "camara-discriminator-aware-unused-component requires dependency graph"
    );
  }

  const documentSource = context.document.source ?? "";
  const schemas = isObject(document.components?.schemas)
    ? document.components.schemas
    : {};
  const referenced = new Set(graph.overallOrder().map(decodePointer));
  for (const target of collectDiscriminatorTargets(
    document,
    documentSource,
    schemas
  )) {
    referenced.add(target);
  }

  const findings = [];
  for (const type of COMPONENT_TYPES) {
    const components = document.components?.[type];
    if (!isObject(components)) continue;

    for (const name of Object.keys(components)) {
      const componentPath = `${documentSource}#/components/${type}/${name}`;
      if (!referenced.has(componentPath)) {
        findings.push({
          message: "Potentially unused component has been detected",
          path: [...context.path, "components", type, name],
        });
      }
    }
  }

  return findings;
};
