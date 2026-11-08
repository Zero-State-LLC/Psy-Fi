/**
 * Raw WebGPU compute pipeline for the Kuramoto kernel (no three.js). Uses its own adapter and
 * device so it never shares state with the renderer the frame stages measure.
 *
 * Bindings (group 0): 0 uniform Params {width, height, dt, coupling}, 1 phase_in (read),
 * 2 natural_freq (read), 3 phase_out (read_write). Two bind groups ping-pong the phase buffers.
 *
 * Timing: each dispatch is its own compute pass, command buffer and submit. Wall time per
 * dispatch is submit -> queue.onSubmittedWorkDone and is always recorded as wall time. When the
 * adapter exposes `timestamp-query`, each pass also writes begin/end timestamps and the GPU pass
 * time becomes the labelled per-dispatch time.
 */

import {
  KERNEL_WORKGROUP,
  KURAMOTO_STEP_WGSL,
  parseKuramotoFixture,
  runKuramotoValidation,
  type AcquireKuramotoGpu,
  type KernelCaptureRecord,
  type KernelInput,
  type KernelRunOutput,
  type KuramotoGpu,
} from './kuramotoKernel'

// Numeric usage flags (the GPUBufferUsage/GPUMapMode globals do not exist outside a WebGPU browser).
const BUF_MAP_READ = 0x0001
const BUF_COPY_SRC = 0x0004
const BUF_COPY_DST = 0x0008
const BUF_UNIFORM = 0x0040
const BUF_STORAGE = 0x0080
const BUF_QUERY_RESOLVE = 0x0200
const MAP_READ = 0x0001

/** Warm-up passes over the same input before the timed run (pipeline and driver caches). */
const WARMUP_RUNS = 1

class WebGpuKuramoto implements KuramotoGpu {
  constructor(
    private readonly device: GPUDevice,
    private readonly timestamps: boolean,
    readonly adapter: Record<string, unknown> | null,
  ) {}

  async run(input: KernelInput): Promise<KernelRunOutput> {
    const { device } = this
    device.pushErrorScope('validation')
    // Compiled here (not at acquisition) so a WGSL or pipeline error is a failed run, not "unsupported".
    const module = device.createShaderModule({ code: KURAMOTO_STEP_WGSL })
    const pipeline = await device.createComputePipelineAsync({ layout: 'auto', compute: { module, entryPoint: 'main' } })
    const n = input.width * input.height
    const bytes = n * 4
    const params = new ArrayBuffer(16)
    new Uint32Array(params, 0, 2).set([input.width, input.height])
    new Float32Array(params, 8, 2).set([input.dt, input.coupling])
    const uniform = device.createBuffer({ size: 16, usage: BUF_UNIFORM | BUF_COPY_DST })
    device.queue.writeBuffer(uniform, 0, params)
    const freq = device.createBuffer({ size: bytes, usage: BUF_STORAGE | BUF_COPY_DST })
    device.queue.writeBuffer(freq, 0, input.naturalFreq)
    const phase = [0, 1].map(() => device.createBuffer({ size: bytes, usage: BUF_STORAGE | BUF_COPY_DST | BUF_COPY_SRC }))
    const layout = pipeline.getBindGroupLayout(0)
    const groups = [0, 1].map((k) =>
      device.createBindGroup({
        layout,
        entries: [
          { binding: 0, resource: { buffer: uniform } },
          { binding: 1, resource: { buffer: phase[k] } },
          { binding: 2, resource: { buffer: freq } },
          { binding: 3, resource: { buffer: phase[1 - k] } },
        ],
      }),
    )
    const gx = Math.ceil(input.width / KERNEL_WORKGROUP)
    const gy = Math.ceil(input.height / KERNEL_WORKGROUP)
    const steps = input.steps
    const querySet = this.timestamps ? device.createQuerySet({ type: 'timestamp', count: 2 * steps }) : null
    const created: { destroy(): void }[] = [uniform, freq, ...phase]
    if (querySet) created.push(querySet)

    const dispatchAll = async (timed: boolean): Promise<number[]> => {
      device.queue.writeBuffer(phase[0], 0, input.phases)
      await device.queue.onSubmittedWorkDone()
      const wall: number[] = []
      for (let s = 0; s < steps; s++) {
        const enc = device.createCommandEncoder()
        const pass = enc.beginComputePass(
          timed && querySet ? { timestampWrites: { querySet, beginningOfPassWriteIndex: 2 * s, endOfPassWriteIndex: 2 * s + 1 } } : {},
        )
        pass.setPipeline(pipeline)
        pass.setBindGroup(0, groups[s % 2])
        pass.dispatchWorkgroups(gx, gy, 1)
        pass.end()
        const cmd = enc.finish()
        const t0 = performance.now()
        device.queue.submit([cmd])
        await device.queue.onSubmittedWorkDone()
        wall.push(performance.now() - t0)
      }
      return wall
    }

    try {
      for (let w = 0; w < WARMUP_RUNS; w++) await dispatchAll(false)
      const wallDispatchMs = await dispatchAll(true)

      // After step s the result sits in phase[(s + 1) % 2]; after all steps, phase[steps % 2].
      const enc = device.createCommandEncoder()
      const readPhase = device.createBuffer({ size: bytes, usage: BUF_MAP_READ | BUF_COPY_DST })
      created.push(readPhase)
      enc.copyBufferToBuffer(phase[steps % 2], 0, readPhase, 0, bytes)
      let readTs: GPUBuffer | null = null
      if (querySet) {
        const resolve = device.createBuffer({ size: 16 * steps, usage: BUF_QUERY_RESOLVE | BUF_COPY_SRC })
        readTs = device.createBuffer({ size: 16 * steps, usage: BUF_MAP_READ | BUF_COPY_DST })
        created.push(resolve, readTs)
        enc.resolveQuerySet(querySet, 0, 2 * steps, resolve, 0)
        enc.copyBufferToBuffer(resolve, 0, readTs, 0, 16 * steps)
      }
      device.queue.submit([enc.finish()])
      const validation = await device.popErrorScope()
      if (validation) throw new Error(`WebGPU validation error: ${validation.message}`)

      await readPhase.mapAsync(MAP_READ)
      const phases = new Float32Array(readPhase.getMappedRange().slice(0))
      readPhase.unmap()

      let gpuMs: number[] | null = null
      let note: string | undefined
      if (readTs) {
        await readTs.mapAsync(MAP_READ)
        const ns = new BigUint64Array(readTs.getMappedRange().slice(0))
        readTs.unmap()
        const out: number[] = []
        let bad = false
        for (let s = 0; s < steps; s++) {
          const d = ns[2 * s + 1] - ns[2 * s]
          if (ns[2 * s + 1] < ns[2 * s]) bad = true
          out.push(Number(d) / 1e6)
        }
        if (bad) {
          note = 'timestamp-query returned end < begin for at least one pass; per-dispatch time falls back to wall time'
        } else {
          gpuMs = out
          note = 'GPU pass time from timestamp-query. Chrome quantizes timestamps (100 us) unless WebGPU developer features are enabled, so a 32x32 dispatch can read as 0.'
        }
      }
      return {
        phases,
        timingSource: gpuMs ? 'timestamp-query' : 'wall',
        dispatchMs: gpuMs ?? wallDispatchMs,
        wallDispatchMs,
        warmupRuns: WARMUP_RUNS,
        note: note ?? 'timestamp-query not available: per-dispatch time is wall time from submit to onSubmittedWorkDone (includes queue and driver latency), not GPU time.',
      }
    } finally {
      for (const r of created) r.destroy()
    }
  }

  destroy(): void {
    this.device.destroy()
  }
}

/** Acquire a dedicated WebGPU device and compile the kernel; unsupported environments get a reason, not a throw. */
export const acquireWebGpuKuramoto: AcquireKuramotoGpu = async () => {
  const gpu = typeof navigator !== 'undefined' ? navigator.gpu : undefined
  if (!gpu?.requestAdapter) return { unsupported: 'navigator.gpu is not available: WebGPU compute is unsupported or disabled in this browser' }
  const adapter = await gpu.requestAdapter({ powerPreference: 'high-performance' })
  if (!adapter) return { unsupported: 'navigator.gpu.requestAdapter() returned no adapter' }
  const timestamps = adapter.features.has('timestamp-query')
  let device: GPUDevice
  try {
    device = await adapter.requestDevice({ requiredFeatures: timestamps ? ['timestamp-query'] : [] })
  } catch (err) {
    return { unsupported: `requestDevice failed: ${err instanceof Error ? err.message : String(err)}` }
  }
  const info = (adapter as GPUAdapter & { info?: GPUAdapterInfo }).info
  const adapterInfo = info
    ? { vendor: info.vendor, architecture: info.architecture, device: info.device, description: info.description, timestamp_query: timestamps }
    : { timestamp_query: timestamps }
  return { gpu: new WebGpuKuramoto(device, timestamps, adapterInfo) }
}

/** The bench page's kernel stage: load the committed fixture (lazily, it is ~45 KB) and validate. */
export async function runKuramotoKernelStage(): Promise<KernelCaptureRecord> {
  const raw = (await import('./fixtures/kuramoto.seed1337.32x32.v1.json')).default
  return runKuramotoValidation(parseKuramotoFixture(raw), acquireWebGpuKuramoto)
}
