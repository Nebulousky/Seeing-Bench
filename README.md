# SeeingBench

SeeingBench is a standalone research and validation platform for benchmarking atmospheric
image-reconstruction algorithms using the Moon as a known static target.

The first implementation is intentionally offline and synthetic: it does not download LRO,
LOLA, NAC, SPICE, or other large datasets. It generates repeatable atmosphere-degraded image
sequences from a local sharp image or a small synthetic crater field, retains exact truth,
accepts external reconstructions, and reports metrics that distinguish genuine recovery from
unsupported fine detail.

## Current Capabilities

- Smooth, temporally correlated multiscale displacement fields plus global image motion.
- Gaussian telescope PSF, seeing blur, Gaussian noise, and explicit sensor saturation.
- Retained latent truth, dense warp truth, and per-scale warp components.
- Filesystem benchmark contract for external tools:
  - `input/frame_000001.tif`, `input/frame_000002.tif`, ...
  - `truth/latent.tif`
  - `truth/warp_000001.npy`, `truth/warp_000002.npy`, ...
  - `metadata.json`
- Baseline mean-stack adapter.
- Global phase-correlation translation-stack adapter.
- Local block phase-correlation stack adapter for practical non-oracle destretching.
- Synthetic-only oracle aligned-stack adapter for upper-bound validation.
- Metrics: MSE, PSNR, global SSIM, gradient correlation, radial frequency recovery,
  diffraction-relative recovery, false-detail energy, and optional warp recovery error.
- Diagnostic truth/reconstruction/frame exports, residual maps, blink pair, warp magnitude,
  warp summaries, and frequency-recovery CSV output.

## Install

```bash
python -m pip install -e ".[dev]"
```

On this machine, use the project virtual environment directly if the Windows Python app
alias is taking precedence:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
```

## Quick Start

Generate a synthetic case without external data:

```bash
seeingbench simulate --output benchmarks/generated/demo --frames 16 --seed 7
```

Or use the checked-in default configuration:

```bash
seeingbench simulate --config configs/synthetic-default.json --output benchmarks/generated/demo
```

Create a simple baseline reconstruction by averaging the input frames:

```bash
seeingbench baseline-stack --case benchmarks/generated/demo --output outputs/demo-baseline
```

Create a global-translation aligned baseline using only the input frames:

```bash
seeingbench translation-stack --case benchmarks/generated/demo --output outputs/demo-translation
```

Create a local block-translation aligned baseline using only the input frames:

```bash
seeingbench local-block-stack \
  --case benchmarks/generated/demo \
  --output outputs/demo-local-block \
  --block-size 32
```

Create a synthetic-only oracle upper-bound stack using retained truth warp fields:

```bash
seeingbench oracle-stack --case benchmarks/generated/demo --output outputs/demo-oracle
```

Evaluate the baseline:

```bash
seeingbench evaluate \
  --case benchmarks/generated/demo \
  --result outputs/demo-baseline \
  --algorithm mean_stack \
  --output outputs/demo-baseline/metrics.json \
  --diagnostics outputs/demo-baseline/diagnostics
```

Render a human-readable Markdown report:

```bash
seeingbench report \
  --metrics outputs/demo-baseline/metrics.json \
  --output outputs/demo-baseline/report.md
```

Compare multiple algorithm outputs:

```bash
seeingbench compare \
  outputs/demo-baseline \
  outputs/another-run \
  --output outputs/comparison.md
```

Run a compact empirical synthetic sweep across seeing and noise settings:

```bash
seeingbench experiment synthetic-sweep \
  --config configs/sweeps/phase1-smoke.json \
  --output outputs/sweeps/phase1-smoke
```

Validate candidate dataset manifests without downloading bulk data:

```bash
seeingbench datasets validate-manifest manifests/*.json --output outputs/manifest-check.json
```

Fetch only the small metadata documents explicitly listed by a manifest:

```bash
seeingbench datasets fetch-metadata \
  manifests/lro_spice_archive.json \
  --output-root data/cache
```

Fetch only small product labels declared by an ROI-specific manifest:

```bash
seeingbench datasets fetch-labels \
  manifests/rois/copernicus_wac_gld100.json \
  --output-root .
```

Write an explicit ROI download plan without downloading bulk data:

```bash
seeingbench datasets roi-download-plan \
  --roi configs/rois/copernicus-100m.json \
  --cache-root . \
  --manifest-root . \
  --output outputs/copernicus-download-plan.json
```

Extract supported ROI windows from already-local verified products:

```bash
seeingbench datasets extract-roi \
  --roi configs/rois/copernicus-100m.json \
  --cache-root . \
  --manifest-root . \
  --output-root outputs/copernicus-roi
```

Inspect whether a documented real-data ROI is locally ready without downloading bulk data:

```bash
seeingbench datasets roi-readiness \
  --roi configs/rois/copernicus-100m.json \
  --cache-root . \
  --manifest-root . \
  --output outputs/copernicus-readiness.json
```

The Copernicus sample ROI points to exact LROC WAC reflectance and GLD100 tile manifests,
but readiness remains blocked until those large files exist locally and exact checksums are
declared. If the small XML labels are cached, readiness also reports the planned row/column
window for the ROI without reading the large raster products.

To evaluate an external reconstruction, place or import a `reconstruction.tif` into a result
directory:

```bash
seeingbench import-result --source path/to/reconstruction.tif --output outputs/m51-run
seeingbench evaluate --case benchmarks/generated/demo --result outputs/m51-run --algorithm m51
```

## Project Boundary

SeeingBench evaluates reconstruction algorithms. It is not M51 and must not become an
internal M51 dependency. Reconstruction engines receive benchmark input frames and
reconstruction-side metadata only; retained truth and orbital references stay on the
validation side of the boundary.

## Data Policy

Raw lunar datasets, generated cases, outputs, caches, and large binary products are ignored
by Git. Future LRO/LOLA/SPICE integrations should provide manifests and explicit download
commands rather than committing data.

## Development

Run the gates before claiming work is done:

```bash
ruff check .
ruff format --check .
mypy src/seeingbench tests
pytest -q
python .claude/hooks/scaffold_check.py
python .claude/hooks/licence_check.py
```

Configuration fields and units are documented in `docs/configuration.md`.
