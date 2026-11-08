/**
 * Lives inside the R3F canvas (passed as children to PsyFiGPUCanvas). Measures per-frame wall
 * spacing, reads renderer.info, and resolves WebGPU timestamp queries when the adapter exposes
 * them. It never changes what is drawn.
 */

import { useFrame, useThree } from '@react-three/fiber'
import { useEffect, useRef } from 'react'
import * as THREE from 'three/webgpu'

export interface ProbeFrame {
  wallMs: number
  gpuMs: number | null
  drawCalls: number
  triangles: number
}

export interface ProbeHandle {
  frames: ProbeFrame[]
  gpuTimestampsAvailable: boolean | null
  reset(): void
  /** Grab a downscaled PNG of the current presented frame (runs after the render in the same task). */
  requestThumbnail(size: number): Promise<string | null>
}

export function createProbeHandle(): ProbeHandle {
  const handle: ProbeHandle = {
    frames: [],
    gpuTimestampsAvailable: null,
    reset() {
      handle.frames = []
    },
    requestThumbnail: async () => null,
  }
  return handle
}

export function BenchProbe({ handle, enabled }: { handle: ProbeHandle; enabled: boolean }) {
  const { gl } = useThree()
  const last = useRef<number | null>(null)
  const lastCalls = useRef<number | null>(null)
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const pendingThumb = useRef<{ size: number; resolve: (v: string | null) => void } | null>(null)

  const captureNow = (size: number): string | null => {
    try {
      const src = canvasRef.current
      if (!src) return null
      const out = document.createElement('canvas')
      out.width = size
      out.height = size
      const ctx = out.getContext('2d')
      if (!ctx) return null
      ctx.drawImage(src, 0, 0, size, size)
      const px = ctx.getImageData(0, 0, size, size).data
      let any = 0
      for (let i = 0; i < px.length; i += 4) {
        if (px[i] || px[i + 1] || px[i + 2]) {
          any = 1
          break
        }
      }
      // A fully black readback means the WebGPU canvas could not be read; report null, never a fake frame.
      return any ? out.toDataURL('image/png').split(',')[1] || null : null
    } catch {
      return null
    }
  }

  useEffect(() => {
    const renderer = gl as unknown as InstanceType<typeof THREE.WebGPURenderer> & { trackTimestamp?: boolean }
    canvasRef.current = (renderer.domElement as HTMLCanvasElement) || null
    try {
      // Opt into GPU timing. Chrome quantizes timestamps unless the developer flag is on.
      renderer.trackTimestamp = true
    } catch {
      handle.gpuTimestampsAvailable = false
    }
    handle.requestThumbnail = (size: number) =>
      new Promise<string | null>((resolve) => {
        // Fulfilled from the next frame callback: a microtask queued there runs after R3F's
        // synchronous render in the same task, before the compositor takes the frame.
        pendingThumb.current = { size, resolve }
      })
    return () => {
      pendingThumb.current = null
      handle.requestThumbnail = async () => null
    }
  }, [gl, handle])

  useFrame(() => {
    const now = performance.now()
    const pending = pendingThumb.current
    if (pending) {
      pendingThumb.current = null
      queueMicrotask(() => pending.resolve(captureNow(pending.size)))
    }
    const renderer = gl as unknown as {
      info?: { render?: { calls?: number; triangles?: number; timestamp?: number } }
      resolveTimestampsAsync?: (type?: unknown) => Promise<unknown>
    }
    if (!enabled) {
      last.current = now
      lastCalls.current = renderer.info?.render?.calls ?? null
      return
    }
    if (last.current !== null) {
      const wallMs = now - last.current
      const info = renderer.info?.render || {}
      let gpuMs: number | null = null
      const ts = info.timestamp
      if (typeof ts === 'number' && Number.isFinite(ts) && ts > 0) {
        gpuMs = ts
        handle.gpuTimestampsAvailable = true
      } else if (handle.gpuTimestampsAvailable === null && handle.frames.length > 30) {
        handle.gpuTimestampsAvailable = false
      }
      // renderer.info counters accumulate across frames in the WebGPU backend; report the per-frame delta.
      const calls = info.calls ?? 0
      const drawCalls = lastCalls.current === null ? calls : Math.max(0, calls - lastCalls.current)
      lastCalls.current = calls
      handle.frames.push({ wallMs, gpuMs, drawCalls, triangles: info.triangles ?? 0 })
    }
    last.current = now
    if (typeof renderer.resolveTimestampsAsync === 'function') {
      // Resolve queued GPU timestamps; without this the query pool fills up.
      const TQ = (THREE as unknown as { TimestampQuery?: { RENDER?: unknown } }).TimestampQuery
      void renderer.resolveTimestampsAsync(TQ?.RENDER).catch(() => {
        handle.gpuTimestampsAvailable = false
      })
    }
  })

  return null
}
