// PsyFi web shell — progressive enhancement on the existing FastAPI static UI.

const SESSION_STORAGE_KEY = 'psyfi.session.v1.last';
const RECOVERY_DISMISS_KEY = 'psyfi.session.v1.recovery_dismissed';
const DB_NAME = 'psyfi-sessions';
const DB_VERSION = 3;
const STORE_NAME = 'history';
const COMPARE_STORE = 'comparisons';
const JOURNEY_STORE = 'journeys';
const API_V1 = '/api/v1';

async function openPsyfiDb() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        request.onupgradeneeded = () => {
            const db = request.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' });
                store.createIndex('updated_at', 'updated_at');
            }
            if (!db.objectStoreNames.contains(COMPARE_STORE)) {
                const store = db.createObjectStore(COMPARE_STORE, { keyPath: 'id' });
                store.createIndex('updated_at', 'updated_at');
            }
            if (!db.objectStoreNames.contains(JOURNEY_STORE)) {
                const store = db.createObjectStore(JOURNEY_STORE, { keyPath: 'id' });
                store.createIndex('updated_at', 'updated_at');
            }
        };
        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

async function saveComparisonRecord(record) {
    if (!record?.id) throw new Error('No comparison record to save');
    const db = await openPsyfiDb();
    await new Promise((resolve, reject) => {
        const tx = db.transaction(COMPARE_STORE, 'readwrite');
        tx.objectStore(COMPARE_STORE).put(record);
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
    });
    db.close();
    return record;
}

async function listComparisonRecords() {
    try {
        const db = await openPsyfiDb();
        const records = await new Promise((resolve, reject) => {
            const tx = db.transaction(COMPARE_STORE, 'readonly');
            const request = tx.objectStore(COMPARE_STORE).getAll();
            request.onsuccess = () => resolve(request.result || []);
            request.onerror = () => reject(request.error);
        });
        db.close();
        return records.sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
    } catch (error) {
        console.warn('[PsyFi] IndexedDB comparisons unavailable:', error);
        return [];
    }
}

async function getComparisonRecord(id) {
    if (!id) return null;
    try {
        const db = await openPsyfiDb();
        const record = await new Promise((resolve, reject) => {
            const tx = db.transaction(COMPARE_STORE, 'readonly');
            const request = tx.objectStore(COMPARE_STORE).get(id);
            request.onsuccess = () => resolve(request.result || null);
            request.onerror = () => reject(request.error);
        });
        db.close();
        return record;
    } catch (error) {
        console.warn('[PsyFi] IndexedDB comparison get failed:', error);
        return null;
    }
}

async function clearComparisonRecords() {
    const db = await openPsyfiDb();
    await new Promise((resolve, reject) => {
        const tx = db.transaction(COMPARE_STORE, 'readwrite');
        tx.objectStore(COMPARE_STORE).clear();
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
    });
    db.close();
}

async function saveJourneyRecord(record) {
    if (!record?.id) throw new Error('No journey record to save');
    const db = await openPsyfiDb();
    await new Promise((resolve, reject) => {
        const tx = db.transaction(JOURNEY_STORE, 'readwrite');
        tx.objectStore(JOURNEY_STORE).put(record);
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
    });
    db.close();
    return record;
}

async function listJourneyRecords() {
    try {
        const db = await openPsyfiDb();
        const records = await new Promise((resolve, reject) => {
            const tx = db.transaction(JOURNEY_STORE, 'readonly');
            const request = tx.objectStore(JOURNEY_STORE).getAll();
            request.onsuccess = () => resolve(request.result || []);
            request.onerror = () => reject(request.error);
        });
        db.close();
        return records.sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
    } catch (error) {
        console.warn('[PsyFi] IndexedDB journeys unavailable:', error);
        return [];
    }
}

async function clearJourneyRecords() {
    const db = await openPsyfiDb();
    await new Promise((resolve, reject) => {
        const tx = db.transaction(JOURNEY_STORE, 'readwrite');
        tx.objectStore(JOURNEY_STORE).clear();
        tx.oncomplete = () => resolve();
        tx.onerror = () => reject(tx.error);
    });
    db.close();
}

window.PsyFiTips = {
    bind(root) {
        const host = root || document;
        let tip = document.getElementById('pfTip');
        if (!tip) {
            tip = document.createElement('div');
            tip.id = 'pfTip';
            tip.className = 'pf-tip';
            tip.setAttribute('role', 'tooltip');
            tip.setAttribute('aria-hidden', 'true');
            document.body.appendChild(tip);
        }
        let showTimer = 0;
        let hideTimer = 0;
        let active = null;
        const place = (el) => {
            const r = el.getBoundingClientRect();
            const pad = 8;
            tip.style.left = `${Math.min(window.innerWidth - tip.offsetWidth - pad, Math.max(pad, r.left))}px`;
            tip.style.top = `${Math.min(window.innerHeight - tip.offsetHeight - pad, r.bottom + 6)}px`;
        };
        const show = (el, immediate) => {
            const text = el.getAttribute('data-tip');
            if (!text) return;
            active = el;
            clearTimeout(hideTimer);
            const run = () => {
                if (active !== el) return;
                tip.textContent = text;
                tip.dataset.open = 'true';
                tip.setAttribute('aria-hidden', 'false');
                el.setAttribute('aria-describedby', 'pfTip');
                place(el);
            };
            if (immediate) run();
            else {
                clearTimeout(showTimer);
                showTimer = setTimeout(run, 900);
            }
        };
        const hide = (el) => {
            clearTimeout(showTimer);
            hideTimer = setTimeout(() => {
                if (el && el.getAttribute('aria-describedby') === 'pfTip') {
                    el.removeAttribute('aria-describedby');
                }
                tip.dataset.open = 'false';
                tip.setAttribute('aria-hidden', 'true');
                active = null;
            }, 80);
        };
        const targets = [];
        host.querySelectorAll('[data-tip]').forEach((el) => {
            // Prefer the focusable control inside a labeled tip host.
            const control = el.matches('input,select,button,textarea,a,summary')
                ? el
                : el.querySelector('input,select,button,textarea,a,summary') || el;
            if (control.dataset.tipBound === '1') return;
            control.dataset.tipBound = '1';
            if (!control.getAttribute('data-tip') && el.getAttribute('data-tip')) {
                control.setAttribute('data-tip', el.getAttribute('data-tip'));
            }
            targets.push(control);
        });
        targets.forEach((el) => {
            el.addEventListener('pointerenter', () => show(el, false));
            el.addEventListener('pointerleave', () => hide(el));
            el.addEventListener('focus', () => show(el, true));
            el.addEventListener('blur', () => hide(el));
        });
    },
};

function setButtonLabel(btn, label) {
    if (!btn) return;
    const textSpan = btn.querySelector('span:not(.pf-icon)');
    if (textSpan) textSpan.textContent = label;
    else btn.textContent = label;
}

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('simulationForm');
    const runButton = document.getElementById('runButton');
    const cancelButton = document.getElementById('cancelButton');
    const installButton = document.getElementById('installButton');
    const loadingOverlay = document.getElementById('loadingOverlay');
    const loadingStatus = document.getElementById('loadingStatus');
    const errorPanel = document.getElementById('errorPanel');
    const networkStatus = document.getElementById('networkStatus');
    const substanceSelect = document.getElementById('substancePreset');
    const substanceGrid = document.getElementById('substanceGrid');
    const presetEmpty = document.getElementById('presetEmpty');
    const resultsEmpty = document.getElementById('resultsEmpty');
    const resultsContent = document.getElementById('resultsContent');
    const historyList = document.getElementById('historyList');
    const historyEmpty = document.getElementById('historyEmpty');
    const canvas2d = document.getElementById('fieldCanvas');
    const canvasGpu = document.getElementById('fieldCanvasGPU');
    const vizBackend = document.getElementById('vizBackend');
    const recoveryBanner = document.getElementById('recoveryBanner');
    const preferWebGPU = document.getElementById('preferWebGPU');
    const importSessionInput = document.getElementById('importSessionInput');

    let lastPayload = null;
    let activeAbort = null;
    let activeJobId = null;
    let cancelRequested = false;
    let recoveryRecord = null;
    let deferredInstallPrompt = null;

    const gridPresets = {
        quick: { width: 32, height: 32, steps: 10, resolution: '32x32' },
        standard: { width: 64, height: 64, steps: 20, resolution: '64x64' },
        detailed: { width: 128, height: 128, steps: 50, resolution: '128x128' },
        deep: { width: 256, height: 256, steps: 100, resolution: '256x256' },
    };
    const resolutionSelect = document.getElementById('resolutionSelect');
    const gridPresetSelect = document.getElementById('gridPresetSelect');
    const widthInput = document.getElementById('width');
    const heightInput = document.getElementById('height');
    const customSizeGroup = document.getElementById('customSizeGroup');
    const customHeightGroup = document.getElementById('customHeightGroup');

    function syncCustomSizeVisibility() {
        const custom = resolutionSelect && resolutionSelect.value === 'custom';
        if (customSizeGroup) customSizeGroup.hidden = !custom;
        if (customHeightGroup) customHeightGroup.hidden = !custom;
    }

    function syncResolutionSelectFromInputs() {
        if (!resolutionSelect || !widthInput || !heightInput) return;
        const key = `${widthInput.value}x${heightInput.value}`;
        const known = ['32x32', '64x64', '128x128', '256x256', '512x512'];
        resolutionSelect.value = known.includes(key) ? key : 'custom';
        if (gridPresetSelect) {
            const byRes = {
                '32x32': 'quick',
                '64x64': 'standard',
                '128x128': 'detailed',
                '256x256': 'deep',
            };
            gridPresetSelect.value = byRes[resolutionSelect.value] || 'custom';
        }
        syncCustomSizeVisibility();
    }

    function applyResolutionSelection(value, { syncSteps } = { syncSteps: true }) {
        if (window.PsyFiViz && typeof window.PsyFiViz.applyFieldResolution === 'function' && value !== 'custom') {
            window.PsyFiViz.applyFieldResolution(value, { syncSteps });
            syncCustomSizeVisibility();
            return;
        }
        const map = {
            '32x32': gridPresets.quick,
            '64x64': gridPresets.standard,
            '128x128': gridPresets.detailed,
            '256x256': gridPresets.deep,
            '512x512': { width: 512, height: 512, steps: 100 },
        };
        const preset = map[value];
        if (!preset) {
            syncCustomSizeVisibility();
            return;
        }
        if (widthInput) widthInput.value = String(preset.width);
        if (heightInput) heightInput.value = String(preset.height);
        if (syncSteps) {
            const stepsEl = document.getElementById('steps');
            if (stepsEl) stepsEl.value = String(preset.steps);
        }
        if (resolutionSelect) resolutionSelect.value = value;
        syncCustomSizeVisibility();
    }

    const bindTooltips = (root) => window.PsyFiTips.bind(root);

    function setHidden(el, hidden) {
        if (!el) return;
        el.hidden = hidden;
    }

    let loadingWatchdog = 0;

    function showLoading(show, statusText) {
        setHidden(loadingOverlay, !show);
        if (loadingOverlay) {
            loadingOverlay.setAttribute('aria-hidden', show ? 'false' : 'true');
        }
        runButton.disabled = show;
        if (cancelButton) {
            setHidden(cancelButton, !show);
            cancelButton.disabled = !show;
        }
        const dismissBtn = document.getElementById('loadingDismissBtn');
        if (dismissBtn) setHidden(dismissBtn, !show);
        if (loadingStatus && statusText) {
            loadingStatus.textContent = statusText;
        } else if (loadingStatus && show) {
            loadingStatus.textContent = 'Computing consciousness field…';
        }
        if (loadingWatchdog) {
            clearTimeout(loadingWatchdog);
            loadingWatchdog = 0;
        }
        // Never leave the overlay stuck if a job poll hangs.
        if (show) {
            loadingWatchdog = setTimeout(() => {
                showLoading(false);
                showError('Simulation timed out. Dismissed the loading overlay — try a smaller grid or fewer steps.');
                cancelRequested = true;
                if (activeJobId) {
                    fetch(`${API_V1}/jobs/${activeJobId}`, { method: 'DELETE' }).catch(() => {});
                }
            }, 90000);
        }
    }

    document.getElementById('loadingDismissBtn')?.addEventListener('click', () => {
        cancelRequested = true;
        if (activeAbort) activeAbort.abort();
        if (activeJobId) {
            fetch(`${API_V1}/jobs/${activeJobId}`, { method: 'DELETE' }).catch(() => {});
        }
        showLoading(false);
        showError('Loading dismissed. No result was applied.');
    });

    function showError(message) {
        document.getElementById('errorMessage').textContent = message;
        setHidden(errorPanel, false);
    }

    function hideError() {
        setHidden(errorPanel, true);
    }

    function updateNetworkStatus() {
        if (!networkStatus) return;
        if (navigator.onLine) {
            networkStatus.dataset.state = 'online';
            networkStatus.textContent = 'Online — server computation available';
        } else {
            networkStatus.dataset.state = 'offline';
            networkStatus.textContent = 'Offline — server simulations unavailable; history restore still works';
        }
    }

    window.addEventListener('online', updateNetworkStatus);
    window.addEventListener('offline', updateNetworkStatus);
    updateNetworkStatus();

    document.querySelectorAll('.preset-btn').forEach((button) => {
        button.addEventListener('click', () => {
            const preset = gridPresets[button.dataset.preset];
            if (!preset) return;
            document.getElementById('width').value = preset.width;
            document.getElementById('height').value = preset.height;
            document.getElementById('steps').value = preset.steps;
            document.querySelectorAll('.preset-btn').forEach((btn) => btn.classList.remove('active'));
            button.classList.add('active');
            if (resolutionSelect) resolutionSelect.value = preset.resolution || 'custom';
            if (gridPresetSelect) gridPresetSelect.value = button.dataset.preset;
            try {
                sessionStorage.setItem('psyfi.resolution.v1', preset.resolution || 'custom');
            } catch (_e) {
                /* ignore */
            }
            syncCustomSizeVisibility();
        });
    });

    gridPresetSelect?.addEventListener('change', () => {
        const key = gridPresetSelect.value;
        if (key === 'custom') {
            if (resolutionSelect) resolutionSelect.value = 'custom';
            syncCustomSizeVisibility();
            return;
        }
        const preset = gridPresets[key];
        if (!preset) return;
        document.querySelector(`.preset-btn[data-preset="${key}"]`)?.click();
        applyResolutionSelection(preset.resolution, { syncSteps: true });
        if (gridPresetSelect) gridPresetSelect.value = key;
    });

    resolutionSelect?.addEventListener('change', () => {
        if (resolutionSelect.value === 'custom') {
            if (gridPresetSelect) gridPresetSelect.value = 'custom';
            syncCustomSizeVisibility();
            return;
        }
        applyResolutionSelection(resolutionSelect.value, { syncSteps: true });
        syncResolutionSelectFromInputs();
    });
    widthInput?.addEventListener('change', syncResolutionSelectFromInputs);
    heightInput?.addEventListener('change', syncResolutionSelectFromInputs);
    window.addEventListener('psyfi:resolution-change', () => syncResolutionSelectFromInputs());
    syncResolutionSelectFromInputs();
    bindTooltips(document);

    function normalizeValue(value, min, max) {
        return (value - min) / (max - min);
    }

    function updateMetric(name, value, barValue) {
        const valueElement = document.getElementById(name);
        valueElement.textContent = value.toFixed(3);
        document.getElementById(`${name}Bar`).style.width =
            `${Math.max(0, Math.min(100, barValue * 100))}%`;
        if (name === 'valence') {
            valueElement.style.color = value > 0
                ? 'var(--color-signal-primary)'
                : 'var(--color-signal-secondary)';
        }
    }

    async function renderVisualization(visualization) {
        const summary = document.getElementById('vizSummary');
        if (summary) {
            summary.textContent = visualization?.accessibility?.summary || '';
        }
        if (!window.PsyFiRenderer) {
            return;
        }
        const result = await window.PsyFiRenderer.renderVisualization({
            canvas2d,
            canvasGpu,
            visualization,
            preferWebGPU: !preferWebGPU || preferWebGPU.checked,
        });
        if (vizBackend) {
            vizBackend.textContent = `Renderer: ${result.backend}` +
                (result.lastError ? ` (fallback note: ${result.lastError})` : '');
        }
    }

    async function showResults(data) {
        lastPayload = data;
        window.PsyFiLastSim = {
            payload: data,
            width: data.width,
            height: data.height,
            seed: data.seed,
            preset: data.preset || null,
            substance: data.preset || data.session?.preset || null,
            provenance_id: data.provenance_id,
            visualization: data.visualization || null,
        };
        setHidden(resultsEmpty, true);
        setHidden(resultsContent, false);

        document.getElementById('fieldDimensions').textContent =
            `${data.width} × ${data.height}`;
        updateMetric('valence', data.valence, normalizeValue(data.valence, -1, 1));
        updateMetric('coherence', data.coherence, data.coherence);
        updateMetric('symmetry', data.symmetry, data.symmetry);
        updateMetric('roughness', data.roughness, data.roughness);
        updateMetric('richness', data.richness, data.richness);

        document.getElementById('resultSeed').textContent = data.seed ?? '--';
        document.getElementById('resultPreset').textContent = data.preset || data.session?.preset || 'none';
        document.getElementById('resultProvenance').textContent = data.provenance_id ?? '--';
        document.getElementById('resultModules').textContent =
            (data.module_chain || []).join(' → ') || '--';

        await renderVisualization(data.visualization);
        try {
            localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({
                ...data,
                interrupted: false,
            }));
        } catch (error) {
            console.warn('[PsyFi] localStorage unavailable:', error);
        }
    }

    async function openDb() {
        return openPsyfiDb();
    }

    async function saveHistoryRecord(payload) {
        if (!payload?.session) throw new Error('No session available to save');
        const db = await openDb();
        const record = {
            id: payload.session.provenance.id,
            updated_at: payload.session.updated_at || new Date().toISOString(),
            session: payload.session,
            visualization: payload.visualization || null,
            metrics: {
                valence: payload.valence,
                coherence: payload.coherence,
                symmetry: payload.symmetry,
                roughness: payload.roughness,
                richness: payload.richness,
            },
            width: payload.width,
            height: payload.height,
            seed: payload.seed,
            preset: payload.preset || null,
            module_chain: payload.module_chain || [],
            provenance_id: payload.provenance_id,
        };
        await new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, 'readwrite');
            tx.objectStore(STORE_NAME).put(record);
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
        db.close();
        await refreshHistory();
        return record;
    }

    async function listHistory() {
        try {
            const db = await openDb();
            const records = await new Promise((resolve, reject) => {
                const tx = db.transaction(STORE_NAME, 'readonly');
                const request = tx.objectStore(STORE_NAME).getAll();
                request.onsuccess = () => resolve(request.result || []);
                request.onerror = () => reject(request.error);
            });
            db.close();
            return records.sort((a, b) => String(b.updated_at).localeCompare(String(a.updated_at)));
        } catch (error) {
            console.warn('[PsyFi] IndexedDB unavailable:', error);
            return [];
        }
    }

    function applyRecordToForm(record) {
        if (!record?.session?.parameters) return;
        document.getElementById('width').value = record.session.parameters.width;
        document.getElementById('height').value = record.session.parameters.height;
        document.getElementById('steps').value = record.session.parameters.steps;
        document.getElementById('seed').value = record.seed;
        if (record.preset) substanceSelect.value = record.preset;
    }

    function recordToPayload(record) {
        return {
            width: record.width,
            height: record.height,
            valence: record.metrics.valence,
            coherence: record.metrics.coherence,
            symmetry: record.metrics.symmetry,
            roughness: record.metrics.roughness,
            richness: record.metrics.richness,
            seed: record.seed,
            preset: record.preset,
            provenance_id: record.provenance_id,
            module_chain: record.module_chain,
            session: record.session,
            visualization: record.visualization,
        };
    }

    function textEl(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text != null) node.textContent = String(text);
        return node;
    }

    function provenanceLabeled(label, value) {
        const div = textEl('div');
        div.append(textEl('strong', '', label), document.createTextNode(` ${value == null ? '' : value}`));
        return div;
    }

    async function refreshHistory() {
        const records = await listHistory();
        historyList.innerHTML = '';
        setHidden(historyEmpty, records.length > 0);
        records.forEach((record) => {
            const item = document.createElement('li');
            item.className = 'history-item';
            const title = textEl('div', 'history-title');
            const icon = textEl('span', 'pf-icon pf-icon-console');
            icon.setAttribute('aria-hidden', 'true');
            title.append(
                icon,
                textEl('strong', '', `${record.width}×${record.height}`),
                document.createTextNode(' · seed '),
                textEl('code', '', record.seed),
                document.createTextNode(` · ${record.preset || 'no preset'}`),
            );
            const restore = textEl('button', 'btn-secondary history-restore', 'Restore');
            restore.type = 'button';
            restore.addEventListener('click', async () => {
                applyRecordToForm(record);
                await showResults(recordToPayload(record));
                hideError();
            });
            item.append(
                title,
                textEl(
                    'div',
                    'history-meta',
                    `${record.id} · valence ${Number(record.metrics?.valence || 0).toFixed(3)}`,
                ),
                restore,
            );
            historyList.appendChild(item);
        });
    }

    const compareList = document.getElementById('compareList');
    const compareEmpty = document.getElementById('compareEmpty');

    async function refreshComparisons() {
        if (!compareList) return;
        const records = await listComparisonRecords();
        compareList.innerHTML = '';
        setHidden(compareEmpty, records.length > 0);
        records.forEach((record) => {
            const item = document.createElement('li');
            item.className = 'history-item';
            const pinHash = String(record.pinned?.hash || '—').slice(0, 8);
            const liveHash = String(record.live?.hash || '—').slice(0, 8);
            const title = textEl('div', 'history-title');
            title.append(
                textEl('strong', '', record.mode || 'off'),
                document.createTextNode(` · ${record.substance || 'field'} · pin `),
                textEl('code', '', pinHash),
                document.createTextNode(' · live '),
                textEl('code', '', liveHash),
            );
            const restore = textEl('button', 'btn-secondary compare-restore', 'Restore');
            restore.type = 'button';
            restore.addEventListener('click', () => {
                window.dispatchEvent(new CustomEvent('psyfi:restore-comparison', { detail: record }));
                const panel = document.getElementById('experiencePanel');
                if (panel) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
            item.append(
                title,
                textEl(
                    'div',
                    'history-meta',
                    `${record.id} · ${record.claim || 'INFERRED'} · ${record.updated_at || ''}`,
                ),
                restore,
            );
            compareList.appendChild(item);
        });
    }

    window.PsyFiCompareArchive = {
        refresh: refreshComparisons,
        save: saveComparisonRecord,
        list: listComparisonRecords,
        clear: clearComparisonRecords,
    };

    const journeyList = document.getElementById('journeyList');
    const journeyEmpty = document.getElementById('journeyEmpty');

    async function refreshJourneys() {
        if (!journeyList) return;
        const records = await listJourneyRecords();
        journeyList.innerHTML = '';
        setHidden(journeyEmpty, records.length > 0);
        records.forEach((record) => {
            const item = document.createElement('li');
            item.className = 'history-item';
            const motifs = (record.planner?.motifs || []).slice(0, 2).join(', ') || '—';
            const title = textEl('div', 'history-title');
            title.append(
                textEl('strong', '', record.title || record.substance || 'journey'),
                document.createTextNode(` · ${record.mode || 'open'} · seed `),
                textEl('code', '', record.seed ?? '—'),
            );
            const restore = textEl('button', 'btn-secondary journey-restore', 'Restore');
            restore.type = 'button';
            restore.addEventListener('click', () => {
                window.dispatchEvent(new CustomEvent('psyfi:restore-journey', { detail: record }));
                const panel = document.getElementById('experiencePanel');
                if (panel) panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
            });
            item.append(
                title,
                textEl('div', 'history-meta', `${record.id} · ${motifs} · ${record.updated_at || ''}`),
                restore,
            );
            journeyList.appendChild(item);
        });
    }

    window.PsyFiJourneyArchive = {
        refresh: refreshJourneys,
        save: saveJourneyRecord,
        list: listJourneyRecords,
        clear: clearJourneyRecords,
    };

    async function clearHistory() {
        const db = await openDb();
        await new Promise((resolve, reject) => {
            const tx = db.transaction(STORE_NAME, 'readwrite');
            tx.objectStore(STORE_NAME).clear();
            tx.oncomplete = () => resolve();
            tx.onerror = () => reject(tx.error);
        });
        db.close();
        await refreshHistory();
    }

    async function loadPresets() {
        try {
            const response = await fetch(`${API_V1}/presets/`);
            if (!response.ok) throw new Error(`Preset catalog failed (${response.status})`);
            const data = await response.json();
            substanceSelect.innerHTML = '<option value="">None (baseline coupling)</option>';
            substanceGrid.innerHTML = '';
            data.presets.forEach((preset) => {
                const option = document.createElement('option');
                option.value = preset.id;
                option.textContent = `${preset.name} (${preset.substance_class})`;
                substanceSelect.appendChild(option);

                const card = document.createElement('button');
                card.type = 'button';
                card.className = 'substance-card';
                card.append(
                    textEl('span', 'preset-name', preset.name),
                    textEl('span', 'preset-desc', `· ${preset.substance_class}`),
                );
                card.addEventListener('click', () => {
                    substanceSelect.value = preset.id;
                    document.querySelectorAll('.substance-card').forEach((el) => el.classList.remove('active'));
                    card.classList.add('active');
                });
                substanceGrid.appendChild(card);
            });
            setHidden(presetEmpty, true);
            setHidden(substanceGrid, false);
        } catch (error) {
            presetEmpty.textContent = `Preset catalog unavailable: ${error.message}`;
            setHidden(presetEmpty, false);
            setHidden(substanceGrid, true);
        }
    }

    function renderCapabilities() {
        const renderer = window.PsyFiRenderer ? window.PsyFiRenderer.getRendererState() : {};
        const sensors =
            (window.PsyFiViz && window.PsyFiViz.probeSensorCapabilities
                ? window.PsyFiViz.probeSensorCapabilities()
                : {}) || {};
        const monitor =
            window.PsyFiViz && typeof window.PsyFiViz.probeMonitor === 'function'
                ? window.PsyFiViz.probeMonitor()
                : { ok: !!(window.screen && window.screen.width), detail: 'screen metrics' };
        const gpuCache = window.__psyfiGpuProbe || null;
        const rows = [
            {
                name: 'Monitor / display',
                supported: !!monitor.ok,
                fallback: monitor.detail || 'Display metrics unavailable',
            },
            {
                name: 'GPU adapter',
                supported: !!(gpuCache ? gpuCache.ok : renderer.webgpuSupported),
                fallback: gpuCache
                    ? gpuCache.detail
                    : renderer.webgpuSupported
                      ? 'WebGPU feature present — open <a href="/gpu/">GPU Lab</a>'
                      : 'Worker + Canvas 2D · GPU Lab unavailable',
            },
            { name: 'Canvas 2D', supported: !!(canvas2d && canvas2d.getContext), fallback: 'Metrics/provenance text only' },
            { name: 'Web Worker rasterizer', supported: !!renderer.workerSupported, fallback: 'Main-thread Canvas rasterize' },
            { name: 'WebGL', supported: !!document.createElement('canvas').getContext('webgl'), fallback: 'Canvas 2D baseline renderer' },
            {
                name: 'WebGPU',
                supported: !!(gpuCache ? gpuCache.webgpu : renderer.webgpuSupported),
                fallback: (gpuCache ? gpuCache.webgpu : renderer.webgpuSupported)
                    ? 'Open <a href="/gpu/">GPU Lab</a> (separate /gpu/ route)'
                    : 'Worker + Canvas 2D · GPU Lab unavailable',
            },
            { name: 'IndexedDB', supported: !!window.indexedDB, fallback: 'localStorage last-session only' },
            { name: 'Service Worker', supported: 'serviceWorker' in navigator, fallback: 'Online-only shell caching' },
            { name: 'Web MIDI', supported: !!sensors.webMidi, fallback: 'REST MIDI routes when server has devices' },
            { name: 'Camera (getUserMedia)', supported: !!sensors.camera, fallback: 'Manual camera modulator slider' },
            { name: 'Microphone (getUserMedia)', supported: !!sensors.microphone, fallback: 'Manual audio modulator slider' },
            {
                name: 'DeviceMotion',
                supported: !!sensors.deviceMotion,
                fallback: sensors.motionNeedsGesture
                    ? 'Needs user gesture / permission'
                    : 'Manual motion slider',
            },
            {
                name: 'DeviceOrientation',
                supported: !!sensors.deviceOrientation,
                fallback: sensors.orientationNeedsGesture
                    ? 'Needs user gesture / permission'
                    : 'Blended into motion channel when enabled',
            },
            { name: 'AmbientLightSensor', supported: !!sensors.ambientLight, fallback: 'Camera luminance proxy / manual slider' },
            { name: 'Gamepad', supported: !!sensors.gamepad, fallback: 'Manual motion slider' },
            { name: 'Vibration / Haptics', supported: !!sensors.vibrate, fallback: 'Visual state feedback only' },
            { name: 'Battery Status', supported: !!sensors.battery, fallback: 'Used for GPU quality tier only — not a field modulator' },
            { name: 'Geolocation', supported: !!sensors.geolocation, fallback: 'Not used as a modulator (privacy)' },
            { name: 'AbortController cancel', supported: typeof AbortController !== 'undefined', fallback: 'Wait for request completion' },
            {
                name: 'GPU Lab route',
                supported: true,
                fallback: '<a href="/gpu/">/gpu/</a> · not embedded in shell (see docs/PWA_GPU_ROUTE.md)',
            },
        ];
        const tbody = document.querySelector('#capabilityTable tbody');
        tbody.innerHTML = '';
        rows.forEach((row) => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${row.name}</td>
                <td data-ok="${row.supported}">${row.supported ? 'yes' : 'no'}</td>
                <td>${row.fallback}</td>
            `;
            tbody.appendChild(tr);
        });
        syncSensorButtons(sensors);
    }

    function syncSensorButtons(sensors) {
        const map = [
            ['enableCameraBtn', sensors.camera],
            ['enableAudioBtn', sensors.microphone],
            ['enableMotionBtn', sensors.deviceMotion || sensors.deviceOrientation],
            ['enableMidiBtn', sensors.webMidi],
            ['enableGamepadBtn', sensors.gamepad],
            ['enableAmbientBtn', sensors.ambientLight],
            ['enableHapticsBtn', sensors.vibrate],
        ];
        map.forEach(([id, ok]) => {
            const btn = document.getElementById(id);
            if (!btn) return;
            btn.disabled = !ok;
            btn.title = ok ? '' : 'Not available on this device/browser';
        });
        const select = document.getElementById('sensorEnableSelect');
        if (!select) return;
        const avail = {
            camera: sensors.camera,
            audio: sensors.microphone,
            motion: sensors.deviceMotion || sensors.deviceOrientation,
            midi: sensors.webMidi,
            gamepad: sensors.gamepad,
            ambient: sensors.ambientLight,
            haptics: sensors.vibrate,
        };
        Array.from(select.options).forEach((opt) => {
            if (!opt.value) return;
            opt.disabled = !avail[opt.value];
        });
    }

    async function maybeShowRecoveryBanner() {
        if (!recoveryBanner) return;
        if (sessionStorage.getItem(RECOVERY_DISMISS_KEY) === '1') {
            setHidden(recoveryBanner, true);
            return;
        }
        const history = await listHistory();
        if (history[0]) {
            recoveryRecord = history[0];
        } else {
            try {
                const raw = localStorage.getItem(SESSION_STORAGE_KEY);
                if (raw) {
                    const parsed = JSON.parse(raw);
                    if (parsed.session) {
                        recoveryRecord = {
                            width: parsed.width || parsed.session.parameters.width,
                            height: parsed.height || parsed.session.parameters.height,
                            seed: parsed.seed || parsed.session.seed,
                            preset: parsed.preset || parsed.session.preset,
                            provenance_id: parsed.provenance_id || parsed.session.provenance.id,
                            module_chain: parsed.module_chain || parsed.session.provenance.module_chain,
                            metrics: parsed.metrics || parsed.session.result?.metrics,
                            session: parsed.session,
                            visualization: parsed.visualization || null,
                        };
                    }
                }
            } catch (error) {
                console.warn('[PsyFi] recovery parse failed', error);
            }
        }
        if (recoveryRecord?.session) {
            document.getElementById('recoveryText').textContent =
                `Recover session ${recoveryRecord.provenance_id || recoveryRecord.id} ` +
                `(${recoveryRecord.width}×${recoveryRecord.height}, seed ${recoveryRecord.seed})?`;
            setHidden(recoveryBanner, false);
        }
    }

    async function sleep(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }

    async function runViaJob(body) {
        showLoading(true, 'Queueing simulation job…');
        const create = await fetch(`${API_V1}/jobs/simulate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (!create.ok) {
            const errorData = await create.json().catch(() => ({}));
            throw new Error(errorData.detail || `Job create failed (${create.status})`);
        }
        const created = await create.json();
        activeJobId = created.id;
        showLoading(true, `Job ${activeJobId} running…`);

        const started = Date.now();
        while (true) {
            if (Date.now() - started > 85000) {
                throw new Error('Simulation job timed out');
            }
            if (cancelRequested && activeJobId) {
                await fetch(`${API_V1}/jobs/${activeJobId}`, { method: 'DELETE' });
            }
            const poll = await fetch(`${API_V1}/jobs/${activeJobId}`);
            if (!poll.ok) throw new Error(`Job poll failed (${poll.status})`);
            const job = await poll.json();
            showLoading(true, `Job ${activeJobId}: ${job.status}`);
            if (job.status === 'completed' && job.result) {
                return job.result;
            }
            if (job.status === 'cancelled') {
                const err = new Error(job.error || 'Simulation cancelled');
                err.name = 'AbortError';
                throw err;
            }
            if (job.status === 'failed') {
                throw new Error(job.error || 'Simulation job failed');
            }
            await sleep(120);
        }
    }

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!navigator.onLine) {
            showError('Server simulation requires network connectivity. Restore a history item to inspect prior results offline.');
            return;
        }

        const width = parseInt(document.getElementById('width').value, 10);
        const height = parseInt(document.getElementById('height').value, 10);
        const steps = parseInt(document.getElementById('steps').value, 10);
        const seed = parseInt(document.getElementById('seed').value, 10);
        const preset = substanceSelect.value || null;

        cancelRequested = false;
        activeJobId = null;
        if (activeAbort) activeAbort.abort();
        activeAbort = typeof AbortController !== 'undefined' ? new AbortController() : null;

        try {
            localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({
                interrupted: true,
                width, height, steps, seed, preset,
                updated_at: new Date().toISOString(),
            }));
        } catch (_error) { /* ignore */ }

        showLoading(true);
        hideError();

        try {
            const body = { width, height, steps, seed };
            if (preset) body.preset = preset;

            // Job API enables true server-side cancellation via should_cancel.
            const data = await runViaJob(body);
            if (cancelRequested) {
                const err = new Error('Simulation cancelled');
                err.name = 'AbortError';
                throw err;
            }
            await showResults(data);
            try {
                await saveHistoryRecord(data);
            } catch (error) {
                console.warn('[PsyFi] History save skipped:', error);
            }
        } catch (error) {
            if (error && error.name === 'AbortError') {
                showError('Simulation cancelled on the server. No result was applied.');
            } else {
                showError(error.message || String(error));
            }
        } finally {
            activeAbort = null;
            activeJobId = null;
            cancelRequested = false;
            showLoading(false);
        }
    });

    cancelButton?.addEventListener('click', async () => {
        cancelRequested = true;
        if (activeAbort) activeAbort.abort();
        if (activeJobId) {
            try {
                await fetch(`${API_V1}/jobs/${activeJobId}`, { method: 'DELETE' });
            } catch (_error) { /* ignore */ }
        }
    });

    window.addEventListener('beforeinstallprompt', (event) => {
        event.preventDefault();
        deferredInstallPrompt = event;
        setHidden(installButton, false);
    });

    installButton?.addEventListener('click', async () => {
        if (!deferredInstallPrompt) {
            showError('Install is unavailable in this browser. On iPhone use Share → Add to Home Screen.');
            return;
        }
        deferredInstallPrompt.prompt();
        await deferredInstallPrompt.userChoice;
        deferredInstallPrompt = null;
        setHidden(installButton, true);
    });

    importSessionInput?.addEventListener('change', async (event) => {
        const file = event.target.files && event.target.files[0];
        if (!file) return;
        try {
            const text = await file.text();
            const session = JSON.parse(text);
            if (!session || session.schema_version !== 'psyfi.session.v1' || !session.parameters) {
                throw new Error('File is not a psyfi.session.v1 document');
            }
            const payload = {
                width: session.parameters.width,
                height: session.parameters.height,
                valence: session.result?.metrics?.valence ?? 0,
                coherence: session.result?.metrics?.coherence ?? 0,
                symmetry: session.result?.metrics?.symmetry ?? 0,
                roughness: session.result?.metrics?.roughness ?? 0,
                richness: session.result?.metrics?.richness ?? 0,
                seed: session.seed,
                preset: session.preset,
                provenance_id: session.provenance?.id,
                module_chain: session.provenance?.module_chain || [],
                session,
                visualization: null,
            };
            applyRecordToForm(payload);
            await showResults(payload);
            hideError();
        } catch (error) {
            showError(`Import failed: ${error.message || error}`);
        } finally {
            importSessionInput.value = '';
        }
    });

    document.getElementById('exportSessionButton')?.addEventListener('click', () => {
        const session = lastPayload?.session;
        if (!session) {
            showError('No session available to export. Run a simulation first.');
            return;
        }
        const blob = new Blob([JSON.stringify(session, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `psyfi-session-${session.provenance?.id || 'export'}.json`;
        anchor.click();
        URL.revokeObjectURL(url);
    });

    document.getElementById('saveHistoryButton')?.addEventListener('click', async () => {
        try {
            await saveHistoryRecord(lastPayload);
            hideError();
        } catch (error) {
            showError(error.message);
        }
    });

    document.getElementById('clearHistoryButton')?.addEventListener('click', async () => {
        try {
            await clearHistory();
        } catch (error) {
            showError(error.message);
        }
    });

    document.getElementById('clearCompareButton')?.addEventListener('click', async () => {
        try {
            await clearComparisonRecords();
            await refreshComparisons();
        } catch (error) {
            showError(error.message);
        }
    });

    document.getElementById('clearJourneyButton')?.addEventListener('click', async () => {
        try {
            await clearJourneyRecords();
            await refreshJourneys();
        } catch (error) {
            showError(error.message);
        }
    });

    document.getElementById('recoveryRestore')?.addEventListener('click', async () => {
        if (!recoveryRecord) return;
        applyRecordToForm(recoveryRecord);
        if (recoveryRecord.metrics) {
            await showResults(recordToPayload(recoveryRecord));
        }
        setHidden(recoveryBanner, true);
        sessionStorage.setItem(RECOVERY_DISMISS_KEY, '1');
        hideError();
    });

    document.getElementById('recoveryDismiss')?.addEventListener('click', () => {
        setHidden(recoveryBanner, true);
        sessionStorage.setItem(RECOVERY_DISMISS_KEY, '1');
    });

    preferWebGPU?.addEventListener('change', async () => {
        if (lastPayload?.visualization) {
            await renderVisualization(lastPayload.visualization);
        }
        renderCapabilities();
    });

    const telemetryOptIn = document.getElementById('telemetryOptIn');
    telemetryOptIn?.addEventListener('change', async () => {
        try {
            await fetch(`${API_V1}/telemetry/opt-in`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ opt_in: !!telemetryOptIn.checked }),
            });
        } catch (error) {
            console.warn('[PsyFi] telemetry opt-in failed', error);
        }
    });

    document.addEventListener('keydown', (event) => {
        if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
            event.preventDefault();
            form.dispatchEvent(new Event('submit'));
        }
        if (event.key === 'Escape') {
            cancelRequested = true;
            if (activeAbort) activeAbort.abort();
            if (activeJobId) {
                fetch(`${API_V1}/jobs/${activeJobId}`, { method: 'DELETE' }).catch(() => {});
            }
        }
    });

    // Explicit offline empty-state copy for results when never run + offline.
    if (!navigator.onLine && resultsEmpty) {
        resultsEmpty.textContent = 'You are offline. Restore a history item or import a session JSON to inspect prior modeled results.';
    }

    // Service worker update nudge
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.addEventListener('controllerchange', () => {
            console.log('[PWA] New service worker activated');
        });
    }

    loadPresets();
    refreshHistory().then(maybeShowRecoveryBanner);
    refreshComparisons();
    refreshJourneys();
    renderCapabilities();

    // Splash finished (or skipped) — refresh capability/sensor UI against final probes.
    window.PsyFiBoot = window.PsyFiBoot || {};
    window.PsyFiBoot.onLaunchReady = function onLaunchReady(results) {
        const gpu = Array.isArray(results) ? results.find((r) => r.id === 'gpu') : null;
        if (gpu && gpu.raw) window.__psyfiGpuProbe = gpu.raw;
        renderCapabilities();
        syncResolutionSelectFromInputs();
    };
    window.addEventListener('psyfi:launch-ready', async (event) => {
        const results = event.detail && event.detail.results;
        const gpu = Array.isArray(results) ? results.find((r) => r.id === 'gpu') : null;
        if (gpu && gpu.raw) {
            window.__psyfiGpuProbe = gpu.raw;
        } else if (window.PsyFiViz && typeof window.PsyFiViz.probeGpu === 'function') {
            window.__psyfiGpuProbe = await window.PsyFiViz.probeGpu();
        }
        renderCapabilities();
        syncResolutionSelectFromInputs();
    });
    // If splash already entered before this handler bound, sync once.
    if (!document.body.classList.contains('launch-pending')) {
        if (window.PsyFiViz && typeof window.PsyFiViz.probeGpu === 'function') {
            window.PsyFiViz.probeGpu().then((gpu) => {
                window.__psyfiGpuProbe = gpu;
                renderCapabilities();
            });
        } else {
            renderCapabilities();
        }
    }
});

// ===== Live Experience workspace =====
(function initExperienceWorkspace() {
    const canvas = document.getElementById('experienceCanvas');
    const glCanvas = document.getElementById('experienceCanvasGL');
    if (!canvas || !window.PsyFiViz || !window.PsyFiViz.ExperiencePlayer) {
        console.warn('[PsyFi] Experience player not available');
        return;
    }

    const substanceSelect = document.getElementById('substanceSelect');
    const experienceSelect = document.getElementById('experienceSelect');
    const modeSelect = document.getElementById('modeSelect');
    const intensityRange = document.getElementById('intensityRange');
    const intensityValue = document.getElementById('intensityValue');
    const intensityMapHint = document.getElementById('intensityMapHint');
    const seedInput = document.getElementById('seedInput');
    const phaseScrub = document.getElementById('phaseScrub');
    const phaseLabel = document.getElementById('phaseLabel');
    const phaseHint = document.getElementById('phaseHint');
    const phaseAdvanceChk = document.getElementById('phaseAdvanceChk');
    const phaseSpeedSelect = document.getElementById('phaseSpeedSelect');
    const reduceMotionChk = document.getElementById('reduceMotionChk');
    const dimFlashChk = document.getElementById('dimFlashChk');
    const preferWebGLChk = document.getElementById('preferWebGLChk');
    const sourcePlaneChk = document.getElementById('sourcePlaneChk');
    const sourcePlaneMix = document.getElementById('sourcePlaneMix');
    const sourcePlaneMixValue = document.getElementById('sourcePlaneMixValue');
    const sourcePlaneMixGroup = document.getElementById('sourcePlaneMixGroup');
    const loadBtn = document.getElementById('loadExperienceBtn');
    const playBtn = document.getElementById('playExperienceBtn');
    const pauseBtn = document.getElementById('pauseExperienceBtn');
    const neutralBtn = document.getElementById('neutralBtn');
    const pinFrameBtn = document.getElementById('pinFrameBtn');
    const clearPinBtn = document.getElementById('clearPinBtn');
    const compareModeSelect = document.getElementById('compareModeSelect');
    const compareWipeGroup = document.getElementById('compareWipeGroup');
    const wipePositionRange = document.getElementById('wipePositionRange');
    const wipePositionValue = document.getElementById('wipePositionValue');
    const openGpuLabBtn = document.getElementById('openGpuLabBtn');
    const gpuLabNavLink = document.getElementById('gpuLabNavLink');
    const statusEl = document.getElementById('experienceStatus');
    /** Pass-1 image seed payload (also mirrored to sessionStorage for /gpu/). */
    let imageSeedState = null;

    const instrumentMap = window.PsyFiViz && window.PsyFiViz.instrumentMap;

    /** Mapped intensity (0–1) sent to ParameterField / API — not raw slider UI position. */
    function getExperienceIntensity() {
        if (instrumentMap && intensityRange) {
            return instrumentMap.readIntensityFromRange(intensityRange);
        }
        return Number(intensityRange?.value) || 0.7;
    }

    function syncIntensityDisplay() {
        if (!intensityValue) return;
        const v = getExperienceIntensity();
        intensityValue.textContent = instrumentMap
            ? instrumentMap.formatIntensity(v)
            : Number(v).toFixed(2);
        if (intensityMapHint && intensityRange) {
            const mode = (intensityRange.dataset && intensityRange.dataset.mapMode) || 'instrument';
            intensityMapHint.textContent = instrumentMap
                ? instrumentMap.mapModeHint(mode)
                : mode === 'linear'
                  ? 'Linear map · Alt+click for instrument'
                  : 'Instrument map · Alt+click for linear';
        }
    }

    function setExperienceIntensity(intensity) {
        if (instrumentMap && intensityRange) {
            instrumentMap.writeIntensityToRange(intensityRange, intensity);
        } else if (intensityRange) {
            intensityRange.value = String(intensity);
        }
        syncIntensityDisplay();
    }

    /** Map shell LOD → GPU Lab tier query param. */
    function mapShellQualityToGpuTier(raw) {
        const t = String(raw || 'balanced').toLowerCase().replace(/-/g, '_');
        if (t === 'survival' || t === 'battery' || t === 'battery_saver') return 'battery';
        if (t === 'efficient') return 'balanced';
        if (t === 'ultra' || t === 'high' || t === 'balanced') return t;
        return 'balanced';
    }

    function persistImageSeedHandoff(body) {
        if (!body || typeof sessionStorage === 'undefined') return;
        try {
            sessionStorage.setItem(
                'psyfi.imageSeed.v1',
                JSON.stringify({
                    schema: 'psyfi.imageSeed.v1',
                    master_seed: body.master_seed,
                    influence: body.influence,
                    parameter_hints: body.parameter_hints || {},
                    conditioned_texture_png_base64: body.conditioned_texture_png_base64 || null,
                    substance: body.substance || substanceSelect?.value || 'lsd',
                    experience_id: body.experience_id || experienceSelect?.value || null,
                    mode: body.applied_mode || body.mode || modeSelect?.value || 'open',
                    features: body.features || null,
                }),
            );
        } catch (_e) { /* ignore quota */ }
    }

    function clearImageSeedHandoff() {
        try {
            sessionStorage?.removeItem('psyfi.imageSeed.v1');
        } catch (_e) { /* ignore */ }
    }

    function buildGpuLabUrl() {
        const q = new URLSearchParams();
        q.set('from', 'shell');
        const substance = substanceSelect?.value || 'lsd';
        const mode = modeSelect?.value || 'open';
        const intensity = getExperienceIntensity();
        const seed = Number(seedInput?.value);
        const tier = mapShellQualityToGpuTier(document.getElementById('qualityTierSelect')?.value);
        const experienceId = experienceSelect?.value || '';
        q.set('substance', substance);
        q.set('mode', mode);
        if (Number.isFinite(intensity)) q.set('intensity', String(intensity));
        if (Number.isFinite(seed)) q.set('seed', String(Math.floor(seed)));
        q.set('tier', tier);
        if (experienceId) q.set('experience_id', experienceId);
        if (imageSeedState) q.set('image_seed', '1');
        return `/gpu/?${q.toString()}`;
    }

    function syncGpuLabLinks() {
        const href = buildGpuLabUrl();
        if (openGpuLabBtn) openGpuLabBtn.href = href;
        if (gpuLabNavLink) gpuLabNavLink.href = href;
    }
    syncGpuLabLinks();
    ;[substanceSelect, experienceSelect, modeSelect, intensityRange, seedInput, document.getElementById('qualityTierSelect')]
        .filter(Boolean)
        .forEach((el) => {
            el.addEventListener('change', syncGpuLabLinks);
            el.addEventListener('input', syncGpuLabLinks);
        });
    function syncFieldStatusLive(msg) {
        if (!statusEl) return;
        const t = String(msg || '');
        const live = /running|loading|bridging|Computing|Playing|timeline/i.test(t)
            && !/idle|paused|failed|Neutral/i.test(t);
        statusEl.dataset.live = live ? 'true' : 'false';
    }
    if (statusEl && typeof MutationObserver !== 'undefined') {
        syncFieldStatusLive(statusEl.textContent);
        new MutationObserver(() => syncFieldStatusLive(statusEl.textContent)).observe(statusEl, {
            characterData: true,
            childList: true,
            subtree: true,
        });
    }

    const provenanceEl = document.getElementById('experienceProvenancePanel');
    const modCamera = document.getElementById('modCamera');
    const modMotion = document.getElementById('modMotion');
    const modMidi = document.getElementById('modMidi');
    const modAudio = document.getElementById('modAudio');
    const modHaptics = document.getElementById('modHaptics');
    let lastBridgeField = null;

    function syncSourcePlaneUI() {
        const on = !!(sourcePlaneChk && sourcePlaneChk.checked && lastBridgeField);
        if (sourcePlaneMixGroup) sourcePlaneMixGroup.hidden = !on;
        if (!on) {
            player.clearSourcePlane();
            return;
        }
        const mix = sourcePlaneMix ? Number(sourcePlaneMix.value) : 0.32;
        if (sourcePlaneMixValue) sourcePlaneMixValue.textContent = mix.toFixed(2);
        player.setSourcePlane(lastBridgeField, mix);
    }

    const player = new PsyFiViz.ExperiencePlayer({
        canvas,
        glCanvas,
        statusEl,
        provenanceEl,
        preferWebGL: !!(preferWebGLChk && preferWebGLChk.checked),
    });
    const viewportResolutionSelect = document.getElementById('viewportResolutionSelect');
    if (viewportResolutionSelect) {
        player.setViewportResolution(viewportResolutionSelect.value);
        viewportResolutionSelect.addEventListener('change', () => {
            player.setViewportResolution(viewportResolutionSelect.value);
        });
    } else {
        player.resize();
    }
    window.addEventListener('resize', () => player.resize());

    // Optional: poll server MIDI activity into the MIDI modulator slider (fallback if no Web MIDI)
    let midiPoll = null;
    function startMidiPoll() {
        if (midiPoll) return;
        if (sensorHub && sensorHub.active && sensorHub.active.webMidi) return;
        midiPoll = setInterval(async () => {
            try {
                const res = await fetch('/api/v1/midi/status');
                if (!res.ok) return;
                const st = await res.json();
                if (!st.running || !modMidi) return;
                const level = typeof st.activity === 'number' ? st.activity : 0.35;
                modMidi.value = Math.min(1, Math.max(Number(modMidi.value), level)).toFixed(2);
                syncModulators();
            } catch (_e) { /* ignore */ }
        }, 1200);
    }
    document.getElementById('modMidi')?.addEventListener('pointerdown', startMidiPoll);

    const sensorHub =
        window.PsyFiViz && window.PsyFiViz.DeviceSensorHub
            ? new window.PsyFiViz.DeviceSensorHub({
                  status: (msg) => {
                      if (statusEl) statusEl.textContent = msg;
                  },
                  onChannels: (ch) => {
                      if (modCamera) modCamera.value = Number(ch.camera || 0).toFixed(2);
                      if (modMotion) modMotion.value = Number(ch.motion || 0).toFixed(2);
                      if (modMidi) modMidi.value = Number(ch.midi || 0).toFixed(2);
                      if (modAudio) modAudio.value = Number(ch.audio || 0).toFixed(2);
                      if (modHaptics) modHaptics.value = Number(ch.haptics || 0).toFixed(2);
                      syncModulators();
                  },
              })
            : null;
    player.onPhaseIndex = (idx, total) => {
        if (!phaseScrub) return;
        phaseScrub.max = String(Math.max(0, total - 1));
        phaseScrub.value = String(idx);
        const frame = player.timeline && player.timeline.frames[idx];
        if (phaseLabel && frame) phaseLabel.textContent = frame.phase || String(idx);
    };

    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        reduceMotionChk.checked = true;
    }

    // Keep displayed intensity at 0.70 (mapped) rather than raw UI position.
    setExperienceIntensity(0.7);
    syncGpuLabLinks();
    intensityRange.addEventListener('input', () => {
        syncIntensityDisplay();
        syncGpuLabLinks();
    });
    intensityRange.addEventListener('click', (e) => {
        if (!e.altKey || !instrumentMap) return;
        e.preventDefault();
        const current = getExperienceIntensity();
        const cur = intensityRange.dataset.mapMode || 'instrument';
        const mode = instrumentMap.nextMapMode(cur);
        intensityRange.dataset.mapMode = mode;
        intensityRange.classList.toggle('stations-mode', mode === 'stations');
        setExperienceIntensity(current);
        syncGpuLabLinks();
        if (statusEl) {
            statusEl.textContent =
                mode === 'linear'
                    ? 'Intensity map: linear'
                    : mode === 'stations'
                      ? 'Intensity map: station dial'
                      : 'Intensity map: instrument';
        }
    });
    intensityRange.addEventListener('keydown', (e) => {
        if (!instrumentMap || !(e.altKey && (e.key === 'm' || e.key === 'M'))) return;
        e.preventDefault();
        const current = getExperienceIntensity();
        const cur = intensityRange.dataset.mapMode || 'instrument';
        const mode = instrumentMap.nextMapMode(cur);
        intensityRange.dataset.mapMode = mode;
        intensityRange.classList.toggle('stations-mode', mode === 'stations');
        setExperienceIntensity(current);
        syncIntensityDisplay();
        syncGpuLabLinks();
        if (statusEl) {
            statusEl.textContent =
                mode === 'linear'
                    ? 'Intensity map: linear'
                    : mode === 'stations'
                      ? 'Intensity map: station dial'
                      : 'Intensity map: instrument';
        }
    });

    const imageSeedControl = document.getElementById('imageSeedControl');
    const imageSeedFile = document.getElementById('imageSeedFile');
    const imageSeedInfluence = document.getElementById('imageSeedInfluence');
    const imageSeedInfluenceValue = document.getElementById('imageSeedInfluenceValue');
    const imageSeedApplyRecommended = document.getElementById('imageSeedApplyRecommended');
    const imageSeedSuggestBtn = document.getElementById('imageSeedSuggestBtn');
    const imageSeedApplyBtn = document.getElementById('imageSeedApplyBtn');
    const imageSeedJourneyBtn = document.getElementById('imageSeedJourneyBtn');
    const imageSeedClearBtn = document.getElementById('imageSeedClearBtn');
    const imageSeedStatus = document.getElementById('imageSeedStatus');
    const imageSeedPreview = document.getElementById('imageSeedPreview');
    const imageSeedPreviewEmpty = document.getElementById('imageSeedPreviewEmpty');
    const imageSeedRecommend = document.getElementById('imageSeedRecommend');
    const imageSeedRecommendTitle = document.getElementById('imageSeedRecommendTitle');
    const imageSeedRecommendMeta = document.getElementById('imageSeedRecommendMeta');
    const imageSeedAltSelect = document.getElementById('imageSeedAltSelect');
    let imageSeedLocalUrl = null;
    let imageSeedSuggest = null;
    let imageSeedAlternatives = [];

    function imageInfluence() {
        return imageSeedInfluence ? Number(imageSeedInfluence.value) : 0;
    }

    function setImageSeedUiState(state, msg) {
        if (imageSeedControl) imageSeedControl.dataset.state = state || 'idle';
        if (imageSeedStatus) imageSeedStatus.textContent = msg || 'Idle';
        const busy = state === 'loading';
        if (imageSeedApplyBtn) imageSeedApplyBtn.disabled = busy;
        if (imageSeedSuggestBtn) imageSeedSuggestBtn.disabled = busy;
        if (imageSeedJourneyBtn) imageSeedJourneyBtn.disabled = busy;
        if (imageSeedFile) imageSeedFile.disabled = busy;
        if (imageSeedAltSelect) imageSeedAltSelect.disabled = busy;
    }

    function revokeImageSeedLocalUrl() {
        if (imageSeedLocalUrl) {
            URL.revokeObjectURL(imageSeedLocalUrl);
            imageSeedLocalUrl = null;
        }
    }

    function showImageSeedPreview(b64OrUrl, { isObjectUrl = false } = {}) {
        if (!imageSeedPreview) return;
        if (b64OrUrl) {
            if (!isObjectUrl) revokeImageSeedLocalUrl();
            imageSeedPreview.src = isObjectUrl
                ? b64OrUrl
                : `data:image/png;base64,${b64OrUrl}`;
            imageSeedPreview.hidden = false;
            if (imageSeedPreviewEmpty) imageSeedPreviewEmpty.hidden = true;
        } else {
            revokeImageSeedLocalUrl();
            imageSeedPreview.removeAttribute('src');
            imageSeedPreview.hidden = true;
            if (imageSeedPreviewEmpty) imageSeedPreviewEmpty.hidden = false;
        }
    }

    function showLocalImageSeedPreview(file) {
        revokeImageSeedLocalUrl();
        if (!file) {
            showImageSeedPreview(null);
            return;
        }
        imageSeedLocalUrl = URL.createObjectURL(file);
        showImageSeedPreview(imageSeedLocalUrl, { isObjectUrl: true });
    }

    function selectedAlternative() {
        if (!imageSeedAltSelect || !imageSeedAltSelect.value) return null;
        return (
            imageSeedAlternatives.find((a) => a.experience_id === imageSeedAltSelect.value) || null
        );
    }

    function topRecommendedId(body) {
        return body?.recommended?.experience_id || body?.applied_experience_id || null;
    }

    function shouldApplyRecommendedWinner(body) {
        if (!imageSeedApplyRecommended?.checked) return false;
        const alt = selectedAlternative();
        const topId = topRecommendedId(body || imageSeedSuggest || imageSeedState);
        if (!alt || !topId) return true;
        return alt.experience_id === topId;
    }

    function populateAlternativeSelect(body, { preferId = null } = {}) {
        imageSeedAlternatives = Array.isArray(body?.recommended_alternatives)
            ? body.recommended_alternatives
            : [];
        if (!imageSeedAltSelect) return;
        imageSeedAltSelect.innerHTML = '';
        if (!imageSeedAlternatives.length) {
            imageSeedAltSelect.hidden = true;
            return;
        }
        imageSeedAltSelect.hidden = false;
        for (const alt of imageSeedAlternatives) {
            const opt = document.createElement('option');
            opt.value = alt.experience_id || '';
            const score =
                alt.score != null ? ` · ${Number(alt.score).toFixed(2)}` : '';
            opt.textContent = `#${alt.rank || '?'} ${alt.title || alt.experience_id}${score}`;
            imageSeedAltSelect.appendChild(opt);
        }
        const want =
            preferId ||
            body?.applied_experience_id ||
            body?.recommended?.experience_id ||
            imageSeedAlternatives[0]?.experience_id;
        if (want) imageSeedAltSelect.value = want;
    }

    function renderImageSeedRecommend(body, { syncAlt = true } = {}) {
        const alt = selectedAlternative();
        const rec = body?.recommended || {};
        const title =
            alt?.title ||
            rec.experience_title ||
            body?.applied_experience_id ||
            rec.experience_id ||
            'Open field';
        const mode =
            alt?.mode_default ||
            body?.applied_mode ||
            rec.mode ||
            modeSelect.value ||
            'open';
        const intensity =
            body?.applied_intensity != null ? body.applied_intensity : rec.intensity;
        const score = alt?.score != null ? alt.score : rec.experience_score;
        if (imageSeedRecommendTitle) imageSeedRecommendTitle.textContent = title;
        if (imageSeedRecommendMeta) {
            const parts = [`mode ${mode}`];
            if (intensity != null) parts.push(`intensity ${Number(intensity).toFixed(2)}`);
            if (score != null) parts.push(`score ${Number(score).toFixed(2)}`);
            if (alt?.rank) parts.push(`rank #${alt.rank}`);
            imageSeedRecommendMeta.textContent = parts.join(' · ');
        }
        if (syncAlt) populateAlternativeSelect(body);
        if (imageSeedRecommend) imageSeedRecommend.hidden = false;
    }

    function clearImageSeedRecommend() {
        imageSeedSuggest = null;
        imageSeedAlternatives = [];
        if (imageSeedRecommend) imageSeedRecommend.hidden = true;
        if (imageSeedRecommendTitle) imageSeedRecommendTitle.textContent = '';
        if (imageSeedRecommendMeta) imageSeedRecommendMeta.textContent = '';
        if (imageSeedAltSelect) {
            imageSeedAltSelect.innerHTML = '';
            imageSeedAltSelect.hidden = true;
        }
    }

    function applyRecommendedControls(body, { fromAlt = null } = {}) {
        const alt = fromAlt || selectedAlternative();
        const recExp =
            alt?.experience_id ||
            body.applied_experience_id ||
            body.recommended?.experience_id;
        if (recExp && experienceSelect) {
            const hasOpt = [...experienceSelect.options].some((o) => o.value === recExp);
            if (hasOpt) experienceSelect.value = recExp;
        }
        if (alt?.mode_default) modeSelect.value = alt.mode_default;
        else if (body.applied_mode) modeSelect.value = body.applied_mode;
        else if (body.recommended?.mode) modeSelect.value = body.recommended.mode;
        const intensity =
            body.applied_intensity != null
                ? body.applied_intensity
                : body.recommended?.intensity;
        if (intensity != null) {
            setExperienceIntensity(intensity);
        }
    }

    function imageSeedRequestFlags(body) {
        const useWinner = shouldApplyRecommendedWinner(body);
        return {
            apply_recommended: useWinner,
            experience_id: useWinner
                ? null
                : experienceSelect.value || selectedAlternative()?.experience_id || null,
        };
    }

    function readOptionalNumber(id) {
        const el = document.getElementById(id);
        if (!el) return null;
        const raw = String(el.value || '').trim();
        if (!raw) return null;
        const n = Number(raw);
        return Number.isFinite(n) ? n : null;
    }

    /** Optional I3 anchors for image-seed / export-journey (null when unset). */
    function readSpatiotemporalAnchors() {
        const latitude = readOptionalNumber('anchorLatitude');
        const longitude = readOptionalNumber('anchorLongitude');
        const year = readOptionalNumber('anchorYear');
        const hour = readOptionalNumber('anchorHour');
        const solar_elevation_deg = readOptionalNumber('anchorSolarElevation');
        if (
            latitude == null &&
            longitude == null &&
            year == null &&
            hour == null &&
            solar_elevation_deg == null
        ) {
            return null;
        }
        const out = {};
        if (latitude != null) out.latitude = latitude;
        if (longitude != null) out.longitude = longitude;
        if (year != null) out.year = Math.round(year);
        if (hour != null) out.hour = hour;
        if (solar_elevation_deg != null) out.solar_elevation_deg = solar_elevation_deg;
        return out;
    }

    /** Approximate solar elevation (degrees) — mirrors Python research plate. */
    function approximateSolarElevationDeg(latitude, longitude, hour, dayOfYear) {
        const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
        const lat = (clamp(latitude, -90, 90) * Math.PI) / 180;
        const lon = clamp(longitude, -180, 180);
        const doy = Math.max(1, Math.min(366, Math.round(dayOfYear)));
        const hr = ((hour % 24) + 24) % 24;
        const decl = ((23.45 * Math.PI) / 180) * Math.sin((2 * Math.PI * (284 + doy)) / 365);
        const localHour = (hr + lon / 15) % 24;
        const ha = ((localHour - 12) * 15 * Math.PI) / 180;
        const sinEl =
            Math.sin(lat) * Math.sin(decl) + Math.cos(lat) * Math.cos(decl) * Math.cos(ha);
        return (Math.asin(clamp(sinEl, -1, 1)) * 180) / Math.PI;
    }

    function solarDayFactorFromElevation(elev) {
        return Math.max(0, Math.min(1, (Number(elev) + 18) / 90));
    }

    /**
     * Live solar lighting modulator day factor (0–1) when the opt-in checkbox is on.
     * Uses explicit elevation, last normalized seed anchors, or a client-side plate.
     */
    function readSolarDayFactor() {
        const chk = document.getElementById('anchorSolarModulator');
        if (!chk || !chk.checked) return null;
        let elev = readOptionalNumber('anchorSolarElevation');
        if (elev == null && imageSeedState?.spatiotemporal_anchors?.solar_elevation_deg != null) {
            elev = Number(imageSeedState.spatiotemporal_anchors.solar_elevation_deg);
        }
        if (elev == null) {
            const a = readSpatiotemporalAnchors();
            if (a && a.latitude != null && a.longitude != null && a.hour != null) {
                elev = approximateSolarElevationDeg(a.latitude, a.longitude, a.hour, 172);
            }
        }
        if (elev == null || !Number.isFinite(elev)) return null;
        return Math.round(solarDayFactorFromElevation(elev) * 10000) / 10000;
    }

    function appendAnchorsToFormData(fd) {
        const a = readSpatiotemporalAnchors();
        if (!a) return;
        if (a.latitude != null) fd.append('latitude', String(a.latitude));
        if (a.longitude != null) fd.append('longitude', String(a.longitude));
        if (a.year != null) fd.append('year', String(a.year));
        if (a.hour != null) fd.append('hour', String(a.hour));
        if (a.solar_elevation_deg != null) fd.append('solar_elevation_deg', String(a.solar_elevation_deg));
    }

    function syncAnchorStatus(normalized) {
        const el = document.getElementById('anchorStatus');
        if (!el) return;
        const a = normalized || readSpatiotemporalAnchors();
        if (!a) {
            el.textContent = 'No anchors set';
            return;
        }
        if (normalized && normalized.solar_elevation_deg != null) {
            const src = normalized.solar_elevation_source || 'set';
            el.textContent = `Anchors active · solar ${Number(normalized.solar_elevation_deg).toFixed(1)}° (${src})`;
            return;
        }
        el.textContent = 'Anchors set · solar derives on server when lat/lon + hour present';
    }

    ;['anchorLatitude', 'anchorLongitude', 'anchorYear', 'anchorHour', 'anchorSolarElevation'].forEach((id) => {
        document.getElementById(id)?.addEventListener('input', () => {
            syncAnchorStatus();
            syncModulators();
        });
    });
    document.getElementById('anchorSolarModulator')?.addEventListener('change', () => {
        syncModulators();
        const el = document.getElementById('anchorStatus');
        const day = readSolarDayFactor();
        if (el && day != null) {
            el.textContent = `Live solar modulator on · day factor ${day.toFixed(2)}`;
        } else if (el) {
            syncAnchorStatus();
        }
    });
    syncAnchorStatus();

    function fileToBase64(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                const result = String(reader.result || '');
                const b64 = result.includes(',') ? result.split(',')[1] : result;
                resolve(b64);
            };
            reader.onerror = () => reject(reader.error || new Error('read failed'));
            reader.readAsDataURL(file);
        });
    }

    function syncModulators() {
        const img = imageSeedState ? imageInfluence() : 0;
        const mods = {
            camera: Number(modCamera?.value || 0),
            motion: Number(modMotion?.value || 0),
            midi: Number(modMidi?.value || 0),
            audio: Number(modAudio?.value || 0),
            haptics: Number(modHaptics?.value || 0),
            image: img,
        };
        const solar = readSolarDayFactor();
        if (solar != null) mods.solar = solar;
        player.setModulators(mods);
    }
    [modCamera, modMotion, modMidi, modAudio, modHaptics].forEach((el) =>
        el?.addEventListener('change', syncModulators),
    );

    imageSeedInfluence?.addEventListener('input', () => {
        if (imageSeedInfluenceValue) {
            imageSeedInfluenceValue.textContent = Number(imageSeedInfluence.value).toFixed(2);
        }
        syncModulators();
    });

    async function readImageFromUpload() {
        const file = imageSeedFile?.files && imageSeedFile.files[0];
        const imageReading = document.getElementById('imageReading');
        if (!file) {
            if (imageReading) imageReading.textContent = 'Choose an image first';
            return;
        }
        if (imageReading) imageReading.textContent = 'Reading…';
        try {
            const form = new FormData();
            form.append('file', file);
            const res = await fetch('/api/v1/visualize/image-reading', { method: 'POST', body: form });
            const body = await res.json().catch(() => ({}));
            if (!res.ok) {
                const detail = body.detail;
                const msg = (detail && (detail.detail || detail.error)) || res.statusText || 'Image reading failed';
                if (imageReading) imageReading.textContent = String(msg);
                return;
            }
            const caption = String(body.caption || '').slice(0, 2000);
            const disclaimer = String(body.disclaimer || '').slice(0, 500);
            if (imageReading) {
                imageReading.textContent = disclaimer ? caption + '\n' + disclaimer : caption;
            }
        } catch (err) {
            if (imageReading) imageReading.textContent = err.message || String(err);
        }
    }

    async function suggestImageSeedFormula() {
        const file = imageSeedFile?.files && imageSeedFile.files[0];
        if (!file) {
            setImageSeedUiState('error', 'Choose an image first');
            return;
        }
        setImageSeedUiState('loading', 'Suggesting formula…');
        try {
            const fd = new FormData();
            fd.append('file', file);
            fd.append('substance', substanceSelect.value || 'lsd');
            fd.append('mode', modeSelect.value || 'open');
            fd.append('intensity', String(getExperienceIntensity()));
            fd.append('influence', String(imageInfluence()));
            fd.append('include_preview', 'false');
            fd.append('include_source_field', 'false');
            fd.append('apply_recommended', 'true');
            fd.append('recommend_only', 'true');
            fd.append('recommend_top_n', '5');
            appendAnchorsToFormData(fd);
            const res = await fetch('/api/v1/visualize/image-seed', { method: 'POST', body: fd });
            const body = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(body.detail || res.statusText || 'suggest failed');
            }
            imageSeedSuggest = body;
            syncAnchorStatus(body.spatiotemporal_anchors);
            renderImageSeedRecommend(body, { syncAlt: true });
            if (imageSeedApplyRecommended?.checked) applyRecommendedControls(body);
            const n = (body.recommended_alternatives || []).length;
            const title = body.recommended?.experience_title || body.applied_experience_id || 'formula';
            setImageSeedUiState(
                'success',
                n > 1
                    ? `Suggested · ${title} (+${n - 1} alts) — pick, then Condition & load`
                    : `Suggested · ${title} — confirm, then Condition & load`,
            );
        } catch (err) {
            console.error(err);
            setImageSeedUiState('error', err.message || String(err));
        }
    }

    imageSeedFile?.addEventListener('change', () => {
        const file = imageSeedFile.files && imageSeedFile.files[0];
        imageSeedState = null;
        clearImageSeedHandoff();
        clearImageSeedRecommend();
        if (typeof player.clearImageHints === 'function') player.clearImageHints();
        showLocalImageSeedPreview(file || null);
        syncGpuLabLinks();
        syncModulators();
        if (!file) {
            setImageSeedUiState('idle', 'Idle');
            return;
        }
        setImageSeedUiState('idle', 'Image ready — suggesting formula…');
        suggestImageSeedFormula();
    });

    imageSeedClearBtn?.addEventListener('click', () => {
        imageSeedState = null;
        clearImageSeedHandoff();
        clearImageSeedRecommend();
        if (typeof player.clearImageHints === 'function') player.clearImageHints();
        if (imageSeedFile) imageSeedFile.value = '';
        showImageSeedPreview(null);
        syncGpuLabLinks();
        // Keep sim source plane if user still has that checkbox; only clear image plane when not bridging.
        if (!(sourcePlaneChk && sourcePlaneChk.checked && lastBridgeField)) {
            player.clearSourcePlane();
        } else {
            syncSourcePlaneUI();
        }
        syncModulators();
        const imageReading = document.getElementById('imageReading');
        if (imageReading) imageReading.textContent = '';
        setImageSeedUiState('idle', 'Image seed cleared');
    });

    async function conditionImageAndLoad() {
        const file = imageSeedFile?.files && imageSeedFile.files[0];
        if (!file) {
            setImageSeedUiState('error', 'Choose an image first');
            return;
        }
        setImageSeedUiState('loading', 'Conditioning image (Pass 1)…');
        const flags = imageSeedRequestFlags(imageSeedSuggest);
        const fd = new FormData();
        fd.append('file', file);
        fd.append('substance', substanceSelect.value || 'lsd');
        if (flags.experience_id) fd.append('experience_id', flags.experience_id);
        fd.append('mode', modeSelect.value || 'open');
        fd.append('intensity', String(getExperienceIntensity()));
        fd.append('influence', String(imageInfluence()));
        fd.append('include_preview', 'true');
        fd.append('include_source_field', 'true');
        fd.append('apply_recommended', flags.apply_recommended ? 'true' : 'false');
        fd.append('recommend_only', 'false');
        fd.append('recommend_top_n', '5');
        appendAnchorsToFormData(fd);
        try {
            const res = await fetch('/api/v1/visualize/image-seed', { method: 'POST', body: fd });
            const body = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(body.detail || res.statusText || 'image-seed failed');
            }
            const pickedId = flags.experience_id || body.applied_experience_id;
            imageSeedState = body;
            imageSeedSuggest = body;
            persistImageSeedHandoff(body);
            syncAnchorStatus(body.spatiotemporal_anchors);
            tryWriteSeed(body.master_seed >>> 0, { reason: 'Pass-1 seed' });
            renderImageSeedRecommend(body, { syncAlt: true });
            if (pickedId && imageSeedAltSelect) imageSeedAltSelect.value = pickedId;
            applyRecommendedControls(body, { fromAlt: selectedAlternative() });
            if (typeof player.setImageHints === 'function') {
                player.setImageHints(body.parameter_hints || null);
            }
            showImageSeedPreview(
                body.conditioned_preview_png_base64 || body.conditioned_texture_png_base64 || null,
            );
            if (body.source_field) {
                lastBridgeField = body.source_field;
                if (sourcePlaneChk) sourcePlaneChk.checked = true;
                if (sourcePlaneMix) {
                    const mix = Math.min(0.72, Math.max(0.18, imageInfluence() * 0.85));
                    sourcePlaneMix.value = String(mix);
                    if (sourcePlaneMixValue) sourcePlaneMixValue.textContent = mix.toFixed(2);
                }
                syncSourcePlaneUI();
            }
            syncModulators();
            syncGpuLabLinks();
            const recTitle = body.recommended?.experience_title || body.applied_experience_id || '';
            setImageSeedUiState(
                'success',
                recTitle
                    ? `Seed ${body.master_seed} · ${recTitle} · loading live field…`
                    : `Seed ${body.master_seed} · loading live field (Pass 2)…`,
            );
            loadBtn.click();
        } catch (err) {
            console.error(err);
            setImageSeedUiState('error', err.message || String(err));
        }
    }

    async function packageImageSeedJourney() {
        const file = imageSeedFile?.files && imageSeedFile.files[0];
        if (!file) {
            setImageSeedUiState('error', 'Choose an image first');
            return;
        }
        setImageSeedUiState('loading', 'Building seed → journey package…');
        try {
            const b64 = await fileToBase64(file);
            const flags = imageSeedRequestFlags(imageSeedSuggest || imageSeedState);
            const res = await fetch('/api/v1/visualize/image-seed-journey', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    image_base64: b64,
                    substance: substanceSelect.value || 'lsd',
                    experience_id: flags.experience_id,
                    mode: modeSelect.value || 'open',
                    intensity: getExperienceIntensity(),
                    influence: imageInfluence(),
                    apply_recommended: flags.apply_recommended,
                    recommend_top_n: 5,
                    include_preview: false,
                    include_source_field: false,
                    steps: 12,
                    quality_tier: (document.getElementById('qualityTierSelect')?.value) || 'balanced',
                    reduce_motion: !!reduceMotionChk?.checked,
                    dim_flashing: !!dimFlashChk?.checked,
                    spatiotemporal_anchors: readSpatiotemporalAnchors(),
                    planner_notes: plannerNotesValue(),
                }),
            });
            const body = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(body.detail || res.statusText || 'image-seed-journey failed');
            }
            imageSeedState = body.image_seed || null;
            if (imageSeedState) {
                imageSeedSuggest = imageSeedState;
                persistImageSeedHandoff(imageSeedState);
                syncAnchorStatus(imageSeedState.spatiotemporal_anchors);
                tryWriteSeed(imageSeedState.master_seed >>> 0, { reason: 'seed→journey' });
                renderImageSeedRecommend(imageSeedState, { syncAlt: true });
                applyRecommendedControls(imageSeedState, { fromAlt: selectedAlternative() });
                if (typeof player.setImageHints === 'function') {
                    player.setImageHints(imageSeedState.parameter_hints || null);
                }
            }
            const blob = new Blob([JSON.stringify(body, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `psyfi-seed-journey-${body.image_seed?.master_seed || 'export'}.json`;
            a.click();
            URL.revokeObjectURL(url);
            const promptLen = (body.journey?.t2v?.prompt || '').length;
            const hint = document.getElementById('t2vPromptHint');
            if (hint) {
                hint.hidden = false;
                hint.textContent = `Seed→journey downloaded · T2V prompt ${promptLen} chars (capture stills via Export journey).`;
            }
            syncModulators();
            syncGpuLabLinks();
            setImageSeedUiState(
                'success',
                `Journey packaged · seed ${body.image_seed?.master_seed ?? '—'}`,
            );
        } catch (err) {
            console.error(err);
            setImageSeedUiState('error', err.message || String(err));
        }
    }

    imageSeedAltSelect?.addEventListener('change', () => {
        const src = imageSeedSuggest || imageSeedState;
        if (!src) return;
        const alt = selectedAlternative();
        applyRecommendedControls(src, { fromAlt: alt });
        renderImageSeedRecommend(src, { syncAlt: false });
        const title = alt?.title || src.recommended?.experience_title || 'formula';
        setImageSeedUiState('success', `Selected · ${title} — Condition & load when ready`);
    });

    imageSeedSuggestBtn?.addEventListener('click', () => {
        suggestImageSeedFormula();
    });
    document.getElementById('imageReadingBtn')?.addEventListener('click', () => {
        readImageFromUpload();
    });
    imageSeedApplyBtn?.addEventListener('click', () => {
        conditionImageAndLoad();
    });
    imageSeedJourneyBtn?.addEventListener('click', () => {
        packageImageSeedJourney();
    });

    let neutralOn = false;
    let neutralExitArmedUntil = 0;
    const NEUTRAL_EXIT_ARM_MS = 2800;

    function clearNeutralExitArm() {
        neutralExitArmedUntil = 0;
        if (neutralOn) setButtonLabel(neutralBtn, 'Exit Neutral');
    }

    function applyNeutral(on) {
        neutralOn = !!on;
        player.neutral(neutralOn);
        clearNeutralExitArm();
        setButtonLabel(neutralBtn, neutralOn ? 'Exit Neutral' : 'Neutral');
        if (neutralBtn) neutralBtn.setAttribute('aria-pressed', neutralOn ? 'true' : 'false');
        statusEl.textContent = neutralOn ? 'Neutral view enabled' : 'Field restored';
    }

    neutralBtn.addEventListener('click', () => {
        if (!neutralOn) {
            // Enter Neutral is one-shot for safety.
            applyNeutral(true);
            return;
        }
        const now = Date.now();
        if (now <= neutralExitArmedUntil) {
            applyNeutral(false);
            return;
        }
        // Lever-style exit: first click arms, second confirms within window.
        neutralExitArmedUntil = now + NEUTRAL_EXIT_ARM_MS;
        neutralBtn.setAttribute('aria-pressed', 'true');
        setButtonLabel(neutralBtn, 'Confirm exit');
        statusEl.textContent = 'Confirm Neutral exit';
        window.setTimeout(() => {
            if (Date.now() >= neutralExitArmedUntil && neutralOn) {
                clearNeutralExitArm();
                neutralBtn.setAttribute('aria-pressed', 'false');
            }
        }, NEUTRAL_EXIT_ARM_MS + 50);
    });

    function syncCompareChrome() {
        const mode = compareModeSelect?.value || 'off';
        const hasPin = !!(player.pinned && player.pinned.frame);
        if (clearPinBtn) clearPinBtn.hidden = !hasPin;
        if (compareWipeGroup) compareWipeGroup.hidden = mode !== 'wipe';
        if (wipePositionValue && wipePositionRange) {
            wipePositionValue.textContent = Number(wipePositionRange.value).toFixed(2);
        }
    }

    pinFrameBtn?.addEventListener('click', () => {
        const pinned = player.pinFrame();
        if (!pinned) {
            statusEl.textContent = 'Load an experience before pinning';
            return;
        }
        syncCompareChrome();
        statusEl.textContent = `Pinned frame · ${pinned.frame.phase || pinned.idx}`;
    });

    clearPinBtn?.addEventListener('click', () => {
        player.clearPin();
        if (compareModeSelect) compareModeSelect.value = 'off';
        player.setCompareMode('off');
        syncCompareChrome();
        statusEl.textContent = 'Pin cleared';
    });

    compareModeSelect?.addEventListener('change', () => {
        const mode = compareModeSelect.value || 'off';
        if (mode !== 'off' && !(player.pinned && player.pinned.frame)) {
            const pinned = player.pinFrame();
            if (!pinned) {
                compareModeSelect.value = 'off';
                statusEl.textContent = 'Pin a frame before comparing';
                syncCompareChrome();
                return;
            }
        }
        player.setCompareMode(mode);
        if (mode === 'wipe' && wipePositionRange) {
            player.setWipePosition(Number(wipePositionRange.value));
        }
        syncCompareChrome();
        statusEl.textContent = mode === 'off' ? 'Compare off' : `Compare: ${mode}`;
    });

    wipePositionRange?.addEventListener('input', () => {
        player.setWipePosition(Number(wipePositionRange.value));
        syncCompareChrome();
    });

    syncCompareChrome();

    playBtn.addEventListener('click', () => {
        player.play();
        statusEl.textContent = player.phaseAdvance ? 'Field running · phase advance on' : 'Field running';
    });
    pauseBtn.addEventListener('click', () => {
        player.pause();
        statusEl.textContent = 'Field paused';
    });

    document.getElementById('regenSeedBtn')?.addEventListener('click', () => {
        tryWriteSeed(Math.floor(Math.random() * 1e9), { reason: 'regen' });
    });

    let seedLocked = false;
    let seedUnlockArmedUntil = 0;
    const SEED_UNLOCK_ARM_MS = 2800;
    const lockSeedBtn = document.getElementById('lockSeedBtn');
    const seedLockHint = document.getElementById('seedLockHint');
    const regenSeedBtn = document.getElementById('regenSeedBtn');

    function syncSeedLockChrome() {
        if (seedInput) {
            seedInput.readOnly = seedLocked;
            seedInput.classList.toggle('seed-locked', seedLocked);
            seedInput.setAttribute('aria-readonly', seedLocked ? 'true' : 'false');
        }
        if (regenSeedBtn) regenSeedBtn.disabled = seedLocked;
        if (lockSeedBtn) {
            lockSeedBtn.setAttribute('aria-pressed', seedLocked ? 'true' : 'false');
            setButtonLabel(
                lockSeedBtn,
                seedLocked
                    ? seedUnlockArmedUntil > Date.now()
                        ? 'Confirm unlock'
                        : 'Unlock seed'
                    : 'Lock seed',
            );
        }
        if (seedLockHint) {
            seedLockHint.textContent = seedLocked
                ? 'Seed locked · regen and Pass-1 overwrites blocked'
                : 'Seed unlocked · regen and Pass-1 may change it';
        }
    }

    function setSeedLocked(on) {
        seedLocked = !!on;
        seedUnlockArmedUntil = 0;
        syncSeedLockChrome();
        statusEl.textContent = seedLocked ? 'Master seed locked' : 'Master seed unlocked';
    }

    /** Write seed only when unlocked (or force); returns false if blocked. */
    function tryWriteSeed(value, { reason, force } = {}) {
        if (seedLocked && !force) {
            statusEl.textContent = reason
                ? `Seed locked — ${reason} ignored`
                : 'Seed locked — write ignored';
            return false;
        }
        if (seedInput) seedInput.value = String(value);
        syncGpuLabLinks();
        return true;
    }

    lockSeedBtn?.addEventListener('click', () => {
        if (!seedLocked) {
            setSeedLocked(true);
            return;
        }
        const now = Date.now();
        if (now <= seedUnlockArmedUntil) {
            setSeedLocked(false);
            return;
        }
        seedUnlockArmedUntil = now + SEED_UNLOCK_ARM_MS;
        syncSeedLockChrome();
        statusEl.textContent = 'Confirm seed unlock';
        window.setTimeout(() => {
            if (Date.now() >= seedUnlockArmedUntil && seedLocked) {
                seedUnlockArmedUntil = 0;
                syncSeedLockChrome();
            }
        }, SEED_UNLOCK_ARM_MS + 50);
    });

    syncSeedLockChrome();

    preferWebGLChk?.addEventListener('change', () => {
        player.setPreferWebGL(!!preferWebGLChk.checked);
        statusEl.textContent = `Renderer preference: ${player.backend}`;
    });

    const qualityTierSelect = document.getElementById('qualityTierSelect');
    qualityTierSelect?.addEventListener('change', () => {
        const tier = qualityTierSelect.value || 'balanced';
        statusEl.textContent = `Quality tier: ${tier} (reload experience to rematerialize)`;
        if (player.loadContext && typeof player.loadTimeline === 'function' && loadBtn && !loadBtn.disabled) {
            // Rematerialize current experience at the new tier when a timeline is loaded.
            loadBtn.click();
        }
    });

    sourcePlaneChk?.addEventListener('change', () => {
        syncSourcePlaneUI();
        statusEl.textContent = sourcePlaneChk.checked
            ? 'Sim source plane enabled'
            : 'Sim source plane cleared';
    });
    sourcePlaneMix?.addEventListener('input', () => {
        if (sourcePlaneMixValue) sourcePlaneMixValue.textContent = Number(sourcePlaneMix.value).toFixed(2);
        if (sourcePlaneChk?.checked && lastBridgeField) {
            player.setSourceMix(Number(sourcePlaneMix.value));
        }
    });

    if (phaseAdvanceChk) {
        player.setPhaseAdvance(!!phaseAdvanceChk.checked);
        phaseAdvanceChk.addEventListener('change', () => {
            player.setPhaseAdvance(!!phaseAdvanceChk.checked);
            statusEl.textContent = phaseAdvanceChk.checked
                ? 'Phase advance on'
                : 'Phase advance off · scrub still works';
        });
    }
    if (phaseSpeedSelect) {
        player.setPhaseSpeed(Number(phaseSpeedSelect.value) || 1);
        phaseSpeedSelect.addEventListener('change', () => {
            player.setPhaseSpeed(Number(phaseSpeedSelect.value) || 1);
            statusEl.textContent = `Phase speed ${phaseSpeedSelect.value}×`;
        });
    }

    phaseScrub?.addEventListener('input', () => {
        player.setPhaseIndex(Number(phaseScrub.value));
        const frame = player.timeline && player.timeline.frames[player.idx];
        if (phaseLabel && frame) phaseLabel.textContent = frame.phase || phaseScrub.value;
    });

    const sensorEnableSelect = document.getElementById('sensorEnableSelect');
    document.getElementById('sensorEnableBtn')?.addEventListener('click', () => {
        const key = sensorEnableSelect && sensorEnableSelect.value;
        const map = {
            camera: 'enableCameraBtn',
            motion: 'enableMotionBtn',
            audio: 'enableAudioBtn',
            midi: 'enableMidiBtn',
            gamepad: 'enableGamepadBtn',
            ambient: 'enableAmbientBtn',
            haptics: 'enableHapticsBtn',
        };
        const id = map[key];
        if (id) document.getElementById(id)?.click();
    });

    document.getElementById('exportTimelineBtn')?.addEventListener('click', () => {
        try {
            player.exportTimelineJson();
        } catch (err) {
            alert(err.message || String(err));
        }
    });
    document.getElementById('exportViewportBtn')?.addEventListener('click', () => {
        player.exportViewportPng();
    });

    let lastComparisonId = null;

    document.getElementById('archiveCompareBtn')?.addEventListener('click', async () => {
        const cs = window.PsyFiViz && window.PsyFiViz.compareSurface;
        if (!cs || !player.pinned) {
            statusEl.textContent = 'Pin a frame before archiving a comparison';
            return;
        }
        const live = player.frame || (player.timeline && player.timeline.frames && player.timeline.frames[player.idx]);
        const record = cs.makeArchiveRecord(
            player.pinned,
            live,
            player.idx,
            player.compareMode || compareModeSelect?.value || 'off',
            player.wipePosition,
            player.blinkHz,
            {
                substance: substanceSelect?.value || (live && live.substance) || null,
                experience_id: experienceSelect?.value || null,
                seed: Number(seedInput?.value) || null,
            },
        );
        if (!record) {
            statusEl.textContent = 'Could not build comparison archive';
            return;
        }
        try {
            await saveComparisonRecord(record);
            lastComparisonId = record.id;
            if (window.PsyFiCompareArchive && typeof window.PsyFiCompareArchive.refresh === 'function') {
                await window.PsyFiCompareArchive.refresh();
            }
            statusEl.textContent = `Comparison archived · ${record.id}`;
        } catch (err) {
            console.error(err);
            statusEl.textContent = 'Archive comparison failed';
            alert(err.message || String(err));
        }
    });

    function plannerNotesValue() {
        const el = document.getElementById('plannerNotesInput');
        const v = el && String(el.value || '').trim();
        return v || null;
    }

    function setPlannerStatus(text, show) {
        const el = document.getElementById('plannerStatus');
        if (!el) return;
        el.hidden = !show;
        el.textContent = text || '';
    }

    document.getElementById('runPlannerBtn')?.addEventListener('click', async () => {
        if (!player.timeline && !player.frame) {
            statusEl.textContent = 'Load an experience before running the planner';
            return;
        }
        try {
            const res = await fetch('/api/v1/visualize/planner', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    timeline: player.timeline || null,
                    parameter_field: player.frame || null,
                    experience_id: experienceSelect?.value || null,
                    spatiotemporal_anchors: readSpatiotemporalAnchors(),
                    notes: plannerNotesValue(),
                }),
            });
            const body = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(body.detail || res.statusText || 'planner failed');
            const motifs = (body.motifs || []).slice(0, 4).join(', ');
            setPlannerStatus(
                `${body.lighting_notes || ''} Motifs: ${motifs || '—'}`,
                true,
            );
            statusEl.textContent = `Planner · ${body.hash || 'ok'}`;
            if (provenanceEl && body.planner_text) {
                provenanceEl.replaceChildren(textEl('div', 'muted', body.planner_text));
            }
        } catch (err) {
            console.error(err);
            statusEl.textContent = 'Planner failed';
            alert(err.message || String(err));
        }
    });

    document.getElementById('saveJourneyBtn')?.addEventListener('click', async () => {
        if (!player.timeline) {
            statusEl.textContent = 'Load an experience before saving a journey';
            return;
        }
        try {
            const res = await fetch('/api/v1/visualize/journey', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    substance: substanceSelect?.value || 'lsd',
                    mode: modeSelect?.value || 'open',
                    intensity: getExperienceIntensity(),
                    seed: Number(seedInput?.value) || 42,
                    experience_id: experienceSelect?.value || null,
                    timeline: player.timeline,
                    parameter_field: player.frame || null,
                    spatiotemporal_anchors: readSpatiotemporalAnchors(),
                    notes: plannerNotesValue(),
                    planner_notes: plannerNotesValue(),
                    comparison_id: lastComparisonId || null,
                    title: experienceSelect?.selectedOptions?.[0]?.textContent || null,
                }),
            });
            const body = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(body.detail || res.statusText || 'journey failed');
            await saveJourneyRecord(body);
            if (window.PsyFiJourneyArchive?.refresh) await window.PsyFiJourneyArchive.refresh();
            setPlannerStatus(body.planner?.planner_text || 'Journey saved', true);
            statusEl.textContent = body.comparison_id
                ? `Journey saved · ${body.id} · compare ${body.comparison_id}`
                : `Journey saved · ${body.id}`;
        } catch (err) {
            console.error(err);
            statusEl.textContent = 'Save journey failed';
            alert(err.message || String(err));
        }
    });

    window.addEventListener('psyfi:restore-journey', async (ev) => {
        const record = ev && ev.detail;
        if (!record) return;
        if (record.substance && substanceSelect) substanceSelect.value = record.substance;
        if (record.mode && modeSelect) modeSelect.value = record.mode;
        if (record.intensity != null) setExperienceIntensity(record.intensity);
        if (record.seed != null) tryWriteSeed(record.seed, { force: true, reason: 'journey restore' });
        if (record.experience_id && experienceSelect) {
            const has = [...experienceSelect.options].some((o) => o.value === record.experience_id);
            if (has) experienceSelect.value = record.experience_id;
        }
        const notesEl = document.getElementById('plannerNotesInput');
        if (notesEl && record.notes != null) notesEl.value = String(record.notes);
        const anchors = record.spatiotemporal_anchors;
        if (anchors) {
            const setVal = (id, v) => {
                const el = document.getElementById(id);
                if (el && v != null) el.value = String(v);
            };
            setVal('anchorLatitude', anchors.latitude);
            setVal('anchorLongitude', anchors.longitude);
            setVal('anchorYear', anchors.year);
            setVal('anchorHour', anchors.hour);
            setVal('anchorSolarElevation', anchors.solar_elevation_deg);
            syncAnchorStatus(anchors);
            const solarChk = document.getElementById('anchorSolarModulator');
            if (solarChk && anchors.solar_elevation_deg != null) {
                solarChk.checked = true;
                syncModulators();
            }
        }
        if (record.planner?.planner_text) {
            setPlannerStatus(record.planner.planner_text, true);
            if (provenanceEl) {
                provenanceEl.replaceChildren(textEl('div', 'muted', record.planner.planner_text));
            }
        }
        if (record.comparison_id) lastComparisonId = record.comparison_id;

        statusEl.textContent = `Restoring journey · ${record.id}…`;
        try {
            if (loadBtn && !loadBtn.disabled) {
                player._pendingTransitionKind = 'journey';
                loadBtn.click();
                // Allow rematerialize to start; surface failures via player status.
                await new Promise((r) => setTimeout(r, 80));
            }
            let compareNote = '';
            if (record.comparison_id) {
                const cmp = await getComparisonRecord(record.comparison_id);
                if (cmp) {
                    window.dispatchEvent(new CustomEvent('psyfi:restore-comparison', { detail: cmp }));
                    compareNote = ` · compare ${record.comparison_id}`;
                } else {
                    compareNote = ` · compare ${record.comparison_id} missing locally`;
                }
            }
            statusEl.textContent = `Restored journey · ${record.id}${compareNote}`;
        } catch (err) {
            console.error(err);
            statusEl.textContent = `Journey restore failed · ${err.message || err}`;
        }
    });

    window.addEventListener('psyfi:restore-comparison', (ev) => {
        const record = ev && ev.detail;
        if (!record || !record.pinned || !record.pinned.frame) {
            statusEl.textContent = 'Invalid comparison archive';
            return;
        }
        const cs = window.PsyFiViz && window.PsyFiViz.compareSurface;
        const pin = cs
            ? cs.makePinPacket(record.pinned.frame, record.pinned.idx, record.pinned.timeline_hash)
            : {
                frame: record.pinned.frame,
                idx: record.pinned.idx | 0,
                hash: record.pinned.hash || null,
                timeline_hash: record.pinned.timeline_hash || null,
                at: record.pinned.at || null,
            };
        player.pinned = pin;
        if (player.renderer && typeof player.renderer.setPinnedFrame === 'function') {
            player.renderer.setPinnedFrame(pin.frame);
        }
        if (player.webgl && typeof player.webgl.setPinnedFrame === 'function') {
            player.webgl.setPinnedFrame(pin.frame);
        }
        const mode = record.mode && record.mode !== 'off' ? record.mode : 'split';
        if (compareModeSelect) compareModeSelect.value = mode;
        player.setCompareMode(mode);
        if (typeof record.wipe_position === 'number' && wipePositionRange) {
            wipePositionRange.value = String(record.wipe_position);
            player.setWipePosition(record.wipe_position);
        }
        if (typeof record.blink_hz === 'number') player.setBlinkHz(record.blink_hz);
        // Prefer setPhaseIndex when timeline exists; otherwise install one-frame live snapshot.
        if (record.live && record.live.frame && !(player.timeline && player.timeline.frames && player.timeline.frames.length)) {
            player.timeline = {
                frames: [record.live.frame],
                timeline_hash: record.pinned.timeline_hash || null,
                seed: record.seed,
                experience_id: record.experience_id || null,
            };
            player.setPhaseIndex(0);
        } else if (
            record.live &&
            record.live.hash &&
            player.timeline &&
            player.timeline.frames
        ) {
            const found = player.timeline.frames.findIndex((f) => f && f.hash === record.live.hash);
            if (found >= 0) {
                player.setPhaseIndex(found);
            }
        }
        syncCompareChrome();
        player.play();
        statusEl.textContent = `Restored comparison · ${mode} · ${record.id}`;
    });

    function imageSeedPayloadForJourney() {
        if (!imageSeedState) return null;
        return {
            master_seed: imageSeedState.master_seed,
            influence: imageSeedState.influence,
            features: imageSeedState.features,
            parameter_hints: imageSeedState.parameter_hints,
            spatiotemporal_anchors: imageSeedState.spatiotemporal_anchors || null,
        };
    }

    function waitForPaintFrames(n = 2) {
        return new Promise((resolve) => {
            let left = Math.max(1, n);
            const tick = () => {
                left -= 1;
                if (left <= 0) resolve();
                else requestAnimationFrame(tick);
            };
            requestAnimationFrame(tick);
        });
    }

    async function captureTimelineStills() {
        if (!player.timeline) throw new Error('Load an experience first');
        const stills = [];
        const frames = player.timeline.frames || [];
        const last = frames.length - 1;
        const picks = [0, Math.floor(last / 2), last].filter(
            (v, i, a) => a.indexOf(v) === i && v >= 0 && frames[v],
        );
        const prevIdx = player.idx;
        for (const idx of picks) {
            player.setPhaseIndex(idx);
            if (typeof player.render === 'function') {
                try {
                    player.render();
                } catch (_) {
                    /* optional redraw hook */
                }
            }
            await waitForPaintFrames(2);
            const target =
                player.backend === 'webgl' && player.glCanvas && !player.glCanvas.hidden
                    ? player.glCanvas
                    : player.canvas;
            const dataUrl = target.toDataURL('image/png');
            const b64 = dataUrl.includes(',') ? dataUrl.split(',')[1] : dataUrl;
            stills.push({
                id: `still_${idx}`,
                phase: frames[idx].phase,
                phase_t: frames[idx].phase_t,
                png_base64: b64,
            });
        }
        player.setPhaseIndex(prevIdx);
        await waitForPaintFrames(1);
        return stills;
    }

    async function fetchJourneyPromptOnly() {
        if (!player.timeline) throw new Error('Load an experience first');
        const res = await fetch('/api/v1/visualize/export-journey', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                timeline: player.timeline,
                stills: [],
                image_seed: imageSeedPayloadForJourney(),
                experience_id: experienceSelect.value || player.timeline.experience_id || null,
                t2v_provider: 'external',
                spatiotemporal_anchors: readSpatiotemporalAnchors(),
                planner_notes: plannerNotesValue(),
            }),
        });
        const body = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(body.detail || res.statusText || 'export-journey failed');
        return body;
    }

    document.getElementById('copyT2vPromptBtn')?.addEventListener('click', async () => {
        const hint = document.getElementById('t2vPromptHint');
        try {
            const body = await fetchJourneyPromptOnly();
            const prompt = body?.t2v?.prompt || '';
            if (!prompt) throw new Error('No prompt returned');
            if (navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(prompt);
            } else {
                const ta = document.createElement('textarea');
                ta.value = prompt;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                ta.remove();
            }
            if (hint) {
                hint.hidden = false;
                hint.textContent = `Copied T2V prompt (${prompt.length} chars) — paste into an external tool.`;
            }
            statusEl.textContent = 'T2V prompt copied';
        } catch (err) {
            console.error(err);
            if (hint) {
                hint.hidden = false;
                hint.textContent = err.message || String(err);
            }
            alert(err.message || String(err));
        }
    });

    let exportJourneyArmedUntil = 0;
    const EXPORT_JOURNEY_ARM_MS = 2800;
    const exportJourneyBtn = document.getElementById('exportJourneyBtn');

    async function runExportJourney() {
        const hint = document.getElementById('t2vPromptHint');
        statusEl.textContent = 'Building export journey…';
        try {
            const stills = await captureTimelineStills();
            const res = await fetch('/api/v1/visualize/export-journey', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    timeline: player.timeline,
                    stills,
                    image_seed: imageSeedPayloadForJourney(),
                    experience_id: experienceSelect.value || player.timeline.experience_id || null,
                    t2v_provider: 'external',
                    spatiotemporal_anchors: readSpatiotemporalAnchors(),
                    planner_notes: plannerNotesValue(),
                }),
            });
            const body = await res.json().catch(() => ({}));
            if (!res.ok) throw new Error(body.detail || res.statusText || 'export-journey failed');
            const blob = new Blob([JSON.stringify(body, null, 2)], { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `psyfi-journey-${body.timeline_hash || body.master_seed || 'export'}.json`;
            a.click();
            URL.revokeObjectURL(url);
            const promptLen = (body.t2v?.prompt || '').length;
            const stillCount = (body.stills || stills).length;
            if (hint) {
                hint.hidden = false;
                hint.textContent = `Journey downloaded · ${stillCount} stills · T2V prompt ${promptLen} chars (external).`;
            }
            statusEl.textContent = `Export journey ready · ${stillCount} stills`;
        } catch (err) {
            console.error(err);
            statusEl.textContent = 'Export journey failed';
            if (hint) {
                hint.hidden = false;
                hint.textContent = err.message || String(err);
            }
            alert(err.message || String(err));
        }
    }

    function clearExportJourneyArm() {
        exportJourneyArmedUntil = 0;
        if (exportJourneyBtn) {
            exportJourneyBtn.classList.remove('lever-armed');
            exportJourneyBtn.setAttribute('aria-pressed', 'false');
            setButtonLabel(exportJourneyBtn, 'Export journey');
        }
    }

    exportJourneyBtn?.addEventListener('click', async () => {
        if (!player.timeline) {
            alert('Load an experience first');
            return;
        }
        const now = Date.now();
        if (now <= exportJourneyArmedUntil) {
            clearExportJourneyArm();
            await runExportJourney();
            return;
        }
        // Lever-style commit: first click arms, second confirms within window.
        exportJourneyArmedUntil = now + EXPORT_JOURNEY_ARM_MS;
        if (exportJourneyBtn) {
            exportJourneyBtn.classList.add('lever-armed');
            exportJourneyBtn.setAttribute('aria-pressed', 'true');
            setButtonLabel(exportJourneyBtn, 'Confirm export');
        }
        statusEl.textContent = 'Confirm export journey (captures stills)';
        window.setTimeout(() => {
            if (Date.now() >= exportJourneyArmedUntil) clearExportJourneyArm();
        }, EXPORT_JOURNEY_ARM_MS + 50);
    });

    document.getElementById('bridgeSimBtn')?.addEventListener('click', async () => {
        statusEl.textContent = 'Bridging simulation field…';
        const last = window.PsyFiLastSim;
        try {
            let data;
            if (last?.visualization && last?.payload) {
                // Prefer last completed workspace simulation (no extra compute).
                const substance = last.substance || substanceSelect.value || 'lsd';
                if (substanceSelect && substance) substanceSelect.value = substance;
                const timeline = await player.loadTimeline({
                    substance,
                    experience_id: experienceSelect.value || null,
                    mode: modeSelect.value || 'open',
                    intensity: getExperienceIntensity(),
                    seed: Number(last.seed ?? seedInput.value) || 42,
                    steps: 12,
                    reduce_motion: !!reduceMotionChk.checked,
                    dim_flashing: !!dimFlashChk.checked,
                    quality_tier: (document.getElementById('qualityTierSelect')?.value) || 'balanced',
                });
                data = {
                    kind: 'field_frame',
                    seed: last.seed,
                    substance,
                    simulation: {
                        width: last.width,
                        height: last.height,
                        visualization: last.visualization,
                        provenance_id: last.provenance_id,
                        api_version: last.payload.api_version,
                        metrics: {
                            valence: last.payload.valence,
                            coherence: last.payload.coherence,
                            symmetry: last.payload.symmetry,
                            roughness: last.payload.roughness,
                            richness: last.payload.richness,
                        },
                    },
                    parameter_field: timeline.frames?.[0] || timeline.frame,
                    note: 'Bridged from last workspace simulation (cached visualization + fresh ParameterField).',
                };
                if (data.parameter_field) {
                    player.setFrame(data.parameter_field);
                    player.play();
                }
            } else {
                data = await player.loadFieldBridge({
                    width: 32,
                    height: 32,
                    steps: 4,
                    seed: Number(seedInput.value) || 42,
                    substance: substanceSelect.value || 'lsd',
                    preset: substanceSelect.value || 'lsd',
                    mode: modeSelect.value || 'open',
                    intensity: getExperienceIntensity(),
                });
                if (data.parameter_field) {
                    player.timeline = {
                        frames: [data.parameter_field],
                        timeline_hash: data.parameter_field.hash,
                        seed: data.seed,
                        experience_id: null,
                    };
                    player.setFrame(data.parameter_field);
                    player.play();
                }
            }
            lastBridgeField = data.simulation?.visualization?.field || null;
            if (lastBridgeField && sourcePlaneChk) {
                sourcePlaneChk.checked = true;
            }
            syncSourcePlaneUI();
            const bridgeNote = textEl('div', 'muted', data.note || '');
            provenanceEl.replaceChildren(
                provenanceLabeled('Bridge', 'simulation → ParameterField'),
                provenanceLabeled('Provenance', data.simulation?.provenance_id || '—'),
                provenanceLabeled('Field hash', data.parameter_field?.hash || '—'),
                provenanceLabeled(
                    'Source plane',
                    lastBridgeField && sourcePlaneChk?.checked ? 'on' : 'off',
                ),
                bridgeNote,
            );
            statusEl.textContent = lastBridgeField && sourcePlaneChk?.checked
                ? 'Simulation bridge loaded · source plane active'
                : 'Simulation bridge loaded';
        } catch (err) {
            console.error(err);
            statusEl.textContent = 'Bridge failed';
            alert(err.message || String(err));
        }
    });

    async function withSensorError(label, fn) {
        if (!sensorHub) {
            alert('Device sensor hub unavailable.');
            return;
        }
        try {
            await fn();
        } catch (err) {
            alert(`${label}: ${err.message || err}`);
        }
    }

    document.getElementById('enableAvailableSensorsBtn')?.addEventListener('click', async () => {
        await withSensorError('Sensors', async () => {
            const result = await sensorHub.enableAvailable();
            if (!result.enabled.length) {
                alert('No sensors could be enabled on this device. Use the manual sliders instead.');
            }
        });
    });
    document.getElementById('disableSensorsBtn')?.addEventListener('click', () => {
        sensorHub?.disableAll();
        syncModulators();
    });
    document.getElementById('enableCameraBtn')?.addEventListener('click', () =>
        withSensorError('Camera', () => sensorHub.enableCamera()),
    );
    document.getElementById('enableMotionBtn')?.addEventListener('click', () =>
        withSensorError('Motion', () => sensorHub.enableMotion()),
    );
    document.getElementById('enableAudioBtn')?.addEventListener('click', () =>
        withSensorError('Microphone', () => sensorHub.enableAudio()),
    );
    document.getElementById('enableMidiBtn')?.addEventListener('click', () =>
        withSensorError('Web MIDI', () => sensorHub.enableWebMidi()),
    );
    document.getElementById('enableGamepadBtn')?.addEventListener('click', () =>
        withSensorError('Gamepad', () => sensorHub.enableGamepad()),
    );
    document.getElementById('enableAmbientBtn')?.addEventListener('click', () =>
        withSensorError('Ambient light', () => sensorHub.enableAmbientLight()),
    );
    document.getElementById('enableHapticsBtn')?.addEventListener('click', () =>
        withSensorError('Haptics', () => sensorHub.enableHaptics()),
    );

    async function loadSubstances() {
        const res = await fetch('/api/v1/substances');
        const data = await res.json();
        substanceSelect.innerHTML = '';
        (data.substances || []).forEach((s) => {
            if (!s.recipe_count && !['lsd','psilocybin','dmt','mescaline','ketamine','5-meo-dmt'].includes(s.id)) return;
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = `${s.id} (${s.recipe_count || 0})`;
            substanceSelect.appendChild(opt);
        });
        if (!substanceSelect.value) {
            const opt = document.createElement('option');
            opt.value = 'lsd';
            opt.textContent = 'lsd';
            substanceSelect.appendChild(opt);
        }
        substanceSelect.value = 'lsd';
    }

    async function loadExperiences() {
        const substance = substanceSelect.value || 'lsd';
        const res = await fetch(`/api/v1/experiences?substance=${encodeURIComponent(substance)}&valence=positive`);
        const data = await res.json();
        experienceSelect.innerHTML = '';
        const items = data.items || [];
        if (!items.length) {
            const opt = document.createElement('option');
            opt.value = '';
            opt.textContent = 'No positive recipes';
            experienceSelect.appendChild(opt);
            return;
        }
        items.forEach((item) => {
            const opt = document.createElement('option');
            opt.value = item.id;
            opt.textContent = item.title || item.id;
            experienceSelect.appendChild(opt);
        });
        if (items[0] && items[0].mode_default) {
            modeSelect.value = items[0].mode_default;
        }
    }

    experienceSelect.addEventListener('change', async () => {
        const id = experienceSelect.value;
        if (!id) return;
        try {
            const res = await fetch(`/api/v1/experiences/${encodeURIComponent(id)}`);
            const data = await res.json();
            const mode = data.recipe && data.recipe.visual_recipe && data.recipe.visual_recipe.mode_default;
            if (mode) modeSelect.value = mode;
        } catch (e) {
            console.warn(e);
        }
    });

    substanceSelect.addEventListener('change', () => loadExperiences());

    loadBtn.addEventListener('click', async () => {
        loadBtn.disabled = true;
        statusEl.textContent = 'Loading timeline…';
        applyNeutral(false);
        syncModulators();
        try {
            const data = await player.loadTimeline({
                substance: substanceSelect.value || 'lsd',
                experience_id: experienceSelect.value || null,
                mode: modeSelect.value || 'open',
                intensity: getExperienceIntensity(),
                seed: Number(seedInput.value) || 42,
                steps: 20,
                reduce_motion: !!reduceMotionChk.checked,
                dim_flashing: !!dimFlashChk.checked,
                quality_tier: (document.getElementById('qualityTierSelect')?.value) || 'balanced',
                modulators: {
                    camera: Number(modCamera?.value || 0),
                    motion: Number(modMotion?.value || 0),
                    midi: Number(modMidi?.value || 0),
                    audio: Number(modAudio?.value || 0),
                    haptics: Number(modHaptics?.value || 0),
                    image: imageSeedState ? imageInfluence() : 0,
                },
                image_hints: imageSeedState?.parameter_hints || undefined,
            });
            if (phaseScrub && data.frames) {
                phaseScrub.disabled = false;
                phaseScrub.max = String(Math.max(0, data.frames.length - 1));
                phaseScrub.value = '0';
                if (phaseLabel) phaseLabel.textContent = data.frames[0].phase || 'comeup';
                if (phaseHint) phaseHint.textContent = 'Scrub to jump phases. Advance steps while playing.';
            }
            player.resize();
            player.play();
            statusEl.textContent = player.phaseAdvance
                ? 'Experience loaded · phase advance on'
                : 'Experience loaded';
            if (imageSeedState) {
                setImageSeedUiState('success', `Live field seeded from image · seed ${imageSeedState.master_seed}`);
            }
        } catch (err) {
            console.error(err);
            statusEl.textContent = 'Load failed';
            alert(err.message || String(err));
        } finally {
            loadBtn.disabled = false;
        }
    });

    document.addEventListener('keydown', (e) => {
        const tag = e.target && e.target.tagName;
        const inField =
            tag === 'INPUT' ||
            tag === 'SELECT' ||
            tag === 'TEXTAREA' ||
            tag === 'BUTTON' ||
            tag === 'A' ||
            (e.target && e.target.isContentEditable);
        if ((e.key === 'n' || e.key === 'N') && !inField) {
            neutralBtn.click();
            return;
        }
        // Space toggles blink compare when not typing / activating a control.
        if (e.code === 'Space' && !inField && compareModeSelect) {
            e.preventDefault();
            const next = compareModeSelect.value === 'blink' ? 'off' : 'blink';
            compareModeSelect.value = next;
            compareModeSelect.dispatchEvent(new Event('change'));
        }
    });

    loadSubstances()
        .then(loadExperiences)
        .then(() => loadBtn.click())
        .catch((e) => console.error('[PsyFi] experience init failed', e));
})();
