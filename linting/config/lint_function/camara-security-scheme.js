// CAMARA Project - support function for Spectral linter
// Security scheme checks (option `check`):
//   requirement-defined  every name in a `security:` requirement (root, operation,
//                        callback operation) exists in components.securitySchemes
//   openid-scheme        secured APIs define the openIdConnect scheme `openId`;
//                        no oauth2 scheme under any name
//   openid-url           openIdConnectUrl is HTTPS and ends in
//                        /.well-known/openid-configuration
//
// The built-in oas3-operation-security-defined cannot be used: it also demands
// every scope in flows.*.scopes, which an openIdConnect scheme does not have.
//
// The rules run on the resolved document, so a scheme given as `$ref` (the
// `../common/CAMARA_common.yaml` form) is checked through its target. A `$ref`
// that Spectral could not resolve stays a `$ref` node and counts as present.

const OPERATION_METHODS = ["get", "put", "post", "delete", "patch", "options"];
const WELL_KNOWN_SUFFIX = "/.well-known/openid-configuration";

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isRef(value) {
  return isObject(value) && typeof value.$ref === "string";
}

function schemeMap(document) {
  const schemes = document?.components?.securitySchemes;
  return isObject(schemes) ? schemes : {};
}

function requirementNames(requirement) {
  return isObject(requirement) ? Object.keys(requirement) : [];
}

// A requirement list is "secured" when at least one entry names a scheme.
// `[{}]` alone means "no authentication".
function isSecured(requirements) {
  return Array.isArray(requirements) &&
    requirements.some((requirement) => requirementNames(requirement).length > 0);
}

// Visits every operation (regular and callback). `visit(operation, ctx)` gets
// ctx = { path, label, callback }.
function walkOperations(document, basePath, visit) {
  function walkPathItem(pathItem, path, label, callback, ancestors) {
    if (!isObject(pathItem) || ancestors.has(pathItem)) return;
    const nextAncestors = new Set(ancestors);
    nextAncestors.add(pathItem);

    for (const method of OPERATION_METHODS) {
      const operation = pathItem[method];
      if (!isObject(operation)) continue;
      const operationPath = [...path, method];
      const operationLabel = `${method.toUpperCase()} ${label}`;
      visit(operation, { path: operationPath, label: operationLabel, callback });

      if (!isObject(operation.callbacks)) continue;
      for (const [callbackName, callbackObject] of Object.entries(operation.callbacks)) {
        if (!isObject(callbackObject)) continue;
        for (const [expression, callbackPathItem] of Object.entries(callbackObject)) {
          walkPathItem(
            callbackPathItem,
            [...operationPath, "callbacks", callbackName, expression],
            `callback ${callbackName} ${expression}`,
            true,
            nextAncestors
          );
        }
      }
    }
  }

  if (!isObject(document?.paths)) return;
  for (const [pathName, pathItem] of Object.entries(document.paths)) {
    walkPathItem(pathItem, [...basePath, "paths", pathName], pathName, false, new Set());
  }
}

function checkRequirementDefined(document, basePath) {
  const findings = [];
  const schemes = schemeMap(document);

  function checkRequirements(requirements, path, where) {
    if (!Array.isArray(requirements)) return;
    requirements.forEach((requirement, index) => {
      for (const name of requirementNames(requirement)) {
        if (!Object.prototype.hasOwnProperty.call(schemes, name)) {
          findings.push({
            message: `Security requirement '${name}' (${where}) is not defined in components.securitySchemes`,
            path: [...path, index, name],
          });
        }
      }
    });
  }

  checkRequirements(document?.security, [...basePath, "security"], "root");
  walkOperations(document, basePath, (operation, ctx) => {
    checkRequirements(operation.security, [...ctx.path, "security"], ctx.label);
  });
  return findings;
}

function checkOpenIdScheme(document, basePath) {
  const findings = [];
  const schemes = schemeMap(document);

  let secured = false;
  walkOperations(document, basePath, (operation, ctx) => {
    if (ctx.callback) return;
    const effective = operation.security !== undefined ? operation.security : document.security;
    if (isSecured(effective)) secured = true;
  });

  const openId = schemes.openId;
  if (openId === undefined) {
    if (secured) {
      findings.push({
        message:
          "API is secured but does not define the 'openId' scheme of type openIdConnect " +
          "in components.securitySchemes",
        path: [...basePath, "components", "securitySchemes"],
      });
    }
  } else if (isObject(openId) && !isRef(openId) && openId.type !== "openIdConnect") {
    findings.push({
      message: `Security scheme 'openId' has type ${openId.type}, CAMARA requires openIdConnect`,
      path: [...basePath, "components", "securitySchemes", "openId", "type"],
    });
  }

  for (const [name, scheme] of Object.entries(schemes)) {
    if (name === "openId" || !isObject(scheme) || isRef(scheme)) continue;
    if (scheme.type === "oauth2") {
      findings.push({
        message:
          `securitySchemes.${name} has type oauth2, CAMARA APIs define only the ` +
          "openIdConnect scheme 'openId'",
        path: [...basePath, "components", "securitySchemes", name, "type"],
      });
    }
  }
  return findings;
}

function checkOpenIdUrl(document, basePath) {
  const findings = [];
  for (const [name, scheme] of Object.entries(schemeMap(document))) {
    if (!isObject(scheme) || isRef(scheme) || scheme.type !== "openIdConnect") continue;
    const url = scheme.openIdConnectUrl;
    if (typeof url !== "string") continue;
    if (!url.startsWith("https://") || !url.endsWith(WELL_KNOWN_SUFFIX)) {
      findings.push({
        message:
          `openIdConnectUrl '${url}' of scheme '${name}' must use HTTPS and end in ` +
          WELL_KNOWN_SUFFIX,
        path: [...basePath, "components", "securitySchemes", name, "openIdConnectUrl"],
      });
    }
  }
  return findings;
}

export default (document, options, context) => {
  if (!isObject(document)) return [];
  const basePath = [...(context?.path || [])];
  switch (options?.check) {
    case "requirement-defined":
      return checkRequirementDefined(document, basePath);
    case "openid-scheme":
      return checkOpenIdScheme(document, basePath);
    case "openid-url":
      return checkOpenIdUrl(document, basePath);
    default:
      return [];
  }
};
