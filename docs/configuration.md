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
| `telescope_psf_sigma_px` | number | `1.656` | pixels | Gaussian approximation of the atmosphere-free telescope PSF for the default 200 mm f/20, 550 nm, 2.9 um setup. |
| `seeing_blur_sigma_px` | number | `2.0` | pixels | Base Gaussian seeing blur applied after warping. |
| `spatial_blur_variation_sigma_px` | number | `0.0` | pixels | Local blur variation around `seeing_blur_sigma_px`. |
| `spatial_blur_correlation_px` | number | `32.0` | pixels | Correlation scale for the smooth local blur map. |
| `global_motion_rms_px` | number | `0.75` | source pixels | Per-axis RMS whole-frame atmospheric displacement. |
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

Per-scale amplitudes are RMS values for each retained component. The combined local
displacement RMS is the quadrature sum of the components, plus the separate global-motion
component when `global_motion_rms_px` is non-zero.

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
Airy-core FWHM, the corresponding Gaussian sigma in pixels, central-obstruction area
fraction, clear aperture area, approximate lunar metres per pixel at mean lunar distance,
and diffraction cutoff frequency as a fraction of sampled-image axial Nyquist. Synthetic
case metadata also records the configured telescope PSF sigma relative to this
geometry-derived diffraction sigma.

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

## Observation Case Import

`seeingbench import-observation` copies local `.npy`/TIFF frames into
`input/frame_000001.tif`, `input/frame_000002.tif`, and so on, and writes `metadata.json`
with `benchmark_mode: real_observation`. It accepts shell-style frame patterns, requires all
frames to have the same shape, and does not create a `truth/` directory. Optional observation
metadata is stored under the `observation` key and remains reconstruction-side metadata; any
standalone orbital/reference image is supplied later to `evaluate-reference` or
`study run-reference-config`.

## Synthetic Sweep Config

The experiment command accepts a separate JSON object:

```bash
seeingbench experiment synthetic-sweep --config <path> --output <dir>
```

It uses the simulation fields above where names match, plus:

| Field | Type | Default | Units | Meaning |
|---|---:|---:|---|---|
| `name` | string | `phase1-smoke` | label | Name written to sweep summaries. |
| `height` | integer | `64` | pixels | Generated crater-field height. |
| `width` | integer | `64` | pixels | Generated crater-field width. |
| `crater_count` | integer | `40` | craters | Number of synthetic craters in the source image. |
| `source_seed` | integer | `0` | seed | Seed for the generated source image. |
| `warp_strengths` | array | `[0.0, 0.5, 1.0, 2.0]` | multiplier | Multipliers applied to every base warp scale. |
| `noise_sigmas` | array | `[0.0, 0.01, 0.03, 0.05]` | image units | Noise levels crossed with each warp strength. |
| `local_block_size_px` | integer | `32` | pixels | Block size used by the local block-stack baseline in the sweep. |

## Built-In Comparative Studies

`seeingbench study builtin-baselines` runs `mean_stack`, `translation_stack`, and
`local_block_stack` against the same benchmark case, evaluates each result with the same
frequency-bin count, and writes `study-summary.json`, `comparison.json`, and
`comparison.md`. Reconstruction adapters consume only case input frames; retained truth is
loaded only by the evaluator after each reconstruction output exists.
Reports keep `reconstruction_runtime_s` separate from `evaluation_runtime_s`; comparison
tables display reconstruction runtime only when an adapter recorded it. Comparison JSON and
Markdown also include direct leaders for best conservative score, most spectral recovery,
best structural recovery, least unsupported fine detail, and fastest reconstruction.

`seeingbench run-command` executes an explicit external command and requires it to write
`reconstruction.tif` into the declared result directory. Command arguments may use `{case}`
and `{result}` placeholders. The adapter records command, stdout, stderr, return code, and
runtime in `metadata.json`; evaluation remains a separate step.

`seeingbench evaluate-reference` compares a standalone reference image (`.npy` or supported
image file) with a reconstruction image. `--register-translation` permits only a global
integer translation estimated by phase correlation before scoring. Repeated
`--registration-rotation-deg` and `--registration-scale` values enable a constrained global
similarity grid search around the image centre, scored by reference MSE. These controls do
not locally deform or otherwise bend the reference to hide reconstruction errors.

`seeingbench study run-config` accepts a JSON object with `case`, `frequency_bins`,
`local_block_size_px`, and an `algorithms` list. Each algorithm has a stable `name` and
`kind`. `builtin` entries select one of `mean_stack`, `translation_stack`, or
`local_block_stack`. `command` entries provide an explicit argument list with `{case}` and
`{result}` placeholders and must write `reconstruction.tif` in the result directory.
Relative `case` paths are resolved from the config file's parent directory.

`seeingbench study run-reference-config` uses the same algorithm entries but evaluates each
result against a standalone `reference` image path instead of synthetic retained truth. It
supports `register_translation`, plus optional `registration_rotation_degrees` and
`registration_scales` lists using the same constrained global registration from
`evaluate-reference`. Relative `case` and `reference` paths are resolved from the config
file's parent directory.

## Validation Rules

- Image arrays must be finite two-dimensional `float64` values.
- Images written to TIFF must already be in `[0, 1]`; the writer refuses to clip silently.
- Sensor downsampling refuses shapes not divisible by `sensor_downsample_factor`.
- Config loading rejects unknown fields.
- Randomness is reproducible from the recorded seed when using the CLI.

## Lunar ROI Config

The ROI readiness command accepts a metadata-only JSON object:

```bash
seeingbench datasets roi-readiness --roi <path> --cache-root . --manifest-root .
```

The sample `configs/rois/copernicus-100m.json` defines a small Copernicus-centered target
for Phase 2 plumbing. It names required product roles and manifests, but it does not imply
that large products have been downloaded.

| Field | Type | Units | Meaning |
|---|---:|---|---|
| `name` | string | label | Stable ROI identifier for reports. |
| `description` | string | text | Optional human-readable purpose. |
| `center_lat_deg` | number | degrees | ROI center latitude in `[-90, 90]`. |
| `center_lon_deg` | number | degrees | ROI center longitude in `[-180, 360]`. |
| `width_km` | number | km | Requested ROI width. |
| `height_km` | number | km | Requested ROI height. |
| `target_resolution_m_per_px` | number | m/pixel | Internal target sampling for reference construction. |
| `required_products` | array | roles | Manifest-backed product roles required by the ROI. |

Each `required_products` entry has:

| Field | Type | Meaning |
|---|---:|---|
| `role` | string | Stable product role such as `reflectance`, `terrain`, or `geometry`. |
| `manifest` | string | Repository-relative path to a dataset manifest. |
| `required` | boolean | Whether missing or unresolved status blocks readiness; default `true`. |
| `notes` | string | Optional role-specific context. |

Dataset manifests may also declare `product_files` for ROI-specific file requirements:

| Field | Type | Meaning |
|---|---:|---|
| `name` | string | Stable file label. |
| `url` | string | Official HTTP(S) source URL. |
| `local_path` | string | Repository-relative expected cache path. |
| `checksum` | string or null | Optional `<algorithm>:<hex>` checksum; supported algorithms are `sha256`, `sha1`, and `md5`. |
| `expected_size_bytes` | integer or null | Optional exact byte size check for already-local files. |
| `label_url` | string or null | Optional official HTTP(S) URL for a small detached PDS label that may be fetched with `datasets fetch-labels`. |
| `label_local_path` | string or null | Optional repository-relative path to a small cached PDS label parsed for coverage and resolution checks. |
| `purpose` | string | Optional explanation of how the file supports the ROI. |

When a cached label includes map bounds, dimensions, and map scale, ROI readiness also
reports an approximate `roi_pixel_window` for each labelled product file. This is only a
metadata-derived extraction plan; it does not read or crop the large raster product.

`datasets extract-roi` currently extracts `.IMG` files whose cached PDS4 labels describe a
two-dimensional image with `IEEE754LSBSingle` or `SignedLSB2` samples. The command refuses
missing, unverified, incompatible, or unsupported products and writes extracted windows as
NumPy `.npy` arrays plus an extraction report.

`datasets reproject-roi` consumes that extraction report and resamples each extracted
map window onto the ROI's declared `target_resolution_m_per_px` grid. This is a basic
north-up map-window reprojection for Phase 2 dataset plumbing; it is not yet the SPICE-backed
Earth-view renderer and does not apply illumination, libration, local registration, or
telescope PSF matching.

`datasets fetch-products` is the guarded bulk downloader. It refuses product files without
`expected_size_bytes`, requires `--max-total-bytes`, streams to a temporary `.part` file,
and verifies declared size and checksum before leaving the product in the cache. If a
product has a cached detached label that describes the same file, the downloader can use
the label's file size and MD5 checksum instead of duplicating those values in the manifest.
Use `--product-name` one or more times to download a subset of declared products, for
example an IMG whose PDS label is cached while a browse TIF remains unresolved.

## Real Observation Metadata

The `render telescope-reference` command accepts the real-observation metadata shape from
`configs/observations/example-lunar-observation.json`. The first implementation requires
`telescope.aperture_mm`, `telescope.focal_length_mm`, `camera.pixel_size_um`, and
`filter.effective_wavelength_nm` to compute a diffraction-matched local reference. Observer
position, timestamp, camera dimensions, and Earth-Moon distance are preserved as metadata.
When `--spice-cache-root` is provided and the observation lists local kernels, the renderer
uses SPICE-derived topocentric Earth-Moon distance for diffraction matching and records
sub-observer, sub-solar, phase, and angular-radius metadata. It still reports limitations
rather than pretending to perform full-disk Earth-view rendering.

`--apply-earth-view-projection` applies a local linear orthographic projection derived from
the ROI centre and SPICE sub-observer point before telescope blurring. This approximates
small ROI foreshortening and orientation on the sky plane; it is not a full spherical
renderer and is labelled `local_linear_orthographic_projection` in reports.

`--apply-illumination` multiplies the selected reflectance reference by a simple
Lambertian shading map derived from the `--terrain-role` DEM reference and SPICE sub-solar
metadata. This is an explicit first-order structural aid, not a full lunar photometric
model; reports label it `simple_lambertian_illumination_model`.

`geometry spice-readiness` checks the SPICE side of that contract. Observation metadata must
include `utc_start`, `observer.latitude`, `observer.longitude`, `observer.altitude_m`, and
`spice.kernels`, where each kernel path is relative to the selected `--cache-root`. The
command parses a local NAIF `checksum.tab` when present, verifies local kernel MD5 values,
reports kernel type counts, and reports whether the optional `spiceypy` package is
available.

`geometry spice-observation` computes topocentric lunar geometry from the observation's
listed local kernels without downloading data. The report includes Earth-Moon distance,
Moon angular radius, sub-observer latitude/longitude, sub-solar latitude/longitude, phase
angle, and illuminated fraction. It returns non-zero when metadata, kernel files, or
`spiceypy` are unavailable.
