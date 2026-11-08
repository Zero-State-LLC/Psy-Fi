import { describe, expect, it } from 'vitest'
import { FALLBACK_MANIFEST, buildCapturePayload, measuredWindowEpochMs, quickSummary, scheduleStages, trimFrames } from './schedule'

describe('bench schedule', () => {
  it('expands cases x tiers then the sustained stage', () => {
    const stages = scheduleStages(FALLBACK_MANIFEST)
    expect(stages).toHaveLength(3 * 4 + 1)
    expect(stages[0]).toMatchObject({ id: 'lsd_open_42.ultra', tier: 'ultra', requestedFrames: 240, warmupFrames: 120, sustained: false })
    expect(stages[stages.length - 1]).toMatchObject({ id: 'sustained.lsd_open_42.ultra', requestedFrames: 1800, sustained: true })
  })

  it('normalizes unknown tiers to balanced and drops warm-up frames', () => {
    const stages = scheduleStages({ ...FALLBACK_MANIFEST, params: { ...FALLBACK_MANIFEST.params, tiers: ['ULTRA', 'nope'], sustained: null } })
    expect(stages.map((s) => s.tier)).toEqual(['ultra', 'balanced', 'ultra', 'balanced', 'ultra', 'balanced'])
    expect(trimFrames([1, 2, 3, NaN, 4, -1, 5], 2)).toEqual([3, 4, 5])
  })

  it('builds a measured capture payload with the schema id and clamp notes', () => {
    const stages = scheduleStages(FALLBACK_MANIFEST).slice(0, 1)
    const payload = buildCapturePayload({
      manifest: { ...FALLBACK_MANIFEST, manifest_hash: 'abc' },
      stages: stages.map((stage) => ({
        stage,
        samples: { warmupUsed: 130, jsErrors: 2, framesMs: [8, 9, 8.5], gpuMs: null, drawCalls: 12, triangles: 1000, durationMs: 25.5, jsHeapBytes: null, thumbnailPngBase64: null, snapshotHash: 'h', effectiveTier: 'balanced' },
      })),
      browser: { user_agent: 'test' },
      aborted: false,
      capturedAt: '2026-11-07T00:00:00Z',
    })
    expect(payload.schema).toBe('psyfi.bench.gpu_capture.v1')
    expect(payload.measurement_class).toBe('measured')
    expect(payload.manifest_hash).toBe('abc')
    expect(payload.stages[0].tier).toBe('balanced')
    expect(payload.stages[0].note).toContain('clamped')
    expect(payload.stages[0].frames_ms).toEqual([8, 9, 8.5])
    expect(payload.stages[0].warmup_frames).toBe(130)
    expect(payload.stages[0].js_errors).toBe(2)
    expect(stages[0].warmupMinMs).toBe(5000)
  })

  it('records the measured window on the epoch clock with warm-up excluded', () => {
    // A 10 ms cadence: 3 warm-up frames, then 4 measured ones. Warm-up runs 90..120.
    const frames = Array.from({ length: 7 }, (_, i) => ({ wallMs: 10, atMs: 100 + i * 10 }))
    const origin = 1_794_000_000_000
    const window = measuredWindowEpochMs(frames, 3, origin)
    expect(window).toEqual([origin + 120, origin + 160])
    // Four measured frames over four intervals: the window length is the sum of their wall times.
    expect(window![1] - window![0]).toBe(frames.slice(3).reduce((a, f) => a + f.wallMs, 0))
    expect(measuredWindowEpochMs(frames, 7, origin)).toBeNull() // nothing measured
    expect(measuredWindowEpochMs([{ wallMs: 10, atMs: NaN }], 0, origin)).toBeNull()
  })

  it('carries the window into the payload only when there is one', () => {
    const stages = scheduleStages(FALLBACK_MANIFEST).slice(0, 1)
    const samples = { warmupUsed: 3, jsErrors: 0, framesMs: [8, 9], gpuMs: null, drawCalls: null, triangles: null, durationMs: 25, jsHeapBytes: null, thumbnailPngBase64: null, snapshotHash: null, effectiveTier: 'ultra' as const }
    const build = (windowEpochMs?: [number, number] | null) =>
      buildCapturePayload({ manifest: FALLBACK_MANIFEST, stages: stages.map((stage) => ({ stage, samples: { ...samples, windowEpochMs } })), browser: {}, aborted: false }).stages[0]
    expect(build([1000, 1017]).window_epoch_ms).toEqual([1000, 1017])
    expect(build(null)).not.toHaveProperty('window_epoch_ms')
    expect(build(undefined)).not.toHaveProperty('window_epoch_ms')
  })

  it('quick summary is a sanity check only', () => {
    const s = quickSummary([10, 10, 10, 20])
    expect(s.fps).toBeCloseTo(80, 5)
    expect(s.p95Ms).toBe(20)
    expect(quickSummary([]).n).toBe(0)
  })
})
