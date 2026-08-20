# Roadmap

## What 1.0 Means

SeeingBench 1.0 can run reproducible synthetic and real lunar-observation benchmarks that
separate reconstruction from validation truth, compare multiple external algorithms, report
genuine spatial-frequency/structural recovery, and separately quantify unsupported
fine-detail generation.

## Phases

### Phase 1 - Synthetic Benchmark Framework

Build an offline synthetic benchmark that starts from a sharp local image or generated
source, produces atmosphere-degraded frames with retained latent and warp truth, imports
external reconstructions, computes complementary metrics, and writes diagnostics/reports.

**Exit:** a user can generate a case, run a baseline or external reconstruction, evaluate it
against retained truth, compare multiple results, render readable reports, and reproduce the
same metrics from the same seed and config.

### Phase 2 - LROC WAC and LOLA Integration

Add manifests, explicit download commands, checksum validation, local cache layout, ROI
extraction, and basic map reprojection for approximately 100 m/pixel public lunar products.

**Exit:** a documented ROI can be constructed from verified local orbital datasets without
committing raw data to Git.

### Phase 3 - Earth-View Reference Renderer

Use observation metadata and SPICE-backed geometry to create a telescope-matched lunar
reference for real observations.

**Exit:** generated references match known lunar orientation and identifiable features well
enough for structural validation limits documented in the report.

### Phase 4 - Comparative Reconstruction Study

Run the same lunar observations through baseline stacking, M51 variants, and practical
third-party tools, then compare genuine recovery, false detail, and runtime.

**Exit:** a reproducible report answers which algorithm recovered the most genuine lunar
information and which introduced the least unsupported fine structure for the study inputs.
