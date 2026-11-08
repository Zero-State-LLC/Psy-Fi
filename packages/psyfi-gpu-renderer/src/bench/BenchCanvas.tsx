/**
 * Bench-only R3F canvas. Mirrors PsyFiGPUCanvas's camera, dpr and shadow settings but creates the
 * WebGPU renderer with optional timestamp tracking (?timestamps=1) so GPU pass times can be
 * resolved when the adapter exposes `timestamp-query`. SceneRoot is reused unchanged. PsyFiGPUCanvas itself is not modified.
 */

import { Canvas } from '@react-three/fiber'
import { Suspense, type ReactNode } from 'react'
import * as THREE from 'three/webgpu'
import { SceneRoot } from '../SceneGraph/SceneRoot'
import type { QualityTier } from '../contracts/QualityTier'
import type { SceneSnapshotV1 } from '../contracts/SceneSnapshot'

async function createBenchRenderer(
  props: ConstructorParameters<typeof THREE.WebGPURenderer>[0] & { canvas?: HTMLCanvasElement },
  trackTimestamp: boolean,
) {
  const renderer = new THREE.WebGPURenderer({
    ...(props as object),
    antialias: true,
    alpha: false,
    powerPreference: 'high-performance',
    trackTimestamp,
  } as ConstructorParameters<typeof THREE.WebGPURenderer>[0])
  await renderer.init()
  return renderer
}

export function BenchCanvas({
  snapshot,
  tier,
  trackTimestamp = false,
  children,
}: {
  snapshot: SceneSnapshotV1 | null
  tier: QualityTier
  /** Opt in with ?timestamps=1. On some adapters the MRT present stack throws with timestamp tracking on. */
  trackTimestamp?: boolean
  children?: ReactNode
}) {
  const cfgScale = tier === 'battery' ? 0.65 : tier === 'balanced' ? 0.85 : 1
  return (
    <Canvas
      shadows={tier !== 'battery'}
      dpr={[1, Math.min(2, 1.5 * cfgScale)]}
      gl={async (props) => createBenchRenderer(props as never, trackTimestamp)}
      camera={{ position: [0, 0.35, 2.4], fov: 45, near: 0.05, far: 80 }}
      style={{ width: '100%', height: '100%', background: 'var(--pf-bg-0)' }}
    >
      <Suspense fallback={null}>
        <SceneRoot snapshot={snapshot} tier={tier} />
        {children}
      </Suspense>
    </Canvas>
  )
}
