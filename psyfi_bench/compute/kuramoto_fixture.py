"""Reference fixture for the browser WGSL Kuramoto kernel (``webgpu_kernel`` stage).

The fixture is a 32x32 field from ``psyfi_core.simulation.initial_field`` (seed 1337)
and the same field after 10 symmetric Kuramoto steps through the canonical numpy
``evolve_consciousness_omega``, both as float32 real/imaginary planes in JSON. The
browser runner evolves the initial field with a WGSL kernel and reports its max abs
error against the evolved planes; Python re-judges that error against
``KERNEL_TOLERANCE``. The GPU result never feeds back into a simulation.

Regenerate (writes the committed file)::

    python -m psyfi_bench.compute.kuramoto_fixture

``tests/bench/test_webgpu_kernel.py`` regenerates it in memory and checks the committed
file still matches within ``REGENERATION_ATOL``.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

from psyfi_bench.environment import REPO_ROOT
from psyfi_bench.schemas import stable_hash
from psyfi_core import ABXRuntime
from psyfi_core.engines import ConsciousnessOmegaParams, evolve_consciousness_omega
from psyfi_core.simulation import SimulationSettings, initial_field

FIXTURE_SCHEMA = "psyfi.bench.kuramoto_fixture.v1"
FIXTURE_ID = "kuramoto.symmetric.32x32.seed1337.steps10"
FIXTURE_NAME = "kuramoto.seed1337.32x32.v1.json"
# The scorer's copy ships as package data (psyfi_bench/fixtures/*.json), so an installed
# psyfi_bench can validate captures without the repo checkout.
FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / FIXTURE_NAME
# The bench page bundles its own copy; the generator writes both and a test keeps them identical.
BENCH_PAGE_FIXTURE_PATH = REPO_ROOT / "packages" / "psyfi-gpu-renderer" / "src" / "bench" / "fixtures" / FIXTURE_NAME
WIDTH = 32
HEIGHT = 32
SEED = 1337
STEPS = 10
KERNEL_NAME = "kuramoto_symmetric_step"

# Declared max abs error of the GPU-evolved complex field (real and imaginary parts)
# against the numpy reference. Same value as the torch accelerator manifest's
# ``accelerator_atol``. It covers float32-only arithmetic (numpy mixes a float64
# natural frequency into the update) and WGSL's sin accuracy bound (absolute 2^-11 on
# [-pi, pi], about 4.9e-4 per call, damped by K*dt/4 per step); a formula slip (a
# missing /4, depth y/(H-1), dt 0.11, K 0.55) moves the field by 2e-2 or more, while a
# float32 emulation of the kernel lands within 1e-6.
KERNEL_TOLERANCE = 1e-3
# The committed fixture must reproduce within this when regenerated on another machine
# (libm and SIMD paths differ in the last bits of sin/cos/exp, never by this much).
REGENERATION_ATOL = 1e-5


def reference_params() -> ConsciousnessOmegaParams:
    """Symmetric Kuramoto params exactly as ``simulate_field`` builds them with default settings."""
    settings = SimulationSettings()
    return ConsciousnessOmegaParams(
        coupling_type="symmetric",
        coupling_strength=settings.coupling_strength,
        steps=STEPS,
        dt=settings.dt,
    )


def _f32_list(arr: np.ndarray) -> list[float]:
    # Shortest decimal that round-trips the float32 value (Math.fround restores it exactly).
    return [float(np.format_float_positional(np.float32(v), unique=True, trim="-")) for v in np.asarray(arr, dtype=np.float32).ravel()]


def build_kuramoto_fixture() -> dict[str, Any]:
    params = reference_params()
    runtime = ABXRuntime(deterministic=True, seed=SEED)
    field = initial_field(runtime, WIDTH, HEIGHT)
    evolved = evolve_consciousness_omega(field, params, None)
    planes = {
        "initial": {"re": _f32_list(field.real), "im": _f32_list(field.imag)},
        "evolved": {"re": _f32_list(evolved.real), "im": _f32_list(evolved.imag)},
    }
    return {
        "schema": FIXTURE_SCHEMA,
        "id": FIXTURE_ID,
        "kernel": KERNEL_NAME,
        "generator": "psyfi_bench.compute.kuramoto_fixture.build_kuramoto_fixture (initial_field + numpy evolve_consciousness_omega)",
        "seed": SEED,
        "width": WIDTH,
        "height": HEIGHT,
        "steps": STEPS,
        "params": {
            "coupling_type": params.coupling_type,
            "coupling_strength": params.coupling_strength,
            "dt": params.dt,
            "natural_freq_base": params.natural_freq_base,
            "freq_depth_scale": params.freq_depth_scale,
            "freq_brightness_scale": params.freq_brightness_scale,
        },
        "dtype": "float32",
        "layout": "row-major, index = y * width + x (numpy axis 0 is y)",
        "tolerance": {
            "max_abs_error": KERNEL_TOLERANCE,
            "compared": "real and imaginary parts of the evolved complex field",
        },
        "content_hash": stable_hash(planes),
        **planes,
    }


def fixture_text(doc: dict[str, Any]) -> str:
    """Metadata pretty-printed, each float plane on one line (keeps the file and its diffs small)."""
    lines = ["{"]
    keys = list(doc)
    for i, key in enumerate(keys):
        comma = "," if i < len(keys) - 1 else ""
        value = doc[key]
        if key in ("initial", "evolved"):
            inner = ",\n".join(f'    "{k}": {json.dumps(v, separators=(",", ":"))}' for k, v in value.items())
            lines.append(f'  "{key}": {{\n{inner}\n  }}{comma}')
        else:
            lines.append(f'  "{key}": {json.dumps(value)}{comma}')
    lines.append("}")
    return "\n".join(lines) + "\n"


def load_committed_fixture(path: Path = FIXTURE_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_fixture(path: Path = FIXTURE_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fixture_text(build_kuramoto_fixture()), encoding="utf-8")
    return path


if __name__ == "__main__":  # pragma: no cover
    targets = [Path(sys.argv[1])] if len(sys.argv) > 1 else [FIXTURE_PATH, BENCH_PAGE_FIXTURE_PATH]
    for target in targets:
        print(f"written {write_fixture(target)}", file=sys.stderr)
