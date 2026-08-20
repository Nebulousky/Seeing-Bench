# SeeingBench

SeeingBench is a standalone research and validation platform for benchmarking atmospheric
image-reconstruction algorithms using the Moon as a known static target.

The first implementation is intentionally offline and synthetic: it does not download LRO,
LOLA, NAC, SPICE, or other large datasets. It generates repeatable atmosphere-degraded image
sequences from a local sharp image or a small synthetic crater field, retains exact truth,
accepts external reconstructions, and reports metrics that distinguish genuine recovery from
unsupported fine detail.

## Current Capabilities

- Smooth, temporally correlated multiscale displacement fields.
- Gaussian telescope PSF, seeing blur, Gaussian noise, and explicit sensor saturation.
- Retained latent truth, dense warp truth, and per-scale warp components.
- Filesystem benchmark contract for external tools:
  - `input/frame_000001.tif`, `input/frame_000002.tif`, ...
  - `truth/latent.tif`
  - `truth/warp_000001.npy`, `truth/warp_000002.npy`, ...
  - `metadata.json`
- Baseline mean-stack adapter.
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
