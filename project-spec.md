# SeeingBench

## Project Purpose

Build a standalone research and validation platform for objectively benchmarking atmospheric image-reconstruction algorithms using the Moon as a known, static target.

The project should use freely available lunar orbital data from missions such as NASA's Lunar Reconnaissance Orbiter to construct high-quality reference representations of the lunar surface, then compare those references against images reconstructed from Earth-based lucky-imaging videos.

The primary motivation is to answer a question that conventional astrophotography quality metrics cannot answer reliably:

> Did the reconstruction recover genuine lunar information, or merely create an image that looks sharper?

SeeingBench should eventually provide a repeatable way to compare algorithms such as:

* M51
* AutoStakkert
* PlanetarySystemStacker
* conventional stacking
* local alignment/destretching approaches
* MFBD/MOMFBD techniques
* experimental reconstruction algorithms

against the same known lunar truth.

SeeingBench must remain a **separate project from M51**.

M51 should be treated as an external reconstruction engine rather than depending on SeeingBench internally.

---

# 1. Core Design Principle

Maintain a strict boundary between:

1. **reconstruction**
2. **ground-truth validation**

Orbital lunar data must never influence the reconstruction itself.

The workflow must conceptually remain:

```text
Earth-based observation
        │
        ▼
 Reconstruction algorithm
        │
        ▼
 Reconstructed lunar image
        │
────────┼────────────────────────────
   validation boundary
────────┼────────────────────────────
        │
        ▼
 LRO / LOLA reference
        │
        ▼
   scoring / analysis
```

The reconstruction algorithm must not receive information derived from LRO, LOLA or other ground-truth datasets.

This prevents the reconstruction from simply reproducing known lunar features instead of recovering information genuinely present in the telescope data.

---

# 2. Project Goals

SeeingBench should support two complementary validation modes.

## 2.1 Synthetic Ground-Truth Benchmark

Generate simulated telescope observations from a known lunar reference.

Start from a high-resolution truth image:

[
O_{\text{truth}}(x,y)
]

then simulate:

[
O_{\text{truth}}
\rightarrow
\text{telescope PSF}
\rightarrow
\text{atmospheric deformation}
\rightarrow
\text{spatially varying blur}
\rightarrow
\text{sensor sampling}
\rightarrow
\text{noise}
]

to create a sequence:

[
I_1,I_2,\ldots,I_N.
]

Because SeeingBench generates the degradation, it must retain the exact ground truth for every frame, including where applicable:

[
u_i^{truth}(x,y)
]

[
v_i^{truth}(x,y)
]

[
PSF_i^{truth}(x,y)
]

and the original latent image.

This allows direct evaluation of:

* displacement-field recovery
* atmospheric warp estimation
* local blur estimation
* PSF recovery
* final image reconstruction
* false-detail generation

---

## 2.2 Real Observation Benchmark

Process actual lunar AVI/SER/image sequences using an external reconstruction algorithm.

Construct an independent orbital-data-derived reference representing what the lunar surface should look like from Earth under approximately the same geometry.

Compare the reconstruction against this reference after:

* geometric reprojection
* orientation correction
* libration correction
* resolution matching
* telescope PSF matching
* photometric normalization where appropriate

This mode does not provide exact atmospheric ground truth but provides an independent test of whether reconstructed structures correspond to real lunar terrain.

---

# 3. Data Sources

Design the system initially around freely available public lunar datasets.

Primary expected datasets:

## LROC WAC

Use the Lunar Reconnaissance Orbiter Camera Wide Angle Camera global morphology products as the main surface imagery/reference texture.

A working global resolution around:

[
100\ \mathrm{m/pixel}
]

is preferred initially.

Do not attempt to construct a global sub-metre NAC dataset.

---

## LOLA

Use Lunar Orbiter Laser Altimeter products for lunar topography.

Useful products include:

* elevation
* slope
* roughness
* gridded digital elevation models

Target approximately:

[
100\text{–}120\ \mathrm{m/pixel}
]

for the first implementation.

---

## LROC NAC

Narrow Angle Camera imagery should be optional and region-specific.

Use it only for selected high-value benchmark areas such as:

* Copernicus
* Tycho
* Plato
* Clavius
* Aristarchus
* other well-imaged lunar regions

Do not attempt a global NAC reconstruction.

NAC can later serve as an extremely high-resolution truth source for local benchmark targets.

---

## SPICE Kernels

Support NASA/NAIF SPICE data where required for:

* lunar orientation
* libration
* observer geometry
* Sun position
* Earth position
* apparent lunar orientation
* illumination calculations

Use established SPICE tooling rather than implementing orbital geometry from scratch.

Python implementations should preferably use `spiceypy`.

---

# 4. Storage Strategy

The Git repository must not contain the raw lunar datasets.

Expected initial working dataset size is approximately:

[
15\text{–}25\ \mathrm{GB}
]

for a practical ~100 m/pixel benchmark installation including:

* WAC imagery
* lunar DEM
* SPICE kernels
* metadata
* derived caches
* processed tiles

Higher-resolution optional datasets may increase this substantially.

Data directories must therefore be ignored by Git.

Suggested layout:

```text
seeingbench/
├── pyproject.toml
├── README.md
├── docs/
├── src/
├── tests/
├── manifests/
├── scripts/
├── configs/
├── benchmarks/
├── outputs/
└── data/                 # gitignored
    ├── lroc/
    ├── lola/
    ├── nac/
    ├── spice/
    ├── derived/
    └── cache/
```

Provide dataset manifests containing:

* dataset name
* source
* version
* expected size
* checksum
* local destination
* license/provenance
* resolution
* coordinate system

Where practical, provide automated download/setup scripts.

---

# 5. Development Phases

Do not attempt the full lunar renderer immediately.

Build the project incrementally.

---

## Phase 1 — Synthetic Benchmark Framework

Create the benchmark infrastructure before integrating large NASA datasets.

Start from any sufficiently sharp lunar source image.

Implement:

* synthetic geometric warping
* known dense displacement fields
* local blur
* global telescope PSF
* noise
* sensor sampling
* benchmark result storage
* reconstruction comparison metrics

The purpose of Phase 1 is to prove that the benchmark architecture works.

### Acceptance criteria

Given a known source image and known synthetic deformation:

1. SeeingBench generates an input sequence.
2. All ground-truth transformations are retained.
3. An external reconstruction can process the frames.
4. SeeingBench loads the result.
5. SeeingBench quantitatively compares the result with truth.
6. Displacement estimates can be compared against exact displacement truth.

---

# 6. Synthetic Atmospheric Seeing

Build the atmospheric simulation as a modular subsystem.

Suggested conceptual interface:

```python
class SeeingModel:
    def generate(self, image, config) -> SimulationResult:
        ...
```

A `SimulationResult` should expose at minimum:

```python
frames
latent_truth
warp_fields
psf_information
noise_information
metadata
```

---

## 6.1 Warp Model

Represent local atmospheric geometric distortion as a dense field:

[
\mathbf d_i(x,y)
================

\begin{bmatrix}
u_i(x,y)\
v_i(x,y)
\end{bmatrix}
]

Support initially:

* smooth random displacement fields
* configurable spatial correlation scale
* configurable displacement amplitude
* configurable temporal correlation
* configurable number of spatial scales

Do not generate independent random pixel motion.

Atmospheric deformation should be spatially smooth and temporally correlated.

Eventually investigate physically motivated Kolmogorov turbulence models.

---

## 6.2 Multiscale Atmospheric Motion

The simulator should support atmospheric motion containing multiple spatial scales.

For example:

[
\mathbf d =
\mathbf d_{\text{large}}
+
\mathbf d_{\text{medium}}
+
\mathbf d_{\text{fine}}.
]

This is particularly important because the reconstruction algorithms being tested may use multiscale alignment.

The benchmark should know each component separately where possible.

This allows questions such as:

> Did the reconstruction recover large-scale motion but fail at fine-scale seeing?

---

## 6.3 Blur / PSF Model

Initially support:

* Gaussian blur
* spatially varying Gaussian blur
* known diffraction PSF
* configurable seeing blur

Later investigate:

* wavefront-derived PSFs
* Kolmogorov turbulence
* Zernike-mode representations
* anisoplanatic PSFs
* temporally varying PSFs

Keep the PSF subsystem modular.

---

## 6.4 Telescope Model

Implement an explicit telescope/instrument model.

Configuration should include:

```text
aperture
focal_length
central_obstruction
wavelength
pixel_size
sensor_resolution
effective_f_ratio
sampling_scale
```

Where appropriate calculate:

* diffraction-limited angular resolution
* Airy PSF
* plate scale
* lunar spatial resolution
* sensor sampling

Do not allow the benchmark to reward algorithms for recovering frequencies that the telescope could never have measured.

This physical resolution boundary is important.

---

# 7. M51 Integration

M51 must be treated as a black-box reconstruction engine.

Preferred architecture:

```text
SeeingBench
    │
    ├── generates test sequence
    │
    ▼
external M51 invocation
    │
    ▼
M51 output
    │
    ▼
SeeingBench evaluator
```

Avoid introducing SeeingBench dependencies into M51.

Initially support a filesystem-based contract.

Example input:

```text
benchmark_case/
├── input/
│   ├── frame_000001.tif
│   ├── frame_000002.tif
│   └── ...
│
├── metadata.json
│
└── truth/
    ├── latent.tif
    ├── warp_000001.npy
    ├── warp_000002.npy
    └── ...
```

External reconstruction output:

```text
result/
├── reconstruction.tif
├── metadata.json
├── warp_fields/
└── diagnostics/
```

Not every reconstruction application will expose estimated warp fields, so only the reconstructed image should be mandatory.

---

# 8. External Algorithm Support

Design a generic adapter interface.

Example:

```python
class ReconstructionAdapter:
    def prepare(self, benchmark_case):
        ...

    def execute(self):
        ...

    def collect_results(self):
        ...
```

Initial adapters may include:

```text
M51Adapter
CommandLineAdapter
ManualImportAdapter
```

Later investigate automation for:

* PlanetarySystemStacker
* AutoStakkert
* torchmfbd
* other command-line capable reconstruction systems

Do not tightly couple the core benchmark framework to any one application.

---

# 9. Evaluation Metrics

Do not judge reconstruction quality using a single metric.

Implement several complementary categories.

---

## 9.1 Image Similarity

Support:

* MSE
* PSNR
* SSIM

These are useful but insufficient.

---

## 9.2 Structural Accuracy

Measure preservation/recovery of genuine lunar structures.

Potential metrics:

* edge correspondence
* gradient correlation
* local structural correlation
* feature matching
* crater/terrain edge consistency

---

## 9.3 Frequency-Domain Recovery

This is a major requirement.

Evaluate reconstruction quality as a function of spatial frequency.

For reference (O) and reconstruction (\hat O), calculate frequency-domain agreement such as:

[
C(f)
====

\mathrm{corr}
\left(
\mathcal F(O)_f,
\mathcal F(\hat O)_f
\right).
]

Produce curves showing reconstruction fidelity versus spatial frequency.

This allows statements such as:

> Algorithm A retains reliable genuine information to a higher fraction of the telescope diffraction limit than Algorithm B.

Normalize frequencies where useful relative to:

[
f_{\text{diffraction}}.
]

---

## 9.4 Warp Recovery Error

For synthetic tests where the true atmospheric displacement is known:

[
E_{\text{warp}}
===============

\frac{1}{N}
\sum_{x,y}
|
\hat{\mathbf d}(x,y)
--------------------

\mathbf d_{\text{truth}}(x,y)
|.
]

Report:

* mean error
* median error
* 95th percentile
* maximum
* error by spatial scale
* error versus image contrast
* error versus seeing strength

---

## 9.5 False Detail / Hallucinated Structure

This should be considered a first-class benchmark metric.

A reconstruction can increase apparent sharpness while introducing:

* ringing
* halos
* false craterlets
* duplicated edges
* invented fine texture

Develop metrics to detect high-frequency reconstructed structures unsupported by the truth image.

Potential approaches:

* unmatched edge energy
* high-frequency residual analysis
* structural feature disagreement
* false-positive feature detection
* reconstruction energy beyond physically recoverable frequency limits

The system should distinguish between:

[
\text{recovered detail}
]

and:

[
\text{invented detail}.
]

---

# 10. Phase 2 — LROC / LOLA Dataset Integration

After the synthetic framework is functional, add real orbital data.

Initial target:

[
\sim100\ \mathrm{m/pixel}
]

global or near-global reference data.

Create scripts capable of:

1. downloading official datasets
2. validating checksums
3. extracting metadata
4. converting into internal representations
5. tiling/caching
6. creating region-of-interest datasets

Do not initially perform complex photometric modelling.

---

# 11. Lunar Coordinate Model

Establish a consistent lunar coordinate representation.

Support conversions between:

* latitude/longitude
* projected image coordinates
* DEM coordinates
* Earth-observer image coordinates

Document conventions clearly.

Pay particular attention to:

* east-positive vs west-positive longitude
* lunar reference frames
* coordinate handedness
* image orientation
* north-up conventions

These are common sources of subtle errors.

---

# 12. Phase 3 — Earth-View Lunar Renderer

Build a renderer capable of constructing the expected lunar appearance from an arbitrary Earth observing geometry.

Inputs should eventually include:

```text
timestamp
observer latitude
observer longitude
observer altitude
wavelength/filter
telescope parameters
camera parameters
```

From timestamp and observer position derive:

* apparent lunar orientation
* libration
* Earth–Moon distance
* solar illumination geometry
* lunar phase
* sub-observer point
* sub-solar point

Use SPICE where practical.

The renderer should use:

[
\text{DEM} + \text{surface texture/albedo}
]

to construct a reference lunar image.

---

# 13. Illumination Model

Begin with a simple physically motivated model.

Possible first implementation:

* Lambertian surface illumination

Later investigate more accurate lunar photometric functions such as:

* Lommel-Seeliger
* Hapke-style models

The aim is not initially to produce photorealistic lunar rendering.

The aim is to reproduce sufficient geometry and shading for structural validation.

Photometric differences must not dominate reconstruction scoring.

---

# 14. Telescope-Matched Reference

Do not compare an Earth reconstruction directly against metre-scale LRO imagery.

Generate a physically achievable reference:

[
O_{\text{reference}}
====================

O_{\text{orbital}}
*
PSF_{\text{telescope}}.
]

Then resample according to the camera geometry.

This produces a reference representing approximately:

> what an ideal atmosphere-free observation through this telescope could contain.

Metrics should preferably operate on this telescope-matched reference.

---

# 15. Real Lunar Observation Metadata

Define a metadata schema for real observations.

Example:

```json
{
  "target": "Moon",
  "utc_start": "2026-08-15T00:46:34Z",
  "observer": {
    "latitude": null,
    "longitude": null,
    "altitude_m": null
  },
  "telescope": {
    "aperture_mm": null,
    "focal_length_mm": null,
    "central_obstruction": null
  },
  "camera": {
    "pixel_size_um": null,
    "width": null,
    "height": null
  },
  "filter": {
    "name": null,
    "effective_wavelength_nm": null
  }
}
```

Support partial metadata but clearly indicate when missing information limits the accuracy of the generated truth reference.

---

# 16. Real-Data Registration

Before scoring a reconstruction against orbital truth, establish accurate geometric correspondence.

Support:

* translation
* rotation
* scale
* mild projective effects if necessary
* local refinement where justified

Do not allow local registration to become so flexible that it hides reconstruction errors.

The benchmark registration itself must not deform truth to match artefacts created by the reconstruction.

Global or physically constrained transformations are preferred.

---

# 17. Benchmark Regions

Create a set of canonical lunar benchmark regions.

Select areas with:

* strong feature density
* fine crater structures
* different terrain types
* different illumination sensitivity
* different spatial-frequency content

Possible initial targets:

* Copernicus
* Tycho
* Plato
* Clavius
* Mare Imbrium
* Aristarchus
* lunar terminator regions

Each region should eventually include:

```text
reference imagery
DEM
coordinates
resolution
recommended test scales
provenance
```

---

# 18. High-Resolution NAC Benchmark Regions

Later add selected LROC NAC imagery for local tests.

Do not use NAC resolution directly as the expected Earth-based result.

Instead:

1. use NAC as high-resolution truth
2. project it into the Earth-view geometry
3. convolve with telescope PSF
4. downsample to the sensor scale
5. use the resulting image as the achievable reference

This allows extremely reliable validation of fine structures.

---

# 19. Algorithm Experiment Framework

SeeingBench should make parameter sweeps easy.

For example, compare multiscale alignment patch sequences:

```text
128
128 → 64
128 → 64 → 32
256 → 128 → 64
256 → 128 → 64 → 32
adaptive
```

Compare displacement estimators:

```text
phase correlation
normalized cross-correlation
ECC
Lucas-Kanade
Farnebäck
other optical flow
learned optical flow
```

Compare reconstruction strategies:

```text
rigid alignment
single-scale local alignment
multiscale destretching
multiscale + iterative reference
MFBD
spatially varying MFBD
```

The benchmark framework should automatically collect and compare results.

---

# 20. Reproducibility

Every benchmark run must be reproducible.

Record:

* Git commit
* benchmark configuration
* algorithm name/version
* random seed
* dataset version
* telescope configuration
* simulated atmosphere configuration
* runtime
* hardware where relevant
* metric results

Use structured machine-readable output such as JSON.

Example:

```text
runs/
└── 2026-08-20_multiscale_ncc_001/
    ├── config.json
    ├── environment.json
    ├── metrics.json
    ├── reconstruction.tif
    ├── plots/
    └── diagnostics/
```

---

# 21. Visualization

Provide diagnostic plots and images useful for algorithm development.

Required examples:

* truth image
* degraded frame
* reconstruction
* absolute residual
* structural residual
* truth displacement field
* estimated displacement field
* displacement error heatmap
* frequency-recovery curve
* edge comparison
* false-detail map
* before/after blink images

For multiscale simulations, optionally display:

* coarse atmospheric field
* medium atmospheric field
* fine atmospheric field
* combined field

---

# 22. Reports

Provide a command capable of generating a benchmark summary.

Conceptually:

```bash
seeingbench evaluate run/
```

Output should include:

```text
Algorithm
Dataset
Runtime

Image similarity
Structural similarity
Warp error
Frequency recovery
False-detail score

Plots
Diagnostic images
```

Eventually support algorithm comparison:

```bash
seeingbench compare \
    results/m51 \
    results/pss \
    results/baseline
```

---

# 23. Suggested Python Architecture

Prefer a modular Python codebase.

Suggested structure:

```text
src/seeingbench/
├── datasets/
│   ├── lroc.py
│   ├── lola.py
│   ├── nac.py
│   └── manifests.py
│
├── geometry/
│   ├── lunar_coordinates.py
│   ├── spice.py
│   ├── projection.py
│   └── observer.py
│
├── rendering/
│   ├── lunar_renderer.py
│   ├── illumination.py
│   └── terrain.py
│
├── simulation/
│   ├── atmosphere.py
│   ├── warp.py
│   ├── psf.py
│   ├── telescope.py
│   ├── sensor.py
│   └── noise.py
│
├── reconstruction/
│   ├── adapter.py
│   ├── m51.py
│   └── command_line.py
│
├── evaluation/
│   ├── image_metrics.py
│   ├── structure.py
│   ├── frequency.py
│   ├── warp_metrics.py
│   └── false_detail.py
│
├── benchmark/
│   ├── case.py
│   ├── runner.py
│   ├── experiment.py
│   └── result.py
│
├── visualization/
│   ├── plots.py
│   ├── vector_fields.py
│   └── diagnostics.py
│
└── cli.py
```

This is a suggested organisation rather than a mandatory API.

Adjust it if a cleaner design emerges.

---

# 24. Technical Priorities

Prioritize:

1. correctness
2. reproducibility
3. transparent metrics
4. modularity
5. scientific validity
6. performance

Only optimize performance after the benchmark results are trusted.

Use GPU acceleration where it clearly helps, particularly for:

* synthetic frame generation
* batched warping
* FFT operations
* PSF convolution
* image pyramids
* large experiment sweeps

PyTorch is acceptable and likely useful, particularly because M51 already operates in this ecosystem.

---

# 25. Relevant Literature and Existing Implementations

Review the following before designing the advanced seeing simulator or reconstruction metrics:

* November (1986), *Measurement of geometric distortion in a turbulent atmosphere*
* November & Simon (1988), local correlation tracking
* Fisher & Welsch (2008), FLCT
* Vargas Domínguez work on repeated multiscale destretching
* Löfdahl (2002), Multi-Frame Blind Deconvolution
* MOMFBD literature
* modern spatially varying MOMFBD work
* `torchmfbd`
* PlanetarySystemStacker
* AutoStakkert Multi-Scale AP / Double Stack Reference behaviour

Also investigate literature on:

* Kolmogorov atmospheric turbulence
* Fried parameter (r_0)
* anisoplanatism
* atmospheric coherence time
* wavefront phase screens
* telescope OTF/MTF
* lunar photometric models
* LROC/LOLA geometric processing
* SPICE lunar coordinate transformations

Document sources rather than relying on remembered formulas.

---

# 26. Explicit Non-Goals for Initial Version

Do not initially attempt:

* global 0.5 m/pixel lunar reconstruction
* downloading all LROC NAC data
* physically perfect lunar rendering
* full adaptive-optics simulation
* real-time reconstruction
* machine-learning reconstruction
* training algorithms against LRO data
* integration of LRO truth directly into M51
* automated control of every third-party stacking program
* complete MFBD implementation inside SeeingBench

SeeingBench evaluates reconstruction algorithms; it is not itself intended to become the primary reconstruction engine.

---

# 27. Scientific Safeguards

The benchmark must be deliberately resistant to misleading results.

### Never reward impossible detail

Suppress or separately classify reconstruction frequencies substantially beyond the telescope's physical transfer function.

### Avoid using sharpness as truth

A sharper image is not necessarily a more accurate image.

### Separate photometry from geometry

Brightness disagreement caused by different illumination must not automatically count as structural reconstruction failure.

### Preserve validation independence

No orbital truth may enter an algorithm under evaluation unless explicitly conducting a separate experiment labelled as prior-informed reconstruction.

### Quantify uncertainty

Where the ground-truth reference itself is uncertain because of:

* illumination
* map projection
* DEM resolution
* sensor response
* registration

record and expose that uncertainty.

---

# 28. Initial Milestone

The first meaningful milestone should require **no LRO data at all**.

Build a synthetic benchmark which:

1. loads a sharp lunar image
2. generates a known temporally coherent multiscale atmospheric warp
3. optionally applies known blur
4. generates an image sequence
5. exports the sequence in a format M51 can ingest
6. accepts an M51 reconstruction
7. compares it with the original truth
8. compares any estimated warp field against the exact simulated warp
9. measures frequency recovery
10. generates diagnostic plots and a machine-readable report

This establishes the core benchmark architecture.

---

# 29. Second Milestone

Add LROC WAC + LOLA support.

Deliver:

* dataset manifest
* automated downloader
* integrity verification
* local cache
* ROI extraction
* basic map reprojection
* lunar surface reference creation

Use approximately 100 m/pixel products.

---

# 30. Third Milestone

Generate a lunar reference for a real Earth observation.

Given:

* timestamp
* observer coordinates
* telescope configuration
* camera configuration

produce:

[
\text{LRO/LOLA}
\rightarrow
\text{Earth-view reference}
\rightarrow
\text{telescope PSF}
\rightarrow
\text{sensor sampling}.
]

Validate the renderer against known lunar orientation and identifiable features before using it as benchmark truth.

---

# 31. Fourth Milestone

Run a real comparative reconstruction study.

For one or more lunar videos:

```text
Baseline rigid stack
vs
M51 current pipeline
vs
M51 multiscale destretch
vs
PlanetarySystemStacker
vs
AutoStakkert where practical
```

Measure:

* genuine spatial-frequency recovery
* structural accuracy
* false-detail generation
* runtime

Produce a report showing which algorithm most closely reconstructs the independently known lunar surface.

---

# 32. Definition of Success

SeeingBench is successful when it can objectively answer:

> Given the same atmosphere-degraded lunar observations, which reconstruction algorithm recovered the greatest amount of genuine lunar information?

and separately:

> Which algorithm introduced the least unsupported fine structure?

The long-term value of the project is not simply benchmarking M51.

The goal is to create a general-purpose, reproducible framework for evaluating astronomical atmospheric reconstruction algorithms against unusually strong ground truth provided by the Moon.

The Moon should effectively become an **algorithm laboratory**:

[
\boxed{
\text{known static surface}
+
\text{orbital truth}
+
\text{real atmosphere}
+
\text{controlled simulations}
}
]

allowing atmospheric imaging methods to be evaluated scientifically rather than primarily by subjective visual sharpness.
