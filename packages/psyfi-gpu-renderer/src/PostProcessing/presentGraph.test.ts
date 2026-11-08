import { beforeEach, describe, expect, it, vi } from 'vitest'
import * as THREE from 'three/webgpu'
import { uniform } from 'three/tsl'
import { tierConfig, type QualityTier } from '../contracts/QualityTier'

const inputs = vi.hoisted(() => ({ ssr: [] as unknown[], motionBlur: [] as unknown[] }))

vi.mock('three/addons/tsl/display/SSRNode.js', async (importOriginal) => {
  const mod = await importOriginal<typeof import('three/addons/tsl/display/SSRNode.js')>()
  return {
    ...mod,
    ssr: (color: unknown, ...rest: unknown[]) => {
      inputs.ssr.push(color)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return (mod.ssr as any)(color, ...rest)
    },
  }
})

vi.mock('three/addons/tsl/display/MotionBlur.js', async (importOriginal) => {
  const mod = await importOriginal<typeof import('three/addons/tsl/display/MotionBlur.js')>()
  return {
    ...mod,
    motionBlur: (input: unknown, ...rest: unknown[]) => {
      inputs.motionBlur.push(input)
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      return (mod.motionBlur as any)(input, ...rest)
    },
  }
})

const { buildPresentGraph } = await import('./presentGraph')

const TIERS: QualityTier[] = ['ultra', 'high', 'balanced', 'battery']

function build(tier: QualityTier) {
  return buildPresentGraph({
    scene: new THREE.Scene(),
    camera: new THREE.PerspectiveCamera(),
    tier,
    uniforms: {
      uExposure: uniform(1),
      uGrade: uniform(new THREE.Vector3(1, 1, 1)),
      uSafety: uniform(1),
    },
  })
}

describe('buildPresentGraph', () => {
  beforeEach(() => {
    inputs.ssr.length = 0
    inputs.motionBlur.length = 0
  })

  it.each(TIERS)('hands SSR and motion blur a texture at tier %s (#55)', (tier) => {
    const cfg = tierConfig(tier)
    build(tier)

    expect(inputs.ssr).toHaveLength(cfg.post.ssr ? 1 : 0)
    expect(inputs.motionBlur).toHaveLength(cfg.post.motionBlur ? 1 : 0)
    for (const input of [...inputs.ssr, ...inputs.motionBlur]) {
      expect((input as { isTextureNode?: boolean }).isTextureNode).toBe(true)
    }
  })

  it('ends every tier in the safety graph and lists its passes for dispose', () => {
    for (const tier of TIERS) {
      const graph = build(tier)
      expect(graph.output).toBeTruthy()
      expect(graph.disposables.length).toBeGreaterThan(0)
      expect(graph.bloomStrength !== null).toBe(tierConfig(tier).post.bloom)
      expect(graph.temporalDamp !== null).toBe(tierConfig(tier).post.taa)
    }
  })
})
