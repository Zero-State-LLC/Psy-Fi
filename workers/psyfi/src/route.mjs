/** Which hostname paths reach the Python container. Everything else is a static asset. */

const CONTAINER_EXACT = new Set(["/health", "/ready", "/docs", "/redoc", "/openapi.json"]);

const NVIDIA_ENV = ["NVIDIA_API_KEY", "NVIDIA_VISION_MODEL", "NVIDIA_API_BASE"];

export function routeTarget(pathname) {
  const path = pathname || "/";
  if (path === "/api" || path.startsWith("/api/")) return "container";
  if (path === "/simulate" || path.startsWith("/simulate/")) return "container";
  if (CONTAINER_EXACT.has(path) || path.startsWith("/docs/")) return "container";
  return "assets";
}

/** Copy only non-empty NVIDIA fields. Never invent a model id or a key. */
export function containerEnv(env) {
  const source = env || {};
  const out = {};
  for (const key of NVIDIA_ENV) {
    const value = typeof source[key] === "string" ? source[key].trim() : "";
    if (value) out[key] = value;
  }
  return out;
}
