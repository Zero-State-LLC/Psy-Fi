import { DurableObject } from "cloudflare:workers";

import { containerEnv, routeTarget } from "./route.mjs";

const PORT = 8000;
const INACTIVITY_TIMEOUT_MS = 10 * 60 * 1000;

export class PsyfiApi extends DurableObject {
  constructor(ctx, env) {
    super(ctx, env);
    this.starting = undefined;
  }

  async fetch(request) {
    this.starting ??= this.startAndWait().finally(() => {
      this.starting = undefined;
    });
    await this.starting;
    const url = new URL(request.url);
    url.protocol = "http:";
    url.host = "container";
    const forwarded = new Request(url, request);
    forwarded.headers.delete("host");
    return this.ctx.container.getTcpPort(PORT).fetch(forwarded);
  }

  async startAndWait() {
    const container = this.ctx.container;
    if (!container.running) {
      // Internet stays on so the container can reach the NVIDIA integrate API.
      // The vision key and model id come from the Worker env at start, not from the image.
      container.start({
        image: container.images.base,
        instance: "standard-1",
        enableInternet: true,
        env: containerEnv(this.env),
      });
    }
    await container.setInactivityTimeout(INACTIVITY_TIMEOUT_MS);
    const port = container.getTcpPort(PORT);
    let lastError;
    for (let attempt = 0; attempt < 100; attempt++) {
      try {
        const response = await port.fetch("http://container/health", {
          signal: AbortSignal.timeout(1000),
        });
        await response.body?.cancel();
        if (!response.ok) throw new Error(`Health check returned ${response.status}`);
        return;
      } catch (error) {
        lastError = error;
        await scheduler.wait(200);
      }
    }
    throw new Error("Psy-Fi container did not become ready on port 8000", { cause: lastError });
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (routeTarget(url.pathname) === "container") {
      return env.PSYFI_API.getByName("psyfi").fetch(request);
    }
    return env.ASSETS.fetch(request);
  },
};
