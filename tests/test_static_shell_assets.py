"""Smoke checks that Phase 2 static shell assets remain wired together."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "psyfi_api" / "static"
TEMPLATE = ROOT / "psyfi_api" / "templates" / "index.html"


def test_renderer_and_worker_assets_exist() -> None:
    assert (STATIC / "renderer.js").exists()
    assert (STATIC / "render_worker.js").exists()
    assert (STATIC / "app.js").exists()
    assert (STATIC / "sw.js").exists()


def test_template_wires_cancel_recovery_and_renderer() -> None:
    html = TEMPLATE.read_text(encoding="utf-8")
    assert 'id="cancelButton"' in html
    assert 'id="recoveryBanner"' in html
    assert 'id="fieldCanvasGPU"' in html
    assert 'id="installButton"' in html
    assert 'id="importSessionInput"' in html
    assert 'id="loadingStatus"' in html
    assert 'id="experienceCanvasGL"' in html
    assert 'id="phaseScrub"' in html
    assert 'id="phaseAdvanceChk"' in html
    assert 'id="phaseSpeedSelect"' in html
    assert 'id="qualityTierSelect"' in html
    assert 'id="openGpuLabBtn"' in html
    assert 'id="gpuLabNavLink"' in html
    assert 'id="gridPresetSelect"' in html
    assert 'data-tip=' in html
    assert 'id="sensorEnableSelect"' in html
    assert 'launch-scan-drawer' in html
    assert 'id="sensorEnableBtn"' in html
    assert 'id="sourcePlaneChk"' in html
    assert 'id="sourcePlaneMix"' in html
    assert 'id="bridgeSimBtn"' in html
    assert 'id="imageSeedSuggestBtn"' in html
    assert 'id="imageSeedJourneyBtn"' in html
    assert 'id="imageSeedRecommend"' in html
    assert 'id="imageSeedAltSelect"' in html
    assert 'id="copyT2vPromptBtn"' in html
    assert 'id="modAudio"' in html
    assert 'id="modHaptics"' in html
    assert 'id="enableAudioBtn"' in html
    assert 'id="enableHapticsBtn"' in html
    assert 'id="enableAvailableSensorsBtn"' in html
    assert 'id="sensorChipRow"' not in html
    assert 'id="launchSplash"' in html
    assert 'id="launchEnterBtn"' in html
    assert 'id="loadingDismissBtn"' in html
    assert 'launch-pending' in html
    assert 'href="/gpu/"' in html
    assert 'src="/static/renderer.js"' in html
    assert 'src="/static/viz/instrumentMap.js"' in html
    assert 'src="/static/viz/compareSurface.js"' in html
    assert 'src="/static/viz/transitionSurface.js"' in html
    assert 'src="/static/viz/parameterFieldWebGL.js"' in html
    assert 'src="/static/viz/deviceSensors.js"' in html
    assert 'src="/static/viz/launchSplash.js"' in html
    assert 'src="/static/app.js"' in html
    assert 'id="pinFrameBtn"' in html
    assert 'id="compareModeSelect"' in html
    assert 'id="archiveCompareBtn"' in html
    assert 'id="compareList"' in html
    assert ">Split</option>" in html or 'value="split"' in html
    assert 'id="anchorLatitude"' in html
    assert 'id="anchorSolarElevation"' in html
    assert 'id="anchorSolarModulator"' in html
    assert 'data-stations="21"' in html
    assert 'id="lockSeedBtn"' in html
    assert 'id="seedLockHint"' in html
    assert 'id="runPlannerBtn"' in html
    assert 'id="saveJourneyBtn"' in html
    assert 'id="journeyList"' in html
    assert 'data-map-mode="instrument"' in html
    assert 'id="intensityMapHint"' in html
    # Root-scoped SW registration (not /static/sw.js — that cannot control `/`).
    assert "serviceWorker.register('/sw.js'" in html
    assert "scope: '/'" in html


def test_service_worker_precaches_renderer_assets() -> None:
    sw = (STATIC / "sw.js").read_text(encoding="utf-8")
    assert "psyfi-shell-v43" in sw
    assert "/static/viz/transitionSurface.js" in sw
    assert ".woff2" in sw
    assert "/assets/icons/pf-icon-reset-24.svg" in sw
    assert "/assets/icons/pf-icon-valence-meter-24.svg" in sw
    assert "/static/renderer.js" in sw
    assert "/static/render_worker.js" in sw
    assert "/static/viz/math.js" in sw
    assert "/static/viz/instrumentMap.js" in sw
    assert "/static/viz/compareSurface.js" in sw
    assert "/static/viz/transitionSurface.js" in sw
    assert "/static/viz/engines/index.js" in sw
    assert "/static/viz/parameterFieldWebGL.js" in sw
    assert "/static/viz/deviceSensors.js" in sw
    assert "/static/viz/launchSplash.js" in sw
    assert "/static/viz/experiencePlayer.js" in sw
    assert "/static/icon-192.png" in sw
    assert "/simulate" in sw  # still treated as network-only path matcher
    assert "isGpuRoute" in sw
    assert "/gpu/" in sw
    # GPU dist must not be shell-precached (separate route decision).
    assert "/gpu/" not in sw.split("SHELL_URLS")[1].split("];")[0]


def test_pwa_gpu_route_decision_documented() -> None:
    doc = (ROOT / "docs" / "PWA_GPU_ROUTE.md").read_text(encoding="utf-8")
    assert "separate route" in doc.lower()
    assert "/gpu/" in doc
    assert "not embed" in doc.lower() or "Do **not** embed" in doc
    manifest = (STATIC / "manifest.json").read_text(encoding="utf-8")
    assert '"url": "/gpu/"' in manifest
    assert '"start_url": "/"' in manifest
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert 'href="/gpu/"' in app_js
    assert "GPU Lab route" in app_js


def test_homepage_social_preview_uses_the_launch_image() -> None:
    html = TEMPLATE.read_text(encoding="utf-8")
    image = "https://psy-fi.space/static/images/psyfi-hero.jpg"
    assert 'property="og:type" content="website"' in html
    assert 'property="og:url" content="https://psy-fi.space/"' in html
    # The card reuses the page title, so a later title change cannot leave the card behind.
    title = html.split("<title>", 1)[1].split("</title>", 1)[0]
    assert f'property="og:title" content="{title}"' in html
    assert f'name="twitter:title" content="{title}"' in html
    assert 'property="og:description" content="Modular consciousness field simulation engine with ABX-Core v1.3"' in html
    assert f'property="og:image" content="{image}"' in html
    assert 'property="og:image:width" content="1400"' in html
    assert 'property="og:image:height" content="933"' in html
    assert 'name="twitter:card" content="summary_large_image"' in html
    assert f'name="twitter:image" content="{image}"' in html
    assert 'rel="canonical" href="https://psy-fi.space/"' in html
    hero = STATIC / "images" / "psyfi-hero.jpg"
    assert hero.exists()
    # JPEG start, and the declared card size matches the file.
    assert hero.read_bytes()[:3] == b"\xff\xd8\xff"
    from PIL import Image

    with Image.open(hero) as im:
        assert im.size == (1400, 933)


def test_pwa_png_icons_exist() -> None:
    assert (STATIC / "icon-192.png").exists()
    assert (STATIC / "icon-512.png").exists()
    assert (STATIC / "apple-touch-icon.png").exists()
    assert (STATIC / "icon-192.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    # Solid cyan placeholders are forbidden — brand mark must have structure.
    assert (STATIC / "icon-192.png").stat().st_size > 2048
    assert (STATIC / "fonts" / "fonts.css").exists()
    html = TEMPLATE.read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in html
    assert "/static/fonts/fonts.css" in html
    assert "/static/apple-touch-icon.png" in html
    assert 'class="sigil-mark"' in html
    assert "pf-icon-reset" in html
    assert "experience-advanced" in html
    assert 'modulator-panel" open' not in html
    assert ">Icons</a>" not in html
    style = (STATIC / "style.css").read_text(encoding="utf-8")
    assert "design-system: design.md" in style
    assert "tabular-nums" in style
    assert ".pf-icon" in style
    assert "max-width: 1280px" in style
    assert "launch-panel-in" in style
    assert "field-pulse" in style
    assert "launch-sigil" in html
    assert "/static/images/psyfi-hero.jpg" in html
    assert "launch-caption" in html
    assert "nav-more" in html
    assert 'rel="preload"' in html
    assert "V8mDoQDjQSkFtoMM3T6r8E7mPbF4Cw.woff2" in html
    assert (STATIC / "images" / "psyfi-hero.jpg").exists()
    assert "pf-icon-valence" in html
    assert "syncFieldStatusLive" in (STATIC / "app.js").read_text(encoding="utf-8")
    gpu_index = ROOT / "packages" / "psyfi-gpu-renderer" / "index.html"
    assert "/static/fonts/fonts.css" in gpu_index.read_text(encoding="utf-8")
    gpu_main = ROOT / "packages" / "psyfi-gpu-renderer" / "src" / "main.tsx"
    assert "styles/chrome.css" in gpu_main.read_text(encoding="utf-8")
    # Live Experience leads Workbench (field before sim form).
    assert html.index('id="experiencePanel"') < html.index('id="workspace"')


def test_app_uses_abort_controller_and_worker_renderer() -> None:
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "AbortController" in app_js
    assert "PsyFiRenderer" in app_js
    assert "const API_V1 = '/api/v1'" in app_js
    assert "beforeinstallprompt" in app_js
    assert "importSessionInput" in app_js
    assert "setSourcePlane" in app_js
    assert "lastBridgeField" in app_js
    assert "modAudio" in app_js
    assert "modHaptics" in app_js
    assert "enableAudioBtn" in app_js
    assert "enableHapticsBtn" in app_js
    assert "DeviceSensorHub" in app_js
    assert "enableAvailableSensorsBtn" in app_js
    assert "probeSensorCapabilities" in app_js
    assert "loadingDismissBtn" in app_js
    assert "timed out" in app_js
    style_css = (STATIC / "style.css").read_text(encoding="utf-8")
    assert "[hidden]" in style_css
    assert "loading-overlay[hidden]" in style_css
    assert "launch-splash" in style_css
    launch_js = (STATIC / "viz" / "launchSplash.js").read_text(encoding="utf-8")
    assert "probeHealth" in launch_js
    assert "buildChecks" in launch_js
    assert "runScan" in launch_js
    assert "psyfi:launch-ready" in launch_js
    assert "id: 'monitor'" in launch_js
    assert "id: 'gpu'" in launch_js
    assert "applyFieldResolution" in launch_js
    html = TEMPLATE.read_text(encoding="utf-8")
    assert "launchResolutionSelect" in html
    assert 'id="resolutionSelect"' in html
    assert 'id="viewportResolutionSelect"' in html
    renderer_js = (STATIC / "renderer.js").read_text(encoding="utf-8")
    assert "render_worker.js" in renderer_js
    assert "navigator.gpu" in renderer_js
    player_js = (STATIC / "viz" / "experiencePlayer.js").read_text(encoding="utf-8")
    assert "setSourcePlane" in player_js
    assert "sampleSourcePlane" in player_js
    assert "packSourceField" in player_js
    assert "audio:" in player_js
    assert "haptics:" in player_js
    assert "neutralOn" in player_js
    assert "_materializeNeutral" in player_js
    assert "_liveRematerialize" in player_js
    assert "loadContext" in player_js
    sensors_js = (STATIC / "viz" / "deviceSensors.js").read_text(encoding="utf-8")
    assert "probeSensorCapabilities" in sensors_js
    assert "probeMonitor" in sensors_js
    assert "probeGpu" in sensors_js
    assert "enableAvailable" in sensors_js
    assert "DeviceOrientation" in sensors_js or "deviceorientation" in sensors_js
    assert "requestMIDIAccess" in sensors_js
    assert "getGamepads" in sensors_js
    player_res = (STATIC / "viz" / "experiencePlayer.js").read_text(encoding="utf-8")
    assert "setViewportResolution" in player_res
    assert "viewportResolution" in player_res
    assert "setPhaseAdvance" in player_res
    assert "setPhaseSpeed" in player_res
    assert "phaseAdvance" in player_res
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "resolutionSelect" in app_js
    assert "viewportResolutionSelect" in app_js
    assert "phaseAdvanceChk" in app_js
    assert "phaseSpeedSelect" in app_js
    assert "PsyFiTips" in app_js
    assert "setButtonLabel" in app_js
    assert "getExperienceIntensity" in app_js
    assert "setExperienceIntensity" in app_js
    assert "pinFrameBtn" in app_js
    assert "compareModeSelect" in app_js
    assert "NEUTRAL_EXIT_ARM_MS" in app_js
    assert "EXPORT_JOURNEY_ARM_MS" in app_js
    assert "SEED_UNLOCK_ARM_MS" in app_js
    assert "tryWriteSeed" in app_js
    assert "lastComparisonId" in app_js
    assert "getComparisonRecord" in app_js
    assert "instrumentMap" in app_js
    assert "nextMapMode" in (STATIC / "viz" / "instrumentMap.js").read_text(encoding="utf-8")
    assert "readSolarDayFactor" in app_js
    assert "archiveCompareBtn" in app_js
    assert "COMPARE_STORE" in app_js
    assert "readSpatiotemporalAnchors" in app_js
    assert "appendAnchorsToFormData" in app_js
    assert "JOURNEY_STORE" in app_js
    assert "saveJourneyBtn" in app_js
    assert "runPlannerBtn" in app_js
    assert "makeArchiveRecord" in (STATIC / "viz" / "compareSurface.js").read_text(encoding="utf-8")
    assert "compositeSplit" in (STATIC / "viz" / "compareSurface.js").read_text(encoding="utf-8")
    assert (STATIC / "viz" / "instrumentMap.js").exists()
    assert (STATIC / "viz" / "compareSurface.js").exists()
    assert (STATIC / "viz" / "transitionSurface.js").exists()
    transition_js = (STATIC / "viz" / "transitionSurface.js").read_text(encoding="utf-8")
    assert "compositeCrossfade" in transition_js
    assert "makeTransitionState" in transition_js
    player_compare = (STATIC / "viz" / "experiencePlayer.js").read_text(encoding="utf-8")
    assert "pinFrame" in player_compare
    assert "setCompareMode" in player_compare
    assert "beginTransition" in player_compare
    assert "setTransitionState" in player_compare
    assert "compositeSplit" in player_compare or 'compareMode === \'split\'' in player_compare
    webgl_js = (STATIC / "viz" / "parameterFieldWebGL.js").read_text(encoding="utf-8")
    assert "setPinnedFrame" in webgl_js
    assert "setCompareState" in webgl_js
    assert "setTransitionState" in webgl_js
    assert "u_xfadeMix" in webgl_js
    assert "u_compareMode" in webgl_js
    assert "Dual-viewport split" in webgl_js or "plateUv" in webgl_js
    assert "_ensurePinTarget" in webgl_js
    assert "_pendingTransitionKind" in player_compare
    assert "aria-describedby" in app_js
    assert "Monitor / display" in app_js
    assert "GPU adapter" in app_js
    gl_js = (STATIC / "viz" / "parameterFieldWebGL.js").read_text(encoding="utf-8")
    assert "u_sourceMix" in gl_js
    assert "u_source" in gl_js
    assert "u_safetyAtten" in gl_js
    assert "measureAtten" in gl_js
    assert "u_chroma" in gl_js
    assert "u_edge" in gl_js
    assert "u_trail" in gl_js
    assert "u_lod" in gl_js
    assert "fractalFold" in gl_js
    assert "Cheap chroma" in gl_js
    math_js = (STATIC / "viz" / "math.js").read_text(encoding="utf-8")
    assert "fractalFold" in math_js
    assert "resolveRenderLod" in math_js
    eng_js = (STATIC / "viz" / "engines" / "index.js").read_text(encoding="utf-8")
    assert "fractalFold" in eng_js
    assert "orbit" in eng_js
    assert "SKIP" in eng_js or "0.05" in eng_js
    player_lod = (STATIC / "viz" / "experiencePlayer.js").read_text(encoding="utf-8")
    assert "resolveRenderLod" in player_lod
    assert "lodDrop" in player_lod
    prefer_html = TEMPLATE.read_text(encoding="utf-8")
    assert 'id="preferWebGLChk" checked' in prefer_html
    assert 'id="qualityTierSelect"' in prefer_html
    app_lod = (STATIC / "app.js").read_text(encoding="utf-8")
    assert "qualityTierSelect" in app_lod
    assert "buildGpuLabUrl" in app_lod
    assert "mapShellQualityToGpuTier" in app_lod
    safety_js = (STATIC / "viz" / "safetyPass.js").read_text(encoding="utf-8")
    assert "measureAtten" in safety_js
