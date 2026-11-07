/**
 * PsyFi Experience Player — orchestrates ParameterField → engines → safety pass.
 * Canvas is default; optional WebGL ParameterField path when preferred.
 * I2: pin + compare surface (wipe/blink/split) via PsyFiViz.compareSurface.
 */
(function (global) {
  'use strict';

  const math = () => global.PsyFiViz.math;
  const engines = () => global.PsyFiViz.engines;

  /** Flatten visualization.field ({values[][], width, height}) for sampling. */
  function packSourceField(field, mix) {
    if (!field || !field.values || !field.width || !field.height) return null;
    const m = Number(mix);
    if (!(m > 0)) return null;
    const width = field.width | 0;
    const height = field.height | 0;
    const data = new Float32Array(width * height);
    for (let y = 0; y < height; y++) {
      const row = field.values[y];
      if (!row) continue;
      for (let x = 0; x < width; x++) {
        const v = Number(row[x]);
        data[y * width + x] = Number.isFinite(v) ? Math.min(1, Math.max(0, v)) : 0;
      }
    }
    return { width, height, data, mix: Math.min(1, Math.max(0, m)) };
  }

  function sampleSourcePlane(plane, nx, ny) {
    if (!plane) return 0;
    const x = Math.min(1, Math.max(0, nx)) * (plane.width - 1);
    const y = Math.min(1, Math.max(0, ny)) * (plane.height - 1);
    const x0 = Math.floor(x);
    const y0 = Math.floor(y);
    const x1 = Math.min(plane.width - 1, x0 + 1);
    const y1 = Math.min(plane.height - 1, y0 + 1);
    const fx = x - x0;
    const fy = y - y0;
    const i00 = plane.data[y0 * plane.width + x0];
    const i10 = plane.data[y0 * plane.width + x1];
    const i01 = plane.data[y1 * plane.width + x0];
    const i11 = plane.data[y1 * plane.width + x1];
    const a = i00 * (1 - fx) + i10 * fx;
    const b = i01 * (1 - fx) + i11 * fx;
    return a * (1 - fy) + b * fy;
  }

  class ExperienceRenderer {
    constructor(canvas) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d', { alpha: false });
      this.w = canvas.width;
      this.h = canvas.height;
      this.safety = new global.PsyFiViz.SafetyPass();
      this.frame = null;
      this.sourcePlane = null;
      this.t0 = performance.now();
      this.running = false;
      this.raf = 0;
      this._buf = null;
      this.onFrameInfo = null;
      this.backend = 'canvas2d';
      this.lodDrop = 0;
      this._emaFrameMs = 16;
      // I2
      this.pinnedFrame = null;
      this.compareMode = 'off';
      this.wipePosition = 0.5;
      this.blinkHz = 2;
      // Safety-clamped transitions
      this.transitionFrom = null;
      this.transitionStart = 0;
      this.transitionDuration = 0;
      this.transitionKind = 'off';
    }

    setPinnedFrame(frame) {
      this.pinnedFrame = frame || null;
      this._pinnedRaster = null;
      this._pinnedRasterHash = '';
    }

    setCompareState(state) {
      if (!state) return;
      this.compareMode = state.mode || 'off';
      if (state.wipe != null) this.wipePosition = state.wipe;
      if (state.blinkHz != null) this.blinkHz = state.blinkHz;
    }

    setTransitionState(state) {
      const s = state || {};
      this.transitionFrom = s.from || null;
      this.transitionStart = Number(s.start) || 0;
      this.transitionDuration = Math.max(0, Number(s.duration) || 0);
      this.transitionKind = s.kind || 'off';
      this._transitionRaster = null;
      this._transitionRasterHash = '';
    }

    _noteFrameMs(ms) {
      this._emaFrameMs = this._emaFrameMs * 0.85 + ms * 0.15;
      if (this._emaFrameMs > 22) this.lodDrop = Math.min(2, this.lodDrop + 1);
      else if (this._emaFrameMs < 13 && this.lodDrop > 0) this.lodDrop = Math.max(0, this.lodDrop - 1);
    }

    setFrame(frame) {
      this.frame = frame;
    }

    setSourcePlane(plane) {
      this.sourcePlane = plane || null;
    }

    resize(w, h, opts) {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const bufferW = opts && opts.bufferW ? Math.floor(opts.bufferW) : Math.floor(w * dpr);
      const bufferH = opts && opts.bufferH ? Math.floor(opts.bufferH) : Math.floor(h * dpr);
      this.canvas.width = Math.max(16, bufferW);
      this.canvas.height = Math.max(16, bufferH);
      this.canvas.style.width = w + 'px';
      this.canvas.style.height = h + 'px';
      this.w = this.canvas.width;
      this.h = this.canvas.height;
      this._buf = null;
      this._pinnedRaster = null;
    }

    start() {
      if (this.running) return;
      this.running = true;
      this.t0 = performance.now();
      const loop = (now) => {
        if (!this.running) return;
        const t0 = performance.now();
        this.draw(now);
        this._noteFrameMs(performance.now() - t0);
        this.raf = requestAnimationFrame(loop);
      };
      this.raf = requestAnimationFrame(loop);
    }

    stop() {
      this.running = false;
      if (this.raf) cancelAnimationFrame(this.raf);
    }

    draw(now) {
      const { clamp, hexToRgb, mulberry32, hash32, fbm, resolveRenderLod } = math();
      const engFns = engines();
      const ctx = this.ctx;
      const w = this.w;
      const h = this.h;
      const f = this.frame || {};
      const lod = resolveRenderLod(f.quality_tier || 'balanced', this.lodDrop);
      const iw = Math.max(lod.canvasMinW, Math.min(lod.canvasMaxW, Math.floor(w / lod.canvasDiv)));
      const ih = Math.max(lod.canvasMinH, Math.min(lod.canvasMaxH, Math.floor(h / lod.canvasDiv)));
      if (!this._buf || this._buf.width !== iw || this._buf.height !== ih) {
        this._buf = ctx.createImageData(iw, ih);
        this._off = document.createElement('canvas');
        this._off.width = iw;
        this._off.height = ih;
        this._offCtx = this._off.getContext('2d', { alpha: false });
        this._prev = null;
      }
      const img = this._buf;
      const d = img.data;
      const p = f.parameters || {};
      const eng = f.engines || {};
      const pal = hexToRgb((f.palette && f.palette.tracers) || '#3ee7f2');
      const seed = (f.master_seed || 42) >>> 0;
      const rnd = mulberry32(hash32(seed + 17));
      const time = (now - this.t0) / 1000;
      const trail = (p.trail_length || 0.35) * lod.trailScale;
      const edge = p.edge_gain || 0.4;
      const chroma = (p.chromatic_aberration || 0.1) * lod.chromaScale;

      const engineCtx = {
        time,
        seed,
        feedback: p.feedback_strength || 0.4,
        recursion: p.recursion_gain || 0.35,
        turb: p.turbulence || 0.25,
        zoom: p.zoom_velocity || 0.08,
        disp: p.displacement || 0.2,
        entropy: p.entropy || 0.3,
        bloom: p.bloom || 0.25,
        depth: p.depth_distortion || 0.35,
        complex: p.pattern_complexity || 0.4,
        voidB: p.void_bias || 0,
        attrB: p.attractor_bias || 0,
        trail,
        edge,
        foldIters: lod.foldIters,
        fbmOctaves: lod.fbmOctaves,
        deepDetail: lod.deepDetail,
        latticeDetail: lod.latticeDetail,
      };
      const symmetry = Math.max(1, Math.floor(2 + (p.symmetry_order || 0.3) * 10));
      const energy = (f.palette && f.palette.energy) || p.palette_energy || 0.5;
      const wR = eng.recursive_feedback || 0.3;
      const wK = eng.kaleidoscope || 0.2;
      const wF = eng.flow_field || 0.2;
      const wO = eng.organic_bloom || 0.2;
      const wV = eng.void_expansion || 0.15;
      const wE = eng.entity_lattice || 0.1;
      const wN = eng.neutral_view || 0.0;
      const neutral = !!f.neutral_view || wN > 0.8;
      const cx = iw * 0.5;
      const cy = ih * 0.5;
      const invMin = 1 / Math.min(iw, ih);
      const doK = wK > 0.05;
      const doR = wR > 0.05;
      const doF = wF > 0.05;
      const doO = wO > 0.05;
      const doV = wV > 0.05;
      const doE = wE > 0.05;

      for (let y = 0; y < ih; y++) {
        for (let x = 0; x < iw; x++) {
          let ux = (x - cx) * invMin;
          let uy = (y - cy) * invMin;
          let feedbackF = 0;
          let organic = 0;
          let voidF = 0;
          let lattice = 0;

          if (!neutral) {
            if (doK) ({ ux, uy } = engFns.kaleidoscope(ux, uy, wK, symmetry));
            if (doR) {
              const rf = engFns.recursiveFeedback(ux, uy, wR, engineCtx);
              ux = rf.ux;
              uy = rf.uy;
              feedbackF = rf.feedbackF || 0;
            }
            if (doF) ({ ux, uy } = engFns.flowField(ux, uy, wF, engineCtx));
            if (doO) organic = engFns.organicBloom(ux, uy, wO, engineCtx);
            if (doV) voidF = engFns.voidExpansion(ux, uy, wV, engineCtx);
            if (doE) lattice = engFns.entityLattice(ux, uy, wE, engineCtx);
          }

          let v = neutral
            ? engFns.neutralView(ux, uy, time)
            : feedbackF * wR +
              organic * wO +
              voidF * wV +
              lattice * wE +
              (doF ? fbm(ux * 1.1, uy * 1.1, seed, lod.fbmOctaves) * wF * 0.5 : 0);

          if (engineCtx.attrB > 0.2 && !neutral) {
            const r = Math.hypot(ux, uy);
            v *= 0.75 + 0.55 * Math.exp(-r * (1.5 + engineCtx.attrB * 2));
            v += engineCtx.attrB * 0.15 * Math.pow(Math.max(0, 1 - r * 2), 2);
          }

          if (!neutral && edge > 0.05) {
            const sharpened = v * v * (3 - 2 * v);
            v = v * (1 - edge * 0.55) + sharpened * edge * 0.55;
            v += edge * 0.1 * Math.abs(lattice - organic);
          }

          v = clamp(v * (0.7 + energy * 0.8) + engineCtx.turb * (rnd() - 0.5) * 0.08, 0, 1);

          if (!neutral && this.sourcePlane && this.sourcePlane.mix > 0) {
            const src = sampleSourcePlane(this.sourcePlane, x / Math.max(1, iw - 1), y / Math.max(1, ih - 1));
            v = clamp(v * (1 - this.sourcePlane.mix * 0.85) + src * this.sourcePlane.mix, 0, 1);
          }

          let rC, gC, bC;
          if (neutral) {
            rC = 10 + v * 30;
            gC = 12 + v * 34;
            bC = 18 + v * 40;
          } else {
            const warm = clamp(v * 1.15, 0, 1);
            const vR = clamp(v + chroma * 0.1 * (ux / (Math.abs(ux) + 0.2)), 0, 1);
            const vB = clamp(v - chroma * 0.1 * (ux / (Math.abs(ux) + 0.2)), 0, 1);
            rC = pal.r * vR * (0.4 + vR) + 6 + chroma * Math.abs(vR - vB) * 40;
            gC = pal.g * warm * (0.45 + organic * 0.35 + v * 0.35) + 8;
            bC = pal.b * vB * (0.5 + vB * 0.55) + lattice * 70 + 10;
            const bAmt = engineCtx.bloom * Math.pow(v, 2);
            rC = rC * (1 - bAmt) + 255 * bAmt * 0.78;
            gC = gC * (1 - bAmt) + 255 * bAmt * 0.88;
            bC = bC * (1 - bAmt) + 255 * bAmt;
            const nr = Math.hypot((x - cx) / iw, (y - cy) / ih);
            const vig = 0.72 + 0.28 * Math.max(0, 1 - nr * 1.6);
            rC *= vig;
            gC *= vig;
            bC *= vig;
          }

          const idx = (y * iw + x) * 4;
          if (!neutral && this._prev && trail > 0.05) {
            const persist = 0.12 + trail * 0.62;
            rC = rC * (1 - persist) + this._prev[idx] * persist;
            gC = gC * (1 - persist) + this._prev[idx + 1] * persist;
            bC = bC * (1 - persist) + this._prev[idx + 2] * persist;
          }
          d[idx] = clamp(rC, 0, 255);
          d[idx + 1] = clamp(gC, 0, 255);
          d[idx + 2] = clamp(bC, 0, 255);
          d[idx + 3] = 255;
        }
      }

      this.safety.apply(img, f.safety || {}, now);
      if (!this._prev || this._prev.length !== d.length) this._prev = new Uint8ClampedArray(d.length);
      this._prev.set(d);

      // Safety-clamped crossfade (skipped when hold-and-compare is active).
      let displayImg = img;
      const ts = global.PsyFiViz && global.PsyFiViz.transitionSurface;
      const compareActive =
        this.pinnedFrame && this.compareMode && this.compareMode !== 'off';
      if (
        ts &&
        !compareActive &&
        this.transitionFrom &&
        this.transitionDuration > 0 &&
        ts.isActive(now, this.transitionStart, this.transitionDuration)
      ) {
        if (!this._xfadeBuf || this._xfadeBuf.width !== iw || this._xfadeBuf.height !== ih) {
          this._xfadeBuf = ctx.createImageData(iw, ih);
        }
        const fromHash = this.transitionFrom.hash || '';
        if (!this._transitionRaster || this._transitionRasterHash !== fromHash) {
          this._rasterizeFrameTo(this.transitionFrom, this._xfadeBuf, iw, ih, now, lod, engFns, math());
          this.safety.apply(this._xfadeBuf, this.transitionFrom.safety || {}, now);
          this._transitionRaster = this._xfadeBuf;
          this._transitionRasterHash = fromHash;
        }
        const t = ts.progress(now, this.transitionStart, this.transitionDuration);
        if (!this._blendBuf || this._blendBuf.width !== iw || this._blendBuf.height !== ih) {
          this._blendBuf = ctx.createImageData(iw, ih);
        }
        displayImg = ts.compositeCrossfade(
          this._transitionRaster,
          img,
          t,
          iw,
          ih,
          this._blendBuf,
        );
      }

      // I2: wipe / blink / split composite against pinned frame (presentation only)
      const cs = global.PsyFiViz && global.PsyFiViz.compareSurface;
      if (cs && compareActive) {
        if (!this._pinBuf || this._pinBuf.width !== iw || this._pinBuf.height !== ih) {
          this._pinBuf = ctx.createImageData(iw, ih);
        }
        if (!this._pinnedRaster || this._pinnedRasterHash !== (this.pinnedFrame.hash || '')) {
          this._rasterizeFrameTo(this.pinnedFrame, this._pinBuf, iw, ih, now, lod, engFns, math());
          this.safety.apply(this._pinBuf, this.pinnedFrame.safety || {}, now);
          this._pinnedRaster = this._pinBuf;
          this._pinnedRasterHash = this.pinnedFrame.hash || '';
        }
        if (this.compareMode === 'wipe') {
          displayImg = cs.compositeWipe(this._pinnedRaster, displayImg, this.wipePosition, iw, ih);
        } else if (this.compareMode === 'blink') {
          let blinkMode = 'blink';
          try {
            if (
              (f && f.reduce_motion) ||
              (typeof window !== 'undefined' &&
                window.matchMedia &&
                window.matchMedia('(prefers-reduced-motion: reduce)').matches)
            ) {
              blinkMode = 'split';
            }
          } catch (_e) {
            /* ignore */
          }
          if (blinkMode === 'split') {
            displayImg = cs.compositeSplit(this._pinnedRaster, displayImg, iw, ih);
          } else {
            const showPin = cs.blinkShowPinned(now, this.blinkHz, this.t0);
            displayImg = showPin ? this._pinnedRaster : displayImg;
          }
        } else if (this.compareMode === 'split') {
          displayImg = cs.compositeSplit(this._pinnedRaster, displayImg, iw, ih);
        }
      }

      this._offCtx.putImageData(displayImg, 0, 0);
      ctx.imageSmoothingEnabled = true;
      ctx.imageSmoothingQuality = 'high';
      ctx.fillStyle = '#0a0e14';
      ctx.fillRect(0, 0, w, h);
      ctx.drawImage(this._off, 0, 0, w, h);

      if (typeof this.onFrameInfo === 'function') {
        this.onFrameInfo({
          phase: f.phase,
          hash: f.hash,
          mode: f.mode,
          substance: f.substance,
          backend: this.backend,
          lod: lod.name,
        });
      }
    }

    /**
     * I2: rasterize a ParameterField frame into ImageData for the pinned side.
     * Mirrors the main draw path at the same LOD; presentation-only.
     */
    _rasterizeFrameTo(frame, imgData, iw, ih, now, lod, engFns, mathFns) {
      const { clamp, hexToRgb, mulberry32, hash32, fbm } = mathFns;
      const d = imgData.data;
      const f = frame || {};
      const p = f.parameters || {};
      const eng = f.engines || {};
      const pal = hexToRgb((f.palette && f.palette.tracers) || '#3ee7f2');
      const seed = (f.master_seed || 42) >>> 0;
      const rnd = mulberry32(hash32(seed + 19));
      const time = (now - this.t0) / 1000;
      const neutral = !!f.neutral_view || (eng.neutral_view || 0) > 0.8;
      const cx = iw * 0.5;
      const cy = ih * 0.5;
      const invMin = 1 / Math.min(iw, ih);
      const symmetry = Math.max(1, Math.floor(2 + (p.symmetry_order || 0.3) * 10));
      const energy = (f.palette && f.palette.energy) || p.palette_energy || 0.5;
      const wR = eng.recursive_feedback || 0.3;
      const wK = eng.kaleidoscope || 0.2;
      const wF = eng.flow_field || 0.2;
      const wO = eng.organic_bloom || 0.2;
      const wV = eng.void_expansion || 0.15;
      const wE = eng.entity_lattice || 0.1;
      const engineCtx = {
        time, seed,
        feedback: p.feedback_strength || 0.4,
        recursion: p.recursion_gain || 0.35,
        turb: p.turbulence || 0.25,
        zoom: p.zoom_velocity || 0.08,
        disp: p.displacement || 0.2,
        entropy: p.entropy || 0.3,
        bloom: p.bloom || 0.25,
        depth: p.depth_distortion || 0.35,
        complex: p.pattern_complexity || 0.4,
        voidB: p.void_bias || 0,
        attrB: p.attractor_bias || 0,
        trail: (p.trail_length || 0.35) * lod.trailScale,
        edge: p.edge_gain || 0.4,
        foldIters: lod.foldIters,
        fbmOctaves: lod.fbmOctaves,
        deepDetail: lod.deepDetail,
        latticeDetail: lod.latticeDetail,
      };
      for (let y = 0; y < ih; y++) {
        for (let x = 0; x < iw; x++) {
          let ux = (x - cx) * invMin;
          let uy = (y - cy) * invMin;
          let feedbackF = 0, organic = 0, voidF = 0, lattice = 0;
          if (!neutral) {
            if (wK > 0.05) ({ ux, uy } = engFns.kaleidoscope(ux, uy, wK, symmetry));
            if (wR > 0.05) {
              const rf = engFns.recursiveFeedback(ux, uy, wR, engineCtx);
              ux = rf.ux; uy = rf.uy; feedbackF = rf.feedbackF || 0;
            }
            if (wF > 0.05) ({ ux, uy } = engFns.flowField(ux, uy, wF, engineCtx));
            if (wO > 0.05) organic = engFns.organicBloom(ux, uy, wO, engineCtx);
            if (wV > 0.05) voidF = engFns.voidExpansion(ux, uy, wV, engineCtx);
            if (wE > 0.05) lattice = engFns.entityLattice(ux, uy, wE, engineCtx);
          }
          let v = neutral
            ? engFns.neutralView(ux, uy, time)
            : feedbackF * wR + organic * wO + voidF * wV + lattice * wE
              + (wF > 0.05 ? fbm(ux * 1.1, uy * 1.1, seed, lod.fbmOctaves) * wF * 0.5 : 0);
          v = clamp(v * (0.7 + energy * 0.8) + engineCtx.turb * (rnd() - 0.5) * 0.08, 0, 1);
          let rC, gC, bC;
          if (neutral) {
            rC = 10 + v * 30; gC = 12 + v * 34; bC = 18 + v * 40;
          } else {
            const warm = clamp(v * 1.15, 0, 1);
            rC = pal.r * v * (0.4 + v) + 6;
            gC = pal.g * warm * (0.45 + organic * 0.35 + v * 0.35) + 8;
            bC = pal.b * v * (0.5 + v * 0.55) + lattice * 70 + 10;
          }
          const idx = (y * iw + x) * 4;
          d[idx] = clamp(rC, 0, 255);
          d[idx + 1] = clamp(gC, 0, 255);
          d[idx + 2] = clamp(bC, 0, 255);
          d[idx + 3] = 255;
        }
      }
    }
  }

  class ExperiencePlayer {
    constructor(opts) {
      this.canvas = opts.canvas;
      this.glCanvas = opts.glCanvas || null;
      this.preferWebGL = !!opts.preferWebGL;
      this.webgl = null;
      this.renderer = new ExperienceRenderer(this.canvas);
      if (
        this.glCanvas &&
        global.PsyFiViz.ParameterFieldWebGL &&
        global.PsyFiViz.ParameterFieldWebGL.supported()
      ) {
        this.webgl = new global.PsyFiViz.ParameterFieldWebGL(this.glCanvas);
        if (!this.webgl.ok) this.webgl = null;
      }
      this.timeline = null;
      this.idx = 0;
      this.playing = false;
      this.neutralOn = false;
      this.statusEl = opts.statusEl || null;
      this.provenanceEl = opts.provenanceEl || null;
      this.renderer.onFrameInfo = (info) => this._status(info);
      this.modulators = { camera: 0, motion: 0, midi: 0, audio: 0, haptics: 0, image: 0 };
      this.imageHints = null;
      this.loadContext = null;
      this.liveModulators = true;
      this._liveAbort = null;
      this._liveModTimer = 0;
      this._lastLiveModMs = 0;
      this.fieldBridge = null;
      this.sourcePlane = null;
      this.viewportResolution = 'auto';
      this.phaseAdvance = true;
      this.phaseSpeed = 1;
      this._phaseBaseMs = 900;
      // I2 hold-and-compare
      this.pinned = null;
      this.compareMode = 'off';
      this.wipePosition = 0.5;
      this.blinkHz = 2;
      this._blinkT0 = performance.now();
      // Safety-clamped transitions
      this._transition = null;
      this._pendingTransitionKind = null;
      this.setPreferWebGL(this.preferWebGL);
    }

    setPhaseAdvance(on) {
      this.phaseAdvance = !!on;
      if (this._phaseTimer) clearInterval(this._phaseTimer);
      if (this.playing && this.phaseAdvance) this._tickPhases();
    }

    setPhaseSpeed(mult) {
      const n = Number(mult);
      this.phaseSpeed = Number.isFinite(n) && n > 0 ? n : 1;
      if (this._phaseTimer) clearInterval(this._phaseTimer);
      if (this.playing && this.phaseAdvance) this._tickPhases();
    }

    setViewportResolution(value) {
      this.viewportResolution = value || 'auto';
      this.resize();
    }

    setSourcePlane(field, mix) {
      const plane = packSourceField(field, mix == null ? 0.32 : mix);
      this.sourcePlane = plane;
      this.renderer.setSourcePlane(plane);
      if (this.webgl && typeof this.webgl.setSourcePlane === 'function') {
        this.webgl.setSourcePlane(plane);
      }
    }

    clearSourcePlane() {
      this.setSourcePlane(null, 0);
    }

    setSourceMix(mix) {
      if (!this.sourcePlane) return;
      const m = Math.min(1, Math.max(0, Number(mix) || 0));
      this.sourcePlane = { ...this.sourcePlane, mix: m };
      this.renderer.setSourcePlane(this.sourcePlane);
      if (this.webgl && typeof this.webgl.setSourcePlane === 'function') {
        this.webgl.setSourcePlane(this.sourcePlane);
      }
    }

    _syncCanvasVisibility() {
      const useGL = this.backend === 'webgl' && this.webgl && this.webgl.ok;
      if (this.canvas) this.canvas.hidden = !!useGL;
      if (this.glCanvas) this.glCanvas.hidden = !useGL;
    }

    setPreferWebGL(on) {
      this.preferWebGL = !!on;
      const wasPlaying = this.playing;
      this.pause();
      if (on && this.webgl && this.webgl.ok) {
        this.backend = 'webgl';
      } else {
        this.backend = 'canvas2d';
      }
      this.renderer.backend = this.backend;
      this._syncCanvasVisibility();
      if (this.timeline && this.timeline.frames && this.timeline.frames[this.idx]) {
        this.setFrame(this.timeline.frames[this.idx]);
      }
      if (wasPlaying) this.play();
    }

    resize() {
      const parent = (this.canvas && this.canvas.parentElement) || (this.glCanvas && this.glCanvas.parentElement);
      const w = Math.max(280, parent ? parent.clientWidth : 480);
      const h = Math.max(220, Math.floor(w * 0.62));
      let opts;
      const mode = this.viewportResolution || 'auto';
      if (mode === 'native') {
        const mon =
          global.PsyFiViz && typeof global.PsyFiViz.probeMonitor === 'function'
            ? global.PsyFiViz.probeMonitor()
            : { width: global.screen && global.screen.width, height: global.screen && global.screen.height };
        const bw = Math.max(320, Math.min(3840, Number(mon.width) || w));
        const bh = Math.max(200, Math.min(2160, Number(mon.height) || h));
        opts = { bufferW: bw, bufferH: bh };
      } else if (/^\d+x\d+$/.test(mode)) {
        const parts = mode.split('x');
        opts = {
          bufferW: Math.max(16, parseInt(parts[0], 10) || w),
          bufferH: Math.max(16, parseInt(parts[1], 10) || h),
        };
      }
      this.renderer.resize(w, h, opts);
      if (this.webgl) this.webgl.resize(w, h, opts);
    }

    async loadTimeline(payload, opts) {
      this.loadContext = {
        substance: payload.substance,
        experience_id: payload.experience_id || null,
        mode: payload.mode || 'open',
        intensity: payload.intensity,
        seed: payload.seed,
        reduce_motion: !!payload.reduce_motion,
        dim_flashing: !!payload.dim_flashing,
        quality_tier: payload.quality_tier || 'balanced',
      };
      const body = {
        ...payload,
        modulators: this.modulators,
      };
      if (this.imageHints) body.image_hints = this.imageHints;
      const res = await fetch('/api/v1/visualize/parameter-timeline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || res.statusText);
      }
      const data = await res.json();
      const transitionKind =
        (opts && opts.transitionKind) || this._pendingTransitionKind || 'load';
      this._pendingTransitionKind = null;
      this.beginTransition(transitionKind);
      this.clearPin();
      if (data.kind === 'snapshot') {
        this.timeline = { frames: [data.frame], timeline_hash: data.frame.hash, seed: data.frame.master_seed };
        this.frame = data.frame;
        this.setFrame(data.frame);
      } else {
        this.timeline = data;
        this.idx = Math.min(this.idx, data.frames.length - 1);
        const fr = data.frames[this.idx] || data.frames[0];
        this.frame = this.neutralOn ? this._materializeNeutral(fr) : fr;
        this.setFrame(this.frame);
      }
      this._pushTransitionState();
      this._provenance(data);
      return data;
    }

    setFrame(frame) {
      this.renderer.setFrame(frame);
      if (this.webgl) this.webgl.setFrame(frame);
    }

    _pushTransitionState() {
      const t = this._transition;
      const now = performance.now();
      const ts = global.PsyFiViz && global.PsyFiViz.transitionSurface;
      let state = { from: null, start: 0, duration: 0, kind: 'off' };
      if (t && ts && ts.isActive(now, t.start, t.duration)) {
        state = {
          from: t.from,
          start: t.start,
          duration: t.duration,
          kind: t.kind,
        };
      } else if (t && (!ts || !ts.isActive(now, t.start, t.duration))) {
        this._transition = null;
      }
      if (this.renderer && typeof this.renderer.setTransitionState === 'function') {
        this.renderer.setTransitionState(state);
      }
      if (this.webgl && typeof this.webgl.setTransitionState === 'function') {
        this.webgl.setTransitionState(state);
      }
    }

    /**
     * Begin a soft crossfade from the current live frame to the next.
     * Skipped when reduce-motion, compare mode active, or no prior frame.
     */
    beginTransition(kind) {
      const ts = global.PsyFiViz && global.PsyFiViz.transitionSurface;
      if (!ts) return;
      const compareOn = this.compareMode && this.compareMode !== 'off' && this.pinned;
      if (compareOn) {
        this._transition = null;
        this._pushTransitionState();
        return;
      }
      const from = this.frame;
      if (!from) return;
      const state = ts.makeTransitionState(from, kind, performance.now());
      this._transition = state.active ? state : null;
      this._pushTransitionState();
    }

    setPhaseIndex(i) {
      if (!this.timeline || !this.timeline.frames) return;
      const next = Math.max(0, Math.min(this.timeline.frames.length - 1, i | 0));
      if (next !== this.idx) this.beginTransition('phase');
      this.idx = next;
      this._applyFrameForIndex(this.idx);
      this._pushTransitionState();
      const shown = this.frame || this.timeline.frames[this.idx];
      this._status({
        phase: shown.phase,
        hash: shown.hash,
        mode: shown.mode,
        substance: shown.substance,
        backend: this.backend,
      });
    }

    _materializeNeutral(base) {
      const neut = JSON.parse(JSON.stringify(base));
      neut.neutral_view = true;
      neut.engines = Object.fromEntries(
        Object.keys(neut.engines || {}).map((k) => [k, k === 'neutral_view' ? 1 : 0])
      );
      if (!neut.engines.neutral_view) neut.engines.neutral_view = 1;
      Object.keys(neut.parameters || {}).forEach((k) => {
        neut.parameters[k] = k === 'stability' ? 0.98 : 0.05;
      });
      neut.parameters.flash_energy = 0;
      neut.phase = 'neutral';
      return neut;
    }

    _applyFrameForIndex(i) {
      if (!this.timeline || !this.timeline.frames) return;
      this.idx = Math.max(0, Math.min(this.timeline.frames.length - 1, i | 0));
      if (this.liveModulators && this._hasActiveModulators() && this.loadContext && !this.neutralOn) {
        this._scheduleLiveRematerialize();
        return;
      }
      const base = this.timeline.frames[this.idx];
      if (!base) return;
      const frame = this.neutralOn ? this._materializeNeutral(base) : base;
      this.frame = frame;
      this.setFrame(frame);
    }

    _hasActiveModulators() {
      const m = this.modulators || {};
      if (m.solar != null && Number.isFinite(Number(m.solar))) return true;
      return ['camera', 'motion', 'midi', 'audio', 'haptics', 'image'].some(
        (k) => Number(m[k] || 0) > 0.02,
      );
    }

    _scheduleLiveRematerialize() {
      if (!this.loadContext || !this.timeline) return;
      const now = performance.now();
      const wait = Math.max(0, 320 - (now - (this._lastLiveModMs || 0)));
      if (this._liveModTimer) clearTimeout(this._liveModTimer);
      this._liveModTimer = setTimeout(() => {
        this._liveRematerialize();
      }, wait);
    }

    async _liveRematerialize() {
      if (!this.loadContext || !this.timeline || !this.timeline.frames) return;
      if (this._liveAbort) this._liveAbort.abort();
      const ac = new AbortController();
      this._liveAbort = ac;
      this._lastLiveModMs = performance.now();
      const base = this.timeline.frames[this.idx] || this.timeline.frames[0];
      const phase_t =
        base && base.phase_t != null
          ? Number(base.phase_t)
          : this.idx / Math.max(1, this.timeline.frames.length - 1);
      const body = {
        ...this.loadContext,
        phase_t,
        modulators: this.modulators,
        neutral_view: !!this.neutralOn,
      };
      if (this.imageHints) body.image_hints = this.imageHints;
      try {
        const res = await fetch('/api/v1/visualize/parameter-timeline', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: ac.signal,
        });
        if (!res.ok || ac.signal.aborted) return;
        const data = await res.json();
        if (ac.signal.aborted) return;
        const frame = data.frame || (data.frames && data.frames[0]);
        if (!frame) return;
        const applied = this.neutralOn ? this._materializeNeutral(frame) : frame;
        this.frame = applied;
        this.setFrame(applied);
        this._status({
          phase: applied.phase,
          hash: applied.hash,
          mode: applied.mode,
          substance: applied.substance,
          backend: this.backend,
        });
      } catch (err) {
        if (err && err.name === 'AbortError') return;
      }
    }

    play() {
      this.playing = true;
      if (this.backend === 'webgl' && this.webgl) this.webgl.start();
      else this.renderer.start();
      if (this._phaseTimer) clearInterval(this._phaseTimer);
      if (this.phaseAdvance) this._tickPhases();
    }

    pause() {
      this.playing = false;
      this.renderer.stop();
      if (this.webgl) this.webgl.stop();
      if (this._phaseTimer) clearInterval(this._phaseTimer);
    }

    neutral(on) {
      if (!this.timeline || !this.timeline.frames || !this.timeline.frames.length) return;
      const next = !!on;
      if (next !== this.neutralOn) {
        this.beginTransition(next ? 'neutral_in' : 'neutral_out');
      }
      this.neutralOn = next;
      this._applyFrameForIndex(this.idx);
      this._pushTransitionState();
    }

    setModulators(mods) {
      this.modulators = {
        camera: Number(mods.camera || 0),
        motion: Number(mods.motion || 0),
        midi: Number(mods.midi || 0),
        audio: Number(mods.audio || 0),
        haptics: Number(mods.haptics || 0),
        image: Number(mods.image || 0),
      };
      if (mods && mods.solar != null && Number.isFinite(Number(mods.solar))) {
        this.modulators.solar = Math.max(0, Math.min(1, Number(mods.solar)));
      }
      if (this.liveModulators && this.timeline && this._hasActiveModulators()) {
        this._scheduleLiveRematerialize();
      }
    }

    setImageHints(hints) {
      this.imageHints = hints && typeof hints === 'object' ? { ...hints } : null;
      if (this.liveModulators && this.timeline && this._hasActiveModulators()) {
        this._scheduleLiveRematerialize();
      }
    }

    clearImageHints() {
      this.setImageHints(null);
    }

    // ===== I2 hold-and-compare =====
    pinFrame(frameOverride) {
      const cs = global.PsyFiViz && global.PsyFiViz.compareSurface;
      if (!cs) return null;
      const f = frameOverride || this.frame || (this.timeline && this.timeline.frames && this.timeline.frames[this.idx]);
      if (!f) return null;
      this.pinned = cs.makePinPacket(f, this.idx, this.timeline && this.timeline.timeline_hash);
      if (this.renderer && typeof this.renderer.setPinnedFrame === 'function') {
        this.renderer.setPinnedFrame(this.pinned.frame);
      }
      if (this.webgl && typeof this.webgl.setPinnedFrame === 'function') {
        this.webgl.setPinnedFrame(this.pinned.frame);
      }
      this._status({
        phase: f.phase,
        hash: f.hash,
        mode: f.mode,
        substance: f.substance,
        backend: this.backend,
        compare: this.compareMode,
      });
      return this.pinned;
    }

    clearPin() {
      this.pinned = null;
      if (this.renderer && typeof this.renderer.setPinnedFrame === 'function') {
        this.renderer.setPinnedFrame(null);
      }
      if (this.webgl && typeof this.webgl.setPinnedFrame === 'function') {
        this.webgl.setPinnedFrame(null);
      }
    }

    setCompareMode(mode) {
      const cs = global.PsyFiViz && global.PsyFiViz.compareSurface;
      this.compareMode = cs ? cs.normalizeMode(mode) : 'off';
      const state = { mode: this.compareMode, wipe: this.wipePosition, blinkHz: this.blinkHz };
      if (this.renderer && typeof this.renderer.setCompareState === 'function') {
        this.renderer.setCompareState(state);
      }
      if (this.webgl && typeof this.webgl.setCompareState === 'function') {
        this.webgl.setCompareState(state);
      }
    }

    setWipePosition(t) {
      const cs = global.PsyFiViz && global.PsyFiViz.compareSurface;
      this.wipePosition = cs ? cs.clamp01(t) : Math.min(1, Math.max(0, Number(t) || 0));
      const state = { mode: this.compareMode, wipe: this.wipePosition, blinkHz: this.blinkHz };
      if (this.renderer && typeof this.renderer.setCompareState === 'function') {
        this.renderer.setCompareState(state);
      }
      if (this.webgl && typeof this.webgl.setCompareState === 'function') {
        this.webgl.setCompareState(state);
      }
    }

    setBlinkHz(hz) {
      const n = Number(hz);
      this.blinkHz = Number.isFinite(n) && n > 0 ? n : 2;
      const state = { mode: this.compareMode, wipe: this.wipePosition, blinkHz: this.blinkHz };
      if (this.renderer && typeof this.renderer.setCompareState === 'function') {
        this.renderer.setCompareState(state);
      }
      if (this.webgl && typeof this.webgl.setCompareState === 'function') {
        this.webgl.setCompareState(state);
      }
    }

    getComparisonPacket() {
      const cs = global.PsyFiViz && global.PsyFiViz.compareSurface;
      if (!cs) return null;
      const live = this.frame || (this.timeline && this.timeline.frames && this.timeline.frames[this.idx]);
      return cs.makeComparisonPacket(this.pinned, live, this.compareMode, this.wipePosition, this.blinkHz);
    }

    exportTimelineJson() {
      if (!this.timeline) throw new Error('No timeline loaded');
      const blob = new Blob([JSON.stringify(this.timeline, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `psyfi-timeline-${this.timeline.timeline_hash || 'export'}.json`;
      a.click();
      URL.revokeObjectURL(url);
    }

    exportViewportPng() {
      const target =
        this.backend === 'webgl' && this.glCanvas && !this.glCanvas.hidden
          ? this.glCanvas
          : this.canvas;
      const url = target.toDataURL('image/png');
      const a = document.createElement('a');
      a.href = url;
      a.download = `psyfi-field-${Date.now()}.png`;
      a.click();
    }

    async loadFieldBridge(simPayload) {
      const res = await fetch('/api/v1/visualize/field-frame', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(simPayload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || res.statusText);
      }
      this.fieldBridge = await res.json();
      return this.fieldBridge;
    }

    _tickPhases() {
      if (!this.playing || !this.phaseAdvance || !this.timeline || !this.timeline.frames) return;
      const frames = this.timeline.frames;
      const speed = this.phaseSpeed > 0 ? this.phaseSpeed : 1;
      const intervalMs = Math.max(120, Math.round((this._phaseBaseMs || 900) / speed));
      this._phaseTimer = setInterval(() => {
        if (!this.playing || !this.phaseAdvance) {
          clearInterval(this._phaseTimer);
          return;
        }
        this.idx = (this.idx + 1) % frames.length;
        this._applyFrameForIndex(this.idx);
        if (typeof this.onPhaseIndex === 'function') this.onPhaseIndex(this.idx, frames.length);
      }, intervalMs);
    }

    _status(info) {
      if (!this.statusEl) return;
      const lod =
        info.lod ||
        (this.backend === 'webgl' && this.webgl && this.webgl._lastLodName) ||
        (this.loadContext && this.loadContext.quality_tier) ||
        '';
      const compareBit =
        this.compareMode && this.compareMode !== 'off' && this.pinned
          ? `compare ${this.compareMode}`
          : '';
      const pinBit = this.pinned && this.pinned.hash ? `pin ${String(this.pinned.hash).slice(0, 8)}` : '';
      this.statusEl.textContent = [
        info.substance || '',
        info.mode || '',
        info.phase || '',
        info.backend || this.backend,
        lod ? `lod ${lod}` : '',
        info.hash ? `hash ${info.hash}` : '',
        pinBit,
        compareBit,
      ]
        .filter(Boolean)
        .join(' · ');
    }

    _provenance(data) {
      if (!this.provenanceEl) return;
      const frame = (data.frames && data.frames[0]) || data.frame || {};
      const tier = frame.quality_tier || (this.loadContext && this.loadContext.quality_tier) || 'balanced';
      const line = (label, value) => {
        const div = document.createElement('div');
        const strong = document.createElement('strong');
        strong.textContent = label;
        div.append(strong, document.createTextNode(` ${value}`));
        return div;
      };
      const disclaimer = document.createElement('div');
      disclaimer.className = 'muted';
      disclaimer.textContent =
        'Modeled phenomenology for research/visualization only. Not medical advice.';
      this.provenanceEl.replaceChildren(
        line('Timeline', data.timeline_hash || frame.hash || '—'),
        line('Seed', data.seed ?? frame.master_seed ?? '—'),
        line('Experience', data.experience_id || frame.experience_id || '—'),
        line('Backend', this.backend),
        line('Quality', tier),
        line('Authority', 'parameters INFERRED · motifs INFERRED · sources OBSERVED'),
        disclaimer,
      );
    }
  }

  global.PsyFiViz = global.PsyFiViz || {};
  global.PsyFiViz.ExperiencePlayer = ExperiencePlayer;
  global.PsyFiViz.ExperienceRenderer = ExperienceRenderer;
})(window);
