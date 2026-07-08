// CAMARA Project - support function for Spectral linter
// Checks integer schema values against the 53-bit integer range recommended
// by the OpenAPI Format Registry for int64.
//
// Recipients that parse JSON numbers into double-precision (binary64)
// representation cannot preserve integer literals outside the 53-bit range;
// release snapshot bundling is one such consumer and can silently round the
// value before the snapshot is published, so r4 validation rejects them.

const MAX_SAFE_INTEGER = Number.MAX_SAFE_INTEGER;
const INTEGER_VALUE_KEYS = [
  "maximum",
  "minimum",
  "exclusiveMaximum",
  "exclusiveMinimum",
  "default",
  "example",
  "multipleOf",
];
const SCHEMA_ARRAY_KEYS = ["allOf", "anyOf", "oneOf"];
const SCHEMA_OBJECT_KEYS = ["items", "additionalProperties", "not"];

export default (document, _options, context) => {
  const errors = [];

  function addFinding(value, path, label) {
    errors.push({
      message:
        `Integer schema ${label} ${String(value)} exceeds the 53-bit ` +
        `integer range [-${MAX_SAFE_INTEGER}, ${MAX_SAFE_INTEGER}] ` +
        "recommended by the OpenAPI Format Registry. Values outside this " +
        "range are silently altered by tooling that parses JSON numbers " +
        "into double-precision (binary64) representation, including " +
        "release bundling; use a value within range or model it as a " +
        "string (CAMARA Design Guide section 2.2).",
      path,
    });
  }

  function isUnsafeIntegerValue(value) {
    return (
      typeof value === "number" &&
      Number.isFinite(value) &&
      Number.isInteger(value) &&
      Math.abs(value) > MAX_SAFE_INTEGER
    );
  }

  function checkIntegerValue(schema, path, key) {
    if (Object.prototype.hasOwnProperty.call(schema, key) && isUnsafeIntegerValue(schema[key])) {
      addFinding(schema[key], [...path, key], `'${key}' value`);
    }
  }

  function checkSchema(schema, path) {
    if (!schema || typeof schema !== "object" || schema.$ref) return;

    if (schema.type === "integer") {
      for (const key of INTEGER_VALUE_KEYS) {
        checkIntegerValue(schema, path, key);
      }

      if (Array.isArray(schema.enum)) {
        schema.enum.forEach((value, index) => {
          if (isUnsafeIntegerValue(value)) {
            addFinding(value, [...path, "enum", index], "enum value");
          }
        });
      }
    }

    if (schema.properties && typeof schema.properties === "object") {
      for (const [name, propertySchema] of Object.entries(schema.properties)) {
        checkSchema(propertySchema, [...path, "properties", name]);
      }
    }

    for (const key of SCHEMA_OBJECT_KEYS) {
      if (schema[key] && typeof schema[key] === "object") {
        checkSchema(schema[key], [...path, key]);
      }
    }

    for (const key of SCHEMA_ARRAY_KEYS) {
      if (Array.isArray(schema[key])) {
        schema[key].forEach((subSchema, index) => {
          checkSchema(subSchema, [...path, key, index]);
        });
      }
    }
  }

  function isPathSuffix(path, suffix) {
    if (path.length < suffix.length) return false;
    return suffix.every((part, index) => path[path.length - suffix.length + index] === part);
  }

  function walkOpenApi(node, path) {
    if (!node || typeof node !== "object") return;

    if (isPathSuffix(path, ["components", "schemas"])) {
      for (const [name, schema] of Object.entries(node)) {
        checkSchema(schema, [...path, name]);
      }
      return;
    }

    if (node.schema && typeof node.schema === "object") {
      checkSchema(node.schema, [...path, "schema"]);
    }

    for (const [key, value] of Object.entries(node)) {
      if (key === "schema") continue;
      walkOpenApi(value, [...path, key]);
    }
  }

  walkOpenApi(document, context.path);
  return errors;
};
