use pyo3::exceptions::PyValueError;
use pyo3::PyErr;

#[derive(Debug, PartialEq)]
pub enum KernelError {
    EmptyField,
    NonFiniteInput,
    InvalidParameter(&'static str),
    AllocationTooLarge,
}

impl From<KernelError> for PyErr {
    fn from(error: KernelError) -> Self {
        PyValueError::new_err(format!("psyfi-native: {error:?}"))
    }
}
