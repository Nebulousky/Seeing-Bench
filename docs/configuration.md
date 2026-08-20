# Configuration

This document describes the JSON configuration accepted by:

```bash
seeingbench simulate --config <path>
```

CLI flags are explicit overrides. The resolved configuration is written into each benchmark
case at `metadata.json` under `config`.

## Synthetic Simulation Config

All fields are optional unless stated otherwise. Unknown fields are rejected so misspelled
parameters do not silently produce a different benchmark.

| Field | Type | Default | Units | Meaning |
|---|---:|---:|---|---|
| `frame_count` | integer | `16` | frames | Number of degraded frames to generate. |
| `random_seed` | integer | `0` | seed | Seed used by the CLI to construct the NumPy random generator. |
| `temporal_correlation` | number | `0.85` | unitless | Frame-to-frame correlation for each warp scale; valid range is `[0, 1)`. |
| `warp_scales` | array | large/medium/fine | pixels | Smooth displacement components retained separately in truth. |
| `telescope` | object | see below | mixed | Telescope/camera geometry for physical metadata. |
| `telescope_psf_sigma_px` | number | `0.8` | pixels | Gaussian approximation of the atmosphere-free telescope PSF. |
| `seeing_blur_sigma_px` | number | `0.4` | pixels | Base Gaussian seeing blur applied after warping. |
| `spatial_blur_variation_sigma_px` | number | `0.0` | pixels | Local blur variation around `seeing_blur_sigma_px`. |
| `spatial_blur_correlation_px` | number | `32.0` | pixels | Correlation scale for the smooth local blur map. |
| `sensor_downsample_factor` | integer | `1` | pixels | Integer block-average factor from source grid to sensor grid. |
| `gaussian_noise_sigma` | number | `0.01` | image units | Standard deviation of additive zero-mean Gaussian noise. |
| `output_min` | number | `0.0` | image units | Lower sensor saturation limit. |
| `output_max` | number | `1.0` | image units | Upper sensor saturation limit. |

## Warp Scale Config

Each `warp_scales` entry has:

| Field | Type | Units | Meaning |
|---|---:|---|---|
| `name` | string | label | Stable component name used in `truth/warp_components.npz`. |
| `amplitude_px` | number | pixels | Target RMS displacement amplitude. |
| `correlation_px` | number | pixels | Approximate spatial correlation length. |

The default components are:

```json
[
  {"name": "large", "amplitude_px": 1.5, "correlation_px": 64.0},
  {"name": "medium", "amplitude_px": 0.7, "correlation_px": 24.0},
  {"name": "fine", "amplitude_px": 0.25, "correlation_px": 8.0}
]
```

## Telescope Config

The telescope object records physical metadata and derived limits. It does not yet implement
a full Airy PSF; `telescope_psf_sigma_px` controls the current image blur model.

| Field | Type | Default | Units | Meaning |
|---|---:|---:|---|---|
| `aperture_mm` | number | `200.0` | mm | Telescope aperture. |
| `focal_length_mm` | number | `4000.0` | mm | Effective focal length. |
| `central_obstruction_ratio` | number | `0.0` | aperture fraction | Central obstruction; valid range is `[0, 1)`. |
| `wavelength_nm` | number | `550.0` | nm | Effective wavelength for Rayleigh limit metadata. |
| `pixel_size_um` | number | `2.9` | micrometres | Camera pixel pitch. |
| `sensor_width_px` | integer or null | `null` | pixels | Sensor width. If omitted, the CLI fills it from the generated frame width. |
| `sensor_height_px` | integer or null | `null` | pixels | Sensor height. If omitted, the CLI fills it from the generated frame height. |

Derived metadata includes effective focal ratio, plate scale, Rayleigh diffraction limit,
approximate lunar metres per pixel at mean lunar distance, and diffraction frequency as a
fraction of sampled-image Nyquist.

## CLI Overrides

The following flags override config-file values:

| Flag | Overrides |
|---|---|
| `--frames` | `frame_count` |
| `--seed` | `random_seed` |
| `--noise-sigma` | `gaussian_noise_sigma` |
| `--sensor-downsample` | `sensor_downsample_factor` |
| `--warp-scale` | multiplies every `warp_scales[*].amplitude_px` |

The source image size flags `--height` and `--width` apply only when no `--truth` image is
provided and the CLI generates its built-in synthetic crater field.

## Validation Rules

- Image arrays must be finite two-dimensional `float64` values.
- Images written to TIFF must already be in `[0, 1]`; the writer refuses to clip silently.
- Sensor downsampling refuses shapes not divisible by `sensor_downsample_factor`.
- Config loading rejects unknown fields.
- Randomness is reproducible from the recorded seed when using the CLI.
