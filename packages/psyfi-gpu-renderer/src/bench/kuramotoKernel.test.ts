import { describe, expect, it } from 'vitest'
import fixtureJson from './fixtures/kuramoto.seed1337.32x32.v1.json'
import {
  KURAMOTO_STEP_WGSL,
  compareToReference,
  kuramotoStepCpu,
  parseKernelMode,
  parseKuramotoFixture,
  prepareKernelInput,
  reconstructField,
  runKuramotoValidation,
  type KernelInput,
  type KernelRunOutput,
  type KuramotoGpu,
} from './kuramotoKernel'
import { FALLBACK_MANIFEST, buildCapturePayload } from './schedule'

const fx = parseKuramotoFixture(fixtureJson)

function evolveCpu(input: KernelInput, step = kuramotoStepCpu): Float32Array {
  let p = input.phases
  for (let s = 0; s < input.steps; s++) p = step(input, p) as Float32Array<ArrayBuffer>
  return p
}

function fakeGpu(run: (input: KernelInput) => Float32Array, opts: { throws?: string } = {}): KuramotoGpu {
  return {
    adapter: { vendor: 'test', timestamp_query: false },
    async run(input: KernelInput): Promise<KernelRunOutput> {
      if (opts.throws) throw new Error(opts.throws)
      const wall = Array.from({ length: input.steps }, (_, i) => 0.05 + i * 0.001)
      return { phases: run(input), timingSource: 'wall', dispatchMs: wall, wallDispatchMs: wall, warmupRuns: 1, note: 'wall time' }
    },
    destroy() {},
  }
}

describe('Kuramoto fixture', () => {
  it('parses the committed Python fixture into float32 planes', () => {
    expect(fx).toMatchObject({ width: 32, height: 32, steps: 10, seed: 1337, kernel: 'kuramoto_symmetric_step' })
    expect(fx.params).toMatchObject({ coupling_type: 'symmetric', coupling_strength: 0.5, dt: 0.1 })
    expect(fx.tolerance.max_abs_error).toBe(1e-3)
    expect(fx.initial.re).toHaveLength(1024)
    expect(fx.evolved.im).toHaveLength(1024)
    expect(fx.content_hash).toMatch(/^[0-9a-f]{16}$/)
    // Magnitudes come from uniform(0.5, 1.5) in initial_field.
    const input = prepareKernelInput(fx)
    expect(Math.min(...input.magnitudes)).toBeGreaterThanOrEqual(0.5 - 1e-6)
    expect(Math.max(...input.magnitudes)).toBeLessThanOrEqual(1.5 + 1e-6)
  })

  it('rejects malformed fixtures', () => {
    const doc = fixtureJson as unknown as Record<string, unknown>
    expect(() => parseKuramotoFixture({ ...doc, schema: 'nope' })).toThrow(/schema/)
    expect(() => parseKuramotoFixture({ ...doc, params: { ...(doc.params as object), coupling_type: 'asymmetric' } })).toThrow(/symmetric/)
    expect(() => parseKuramotoFixture({ ...doc, initial: { re: [1, 2], im: [1, 2] } })).toThrow(/1024/)
    const bad = [...(doc.evolved as { re: number[] }).re]
    bad[3] = Number.NaN
    expect(() => parseKuramotoFixture({ ...doc, evolved: { ...(doc.evolved as object), re: bad } })).toThrow(/finite/)
  })
})

describe('Kuramoto kernel formula', () => {
  it('a float32 emulation of the WGSL step reproduces the numpy field well inside the tolerance', () => {
    const input = prepareKernelInput(fx)
    const cmp = compareToReference(reconstructField(evolveCpu(input), input.magnitudes), fx)
    expect(cmp.nonFinite).toBe(0)
    expect(cmp.maxAbsError).not.toBeNull()
    expect(cmp.maxAbsError!).toBeLessThan(1e-5)
  })

  it('the tolerance discriminates: a step without the /4 average fails it', () => {
    const input = prepareKernelInput(fx)
    // Coupling summed instead of averaged over the four neighbours.
    const wrong = (inp: KernelInput, p: Float32Array) => {
      const { width: w, height: h } = inp
      const out = new Float32Array(p.length)
      for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
          const i = y * w + x
          const c = p[i]
          const sum = Math.sin(p[((y + h - 1) % h) * w + x] - c) + Math.sin(p[((y + 1) % h) * w + x] - c) + Math.sin(p[y * w + ((x + w - 1) % w)] - c) + Math.sin(p[y * w + ((x + 1) % w)] - c)
          out[i] = c + inp.dt * (inp.naturalFreq[i] + inp.coupling * sum)
        }
      }
      return out
    }
    const cmp = compareToReference(reconstructField(evolveCpu(input, wrong), input.magnitudes), fx)
    expect(cmp.maxAbsError!).toBeGreaterThan(fx.tolerance.max_abs_error * 10)
  })

  it('the WGSL source declares the four bindings and the averaged sin coupling', () => {
    for (const b of [0, 1, 2, 3]) expect(KURAMOTO_STEP_WGSL).toContain(`@binding(${b})`)
    expect(KURAMOTO_STEP_WGSL).toContain('(sin(up - c) + sin(down - c) + sin(left - c) + sin(right - c)) / 4.0')
    expect(KURAMOTO_STEP_WGSL).toContain('c + params.dt * (natural_freq[i] + params.coupling * coupling)')
  })
})

describe('Kuramoto kernel capture record', () => {
  it('records error, tolerance, verdict and wall-labelled per-dispatch time', async () => {
    const rec = await runKuramotoValidation(fx, async () => ({ gpu: fakeGpu((inp) => evolveCpu(inp)) }))
    expect(rec).toMatchObject({
      id: 'kernel.kuramoto_symmetric_step.32x32',
      kernel: 'kuramoto_symmetric_step',
      fixture_id: fx.id,
      fixture_hash: fx.content_hash,
      status: 'ran',
      tolerance: 1e-3,
      passed: true,
      nonfinite_count: 0,
      timing_source: 'wall',
      unsupported_reason: null,
      error: null,
      warmup_runs: 1,
    })
    expect(rec.max_abs_error!).toBeLessThan(1e-5)
    expect(rec.dispatch_ms).toHaveLength(10)
    expect(rec.wall_dispatch_ms).toEqual(rec.dispatch_ms)
  })

  it('a field off by more than the tolerance is recorded as not passed', async () => {
    const rec = await runKuramotoValidation(fx, async () => ({ gpu: fakeGpu((inp) => evolveCpu(inp).map((v) => v + 0.01)) }))
    expect(rec.status).toBe('ran')
    expect(rec.passed).toBe(false)
    expect(rec.max_abs_error!).toBeGreaterThan(1e-3)
  })

  it('NaN output gives a null error, a non-finite count and a fail', async () => {
    const rec = await runKuramotoValidation(fx, async () => ({ gpu: fakeGpu((inp) => { const p = evolveCpu(inp); p[5] = Number.NaN; return p }) }))
    expect(rec).toMatchObject({ status: 'ran', max_abs_error: null, nonfinite_count: 1, passed: false })
    // JSON keeps the record valid (no NaN literals).
    expect(JSON.parse(JSON.stringify(rec)).max_abs_error).toBeNull()
  })

  it('unsupported WebGPU is an explicit reason, never a number', async () => {
    const rec = await runKuramotoValidation(fx, async () => ({ unsupported: 'navigator.gpu is not available' }))
    expect(rec).toMatchObject({ status: 'unsupported', unsupported_reason: 'navigator.gpu is not available', max_abs_error: null, passed: null, timing_source: null, dispatch_ms: [] })
    const thrown = await runKuramotoValidation(fx, async () => { throw new Error('boom') })
    expect(thrown.status).toBe('unsupported')
    expect(thrown.unsupported_reason).toContain('boom')
  })

  it('a kernel failure is an error record', async () => {
    const rec = await runKuramotoValidation(fx, async () => ({ gpu: fakeGpu((inp) => inp.phases, { throws: 'WebGPU validation error: bad binding' }) }))
    expect(rec).toMatchObject({ status: 'error', passed: null, max_abs_error: null })
    expect(rec.error).toContain('bad binding')
  })

  it('the capture carries kernels only when one ran, and parses the ?kernel= flag', async () => {
    const rec = await runKuramotoValidation(fx, async () => ({ unsupported: 'x' }))
    const withK = buildCapturePayload({ manifest: FALLBACK_MANIFEST, stages: [], browser: {}, aborted: false, kernels: [rec] })
    expect(withK.kernels).toHaveLength(1)
    const without = buildCapturePayload({ manifest: FALLBACK_MANIFEST, stages: [], browser: {}, aborted: false })
    expect('kernels' in without).toBe(false)
    expect(parseKernelMode('?kernel=only')).toBe('only')
    expect(parseKernelMode('?timestamps=1&kernel=off')).toBe('off')
    expect(parseKernelMode('')).toBe('on')
  })
})
