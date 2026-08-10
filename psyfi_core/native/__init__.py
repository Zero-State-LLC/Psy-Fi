"""Optional native numerical backend; Python remains semantically authoritative."""

from .backend import NativeBackendUnavailable, consciousness_omega, native_available

__all__ = ["NativeBackendUnavailable", "consciousness_omega", "native_available"]
