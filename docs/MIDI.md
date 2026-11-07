# PsyFi MIDI Integration Guide

**Applied Alchemy Labs - ABX-Core v1.3**

Real-time MIDI control for consciousness field simulation.

---

## Overview

PsyFi includes comprehensive MIDI integration for real-time control of consciousness field parameters using hardware controllers, DAWs, or software synthesizers. The MIDI system is bidirectional:

- **Input**: Control PsyFi parameters via MIDI controllers (CC, notes, program changes)
- **Output**: Export field metrics as MIDI data for music production or analysis

---

## Installation

`mido` and `python-rtmidi` are part of the default install. They are listed in the package dependencies, not as an extra. Installing Psy-Fi installs them:

```bash
pip install -e .
```

---

## Quick Start

### 1. List Available MIDI Devices

```bash
curl http://localhost:8000/api/midi/devices
```

**Response:**
```json
{
  "input": ["Launchpad Mini", "IAC Driver Bus 1"],
  "output": ["Launchpad Mini", "IAC Driver Bus 1"],
  "midi_available": true
}
```

### 2. Start MIDI Service

```bash
curl -X POST http://localhost:8000/api/midi/start \
  -H "Content-Type: application/json" \
  -d '{
    "input_device": "Launchpad Mini",
    "output_device": null,
    "channel": 0,
    "velocity_curve": "linear",
    "cc_smooth_factor": 0.1
  }'
```

### 3. Check Status

```bash
curl http://localhost:8000/api/midi/status
```

**Response:**
```json
{
  "running": true,
  "input_device": "Launchpad Mini",
  "output_device": null,
  "channel": 0,
  "current_params": {
    "phase_noise": 0.45,
    "coupling_strength": 0.7,
    "drift_amplitude": 0.3
  }
}
```

---

## MIDI Control Mappings

### Control Change (CC) → Parameter Mappings

Default mappings from `MIDIControlMap` in `psyfi_core/midi/service.py`:

| CC # | Controller           | PsyFi Parameter      | Range   | Description                           |
|------|----------------------|----------------------|---------|---------------------------------------|
| 1    | Modulation Wheel     | `phase_noise`        | 0.0-1.0 | Phase field noise intensity           |
| 2    | Breath Controller    | `drift_amplitude`    | 0.0-1.0 | Phase drift amplitude                 |
| 4    | Foot Controller      | `drift_velocity`     | 0.0-1.0 | Phase drift velocity                  |
| 7    | Volume               | `coupling_strength`  | 0.0-1.0 | Kuramoto oscillator coupling (CC path)|
| 10   | Pan                  | `normalization_P`    | 0.0-1.0 | Divisive-norm exponent (normalized)   |
| 11   | Expression           | `normalization_V`    | 0.0-1.0 | Surround suppression strength         |
| 16   | General Purpose 1    | `symmetry_bias`      | 0.0-1.0 | Visual symmetry bias                  |
| 17   | General Purpose 2    | `depth_distortion`   | 0.0-1.0 | Depth distortion                      |
| 18   | General Purpose 3    | `valence_bias`       | 0.0-1.0 | Affective valence bias                |
| 19   | General Purpose 4    | `arousal_level`      | 0.0-1.0 | Arousal level                         |

**Example**: Moving the modulation wheel (CC1) from 0 to 127 will smoothly increase `phase_noise` from 0.0 to 1.0.

### Note → Preset Mappings

Trigger substance presets via MIDI notes (C4 = 60):

| Note | Note Name | Preset         | Description                    |
|------|-----------|----------------|--------------------------------|
| 60   | C4        | baseline       | Default baseline state         |
| 61   | C#4       | lsd            | LSD (5-HT2A agonist)          |
| 62   | D4        | psilocybin     | Psilocybin (classic tryptamine)|
| 63   | D#4       | dmt            | DMT (breakthrough intensity)   |
| 64   | E4        | 5-meo-dmt      | 5-MeO-DMT                      |
| 65   | F4        | ketamine       | Ketamine (NMDA antagonist)     |
| 66   | F#4       | mdma           | MDMA (empathogen)              |
| 67   | G4        | mescaline      | Mescaline (phenethylamine)     |
| 68   | G#4       | 2c-b           | 2C-B (visual psychedelic)      |
| 69   | A4        | jhana          | Meditative jhana state         |
| 70   | A#4       | rem_dream      | REM sleep dreaming             |

**Velocity Sensitivity**: Note velocity (0-127) controls preset intensity (0.0-1.0).

### Program Change → Class Mappings

| Program # | Substance Class        | Description                  |
|-----------|------------------------|------------------------------|
| 0         | baseline               | Default/sober state          |
| 1         | classic_psychedelic    | Classic psychedelics         |
| 2         | dissociative           | NMDA antagonists             |
| 3         | empathogen             | Serotonin releasers          |
| 4         | meditative             | Meditative states            |

---

## API Reference

### List MIDI Devices

```http
GET /api/midi/devices
```

**Response:**
```json
{
  "input": ["Device 1", "Device 2"],
  "output": ["Device 1", "Device 2"],
  "midi_available": true
}
```

---

### Start MIDI Service

```http
POST /api/midi/start
Content-Type: application/json

{
  "input_device": "Optional device name or null for default",
  "output_device": "Optional device name or null for none",
  "channel": 0,
  "velocity_curve": "linear",
  "cc_smooth_factor": 0.1
}
```

**Parameters:**
- `input_device` (optional): MIDI input device name or null for default
- `output_device` (optional): MIDI output device name or null for none
- `channel` (0-15): MIDI channel to listen on (default: 0)
- `velocity_curve` ("linear" | "exponential" | "logarithmic"): Note velocity response
- `cc_smooth_factor` (0.0-1.0): Exponential smoothing for CC values (default: 0.1)

**Response:**
```json
{
  "status": "started",
  "message": "MIDI service started successfully"
}
```

---

### Stop MIDI Service

```http
POST /api/midi/stop
```

**Response:**
```json
{
  "status": "stopped",
  "message": "MIDI service stopped successfully"
}
```

---

### Get MIDI Status

```http
GET /api/midi/status
```

**Response:**
```json
{
  "running": true,
  "input_device": "Launchpad Mini",
  "output_device": null,
  "channel": 0,
  "current_params": {
    "phase_noise": 0.45,
    "coupling_strength": 0.7
  }
}
```

---

### Get Control Mappings

```http
GET /api/midi/mappings
```

**Response:**
```json
{
  "cc_to_param": {
    "1": "phase_noise",
    "7": "coupling_strength",
    "10": "normalization_P"
  },
  "note_to_preset": {
    "60": "baseline",
    "61": "lsd",
    "62": "psilocybin",
    "64": "5-meo-dmt"
  },
  "program_to_class": {
    "0": "baseline",
    "1": "classic_psychedelic"
  }
}
```

---

### Send MIDI CC

```http
POST /api/midi/send/cc
Content-Type: application/json

{
  "control": 1,
  "value": 64
}
```

**Parameters:**
- `control` (0-127): CC number
- `value` (0-127): CC value

**Response:**
```json
{
  "status": "sent",
  "message": "CC 1 = 64 sent"
}
```

---

### Send MIDI Note

```http
POST /api/midi/send/note
Content-Type: application/json

{
  "note": 60,
  "velocity": 100,
  "duration": 0.5
}
```

**Parameters:**
- `note` (0-127): MIDI note number
- `velocity` (0-127): Note velocity
- `duration` (0.0-10.0): Note duration in seconds (default: 0.1)

**Response:**
```json
{
  "status": "sent",
  "message": "Note 60 velocity 100 sent"
}
```

---

### Get Current Parameters

```http
GET /api/midi/params
```

**Response:**
```json
{
  "phase_noise": 0.45,
  "coupling_strength": 0.7,
  "drift_amplitude": 0.3,
  "V": 0.35,
  "P": 1.8
}
```

---

## Python API

### Direct MIDIService Usage

```python
from psyfi_core.midi import MIDIService, MIDIConfig

# Create configuration
config = MIDIConfig(
    input_device=None,  # Use default
    output_device=None,
    channel=0,
    velocity_curve="linear",
    cc_smooth_factor=0.1,
)

# Create service
midi = MIDIService(config)

# List available devices
devices = midi.list_devices()
print(f"Input devices: {devices['input']}")

# Open MIDI ports
midi.open(input_device="Launchpad Mini", output_device=None)

# Register parameter change callback
def on_param_change(param_name: str, value: float):
    print(f"{param_name} changed to {value}")

midi.register_callback(on_param_change)

# Start listening
midi.start()

# Get current parameters
params = midi.get_params()
print(params)

# Send MIDI CC
midi.send_cc(control=1, value=64)

# Send MIDI note
midi.send_note(note=60, velocity=100, duration=0.5)

# Export to MIDI file
metrics_sequence = [
    {"timestamp": 0.0, "coherence": 0.5, "richness": 0.3},
    {"timestamp": 1.0, "coherence": 0.7, "richness": 0.6},
]
midi.export_to_midi(metrics_sequence, "output.mid")

# Clean up
midi.close()
```

---

## DAW Integration

### Ableton Live

1. **Setup IAC Driver (macOS) or loopMIDI (Windows)**:
   - macOS: Audio MIDI Setup → MIDI Studio → IAC Driver → Enable
   - Windows: Install loopMIDI and create virtual port

2. **Configure PsyFi**:
   ```bash
   curl -X POST http://localhost:8000/api/midi/start \
     -H "Content-Type: application/json" \
     -d '{"input_device": "IAC Driver Bus 1"}'
   ```

3. **In Ableton**:
   - Preferences → Link/Tempo/MIDI → Track: "IAC Driver Bus 1" → Output: On
   - Create MIDI track
   - Add MIDI clips or controllers
   - Route to IAC Driver Bus 1

4. **Map Controls**:
   - Use CC1 (Modulation) for phase noise
   - Use CC7 (Volume) for coupling strength
   - Use notes C4–A#4 (60–70) for preset changes

### Logic Pro / FL Studio / Bitwig

Similar setup using virtual MIDI buses:
- Enable virtual MIDI port
- Route MIDI output to virtual port
- Start PsyFi MIDI service listening to that port

---

## Hardware Controllers

### Novation Launchpad

```python
# Start service
curl -X POST http://localhost:8000/api/midi/start \
  -d '{"input_device": "Launchpad Mini", "channel": 0}'

# Map buttons to presets:
# Row 1 buttons → Notes 60-69 (C4-A4) → Presets
# Faders → CC1, CC7, CC10, etc. → Parameters
```

### Akai MPK / Arturia KeyLab

```python
# Configure knobs/faders to send CC1, CC2, CC4, CC7, CC10, CC11, CC16-19
# Configure pads to send notes 60-70
# Start PsyFi MIDI service
```

### Touch OSC / MIDI Controller Apps

Create custom layouts with:
- Faders → CC1, 2, 4, 7, 10, 11 (plus CC16–19 for visual/affect)
- Buttons → Notes 60–70
- Program change buttons → 0–4

---

## Advanced Usage

### Parameter Smoothing

CC values are smoothed using exponential moving average to prevent jitter:

```python
# Lower smooth_factor = smoother (more lag)
# Higher smooth_factor = more responsive (more jitter)

config = MIDIConfig(cc_smooth_factor=0.1)  # Default: smooth
config = MIDIConfig(cc_smooth_factor=0.5)  # Responsive
config = MIDIConfig(cc_smooth_factor=1.0)  # No smoothing
```

### Velocity Curves

Control how note velocity maps to preset intensity:

```python
config = MIDIConfig(velocity_curve="linear")        # Direct mapping
config = MIDIConfig(velocity_curve="exponential")   # More sensitive at high velocities
config = MIDIConfig(velocity_curve="logarithmic")   # More sensitive at low velocities
```

### MIDI Output from Field

Export consciousness field metrics as MIDI:

```python
from psyfi_core.midi import MIDIService
from psyfi_core.engine import PsyFiEngine

engine = PsyFiEngine(...)
midi = MIDIService(...)

# Run simulation
for t in range(1000):
    field = engine.step()
    metrics = engine.get_metrics()

    # Convert to MIDI in real-time
    midi.field_to_midi(field, metrics)
```

Metrics are mapped to CC:
- `coherence` → CC1
- `richness` → CC7
- `valence` → CC10
- `flux` → CC11

---

## Troubleshooting

### "MIDI not available" Error

**Cause**: the process is running from an environment that does not have the default dependencies. `mido` and `python-rtmidi` are not an optional extra.

**Solution**: reinstall Psy-Fi so those default dependencies are present.

```bash
pip install -e .
```

### "No MIDI devices found"

**Cause**: No MIDI devices connected or virtual ports not configured

**Solution**:
- macOS: Enable IAC Driver in Audio MIDI Setup
- Windows: Install loopMIDI
- Linux: Install `alsa-utils` and configure ALSA MIDI

### "Failed to open MIDI port"

**Cause**: Device already in use or incorrect device name

**Solution**:
```bash
# List exact device names
curl http://localhost:8000/api/midi/devices

# Use exact name from list
curl -X POST http://localhost:8000/api/midi/start \
  -d '{"input_device": "Exact Device Name Here"}'
```

### Parameter Changes Not Smooth

**Cause**: CC smoothing factor too high

**Solution**:
```bash
# Increase smoothing (lower factor)
curl -X POST http://localhost:8000/api/midi/start \
  -d '{"cc_smooth_factor": 0.05}'
```

---

## Safety & Limits

All MIDI-controlled parameters are clamped to safe ranges:

- `phase_noise`: [0.0, 1.0]
- `coupling_strength`: [0.0, 2.0]
- `drift_amplitude`: [0.0, 1.0]
- `V`: [0.0, 1.0]
- `P`: [1.0, 3.0]
- `decay_rate`: [0.0, 1.0]

Preset intensities are clamped to [0.0, 1.0] and safety defaults are enforced (see `docs/SUBSTANCE_PRESETS.md`).

---

## Performance Notes

- **Latency**: ~5-20ms typical (depends on audio buffer size)
- **CPU Usage**: <1% additional overhead for MIDI processing
- **Thread Safety**: MIDI runs in background thread, thread-safe parameter access
- **Max CC Rate**: ~1000 messages/second (MIDI bandwidth limit)

---

## See Also

- [Substance Presets](SUBSTANCE_PRESETS.md) - Complete preset reference
- [API Documentation](API.md) - Full API reference
- [Deployment Guide](DEPLOYMENT.md) - Production deployment

---

**Applied Alchemy Labs**
ABX-Core v1.3 - Deterministic Consciousness Simulation
