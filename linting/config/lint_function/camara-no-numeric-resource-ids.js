// CAMARA Project - support function for Spectral linter
// Resource-ID type check that walks allOf/anyOf/oneOf combiners to find
// the terminal type. Replaces the stock owasp:api1:2023-no-numeric-ids
// rule which fires false positives on allOf-wrapped $ref schemas (the
// only OAS-3.0.3-legal way to attach a sibling description to a $ref).
//
// Fires only when the schema chain terminates at type: "integer".
// Schemas with no resolvable terminal type pass cleanly — the rule's
// intent is to reject explicit numeric IDs, not to require an explicit
// type declaration (S-016 / camara-schema-type-check covers that).

export default (schema, _options, context) => {
  if (hasIntegerType(schema)) {
    return [{ message: "Resource ID schema declares type: integer", path: context.path }];
  }
  return [];
};

function hasIntegerType(node) {
  if (!node || typeof node !== "object") return false;
  if (node.type === "integer") return true;
  for (const combiner of ["allOf", "anyOf", "oneOf"]) {
    if (Array.isArray(node[combiner])) {
      for (const sub of node[combiner]) {
        if (hasIntegerType(sub)) return true;
      }
    }
  }
  return false;
}
