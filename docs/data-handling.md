# Data Handling

This document owns the rules that keep SeeingBench data correct: precision, types,
conventions, and what must never be silently destroyed. The path-scoped loader at
`.claude/rules/data-handling.md` carries only the lines that must never be missed and points
here for the rest.

Rules here are binding. Write them as checkable statements, not aspirations.

## The Rule That Does Not Bend

**Never silently destroy information.** No silent clipping, no silent NaN or null
substitution, no destructive normalisation, no unnecessary quantisation. Where corrupted
output would otherwise result, fail loudly.

## Precision and Types

Internal grayscale images are two-dimensional `numpy.float64` arrays. Internal displacement
fields are `numpy.float64` arrays whose final dimension is `[u_px, v_px]`. Metric
accumulation uses `float64`. TIFF export is an explicit conversion to unsigned 16-bit
samples and may only write values already in `[0, 1]`. Sensor downsampling uses explicit
integer block averaging and refuses non-divisible image shapes rather than silently cropping.

## Transformations

Transforms that change scale, range, units, or interpretation are named at the API boundary:
warps use pixel displacements, telescope fields use units in their names, sensor-grid
downsampling records pre/post truth shapes, and diagnostic visualizations record their
source min/max when scaled to `[0, 1]`. Synthetic sensor downsampling is applied after
telescope blur, atmospheric warp, and seeing blur. Sensor saturation is an explicit
simulation step and records saturated pixel counts.

## Conventions

Images are indexed as `[y, x]`. Dense warp fields have shape `(height, width, 2)` or
`(frames, height, width, 2)` with vector order `[u, v]`, where `u` is horizontal pixels and
`v` is vertical pixels. Applying a displacement samples the source at `(x - u, y - v)`.
Frequency metrics report radial frequency as a fraction of sampled-image axial Nyquist.
Diagonal Fourier samples above axial Nyquist are not part of the reported `0..1` radial
frequency range. Frequency-bin `sample_count` values count independent real-image Fourier
samples rather than Hermitian mirror pairs.

## Boundaries

External image encoding is converted in `seeingbench.io`. External reconstruction tools see
only benchmark inputs and metadata intended for reconstruction; latent truth, warp truth,
and evaluator output remain under the validation side of the filesystem contract.

## Metadata That Must Survive

Synthetic benchmark cases preserve random seed, simulation configuration, source-image
identity, telescope metadata, PSF/blur parameters, noise parameters, saturation counts,
software versions, and the validation-boundary statement. Future real-data cases must also
preserve observation time, observer location, telescope/camera/filter configuration,
dataset provenance, coordinate conventions, and uncertainty notes.

## Docstring Standard

Use concise docstrings. For public array APIs, document shape, dtype, value range, and units
where the function name or type does not make them obvious.

## Related

- `docs/architecture.md`: where these types flow and which layer may know about them
- `docs/development/testing.md`: how a data-handling rule gets a test
- `AGENTS.md`: hard rule 4, user data is not damaged
