/**
 * FieldLoop GPU bench runner. Reuses SceneRoot unchanged inside a bench-only canvas; drives it through
 * a scripted schedule and emits a psyfi.bench.gpu_capture.v1 payload. Python scores it.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { BenchCanvas } from './BenchCanvas'
import {
  probeDeviceCaps,
  refineDeviceCaps,
  resolveTier,
  type DeviceCaps,
  type QualityTier,
} from '../contracts/QualityTier'
import type { SceneSnapshotV1 } from '../contracts/SceneSnapshot'
import { BenchProbe, createProbeHandle } from './BenchProbe'
import {
  FALLBACK_MANIFEST,
  buildCapturePayload,
  quickSummary,
  scheduleStages,
  trimFrames,
  type BenchManifestDoc,
  type CapturePayload,
  type ScheduledStage,
  type StageSamples,
} from './schedule'

type Phase = 'idle' | 'loading' | 'running' | 'done' | 'error'

async function fetchManifest(): Promise<BenchManifestDoc> {
  try {
    const res = await fetch('/api/bench/v1/workloads/render.webgpu.tiers')
    if (res.ok) return (await res.json()) as BenchManifestDoc
  } catch {
    /* fall through */
  }
  return FALLBACK_MANIFEST
}

async function fetchSnapshot(c: { substance: string; mode: string; seed: number; intensity: number }, tier: QualityTier, includeSimulation: boolean, sequence: number): Promise<SceneSnapshotV1> {
  const res = await fetch('/api/v1/visualize/scene-snapshot', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ substance: c.substance, mode: c.mode, seed: c.seed, intensity: c.intensity, quality_tier: tier, include_simulation: includeSimulation, sequence }),
  })
  if (!res.ok) throw new Error(`scene-snapshot ${res.status}`)
  return (await res.json()) as SceneSnapshotV1
}

function downloadJson(filename: string, data: unknown): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function BenchApp() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [status, setStatus] = useState('Idle. WebGPU bench runner for render.webgpu.tiers.')
  const [caps, setCaps] = useState<DeviceCaps>(() => probeDeviceCaps())
  const [manifest, setManifest] = useState<BenchManifestDoc | null>(null)
  const [snapshot, setSnapshot] = useState<SceneSnapshotV1 | null>(null)
  const [tier, setTier] = useState<QualityTier>('balanced')
  const [stageIndex, setStageIndex] = useState(-1)
  const [rows, setRows] = useState<{ stage: ScheduledStage; samples: StageSamples }[]>([])
  const [payload, setPayload] = useState<CapturePayload | null>(null)
  const [postStatus, setPostStatus] = useState<string | null>(null)
  const probe = useMemo(() => createProbeHandle(), [])
  const abortRef = useRef(false)
  const errorCount = useRef(0)

  useEffect(() => {
    // Renderer exceptions during a stage invalidate its frames; count them into the capture.
    const onError = () => {
      errorCount.current += 1
    }
    window.addEventListener('error', onError)
    window.addEventListener('unhandledrejection', onError)
    return () => {
      window.removeEventListener('error', onError)
      window.removeEventListener('unhandledrejection', onError)
    }
  }, [])
  const measuring = phase === 'running'

  useEffect(() => {
    void refineDeviceCaps(probeDeviceCaps()).then(setCaps)
    void fetchManifest().then(setManifest)
  }, [])

  const stages = useMemo(() => (manifest ? scheduleStages(manifest) : []), [manifest])

  const browserInfo = useCallback((): Record<string, unknown> => {
    const nav = navigator as Navigator & { deviceMemory?: number; hardwareConcurrency?: number }
    return {
      user_agent: navigator.userAgent,
      adapter: {
        vendor: caps.adapter.vendor,
        description: caps.adapter.description,
        device: caps.adapter.device,
        architecture: caps.adapter.architecture,
        perf_band: caps.adapter.perfBand,
      },
      webgpu: caps.webgpu,
      device_pixel_ratio: window.devicePixelRatio,
      viewport: { width: window.innerWidth, height: window.innerHeight },
      hardware_concurrency: nav.hardwareConcurrency ?? null,
      device_memory_gb: nav.deviceMemory ?? null,
      features: { timestamp_query: probe.gpuTimestampsAvailable },
      prefer_battery: caps.preferBattery,
      is_mobile: caps.isMobile,
      note: 'Frame times are requestAnimationFrame wall spacing; the compositor caps them at the display refresh rate. Chrome quantizes GPU timestamps unless WebGPU developer features are enabled.',
    }
  }, [caps, probe])

  const run = useCallback(async () => {
    if (!manifest || !caps.webgpu) return
    abortRef.current = false
    setRows([])
    setPayload(null)
    setPostStatus(null)
    setPhase('loading')
    const collected: { stage: ScheduledStage; samples: StageSamples }[] = []
    try {
      for (let i = 0; i < stages.length; i++) {
        if (abortRef.current) break
        const stage = stages[i]
        const c = manifest.params.cases.find((x) => x.key === stage.caseKey)
        if (!c) throw new Error(`case ${stage.caseKey} missing from manifest`)
        const effective = resolveTier(stage.tier, caps)
        setStatus(`Stage ${i + 1}/${stages.length}: ${stage.id} (tier ${effective}) · loading snapshot…`)
        const snap = await fetchSnapshot(c, effective, !!manifest.params.include_simulation, i + 1)
        setTier(effective)
        setSnapshot(snap)
        setStageIndex(i)
        probe.reset()
        setPhase('running')
        const t0 = performance.now()
        setStatus(`Stage ${i + 1}/${stages.length}: ${stage.id} (tier ${effective}) · warm-up ≥ ${stage.warmupFrames} frames / ${stage.warmupMinMs} ms, then ${stage.requestedFrames} frames…`)
        // Warm-up: both a frame floor and a time floor, so late pipeline compilation stays out of the sample.
        let warmupUsed = 0
        await new Promise<void>((resolve) => {
          const tick = () => {
            if (abortRef.current) return resolve()
            if (probe.frames.length >= stage.warmupFrames && performance.now() - t0 >= stage.warmupMinMs) {
              warmupUsed = probe.frames.length
              return resolve()
            }
            requestAnimationFrame(tick)
          }
          requestAnimationFrame(tick)
        })
        const need = warmupUsed + stage.requestedFrames
        const errorsBefore = errorCount.current
        await new Promise<void>((resolve) => {
          const tick = () => {
            if (abortRef.current || probe.frames.length >= need) return resolve()
            requestAnimationFrame(tick)
          }
          requestAnimationFrame(tick)
        })
        const thumb = await probe.requestThumbnail(manifest.params.thumbnail_size ?? 128)
        const frames = probe.frames.slice(0, need)
        const wall = trimFrames(frames.map((f) => f.wallMs), warmupUsed)
        const gpuAll = frames.slice(warmupUsed).map((f) => f.gpuMs)
        const gpu = gpuAll.every((g) => g === null) ? null : gpuAll.map((g) => (g === null ? NaN : g)).filter((g) => Number.isFinite(g))
        const lastFrame = frames[frames.length - 1]
        const perf = performance as Performance & { memory?: { usedJSHeapSize?: number } }
        collected.push({
          stage,
          samples: {
            warmupUsed,
            jsErrors: errorCount.current - errorsBefore,
            framesMs: wall,
            gpuMs: gpu && gpu.length ? gpu : null,
            drawCalls: lastFrame?.drawCalls ?? null,
            triangles: lastFrame?.triangles ?? null,
            durationMs: performance.now() - t0,
            jsHeapBytes: perf.memory?.usedJSHeapSize ?? null,
            thumbnailPngBase64: thumb,
            snapshotHash: snap.parameter_field?.hash ?? null,
            effectiveTier: effective,
            note: thumb ? undefined : 'thumbnail unavailable (canvas readback returned empty)',
          },
        })
        setRows([...collected])
        setPhase('loading')
      }
      const cap = buildCapturePayload({ manifest, stages: collected, browser: browserInfo(), aborted: abortRef.current })
      setPayload(cap)
      setPhase('done')
      setStatus(abortRef.current ? 'Aborted. Partial capture ready.' : 'Capture ready. Download it and run `psyfi-bench ingest <file>`, or post it if ingest is enabled.')
    } catch (err) {
      setPhase('error')
      setStatus(err instanceof Error ? err.message : 'bench failed')
    }
  }, [manifest, caps, stages, probe, browserInfo])

  const post = useCallback(async () => {
    if (!payload) return
    setPostStatus('posting…')
    try {
      const res = await fetch('/api/bench/v1/captures', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
      const body = await res.json()
      setPostStatus(res.ok ? `scored: run ${body.run_id} (${body.status})` : `${res.status}: ${body?.error?.message ?? 'rejected'}`)
    } catch (err) {
      setPostStatus(err instanceof Error ? err.message : 'post failed')
    }
  }, [payload])

  const filename = `psyfi-fieldloop-gpu-capture-${(caps.adapter.description || caps.adapter.vendor || 'adapter').replace(/[^a-z0-9]+/gi, '-').toLowerCase()}-${new Date().toISOString().slice(0, 10)}.json`

  return (
    <div style={{ display: 'grid', gridTemplateRows: 'auto 1fr auto', height: '100%', background: '#0a0e14', color: '#e6edf3', fontFamily: 'IBM Plex Sans, system-ui, sans-serif' }}>
      <header style={{ padding: '10px 14px', display: 'flex', gap: 12, alignItems: 'center', borderBottom: '1px solid #1f2a36', flexWrap: 'wrap' }}>
        <strong>PsyFi FieldLoop · GPU bench</strong>
        <span style={{ opacity: 0.8 }}>{status}</span>
        <button type="button" onClick={() => void run()} disabled={!manifest || !caps.webgpu || phase === 'running' || phase === 'loading'}>
          Run {stages.length ? `(${stages.length} stages)` : ''}
        </button>
        <button type="button" onClick={() => { abortRef.current = true }} disabled={phase !== 'running' && phase !== 'loading'}>
          Abort
        </button>
        <button type="button" onClick={() => payload && downloadJson(filename, payload)} disabled={!payload}>
          Download capture
        </button>
        <button type="button" onClick={() => void post()} disabled={!payload}>
          Post to /api/bench
        </button>
        {postStatus ? <span>{postStatus}</span> : null}
        <a href="/gpu/" style={{ marginLeft: 'auto', color: '#3ee7f2' }}>GPU lab</a>
      </header>
      <div style={{ position: 'relative', minHeight: 320 }}>
        {caps.webgpu ? (
          <BenchCanvas snapshot={snapshot} tier={tier}>
            <BenchProbe handle={probe} enabled={measuring} />
          </BenchCanvas>
        ) : (
          <p style={{ padding: 16 }}>WebGPU is not available in this browser. The bench needs Chrome/Edge with WebGPU enabled. No frames were recorded.</p>
        )}
      </div>
      <footer style={{ padding: '8px 14px', borderTop: '1px solid #1f2a36', fontSize: 13, maxHeight: '40vh', overflow: 'auto' }}>
        <div style={{ opacity: 0.8, marginBottom: 6 }}>
          adapter: {caps.adapter.description || caps.adapter.vendor || 'unknown'} · band {caps.adapter.perfBand} · GPU timestamps: {probe.gpuTimestampsAvailable === null ? 'probing' : probe.gpuTimestampsAvailable ? 'yes' : 'no'} · stage {stageIndex + 1}/{stages.length}
        </div>
        <table style={{ borderCollapse: 'collapse', width: '100%' }}>
          <thead>
            <tr style={{ textAlign: 'left', opacity: 0.7 }}>
              <th>stage</th><th>tier</th><th>frames</th><th>fps (quick)</th><th>p95 ms</th><th>gpu ms</th><th>thumb</th><th>js errors</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ stage, samples }) => {
              const q = quickSummary(samples.framesMs)
              return (
                <tr key={stage.id}>
                  <td>{stage.id}</td><td>{samples.effectiveTier}</td><td>{q.n}</td><td>{q.fps.toFixed(1)}</td><td>{q.p95Ms.toFixed(2)}</td>
                  <td>{samples.gpuMs ? 'yes' : 'n/a'}</td><td>{samples.thumbnailPngBase64 ? 'yes' : 'no'}</td><td>{samples.jsErrors}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <p style={{ opacity: 0.6, marginTop: 8 }}>
          The quick numbers are a sanity check. Scoring (percentiles, 1% low, pacing, drift, tier fidelity, budgets) happens in Python. Modeled phenomenology for research/visualization only. Not medical advice.
        </p>
      </footer>
    </div>
  )
}
