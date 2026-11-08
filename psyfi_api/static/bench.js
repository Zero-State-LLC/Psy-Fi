/**
 * FieldLoop bench results page (/bench). Read only: GET /api/bench/v1/results and
 * /api/bench/v1/results/{run_id}, plus a scorecard file the operator opens.
 *
 * Every value from the API or a file reaches the page through textContent, never innerHTML.
 * measurement_class and hardware_class sit beside every number; a scorecard is ranked only
 * when its own validity.comparable is true.
 */
(function () {
  'use strict';

  const API = '/api/bench/v1';
  const STAT_PREFERENCE = ['wall_ms', 'frame_ms', 'latency_ms', 'end_to_end_ms'];
  const NOT_EVIDENCE = new Set(['synthetic', 'replay']);

  // One or two headline numbers per family, read from result.metrics (index entry `headline`).
  const HEADLINES = {
    field_compute: [
      ['peak_cell_steps_per_s', 'peak', 'cell-steps/s'],
      ['scaling.exponent', 'scaling exponent', ''],
    ],
    interpretation: [
      ['fde_mean', 'FDE mean', 'field L1'],
      ['parse_rate', 'parse rate', ''],
    ],
    fieldloop: [
      ['e2e_ms_median', 'end to end median', 'ms'],
      ['fde_median', 'FDE median', 'field L1'],
    ],
    render: [
      ['per_tier.ultra.fps_avg_median', 'ultra fps median', 'fps'],
      ['per_tier.ultra.raster_ms_per_megapixel_median', 'ultra raster', 'ms/MP'],
    ],
  };

  const $ = (id) => document.getElementById(id);
  const compact = new Intl.NumberFormat('en', { notation: 'compact', maximumSignificantDigits: 3 });
  const plain = new Intl.NumberFormat('en', { maximumSignificantDigits: 4 });

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const [key, value] of Object.entries(attrs)) {
        if (value === undefined || value === null || value === false) continue;
        if (key === 'text') node.textContent = String(value);
        else if (key === 'class') node.className = value;
        else node.setAttribute(key, value === true ? '' : String(value));
      }
    }
    for (const child of [].concat(children || [])) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  }

  // The phone layout restacks rows into cards and prints each cell's column head beside it.
  function labelCells(rows, head) {
    for (const row of rows) {
      [...row.children].forEach((cell, i) => cell.setAttribute('data-label', head[i] || ''));
    }
    return rows;
  }

  const RESULTS_HEAD = ['Run', 'Workload', 'Status', 'Evidence', 'Hardware', 'Headline'];

  function pick(obj, path) {
    return String(path)
      .split('.')
      .reduce((value, key) => (value && typeof value === 'object' ? value[key] : undefined), obj);
  }

  function formatNumber(value) {
    if (typeof value !== 'number' || !Number.isFinite(value)) return null;
    const abs = Math.abs(value);
    if (abs !== 0 && abs < 0.001) return value.toExponential(2);
    if (abs >= 100000) return compact.format(value);
    return plain.format(value);
  }

  function formatValue(value) {
    if (value === null || value === undefined) return 'not recorded';
    if (typeof value === 'number') return formatNumber(value) ?? 'not finite';
    if (typeof value === 'boolean') return value ? 'yes' : 'no';
    if (Array.isArray(value)) return value.map(formatValue).join(', ');
    return String(value);
  }

  function formatTime(iso) {
    if (!iso) return 'time not recorded';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return String(iso);
    return `${date.toISOString().slice(0, 16).replace('T', ' ')} UTC`;
  }

  function evidenceTag(measurementClass) {
    const cls = measurementClass || 'unknown';
    const notEvidence = NOT_EVIDENCE.has(cls);
    return el('span', {
      class: 'bench-tag',
      'data-tone': cls === 'measured' ? 'measured' : notEvidence ? 'not-evidence' : null,
      title: notEvidence ? 'Never hardware or model evidence' : null,
      text: notEvidence ? `${cls}, not evidence` : cls,
    });
  }

  function statusTag(status) {
    const tone = status === 'failed' ? 'failed' : status === 'partial' ? 'partial' : null;
    return el('span', { class: 'bench-tag', 'data-tone': tone, text: status || 'unknown' });
  }

  function hardwareText(entry) {
    const parts = [entry.hardware_class || 'unknown class'];
    if (entry.cpu) parts.push(entry.cpu);
    for (const gpu of entry.gpus || []) {
      if (gpu && gpu !== entry.cpu) parts.push(gpu);
    }
    return parts.join(', ');
  }

  function headlineText(family, metrics) {
    const lines = [];
    for (const [path, label, unit] of HEADLINES[family] || []) {
      const shown = formatNumber(pick(metrics, path));
      if (shown !== null) lines.push(`${label} ${shown}${unit ? ` ${unit}` : ''}`);
    }
    return lines.length ? lines.join('; ') : 'see the run';
  }

  async function api(path, signal) {
    let response;
    try {
      response = await fetch(path, { headers: { Accept: 'application/json' }, signal });
    } catch (err) {
      if (signal?.aborted) throw err;
      throw new Error(`Could not reach the bench API (${err.message}).`);
    }
    let body = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    if (!response.ok) {
      const message = body?.error?.message || body?.detail || `HTTP ${response.status}`;
      if (response.status === 404 && !body?.error) {
        throw new Error(`The bench API is not served on this host yet (HTTP 404 at ${path}).`);
      }
      throw new Error(`The bench API answered ${response.status}: ${message}`);
    }
    return body;
  }

  // ----- Results list -----

  // Only the newest list request and the newest run request may render: each new one aborts the last.
  const state = { selected: null, entries: [], listRequest: null, runRequest: null };

  function supersede(key) {
    state[key]?.abort();
    const controller = new AbortController();
    state[key] = controller;
    return controller;
  }

  function showResultsError(message) {
    $('benchResultsWrap').hidden = true;
    $('benchResultsEmpty').hidden = true;
    const box = $('benchResultsError');
    box.textContent = message;
    box.hidden = false;
    $('benchResultsStatus').textContent = 'The results could not be read.';
  }

  function renderResults(entries) {
    const body = $('benchResultsBody');
    body.replaceChildren();
    $('benchResultsError').hidden = true;
    const family = $('benchFamily').value;
    if (!entries.length) {
      $('benchResultsWrap').hidden = true;
      $('benchResultsEmpty').hidden = false;
      $('benchResultsStatus').textContent = family ? `No ${family} results on this host.` : 'No results on this host.';
      return;
    }
    $('benchResultsEmpty').hidden = true;
    $('benchResultsWrap').hidden = false;
    $('benchResultsStatus').textContent = `${entries.length} ${entries.length === 1 ? 'run' : 'runs'}, newest first.`;
    for (const entry of entries) {
      const selected = entry.run_id === state.selected;
      const button = el('button', { type: 'button', class: 'bench-row-button', 'aria-pressed': selected ? 'true' : 'false', 'data-run-id': entry.run_id }, [
        el('span', { text: formatTime(entry.created_at) }),
        el('span', { class: 'bench-run-id', text: entry.run_id }),
      ]);
      button.addEventListener('click', () => selectRun(entry.run_id));
      body.append(...labelCells([
        el('tr', { 'data-selected': selected ? 'true' : 'false' }, [
          el('td', null, button),
          el('td', null, el('span', null, [
            el('span', { text: entry.manifest_id || 'unknown workload' }),
            el('span', { class: 'bench-muted', text: entry.manifest_version ? ` v${entry.manifest_version}` : '' }),
          ])),
          el('td', null, statusTag(entry.status)),
          el('td', null, evidenceTag(entry.measurement_class)),
          el('td', { text: hardwareText(entry) }),
          el('td', { text: headlineText(entry.family, entry.headline) }),
        ]),
      ], RESULTS_HEAD));
    }
  }

  async function loadResults() {
    const family = $('benchFamily').value;
    const query = new URLSearchParams({ limit: '100' });
    if (family) query.set('family', family);
    $('benchResultsStatus').textContent = 'Reading the results on this host.';
    $('benchRefresh').setAttribute('aria-busy', 'true');
    const request = supersede('listRequest');
    try {
      const doc = await api(`${API}/results?${query}`, request.signal);
      if (state.listRequest !== request) return;
      state.entries = Array.isArray(doc?.results) ? doc.results : [];
      renderResults(state.entries);
    } catch (err) {
      if (state.listRequest !== request) return;
      showResultsError(err.message);
    } finally {
      if (state.listRequest === request) $('benchRefresh').removeAttribute('aria-busy');
    }
  }

  // ----- One run -----

  function dl(rows) {
    const list = el('dl', { class: 'bench-dl' });
    for (const [label, value] of rows) {
      if (value === undefined) continue;
      list.append(el('dt', { text: label }), el('dd', null, value instanceof Node ? value : formatValue(value)));
    }
    return list;
  }

  function primaryStatistic(stage) {
    const stats = stage.statistics || {};
    const key = STAT_PREFERENCE.find((name) => stats[name]) || Object.keys(stats)[0];
    return key ? [key, stats[key]] : [null, null];
  }

  function stagesTable(stages) {
    const rows = stages.map((stage) => {
      const [name, stat] = primaryStatistic(stage);
      const ci = Array.isArray(stat?.ci95_median) ? stat.ci95_median.map(formatNumber).join(' to ') : 'not recorded';
      return el('tr', null, [
        el('td', null, el('span', null, [el('span', { text: stage.id }), stage.error ? el('span', { class: 'bench-stage-error', text: stage.error }) : null])),
        el('td', { text: stage.kind || '' }),
        el('td', null, statusTag(stage.status === 'ok' ? 'complete' : stage.status)),
        el('td', null, evidenceTag(stage.measurement_class)),
        el('td', { text: name ? `${name}${stat?.unit ? ` (${stat.unit})` : ''}` : 'no statistics' }),
        el('td', { text: stat ? formatValue(stat.n) : '' }),
        el('td', { text: stat ? formatValue(stat.median) : '' }),
        el('td', { text: stat ? formatValue(stat.p95) : '' }),
        el('td', { text: stat ? ci : '' }),
      ]);
    });
    const head = ['Stage', 'Kind', 'Status', 'Evidence', 'Statistic', 'n', 'Median', 'p95', '95% CI of the median'];
    labelCells(rows, head);
    return el('div', { class: 'bench-table-wrap' }, el('table', { class: 'bench-table' }, [
      el('caption', { class: 'visually-hidden', text: 'Stages of this run' }),
      el('thead', null, el('tr', null, head.map((h) => el('th', { scope: 'col', text: h })))),
      el('tbody', null, rows),
    ]));
  }

  function scalarMetrics(metrics, prefix = '', depth = 0, out = []) {
    for (const [key, value] of Object.entries(metrics || {})) {
      const path = prefix ? `${prefix}.${key}` : key;
      if (value && typeof value === 'object' && !Array.isArray(value)) {
        if (depth < 2) scalarMetrics(value, path, depth + 1, out);
      } else if (typeof value === 'number' || typeof value === 'boolean' || typeof value === 'string') {
        out.push([path, value]);
      }
    }
    return out;
  }

  function renderRun(result) {
    const env = result.environment || {};
    const manifest = result.manifest || {};
    const notEvidence = NOT_EVIDENCE.has(result.measurement_class);
    const unavailable = Object.entries(env.unavailable || {});
    const metrics = scalarMetrics(result.metrics).slice(0, 24);
    const failures = Array.isArray(result.failures) ? result.failures : [];
    const commit = result.provenance?.git_commit;

    const sections = [
      el('div', null, [
        el('h3', { text: `${manifest.title || manifest.id || 'Workload'}${manifest.version ? ` v${manifest.version}` : ''}` }),
        dl([
          ['Run', el('span', { class: 'bench-run-id', text: result.run_id })],
          ['Created', formatTime(result.created_at)],
          ['Status', statusTag(result.status)],
          ['Evidence', el('span', { class: 'bench-tags' }, [evidenceTag(result.measurement_class), notEvidence ? el('span', { class: 'bench-muted', text: 'Synthetic and replay runs are never hardware or model evidence.' }) : null])],
          ['Workload', `${manifest.id || 'unknown'}${manifest.version ? ` v${manifest.version}` : ''}`],
          ['Manifest hash', el('span', { class: 'bench-seal', text: result.manifest_hash || 'not recorded' })],
          ['Hardware class', env.hardware_class || 'unknown'],
          ['CPU', env.cpu?.brand],
          ['GPUs', (env.gpus || []).map((gpu) => gpu?.name).filter(Boolean).join(', ') || 'none recorded'],
          ['Browser adapter', env.browser?.adapter_classified ?? undefined],
          ['Bench version', result.bench_version],
          ['Commit', commit ? `${String(commit).slice(0, 7)}${result.provenance?.git_dirty ? ', with local changes' : ''}` : undefined],
        ]),
      ]),
      el('div', null, [
        el('h3', { text: 'Not collected' }),
        unavailable.length
          ? el('ul', { class: 'bench-list' }, unavailable.map(([key, reason]) => el('li', null, [el('code', { text: key }), ` ${reason}`])))
          : el('p', { class: 'bench-help', text: 'The environment record lists nothing it could not collect.' }),
      ]),
      el('div', null, [
        el('h3', { text: 'Headline metrics' }),
        metrics.length ? dl(metrics.map(([key, value]) => [key, value])) : el('p', { class: 'bench-help', text: 'This run recorded no headline metrics.' }),
      ]),
      el('div', null, [el('h3', { text: 'Stages' }), stagesTable(Array.isArray(result.stages) ? result.stages : [])]),
      failures.length
        ? el('div', null, [
            el('h3', { text: 'Failures' }),
            el('ul', { class: 'bench-list' }, failures.map((f) => el('li', null, [el('code', { text: `${f.stage || 'run'} ${f.category || ''}`.trim() }), ` ${f.detail || ''}`]))),
          ])
        : null,
      el('div', null, [
        el('h3', { text: 'Seal' }),
        el('p', { class: 'bench-seal', text: result.result_hash || 'no seal recorded' }),
        el('p', { class: 'bench-help' }, ['Check it with ', el('code', { text: 'python3 -m psyfi_bench validate <file>' }), '.']),
      ]),
      result.non_claim ? el('p', { class: 'bench-nonclaim', text: result.non_claim }) : null,
    ];

    const body = $('benchDetailBody');
    body.replaceChildren(...sections.filter(Boolean));
    body.hidden = false;
    $('benchDetailEmpty').hidden = true;
  }

  async function selectRun(runId) {
    state.selected = runId;
    renderResults(state.entries);
    const status = $('benchDetailStatus');
    status.textContent = `Reading run ${runId}.`;
    const request = supersede('runRequest');
    try {
      const result = await api(`${API}/results/${encodeURIComponent(runId)}`, request.signal);
      // A slower answer for a run the operator has since moved off must not overwrite the current one.
      if (state.runRequest !== request || state.selected !== runId) return;
      renderRun(result);
      status.textContent = `Showing run ${runId}.`;
      const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      $('benchDetail').scrollIntoView({ block: 'start', behavior: reduce ? 'auto' : 'smooth' });
    } catch (err) {
      if (state.runRequest !== request || state.selected !== runId) return;
      $('benchDetailBody').hidden = true;
      $('benchDetailEmpty').hidden = false;
      status.textContent = err.message;
    }
  }

  // ----- Scorecard file -----

  function bestLabels(cells, better) {
    const scored = cells.filter(([, cell]) => typeof cell?.value === 'number' && Number.isFinite(cell.value));
    if (scored.length < 2) return new Set();
    const target = better === 'higher' ? Math.max(...scored.map(([, c]) => c.value)) : Math.min(...scored.map(([, c]) => c.value));
    return new Set(scored.filter(([, c]) => c.value === target).map(([label]) => label));
  }

  function renderScorecard(card) {
    const subjects = Array.isArray(card.subjects) ? card.subjects : [];
    const labels = subjects.map((s) => s.label);
    const validity = card.validity || {};
    const comparable = validity.comparable === true;
    const reasons = Array.isArray(validity.reasons) ? validity.reasons : [];

    const validityBox = el('div', { class: 'bench-validity', 'data-comparable': comparable ? 'true' : 'false' }, [
      el('p', { text: comparable ? 'Comparable: the subjects share a manifest hash and the scorecard allows a ranking.' : 'Not comparable. This page does not rank these subjects.' }),
      reasons.length ? el('ul', { class: 'bench-list' }, reasons.map((r) => el('li', { text: r }))) : null,
      validity.rule ? el('p', { class: 'bench-muted', text: `Rule: ${validity.rule}` }) : null,
    ]);

    const subjectRows = subjects.map((s) => el('tr', null, [
      el('td', { text: s.label }),
      el('td', null, el('span', { class: 'bench-run-id', text: s.run_id || '' })),
      el('td', null, evidenceTag(s.measurement_class)),
      el('td', null, statusTag(s.status)),
      el('td', { text: hardwareText(s) }),
      el('td', { text: [s.provider, s.backend].filter(Boolean).join(', ') || 'none' }),
    ]));

    const dimensionRows = Object.entries(card.dimensions || {}).map(([name, perSubject]) => {
      const cells = labels.map((label) => [label, perSubject?.[label]]);
      const any = cells.find(([, c]) => c)?.[1] || {};
      const best = comparable ? bestLabels(cells, any.better) : new Set();
      return el('tr', null, [
        el('td', null, el('span', null, [el('span', { text: name }), el('span', { class: 'bench-muted', text: ` ${[any.unit, any.better ? `${any.better} is better` : ''].filter(Boolean).join(', ')}` })])),
        ...cells.map(([label, cell]) => {
          if (!cell || typeof cell.value !== 'number') {
            return el('td', { class: 'bench-muted', text: cell?.missing_reason ? `missing: ${cell.missing_reason}` : 'missing' });
          }
          const ci = Array.isArray(cell.ci95) ? ` (95% CI ${cell.ci95.map(formatNumber).join(' to ')})` : '';
          return el('td', { class: best.has(label) ? 'bench-best' : null }, [
            `${formatValue(cell.value)}${ci}`,
            best.has(label) ? el('span', { class: 'visually-hidden', text: ' best' }) : null,
          ]);
        }),
      ]);
    });

    const table = (caption, head, rows) => el('div', { class: 'bench-table-wrap' }, el('table', { class: 'bench-table' }, [
      el('caption', { class: 'visually-hidden', text: caption }),
      el('thead', null, el('tr', null, head.map((h) => el('th', { scope: 'col', text: h })))),
      el('tbody', null, labelCells(rows, head)),
    ]));

    const recommendations = comparable && Array.isArray(card.recommendations) ? card.recommendations : [];
    const body = $('benchScorecardBody');
    body.replaceChildren(...[
      el('div', null, [
        el('h3', { text: `${card.family || 'Scorecard'}${card.manifest_id ? `, ${card.manifest_id}` : ''}` }),
        dl([
          ['Generated', formatTime(card.generated_at)],
          ['Manifest hash', el('span', { class: 'bench-seal', text: card.manifest_hash || (validity.manifest_hashes || []).join(', ') || 'not recorded' })],
        ]),
      ]),
      validityBox,
      el('div', null, [el('h3', { text: 'Subjects' }), table('Scorecard subjects', ['Label', 'Run', 'Evidence', 'Status', 'Hardware', 'Provider'], subjectRows)]),
      el('div', null, [el('h3', { text: 'Dimensions' }), table('Scorecard dimensions per subject', ['Dimension', ...labels], dimensionRows)]),
      recommendations.length ? el('div', null, [el('h3', { text: 'Recommendations' }), el('ul', { class: 'bench-list' }, recommendations.map((r) => el('li', { text: r })))]) : null,
      card.non_claim ? el('p', { class: 'bench-nonclaim', text: card.non_claim }) : null,
    ].filter(Boolean));
    body.hidden = false;
    $('benchScorecardError').hidden = true;
    $('benchScorecardStatus').textContent = `${subjects.length} ${subjects.length === 1 ? 'subject' : 'subjects'}, ${comparable ? 'comparable' : 'not comparable'}.`;
  }

  function scorecardError(message) {
    $('benchScorecardBody').hidden = true;
    const box = $('benchScorecardError');
    box.textContent = message;
    box.hidden = false;
    $('benchScorecardStatus').textContent = '';
  }

  async function openScorecard(file) {
    if (!file) return;
    let card;
    try {
      card = JSON.parse(await file.text());
    } catch (err) {
      scorecardError(`${file.name} is not JSON (${err.message}).`);
      return;
    }
    if (!card || card.schema !== 'psyfi.bench.scorecard.v1') {
      scorecardError(`${file.name} is not a psyfi.bench.scorecard.v1 document.`);
      return;
    }
    renderScorecard(card);
  }

  // ----- Wiring -----

  document.addEventListener('DOMContentLoaded', () => {
    $('benchFamily').addEventListener('change', loadResults);
    $('benchRefresh').addEventListener('click', loadResults);
    $('benchScorecardFile').addEventListener('change', (event) => openScorecard(event.target.files?.[0]));
    loadResults();
  });
})();
