use num_complex::Complex32;

use crate::error::KernelError;

pub const MAX_ELEMENTS: usize = 16_777_216;
const EPSILON: f32 = 1.0e-8;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum CouplingType {
    Symmetric,
    Asymmetric,
}

#[derive(Clone, Copy, Debug)]
pub struct OmegaParams {
    pub coupling_type: CouplingType,
    pub coupling_strength: f32,
    pub natural_freq_base: f32,
    pub freq_depth_scale: f32,
    pub freq_brightness_scale: f32,
    pub steps: usize,
    pub dt: f32,
}

fn validate(
    field: &[Complex32],
    width: usize,
    height: usize,
    params: OmegaParams,
) -> Result<(), KernelError> {
    let elements = width
        .checked_mul(height)
        .ok_or(KernelError::AllocationTooLarge)?;
    if width == 0 || height == 0 || field.is_empty() {
        return Err(KernelError::EmptyField);
    }
    if elements > MAX_ELEMENTS || elements != field.len() {
        return Err(KernelError::AllocationTooLarge);
    }
    if field
        .iter()
        .any(|value| !value.re.is_finite() || !value.im.is_finite())
    {
        return Err(KernelError::NonFiniteInput);
    }
    if params.steps == 0 {
        return Err(KernelError::InvalidParameter("steps"));
    }
    for (name, value) in [
        ("coupling_strength", params.coupling_strength),
        ("natural_freq_base", params.natural_freq_base),
        ("freq_depth_scale", params.freq_depth_scale),
        ("freq_brightness_scale", params.freq_brightness_scale),
        ("dt", params.dt),
    ] {
        if !value.is_finite() {
            return Err(KernelError::InvalidParameter(name));
        }
    }
    if !(0.0..=2.0).contains(&params.coupling_strength) || params.dt <= 0.0 {
        return Err(KernelError::InvalidParameter("range"));
    }
    Ok(())
}

pub fn evolve(
    field: &[Complex32],
    width: usize,
    height: usize,
    params: OmegaParams,
) -> Result<Vec<Complex32>, KernelError> {
    validate(field, width, height, params)?;

    let magnitudes: Vec<f32> = field.iter().map(|value| value.norm()).collect();
    let mut phases: Vec<f32> = field.iter().map(|value| value.arg()).collect();
    let max_magnitude = magnitudes.iter().copied().fold(f32::NEG_INFINITY, f32::max);
    let mut natural_frequency = vec![0.0; field.len()];
    for y in 0..height {
        let depth = y as f32 / height as f32;
        for x in 0..width {
            let index = y * width + x;
            natural_frequency[index] = params.natural_freq_base
                + params.freq_depth_scale * depth
                + params.freq_brightness_scale * magnitudes[index] / (max_magnitude + EPSILON);
        }
    }

    let mut next = vec![0.0; phases.len()];
    for _ in 0..params.steps {
        for y in 0..height {
            let up = if y == 0 { height - 1 } else { y - 1 };
            let down = if y + 1 == height { 0 } else { y + 1 };
            for x in 0..width {
                let left = if x == 0 { width - 1 } else { x - 1 };
                let right = if x + 1 == width { 0 } else { x + 1 };
                let index = y * width + x;
                let neighbors = [
                    up * width + x,
                    down * width + x,
                    y * width + left,
                    y * width + right,
                ];
                let coupling = match params.coupling_type {
                    CouplingType::Symmetric => {
                        neighbors
                            .iter()
                            .map(|&other| (phases[other] - phases[index]).sin())
                            .sum::<f32>()
                            / 4.0
                    }
                    CouplingType::Asymmetric => {
                        let total = neighbors
                            .iter()
                            .map(|&other| magnitudes[other])
                            .sum::<f32>()
                            + EPSILON;
                        neighbors
                            .iter()
                            .map(|&other| magnitudes[other] * (phases[other] - phases[index]).sin())
                            .sum::<f32>()
                            / total
                    }
                };
                next[index] = phases[index]
                    + params.dt * (natural_frequency[index] + params.coupling_strength * coupling);
            }
        }
        std::mem::swap(&mut phases, &mut next);
    }

    Ok(phases
        .iter()
        .zip(magnitudes.iter())
        .map(|(&phase, &magnitude)| {
            Complex32::from_polar(magnitude, phase.sin().atan2(phase.cos()))
        })
        .collect())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn params() -> OmegaParams {
        OmegaParams {
            coupling_type: CouplingType::Symmetric,
            coupling_strength: 0.5,
            natural_freq_base: 1.0,
            freq_depth_scale: 0.5,
            freq_brightness_scale: 0.1,
            steps: 2,
            dt: 0.1,
        }
    }

    #[test]
    fn repeated_execution_is_identical() {
        let field = vec![
            Complex32::new(1.0, 0.0),
            Complex32::new(0.0, 1.0),
            Complex32::new(1.0, 0.0),
            Complex32::new(0.0, 1.0),
        ];
        let first = evolve(&field, 2, 2, params()).unwrap();
        let second = evolve(&field, 2, 2, params()).unwrap();
        assert_eq!(first, second);
    }

    #[test]
    fn rejects_non_finite_input() {
        let field = vec![Complex32::new(f32::NAN, 0.0)];
        assert_eq!(
            evolve(&field, 1, 1, params()),
            Err(KernelError::NonFiniteInput)
        );
    }
}
