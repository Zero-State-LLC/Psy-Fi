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
  const canvasRef = useRef<HTMLCanvasElement | null>(null)

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
        // Microtask: runs after this task's synchronous render, before the compositor takes the frame.
        queueMicrotask(() => {
          try {
            const src = canvasRef.current
            if (!src) return resolve(null)
            const out = document.createElement('canvas')
            out.width = size
            out.height = size
            const ctx = out.getContext('2d')
            if (!ctx) return resolve(null)
            ctx.drawImage(src, 0, 0, size, size)
            const url = out.toDataURL('image/png')
            const data = url.split(',')[1] || null
            // A fully black readback means the WebGPU canvas could not be read; report null, never a fake frame.
            const px = ctx.getImageData(0, 0, size, size).data
            let any = 0
            for (let i = 0; i < px.length; i += 4) {
              if (px[i] || px[i + 1] || px[i + 2]) {
                any = 1
                break
              }
            }
            resolve(any ? data : null)
          } catch {
            resolve(null)
          }
        })
      })
    return () => {
      handle.requestThumbnail = async () => null
    }
  }, [gl, handle])

  useFrame(() => {
    const now = performance.now()
    const renderer = gl as unknown as {
      info?: { render?: { calls?: number; triangles?: number; timestamp?: number } }
      resolveTimestampsAsync?: (type?: unknown) => Promise<unknown>
    }
    if (!enabled) {
      last.current = now
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
      handle.frames.push({ wallMs, gpuMs, drawCalls: info.calls ?? 0, triangles: info.triangles ?? 0 })
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
