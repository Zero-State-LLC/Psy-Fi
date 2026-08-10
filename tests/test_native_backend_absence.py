"""Backend absence behavior runs even when the extension is not installed."""

import numpy as np
import pytest

from psyfi_core.native import NativeBackendUnavailable
from psyfi_core.native import backend as backend_module


def test_explicit_native_absence_fails_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(backend_module, "_load_native", lambda: None)
    with pytest.raises(NativeBackendUnavailable, match="psyfi-native is not installed"):
        backend_module.consciousness_omega(
            np.ones((1, 1), dtype=np.complex64),
            coupling_type="symmetric",
            coupling_strength=0.5,
            natural_freq_base=1.0,
            freq_depth_scale=0.5,
            freq_brightness_scale=0.1,
            steps=1,
            dt=0.1,
            reference=lambda: np.ones((1, 1), dtype=np.complex64),
            backend="native",
        )
