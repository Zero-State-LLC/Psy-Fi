/**
 * Browser WGSL Kuramoto kernel validated against the Python reference (issue #51).
 *
 * Pure part: fixture parsing, kernel inputs, a float32 CPU emulation of the WGSL step, error
 * computation and the capture record. No DOM and no WebGPU globals, so vitest runs it in node.
 * The WebGPU part sits behind `KuramotoGpu` (see kuramotoWebGpu.ts).
 *
 * The CPU simulation stays the authority: the GPU-evolved field is only compared against the
 * fixture's numpy-evolved field and is never fed back into anything. Python re-judges the error
 * against its own declared tolerance at ingest (stage kind `webgpu_kernel`).
 */

export const KURAMOTO_FIXTURE_SCHEMA = 'psyfi.bench.kuramoto_fixture.v1' as const
export const KURAMOTO_KERNEL_NAME = 'kuramoto_symmetric_step' as const
export const KERNEL_WORKGROUP = 8

/**
 * One symmetric Kuramoto step, the same formula as `evolve_consciousness_omega` (numpy):
 * periodic 4-neighbour roll, coupling = (sum of sin(neighbour - self)) / 4,
 * phase += dt * (natural_freq + K * coupling). Ping-pong buffers; one dispatch is one step.
 */
export const KURAMOTO_STEP_WGSL = /* wgsl */ `
struct Params {
  width: u32,
  height: u32,
  dt: f32,
  coupling: f32,
}

@group(0) @binding(0) var<uniform> params: Params;
@group(0) @binding(1) var<storage, read> phase_in: array<f32>;
@group(0) @binding(2) var<storage, read> natural_freq: array<f32>;
@group(0) @binding(3) var<storage, read_write> phase_out: array<f32>;

@compute @workgroup_size(${KERNEL_WORKGROUP}, ${KERNEL_WORKGROUP}, 1)
fn main(@builtin(global_invocation_id) gid: vec3<u32>) {
  let w = params.width;
  let h = params.height;
  if (gid.x >= w || gid.y >= h) {
    return;
  }
  let x = gid.x;
  let y = gid.y;
  let i = y * w + x;
  let c = phase_in[i];
  // np.roll(p, 1, axis=0)[y] = p[y-1]; np.roll(p, -1, axis=0)[y] = p[y+1]; same on axis 1 for x.
  let up = phase_in[((y + h - 1u) % h) * w + x];
  let down = phase_in[((y + 1u) % h) * w + x];
  let left = phase_in[y * w + (x + w - 1u) % w];
  let right = phase_in[y * w + (x + 1u) % w];
  let coupling = (sin(up - c) + sin(down - c) + sin(left - c) + sin(right - c)) / 4.0;
  phase_out[i] = c + params.dt * (natural_freq[i] + params.coupling * coupling);
}
`

export interface KuramotoParams {
  coupling_type: string
  coupling_strength: number
  dt: number
  natural_freq_base: number
  freq_depth_scale: number
  freq_brightness_scale: number
}

export interface KuramotoFixture {
  schema: typeof KURAMOTO_FIXTURE_SCHEMA
  id: string
  kernel: string
  seed: number
  width: number
  height: number
  steps: number
  params: KuramotoParams
  tolerance: { max_abs_error: number }
  content_hash: string
  initial: { re: Float32Array; im: Float32Array }
  evolved: { re: Float32Array; im: Float32Array }
}

function plane(raw: unknown, n: number, name: string): Float32Array {
  if (!Array.isArray(raw) || raw.length !== n) throw new Error(`fixture ${name}: expected ${n} values`)
  const out = new Float32Array(n)
  for (let i = 0; i < n; i++) {
    const v = raw[i]
    if (typeof v !== 'number' || !Number.isFinite(v)) throw new Error(`fixture ${name}[${i}] is not a finite number`)
    out[i] = v
  }
  return out
}

function num(raw: unknown, name: string): number {
  if (typeof raw !== 'number' || !Number.isFinite(raw)) throw new Error(`fixture ${name} must be a finite number`)
  return raw
}

/** Validate the JSON written by `psyfi_bench.compute.kuramoto_fixture` and lift the planes to float32. */
export function parseKuramotoFixture(raw: unknown): KuramotoFixture {
  if (!raw || typeof raw !== 'object') throw new Error('fixture is not an object')
  const doc = raw as Record<string, unknown>
  if (doc.schema !== KURAMOTO_FIXTURE_SCHEMA) throw new Error(`fixture schema ${String(doc.schema)} is not ${KURAMOTO_FIXTURE_SCHEMA}`)
  const width = num(doc.width, 'width')
  const height = num(doc.height, 'height')
  const steps = num(doc.steps, 'steps')
  if (!Number.isInteger(width) || !Number.isInteger(height) || width < 1 || height < 1) throw new Error('fixture width/height must be positive integers')
  if (!Number.isInteger(steps) || steps < 1) throw new Error('fixture steps must be a positive integer')
  const p = (doc.params ?? {}) as Record<string, unknown>
  if (p.coupling_type !== 'symmetric') throw new Error('the WGSL kernel implements symmetric coupling only')
  const params: KuramotoParams = {
    coupling_type: 'symmetric',
    coupling_strength: num(p.coupling_strength, 'params.coupling_strength'),
    dt: num(p.dt, 'params.dt'),
    natural_freq_base: num(p.natural_freq_base, 'params.natural_freq_base'),
    freq_depth_scale: num(p.freq_depth_scale, 'params.freq_depth_scale'),
    freq_brightness_scale: num(p.freq_brightness_scale, 'params.freq_brightness_scale'),
  }
  const tol = (doc.tolerance ?? {}) as Record<string, unknown>
  const n = width * height
  const initial = (doc.initial ?? {}) as Record<string, unknown>
  const evolved = (doc.evolved ?? {}) as Record<string, unknown>
  return {
    schema: KURAMOTO_FIXTURE_SCHEMA,
    id: String(doc.id ?? ''),
    kernel: String(doc.kernel ?? ''),
    seed: num(doc.seed, 'seed'),
    width,
    height,
    steps,
    params,
    tolerance: { max_abs_error: num(tol.max_abs_error, 'tolerance.max_abs_error') },
    content_hash: String(doc.content_hash ?? ''),
    initial: { re: plane(initial.re, n, 'initial.re'), im: plane(initial.im, n, 'initial.im') },
    evolved: { re: plane(evolved.re, n, 'evolved.re'), im: plane(evolved.im, n, 'evolved.im') },
  }
}

export interface KernelInput {
  width: number
  height: number
  steps: number
  dt: number
  coupling: number
  /** Initial phases, float32, row-major (index = y * width + x). */
  phases: Float32Array<ArrayBuffer>
  magnitudes: Float32Array<ArrayBuffer>
  /** Per-cell natural frequency, computed once before the loop exactly as numpy does. */
  naturalFreq: Float32Array<ArrayBuffer>
}

/** Phases, magnitudes and natural frequencies, as `evolve_consciousness_omega` derives them. */
export function prepareKernelInput(fx: KuramotoFixture): KernelInput {
  const { width, height } = fx
  const n = width * height
  const phases = new Float32Array(n)
  const magnitudes = new Float32Array(n)
  let maxMag = 0
  for (let i = 0; i < n; i++) {
    const re = fx.initial.re[i]
    const im = fx.initial.im[i]
    phases[i] = Math.atan2(im, re)
    magnitudes[i] = Math.hypot(re, im)
    if (magnitudes[i] > maxMag) maxMag = magnitudes[i]
  }
  const p = fx.params
  const naturalFreq = new Float32Array(n)
  for (let y = 0; y < height; y++) {
    const depth = y / height
    for (let x = 0; x < width; x++) {
      const i = y * width + x
      naturalFreq[i] = p.natural_freq_base + p.freq_depth_scale * depth + p.freq_brightness_scale * (magnitudes[i] / (maxMag + 1e-8))
    }
  }
  return { width, height, steps: fx.steps, dt: p.dt, coupling: p.coupling_strength, phases, magnitudes, naturalFreq }
}

/** Float32 CPU emulation of one WGSL dispatch. Used by tests to pin the formula, never by the bench. */
export function kuramotoStepCpu(input: KernelInput, phases: Float32Array): Float32Array {
  const { width: w, height: h } = input
  const f = Math.fround
  const dt = f(input.dt)
  const k = f(input.coupling)
  const out = new Float32Array(w * h)
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x
      const c = phases[i]
      const up = phases[((y + h - 1) % h) * w + x]
      const down = phases[((y + 1) % h) * w + x]
      const left = phases[y * w + ((x + w - 1) % w)]
      const right = phases[y * w + ((x + 1) % w)]
      const s = f(f(f(f(Math.sin(f(up - c))) + f(Math.sin(f(down - c)))) + f(Math.sin(f(left - c)))) + f(Math.sin(f(right - c))))
      const coupling = f(s / 4)
      out[i] = f(c + f(dt * f(input.naturalFreq[i] + f(k * coupling))))
    }
  }
  return out
}

/** magnitude * exp(i * phase): the field numpy reconstructs after the loop (phase wrap does not change cos/sin). */
export function reconstructField(phases: Float32Array, magnitudes: Float32Array): { re: Float64Array; im: Float64Array } {
  const n = phases.length
  const re = new Float64Array(n)
  const im = new Float64Array(n)
  for (let i = 0; i < n; i++) {
    re[i] = Math.fround(magnitudes[i] * Math.cos(phases[i]))
    im[i] = Math.fround(magnitudes[i] * Math.sin(phases[i]))
  }
  return { re, im }
}

/** Max abs error over real and imaginary parts (as psyfi_bench.determinism.max_abs_error). Null when any value is non-finite. */
export function compareToReference(field: { re: ArrayLike<number>; im: ArrayLike<number> }, fx: KuramotoFixture): { maxAbsError: number | null; nonFinite: number } {
  const n = fx.width * fx.height
  if (field.re.length !== n || field.im.length !== n) return { maxAbsError: null, nonFinite: n }
  let max = 0
  let nonFinite = 0
  for (let i = 0; i < n; i++) {
    const a = field.re[i]
    const b = field.im[i]
    if (!Number.isFinite(a) || !Number.isFinite(b)) {
      nonFinite++
      continue
    }
    max = Math.max(max, Math.abs(a - fx.evolved.re[i]), Math.abs(b - fx.evolved.im[i]))
  }
  return { maxAbsError: nonFinite ? null : max, nonFinite }
}

export type KernelTimingSource = 'timestamp-query' | 'wall'

export interface KernelRunOutput {
  /** Phases after `steps` dispatches, read back from the GPU. */
  phases: Float32Array
  timingSource: KernelTimingSource
  /** Per-dispatch ms from `timingSource`: GPU pass time with timestamp-query, else the wall time below. */
  dispatchMs: number[]
  /** Per-dispatch wall ms: submit to queue.onSubmittedWorkDone. Always recorded; never GPU time. */
  wallDispatchMs: number[]
  warmupRuns: number
  note?: string
}

/** The only GPU-facing surface the validation needs. */
export interface KuramotoGpu {
  adapter: Record<string, unknown> | null
  run(input: KernelInput): Promise<KernelRunOutput>
  destroy(): void
}

export type AcquireKuramotoGpu = () => Promise<{ gpu: KuramotoGpu } | { unsupported: string }>

/** Capture entry; mirrors psyfi_bench.schemas.CaptureKernel. */
export interface KernelCaptureRecord {
  id: string
  kernel: string
  fixture_id: string
  fixture_hash: string
  width: number
  height: number
  steps: number
  status: 'ran' | 'unsupported' | 'error'
  unsupported_reason: string | null
  error: string | null
  max_abs_error: number | null
  nonfinite_count: number | null
  tolerance: number
  passed: boolean | null
  timing_source: KernelTimingSource | null
  dispatch_ms: number[]
  wall_dispatch_ms: number[]
  warmup_runs: number
  adapter: Record<string, unknown> | null
  note: string | null
}

export function kernelStageId(fx: Pick<KuramotoFixture, 'width' | 'height'>): string {
  return `kernel.${KURAMOTO_KERNEL_NAME}.${fx.width}x${fx.height}`
}

function baseRecord(fx: KuramotoFixture): KernelCaptureRecord {
  return {
    id: kernelStageId(fx),
    kernel: KURAMOTO_KERNEL_NAME,
    fixture_id: fx.id,
    fixture_hash: fx.content_hash,
    width: fx.width,
    height: fx.height,
    steps: fx.steps,
    status: 'error',
    unsupported_reason: null,
    error: null,
    max_abs_error: null,
    nonfinite_count: null,
    tolerance: fx.tolerance.max_abs_error,
    passed: null,
    timing_source: null,
    dispatch_ms: [],
    wall_dispatch_ms: [],
    warmup_runs: 0,
    adapter: null,
    note: null,
  }
}

export function unsupportedKernelRecord(fx: KuramotoFixture, reason: string): KernelCaptureRecord {
  return { ...baseRecord(fx), status: 'unsupported', unsupported_reason: reason }
}

/** Build the record from a finished GPU run: reconstruct, compare, judge against the fixture's tolerance. */
export function buildKernelRecord(fx: KuramotoFixture, input: KernelInput, out: KernelRunOutput, adapter: Record<string, unknown> | null): KernelCaptureRecord {
  const cmp = compareToReference(reconstructField(out.phases, input.magnitudes), fx)
  const tol = fx.tolerance.max_abs_error
  return {
    ...baseRecord(fx),
    status: 'ran',
    max_abs_error: cmp.maxAbsError,
    nonfinite_count: cmp.nonFinite,
    passed: cmp.maxAbsError !== null && cmp.nonFinite === 0 && cmp.maxAbsError <= tol,
    timing_source: out.timingSource,
    dispatch_ms: out.dispatchMs,
    wall_dispatch_ms: out.wallDispatchMs,
    warmup_runs: out.warmupRuns,
    adapter,
    note: out.note ?? null,
  }
}

/** Run the fixture through the GPU kernel. Never throws: unsupported and failures become explicit records. */
export async function runKuramotoValidation(fx: KuramotoFixture, acquire: AcquireKuramotoGpu): Promise<KernelCaptureRecord> {
  let got: Awaited<ReturnType<AcquireKuramotoGpu>>
  try {
    got = await acquire()
  } catch (err) {
    return unsupportedKernelRecord(fx, `WebGPU device acquisition failed: ${err instanceof Error ? err.message : String(err)}`)
  }
  if ('unsupported' in got) return unsupportedKernelRecord(fx, got.unsupported)
  const { gpu } = got
  try {
    const input = prepareKernelInput(fx)
    const out = await gpu.run(input)
    return buildKernelRecord(fx, input, out, gpu.adapter)
  } catch (err) {
    return { ...baseRecord(fx), status: 'error', error: err instanceof Error ? `${err.name}: ${err.message}` : String(err), adapter: gpu.adapter }
  } finally {
    try {
      gpu.destroy()
    } catch {
      /* ignore */
    }
  }
}

export type KernelMode = 'on' | 'off' | 'only'

/** `?kernel=only` runs just the kernel stage, `?kernel=off` skips it; default runs it before the frame stages. */
export function parseKernelMode(search: string): KernelMode {
  const m = /[?&]kernel=([^&]*)/i.exec(search)
  const v = (m?.[1] ?? '').toLowerCase()
  if (v === 'only') return 'only'
  if (v === 'off' || v === '0' || v === 'false' || v === 'no') return 'off'
  return 'on'
}
