/**
 * Pure scheduling and payload assembly for the WebGPU bench runner.
 * No DOM, no fetch: unit-tested in node. The browser part lives in BenchApp.tsx.
 */

import type { QualityTier } from '../contracts/QualityTier'

export const CAPTURE_SCHEMA = 'psyfi.bench.gpu_capture.v1' as const

export interface BenchCase {
  key: string
  substance: string
  mode: string
  seed: number
  intensity: number
}

export interface BenchManifestDoc {
  id: string
  version: number
  manifest_hash?: string
  params: {
    cases: BenchCase[]
    tiers: string[]
    frames_per_stage: number
    warmup_frames: number
    /** Warm-up also lasts at least this long so late pipeline compilation stays out of the sample. */
    warmup_min_ms?: number
    sustained?: { case: string; tier: string; frames: number } | null
    thumbnail_size?: number
    include_simulation?: boolean
  }
}

export interface ScheduledStage {
  id: string
  caseKey: string
  tier: QualityTier
  requestedFrames: number
  warmupFrames: number
  warmupMinMs: number
  sustained: boolean
}

export interface StageSamples {
  /** Warm-up frames actually discarded (>= stage.warmupFrames when warmupMinMs extended it). */
  warmupUsed: number
  /** Uncaught errors and unhandled rejections observed while this stage was measured. */
  jsErrors: number
  framesMs: number[]
  gpuMs: number[] | null
  drawCalls: number | null
  triangles: number | null
  durationMs: number
  jsHeapBytes: number | null
  thumbnailPngBase64: string | null
  snapshotHash: string | null
  effectiveTier: QualityTier
  note?: string
}

export interface CaptureStagePayload {
  id: string
  tier: string
  snapshot_key: string
  requested_frames: number
  warmup_frames: number
  frames_ms: number[]
  gpu_ms: number[] | null
  draw_calls: number | null
  triangles: number | null
  duration_ms: number
  js_heap_bytes: number | null
  thumbnail_png_base64: string | null
  snapshot_hash: string | null
  js_errors: number
  note: string | null
}

export interface CapturePayload {
  schema: typeof CAPTURE_SCHEMA
  captured_at: string
  manifest_id: string
  manifest_hash: string | null
  measurement_class: 'measured'
  browser: Record<string, unknown>
  stages: CaptureStagePayload[]
  aborted: boolean
  note: string | null
}

const TIERS: QualityTier[] = ['ultra', 'high', 'balanced', 'battery']

export function asTier(raw: string): QualityTier {
  const t = raw.toLowerCase()
  return (TIERS as string[]).includes(t) ? (t as QualityTier) : 'balanced'
}

/** Expand a manifest into the ordered stage list: every case x tier, then the sustained stage. */
export function scheduleStages(manifest: BenchManifestDoc): ScheduledStage[] {
  const out: ScheduledStage[] = []
  const frames = Math.max(1, Math.floor(manifest.params.frames_per_stage))
  const warmup = Math.max(0, Math.floor(manifest.params.warmup_frames))
  const warmupMinMs = Math.max(0, Math.floor(manifest.params.warmup_min_ms ?? 0))
  for (const c of manifest.params.cases) {
    for (const tierRaw of manifest.params.tiers) {
      const tier = asTier(tierRaw)
      out.push({ id: `${c.key}.${tier}`, caseKey: c.key, tier, requestedFrames: frames, warmupFrames: warmup, warmupMinMs, sustained: false })
    }
  }
  const s = manifest.params.sustained
  if (s) {
    const tier = asTier(s.tier)
    out.push({ id: `sustained.${s.case}.${tier}`, caseKey: s.case, tier, requestedFrames: Math.max(1, Math.floor(s.frames)), warmupFrames: warmup, warmupMinMs, sustained: true })
  }
  return out
}

/** Drop warm-up frames and non-finite samples. */
export function trimFrames(allMs: number[], warmupFrames: number): number[] {
  return allMs.slice(Math.max(0, warmupFrames)).filter((v) => Number.isFinite(v) && v > 0)
}

export function buildCapturePayload(opts: {
  manifest: BenchManifestDoc
  stages: { stage: ScheduledStage; samples: StageSamples }[]
  browser: Record<string, unknown>
  aborted: boolean
  capturedAt?: string
  note?: string | null
}): CapturePayload {
  return {
    schema: CAPTURE_SCHEMA,
    captured_at: opts.capturedAt ?? new Date().toISOString(),
    manifest_id: opts.manifest.id,
    manifest_hash: opts.manifest.manifest_hash ?? null,
    measurement_class: 'measured',
    browser: opts.browser,
    stages: opts.stages.map(({ stage, samples }) => ({
      id: stage.id,
      tier: samples.effectiveTier,
      snapshot_key: stage.caseKey,
      requested_frames: stage.requestedFrames,
      warmup_frames: samples.warmupUsed,
      frames_ms: samples.framesMs,
      gpu_ms: samples.gpuMs,
      draw_calls: samples.drawCalls,
      triangles: samples.triangles,
      duration_ms: samples.durationMs,
      js_heap_bytes: samples.jsHeapBytes,
      thumbnail_png_base64: samples.thumbnailPngBase64,
      snapshot_hash: samples.snapshotHash,
      js_errors: samples.jsErrors,
      note: [samples.effectiveTier !== stage.tier ? `requested tier ${stage.tier} clamped to ${samples.effectiveTier}` : '', samples.note || ''].filter(Boolean).join('; ') || null,
    })),
    aborted: opts.aborted,
    note: opts.note ?? null,
  }
}

/** Quick in-browser summary so the operator can sanity-check before download; Python is the scorer. */
export function quickSummary(framesMs: number[]): { fps: number; p95Ms: number; n: number } {
  const clean = framesMs.filter((v) => Number.isFinite(v) && v > 0)
  if (!clean.length) return { fps: 0, p95Ms: 0, n: 0 }
  const avg = clean.reduce((a, b) => a + b, 0) / clean.length
  const sorted = [...clean].sort((a, b) => a - b)
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.ceil(0.95 * sorted.length) - 1))
  return { fps: 1000 / avg, p95Ms: sorted[idx], n: clean.length }
}

/** Fallback manifest used when /api/bench is unreachable (same values as the shipped manifest). */
export const FALLBACK_MANIFEST: BenchManifestDoc = {
  id: 'render.webgpu.tiers',
  version: 1,
  params: {
    cases: [
      { key: 'lsd_open_42', substance: 'lsd', mode: 'open', seed: 42, intensity: 0.75 },
      { key: 'psilocybin_attractor_7', substance: 'psilocybin', mode: 'attractor', seed: 7, intensity: 0.6 },
      { key: 'dmt_void_99', substance: 'dmt', mode: 'void', seed: 99, intensity: 0.85 },
    ],
    tiers: ['ultra', 'high', 'balanced', 'battery'],
    frames_per_stage: 240,
    warmup_frames: 120,
    warmup_min_ms: 5000,
    sustained: { case: 'lsd_open_42', tier: 'ultra', frames: 1800 },
    thumbnail_size: 128,
    include_simulation: false,
  },
}
