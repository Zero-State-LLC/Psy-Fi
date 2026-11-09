# Discrete GPU handoff

Written 2026-11-08 at `main` `712ed31`. Use it on the first machine with a discrete GPU. It says what the machine can close, how to set it up, what to run in what order, and what to bring back.

A person has to be at the machine for step 2 onward: the browser run needs a focused tab, and steps 3 and 4 are theirs to call.

## Where things stand

| | |
| --- | --- |
| Code | `main` at `712ed31`. No open pull requests. |
| Live host | psy-fi.space on Worker version `25fdefd7`, built from `58d3b79`. Nothing here needs a deploy. |
| Measured so far | One Apple M5, integrated class ([`MEASUREMENTS.md`](MEASUREMENTS.md)). Never Ultra evidence. |
| Built, never run on real hardware | `nvidia-smi` power sampling (#59), energy per frame (#70, [ADR 0011](adr/0011-host-power-trace-for-browser-captures.md)), the torch CUDA path. All tested only against fakes. |

## What this machine can close

| Machine | #53 CUDA check | #48 WebGPU capture | Real power and energy | #10 Ultra evidence |
| --- | --- | --- | --- | --- |
| Physical desktop, NVIDIA RTX 30/40/50, display 120 Hz or faster | Yes | Yes | Yes | Yes, once the operator says so |
| Physical desktop, AMD RX 6000+ or Intel Arc | No | Yes | No | Yes, once the operator says so |
| Laptop with an NVIDIA GPU, plugged in | Yes | Yes | If `nvidia-smi` reports power | No |
| Cloud NVIDIA passthrough (T4, A10G, rented 4090) | Yes | Yes, labelled "discrete, datacenter, remote-displayed" | If `nvidia-smi` reports power | No |
| Time-sliced vGPU | Do not use it as evidence | | | |

#10 needs a consumer card on physical silicon with a high-refresh display ([`DESKTOP_GPU.md`](../DESKTOP_GPU.md), register entry 3). Its pass bar is 120 fps, which a 60 Hz display cannot reach.

## Set up

You need git, Python 3.12 (3.10 is the minimum; CI uses 3.12), Node 22, Chrome or Edge, and current GPU drivers. `gh auth login` if you will post results.

```bash
git clone https://github.com/Zero-State-LLC/Psy-Fi.git
cd Psy-Fi
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
npm ci
npm run gpu:build
```

On Windows, clone with `git clone -c core.autocrlf=false <url>` so fixtures keep their bytes, create the venv with `python -m venv .venv`, and activate it with `.venv\Scripts\Activate.ps1`. Every command below uses `python`, which is the venv's.

NVIDIA only: install torch from the selector at <https://pytorch.org/get-started/locally/>. On Windows, plain `pip install torch` gets a CPU-only build.

Then check the machine:

```bash
python -m pytest -q tests
npm run gpu:test
python -m psyfi_bench env
nvidia-smi --query-gpu=name,driver_version,power.draw,power.draw.instant --format=csv
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))"
```

- At `712ed31` on macOS: 336 Python tests passed, 2 skipped, and 123 GPU tests passed. CI runs Linux. The suite has never run on Windows, so a Windows-only failure does not block the runs below; report it.
- pytest rewrites `tests/fixtures/qa/simulated_ultra_qa.v1.json`. Run `git checkout -- tests/fixtures/qa/simulated_ultra_qa.v1.json` before committing.
- If `nvidia-smi` rejects `power.draw.instant` (older drivers fail the whole query), or shows `[N/A]` or `[Not Supported]` for it, that is not fatal. The sampler falls back to `power.draw`, a 1 s average on Ampere and newer. Query `power.draw` alone to check it. If that has no number either, this GPU cannot report power.
- `AGENTS.md` tells agents to use `trail`. Its index is not committed, so run `trail build` first. If `trail` is not installed, use `grep`.

No key, token or Cloudflare login is needed for steps 1 to 3.

## Run in this order

### 1. CUDA validation and real power (#53)

NVIDIA only. No browser.

```bash
python -m psyfi_bench run field-compute.accelerator --backend torch-cuda --min-duration 3
```

`--min-duration 3` keeps each stage running long enough to report energy per cell-step. Without it, fast stages stay under the 1 s rule and report no per-unit energy. It does not change the manifest hash.

- **It passes when** the command exits 0 and every stage has `within_tolerance` true, meaning `pipeline_max_abs_error` is at or under `atol` (1e-3). MPS on an Apple M5 was 1.3e-6.
- **Over tolerance:** the stage fails by design. Report it. Do not loosen the tolerance.
- **`skipped: yes`, or every stage errors on CUDA:** torch is not installed, or it cannot see the GPU. Go back to the `torch.cuda.is_available()` check in setup.
- **Power:** each stage has `stage.power` with `power_w_mean` and `energy_j_per_work_unit`, or an `unavailable_reason` saying why not.

This closes #53 and gives the first real run of the #59 sampler.

### 2. WebGPU capture with energy per frame (#48)

Get the machine ready:

- Plug it in, stop it from sleeping, and close other GPU work.
- Force the browser onto the discrete GPU (Windows: Settings, System, Display, Graphics, High performance). `chrome://gpu` should say WebGPU is hardware accelerated.
- Set the display to 120 to 165 Hz and write the rate down. Each stage measures 240 frames and per-frame energy needs at least 1 s, so 240 Hz is borderline and anything faster loses it.

Then, in this order, all on this machine:

```bash
# Terminal 1
python scripts/run_dev_server.py

# Terminal 2, NVIDIA only: start this before pressing Run
python -m psyfi_bench power-trace --out trace.json
```

Open <http://localhost:8000/gpu/bench.html> fresh, right before the run. The browser clock does not follow wall-clock changes made after the page loads. Press **Run (13 stages) + kernel**, keep the tab focused and visible, and wait for it to finish. Press **Download capture**. Then stop the trace with Ctrl-C a few seconds later, and score it:

```bash
python -m psyfi_bench ingest <path to psyfi-fieldloop-gpu-capture-*.json> --power-trace trace.json
python -m psyfi_bench validate <result file printed above>
python -m psyfi_bench report <result file>
```

On AMD or Intel, leave out `--power-trace`.

Check the result:

| Field | Want |
| --- | --- |
| `status` and `measurement_class` | `complete` and `measured` |
| `environment.hardware_class` | `discrete` |
| `metrics.adapter` | Your discrete GPU, not an integrated one |
| `metrics.per_tier` | Tier fidelity (SSIM against this device's own Ultra frame) |
| `metrics.sustained` and the sustained stage | Drift over the 1800-frame run |
| `metrics.timestamp_query` | Whether GPU timing was available |
| `metrics.power_trace.stages_with_energy_per_frame` | Above 0 on NVIDIA |
| `stages[].metrics.power_unavailable` | Empty, or a reason you can act on |

This closes #48 once fidelity and drift are reported. It is also the first real proof of #70.

### 3. Hardware Ultra fps (#10): only if the operator says so

#10 stays in Backlog and is not an agent ticket. It is a separate path from FieldLoop, and FieldLoop results never go into these fixtures. On a qualifying physical desktop, the operator follows [`HARDWARE_ULTRA_FPS.md`](../HARDWARE_ULTRA_FPS.md): open `/gpu/?measure_fps=1&tier=ultra`, keep the tab focused for about 3 s, then run `python scripts/merge_ultra_fps_measured.py <download>` and `npm run gpu:test`, and update [`BROWSER_CAPABILITY_MATRIX.md`](../BROWSER_CAPABILITY_MATRIX.md).

### 4. Local vision model (#49): optional

#49 needs one measured result per locality. A discrete GPU makes the local half possible with any OpenAI-compatible vision server. Run the smoke workload (28 posts) first:

```bash
python -m psyfi_bench run interpretation.fieldread.smoke --provider "openai:http://localhost:8080#<model>" --record receipt-local.json
```

The remote half spends the NVIDIA key and is the operator's to run. See register entry 4. Never print or commit a key or model id, and do not commit receipts.

## What to bring back

- **Commit:** a new dated section in [`MEASUREMENTS.md`](MEASUREMENTS.md), in the shape of the first one: a machine table (GPU, driver, OS, browser, display rate, git commit, hardware class), then numbers copied from the reports, each with its `run_id` and `result_hash`. Update register entries 3 and 6 and the ticket table in [`docs/specs/README.md`](../specs/README.md).
- **Post on the issue:** the `run_id`, `result_hash`, the headline table, and which `query` field the power came from.
- **Do not commit:** `bench_results/`, captures, `trace.json` or receipts. Committing a measured result as a fixture needs an accepted intent ([`ROADMAP.md`](ROADMAP.md)). The #10 fixture is the one exception, through its merge script.
- **Keep the sealed files.** Copy them off the machine before it goes away. Nothing else holds them.
- **Open a pull request** into `main`. Docs only, so no deploy.

## If something goes wrong

| Symptom | Meaning | Do this |
| --- | --- | --- |
| `torch.cuda.is_available()` is False | CPU-only torch, or a driver mismatch | Reinstall torch from the selector |
| Adapter shows Intel UHD, Iris or similar | The browser is on the integrated GPU | Force High performance and restart the browser |
| `the capture's adapter vendor is unknown` or `GPU vendor ... is not the capture adapter's vendor` | No power is written | Same fix, then run again |
| `hostname_hash ... differs` | The trace came from another machine | Run the trace and the ingest where the page ran |
| `does not reach this stage's window` | The trace started late or stopped early | Start it before Run and stop it after the download |
| `stage window ... shorter than 1 s` | The display is too fast for 240 frames | Lower the refresh rate |
| `samples span ... under 90%` | Too few sensor readings landed in the window | Close other GPU work and run again. A single stage doing this is not a failure |
| A stage fails with `uncaught renderer errors` | Frames are not trustworthy, by design | Capture the console and file an issue. Do not edit the result |
| `gpu_ms_unavailable` | The browser did not expose timestamp-query | Note it. Frame times still count |
| Frame times pinned at 16.7 ms | The display or a remote session is capping `requestAnimationFrame` | Check the refresh rate. On cloud, record it as remote-displayed |

## Rules that still hold

- A number goes in a doc only if it came from a sealed result on this machine. Nothing is estimated or adjusted.
- Compare only identical `manifest_hash`. Fidelity is within one device, never across devices.
- A cloud or laptop result is never Ultra evidence.
- Do not touch tolerances, locked references or the Ultra fixtures to make a run pass.
- [`HANDOFF.md`](../../HANDOFF.md) section 3 applies. Do not admin-merge unless a human asks.
- Modeled phenomenology for research and visualization only. Not medical advice.
