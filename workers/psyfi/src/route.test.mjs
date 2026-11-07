import assert from "node:assert/strict";
import test from "node:test";

import { containerEnv, routeTarget } from "./route.mjs";

test("api, simulate, and probes go to the container", () => {
  for (const path of [
    "/api",
    "/api/v1/visualize/image-reading",
    "/simulate",
    "/simulate/",
    "/health",
    "/ready",
  ]) {
    assert.equal(routeTarget(path), "container", path);
  }
});

test("shell, static, and the gpu lab stay on assets", () => {
  for (const path of ["/", "/static/app.js", "/gpu/", "/gpu/index.html", "/sw.js", "/assets/icons/x.svg"]) {
    assert.equal(routeTarget(path), "assets", path);
  }
});

test("container env copies only set nvidia fields", () => {
  assert.deepEqual(
    containerEnv({
      NVIDIA_API_KEY: "k",
      NVIDIA_VISION_MODEL: "nvidia/test-vl",
      NVIDIA_API_BASE: "https://example.test",
      OTHER: "no",
    }),
    {
      NVIDIA_API_KEY: "k",
      NVIDIA_VISION_MODEL: "nvidia/test-vl",
      NVIDIA_API_BASE: "https://example.test",
    },
  );
  assert.deepEqual(containerEnv({ NVIDIA_VISION_MODEL: "", NVIDIA_API_KEY: "  " }), {});
  assert.deepEqual(containerEnv(undefined), {});
});
