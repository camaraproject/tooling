// CAMARA Project - support function for Spectral linter
// Checks x-correlator documentation on regular and callback operations.

const OPERATION_METHODS = ["get", "put", "post", "delete", "patch", "options"];

function isObject(value) {
  return value !== null && typeof value === "object";
}

function hasXCorrelatorParameter(parameters) {
  return Array.isArray(parameters) && parameters.some((parameter) => (
    isObject(parameter) &&
    String(parameter.in).toLowerCase() === "header" &&
    String(parameter.name).toLowerCase() === "x-correlator"
  ));
}

function hasXCorrelatorHeader(response) {
  return isObject(response?.headers) && Object.keys(response.headers).some(
    (name) => name.toLowerCase() === "x-correlator"
  );
}

export default (document, options, context) => {
  const target = options?.target;
  if (target !== "request" && target !== "response") return [];

  const findings = [];

  function checkOperation(operation, inheritedParameters, path, ancestors) {
    if (!isObject(operation)) return;

    if (target === "request") {
      const effectiveParameters = [
        ...(Array.isArray(inheritedParameters) ? inheritedParameters : []),
        ...(Array.isArray(operation.parameters) ? operation.parameters : []),
      ];
      if (!hasXCorrelatorParameter(effectiveParameters)) {
        findings.push({
          message: "Operation must document the 'x-correlator' request header parameter",
          path: [...path, "parameters"],
        });
      }
    } else if (isObject(operation.responses)) {
      for (const [status, response] of Object.entries(operation.responses)) {
        if (!hasXCorrelatorHeader(response)) {
          findings.push({
            message: `Response '${status}' must document the 'x-correlator' response header`,
            path: [...path, "responses", status, "headers"],
          });
        }
      }
    }

    if (!isObject(operation.callbacks)) return;
    for (const [callbackName, callback] of Object.entries(operation.callbacks)) {
      if (!isObject(callback)) continue;
      for (const [expression, pathItem] of Object.entries(callback)) {
        walkPathItem(
          pathItem,
          [...path, "callbacks", callbackName, expression],
          ancestors
        );
      }
    }
  }

  function walkPathItem(pathItem, path, ancestors) {
    if (!isObject(pathItem) || ancestors.has(pathItem)) return;

    const nextAncestors = new Set(ancestors);
    nextAncestors.add(pathItem);
    const inheritedParameters = pathItem.parameters;

    for (const method of OPERATION_METHODS) {
      if (isObject(pathItem[method])) {
        checkOperation(
          pathItem[method],
          inheritedParameters,
          [...path, method],
          nextAncestors
        );
      }
    }
  }

  if (isObject(document?.paths)) {
    for (const [pathName, pathItem] of Object.entries(document.paths)) {
      walkPathItem(pathItem, [...context.path, "paths", pathName], new Set());
    }
  }

  return findings;
};
