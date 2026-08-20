# Dataset Manifests

This directory stores metadata for external datasets, not the datasets themselves. Raw LRO,
LOLA, NAC, SPICE, derived tiles, and caches belong under `data/`, which is ignored by Git.

Phase 1 does not require any external dataset. The manifests in this directory record
candidate Phase 2 product families and official source pages without implying that data has
been downloaded, labels have been inspected, or checksums have been verified.

Validate manifests:

```bash
seeingbench datasets validate-manifest manifests/*.json
```

Fetch only declared metadata/index documents:

```bash
seeingbench datasets fetch-metadata manifests/lro_spice_archive.json --output-root data/cache
```
