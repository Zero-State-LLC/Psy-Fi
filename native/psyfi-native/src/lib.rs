mod consciousness_omega;
mod error;

use consciousness_omega::{CouplingType, OmegaParams, MAX_ELEMENTS};
use num_complex::Complex32;
use numpy::{PyArray2, PyReadonlyArray2, PyUntypedArrayMethods};
use pyo3::prelude::*;

#[pyfunction]
#[pyo3(name = "consciousness_omega")]
#[pyo3(signature = (field, coupling_type, coupling_strength, natural_freq_base, freq_depth_scale, freq_brightness_scale, steps, dt))]
// The explicit primitive FFI signature is intentional: Rust must not acquire a
// Psy-Fi domain object merely to satisfy an internal argument-count heuristic.
#[allow(clippy::too_many_arguments)]
fn py_consciousness_omega<'py>(
    py: Python<'py>,
    field: PyReadonlyArray2<'py, Complex32>,
    coupling_type: &str,
    coupling_strength: f32,
    natural_freq_base: f32,
    freq_depth_scale: f32,
    freq_brightness_scale: f32,
    steps: usize,
    dt: f32,
) -> PyResult<Bound<'py, PyArray2<Complex32>>> {
    let coupling_type = match coupling_type {
        "symmetric" => CouplingType::Symmetric,
        "asymmetric" => CouplingType::Asymmetric,
        _ => return Err(error::KernelError::InvalidParameter("coupling_type").into()),
    };
    let shape = field.shape();
    let height = shape[0];
    let width = shape[1];
    let elements = width
        .checked_mul(height)
        .ok_or(error::KernelError::AllocationTooLarge)?;
    if elements > MAX_ELEMENTS {
        return Err(error::KernelError::AllocationTooLarge.into());
    }
    let values: Vec<Complex32> = field.as_array().iter().copied().collect();
    let params = OmegaParams {
        coupling_type,
        coupling_strength,
        natural_freq_base,
        freq_depth_scale,
        freq_brightness_scale,
        steps,
        dt,
    };
    let result = consciousness_omega::evolve(&values, width, height, params)?;
    let rows: Vec<Vec<Complex32>> = result.chunks(width).map(<[Complex32]>::to_vec).collect();
    PyArray2::from_vec2(py, &rows).map_err(Into::into)
}

#[pymodule]
fn psyfi_native(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(py_consciousness_omega, module)?)?;
    Ok(())
}
