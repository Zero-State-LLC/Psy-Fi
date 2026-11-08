import type * as THREE from 'three/webgpu'
import {
  pass,
  vec3,
  float,
  mix,
  max,
  div,
  mul,
  select,
  greaterThan,
  renderOutput,
  mrt,
  output,
  normalView,
  metalness,
  velocity,
  convertToTexture,
} from 'three/tsl'
import { bloom } from 'three/addons/tsl/display/BloomNode.js'
import { afterImage } from 'three/addons/tsl/display/AfterImageNode.js'
import { ao } from 'three/addons/tsl/display/GTAONode.js'
import { ssr } from 'three/addons/tsl/display/SSRNode.js'
import { dof } from 'three/addons/tsl/display/DepthOfFieldNode.js'
import { rgbShift } from 'three/addons/tsl/display/RGBShiftNode.js'
import { motionBlur } from 'three/addons/tsl/display/MotionBlur.js'
import type { QualityTier } from '../contracts/QualityTier'
import { tierConfig } from '../contracts/QualityTier'
import type { DisposableGpuResource } from './presentDispose'

/* eslint-disable @typescript-eslint/no-explicit-any */
export type PresentUniforms = {
  uExposure: any
  uGrade: any
  uSafety: any
}

export type PresentGraph = {
  output: any
  disposables: DisposableGpuResource[]
  bloomStrength: { value: number } | null
  temporalDamp: { value: number } | null
}

/**
 * Present path: scene → GTAO → SSR → bloom → DoF → motion blur → chroma → temporal → grade → safety.
 *
 * SSR and motion blur sample their colour input, so each gets a texture (`convertToTexture`),
 * the same way three's `dof`, `afterImage` and `rgbShift` wrap theirs. Handing them a
 * non-texture node fails the shader build after a runtime tier switch (#55).
 */
export function buildPresentGraph({
  scene,
  camera,
  tier,
  uniforms,
}: {
  scene: THREE.Scene
  camera: THREE.Camera
  tier: QualityTier
  uniforms: PresentUniforms
}): PresentGraph {
  const cfg = tierConfig(tier)
  const scenePass = pass(scene, camera)
  const disposables: DisposableGpuResource[] = [scenePass]
  const needsMrt = cfg.post.ssao || cfg.post.ssr || cfg.post.motionBlur
  let bloomStrength: { value: number } | null = null
  let temporalDamp: { value: number } | null = null

  if (needsMrt) {
    scenePass.setMRT(
      mrt({
        output,
        normal: normalView,
        metalness,
        ...(cfg.post.motionBlur ? { velocity } : {}),
      }),
    )
  }

  const color = scenePass.getTextureNode('output')

  let node: any = color
  const depth = scenePass.getTextureNode('depth')
  const normal = needsMrt ? scenePass.getTextureNode('normal') : null

  if (cfg.post.ssao && normal) {
    const aoPass = ao(depth, normal, camera)
    aoPass.resolutionScale = tier === 'balanced' ? 0.5 : 1
    disposables.push(aoPass)
    node = aoPass.getTextureNode().mul(color)
  }

  if (cfg.post.ssr && normal) {
    const metal = scenePass.getTextureNode('metalness')
    const ssrPass = ssr(convertToTexture(node), depth, normal, metal, camera)
    disposables.push(ssrPass)
    node = node.add(ssrPass.getTextureNode().mul(float(0.28)))
  }

  if (cfg.post.bloom) {
    const bloomPass = bloom(node, 0.35, 0.4, 0.85)
    bloomStrength = bloomPass.strength
    disposables.push(bloomPass)
    node = node.add(bloomPass)
  }

  if (cfg.post.depthOfField) {
    const viewZ = scenePass.getViewZNode('depth')
    // Subtle DoF — Neutral path still reads clearly via safety/exposure later
    const dofPass = dof(node, viewZ, float(2.2), float(0.018), float(0.006))
    disposables.push(dofPass)
    node = dofPass
  }

  if (cfg.post.motionBlur) {
    const vel = scenePass.getTextureNode('velocity')
    const mb = motionBlur(convertToTexture(node), vel, 8)
    disposables.push(mb)
    node = mb
  }

  if (cfg.post.chromaticAberration) {
    const chroma = rgbShift(node, 0.0018, 0.0)
    disposables.push(chroma)
    node = chroma
  }

  if (cfg.post.taa) {
    const temporal = afterImage(node, 0.82)
    temporalDamp = temporal.damp
    disposables.push(temporal)
    node = temporal.getTextureNode()
  }

  if (cfg.post.colorGrading || cfg.post.hdr) {
    node = node.mul(uniforms.uGrade).mul(uniforms.uExposure)
  }

  // Mandatory safety: peak luminance clamp (safety_clamp.wgsl) then attenuator.
  // Peak clamp must run even when uSafety === 1 (common happy path).
  const peak = max(node.r, max(node.g, node.b))
  const peakScale = select(greaterThan(peak, float(0.96)), div(float(0.96), peak), float(1))
  node = mul(node, peakScale)
  node = node.mul(uniforms.uSafety)
  node = mix(vec3(0.05, 0.05, 0.055), node, float(0.98))

  if (cfg.post.hdr) {
    node = renderOutput(node)
  }

  return { output: node, disposables, bloomStrength, temporalDamp }
}
