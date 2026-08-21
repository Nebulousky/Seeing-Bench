# Architecture

This document owns layering, the module map, dependency direction, and project-wide
conventions. The path-scoped loader at `.claude/rules/architecture.md` carries only the
lines that must never be missed and points here for the rest.

## Dependency Direction

Dependency direction is:

`cli -> benchmark/reconstruction adapters -> simulation/evaluation/io -> numerical helpers`

Simulation and evaluation modules operate on arrays and typed configuration, not filenames.
Filesystem knowledge lives in `seeingbench.io`, `seeingbench.benchmark`, and
`seeingbench.reconstruction`. The CLI may import every public layer; domain modules must not
import the CLI or application state. No module may pass validation truth into reconstruction
adapter execution except for an explicitly labelled prior-informed experiment.

## Layers

- `simulation` owns synthetic seeing, telescope metadata, PSF, noise, and source generation.
- `datasets` owns dataset manifests and validation metadata, not downloaded data.
- `evaluation` owns metrics over aligned truth/reconstruction arrays and warp fields.
- `io` owns supported file formats and explicit numeric range conversion.
- `benchmark` owns the filesystem contract, report model, and orchestration.
- `reconstruction` owns black-box adapters and must preserve validation independence.
- `visualization` owns derived diagnostic artifacts only; diagnostics are not metrics.
- `cli` is a thin command dispatcher.

## Home Library Per Module

NumPy is the only runtime array library in Phase 1. Internal image arrays and displacement
fields are `numpy.float64`. Conversion to external storage formats happens only in `io`.

## Conventions

- **No silent fallbacks.** If a failure would change the algorithm, quality, or behaviour of
  the result, raise or warn explicitly; never silently substitute a different method.
- **Errors and logging.** Conditions affecting output validity raise informative exceptions;
  degraded-but-continuable conditions warn. Use the `logging` module; no `print` in
  production code. The library never configures global logging.
- **Randomness.** Pass generator objects explicitly through APIs. Never seed or read global
  RNG state in library code. CLI commands may construct a generator from a recorded seed.
- **Configuration.** Parameters live in typed, serialisable config objects with documented
  units and sensible defaults. No magic numbers. Not every internal constant becomes a
  public option.
- **Provenance.** Every derived product records how it was produced: inputs, algorithm name
  and version, parameters, seed, software version, and the model or agent identity where one
  was involved. Diagnostics from iterative or approximate processes are first-class outputs,
  not log lines.
- **Memory and scale.** Design for streaming or batching where datasets are large; do not
  require everything resident at once when it can be avoided. Do not optimise prematurely,
  and do not copy large objects casually.
- **Simplicity.** Small composable functions over monolithic classes; classes only where
  there is real state or abstraction. No plugin systems, DI frameworks, event buses, service
  boundaries or database layers until a real requirement exists.

## Status

Implemented today: offline synthetic Phase 1 scaffolding with JSON simulation configs,
smooth multiscale warp fields, Gaussian/Airy telescope PSF, Gaussian noise, approximate
spatially varying seeing blur, explicit integer sensor-grid downsampling, explicit sensor
saturation metadata,
TIFF/NumPy benchmark export, baseline mean-stack adapter, global and local block translation
stack adapters, image/structure/frequency/false-detail/warp metrics, diffraction-relative
frequency interpretation, standalone-reference evaluation, Markdown reports, comparison
reports, richer diagnostics, CLI commands, explicit external command execution, built-in
baseline comparative studies, and unit tests. Phase 2 now has manifests,
metadata/label fetching, ROI readiness checks for local cache presence and declared
checksums, explicit no-download ROI download plans, verified local IMG window extraction,
basic map-window reprojection into ROI reference grids, guarded product downloading with
explicit byte budgets, and PDS label provenance carried through readiness, extraction, and
reference reports. Phase 3 has real-observation metadata parsing, SPICE readiness and
observation-geometry reports, a telescope-diffraction matching renderer for local ROI
references with Gaussian or Airy PSFs, optional local orthographic projection, and optional
simple terrain-derived Lambertian illumination. Full-disk spherical rendering,
high-fidelity lunar photometry, and
real third-party application automation still require local datasets/tools and further
implementation.

## Related

- `docs/data-handling.md`: the types and conventions flowing through these layers
- `docs/decisions/`: decisions that changed this document, with their reasons
- `docs/roadmap.md`: what is being built next
