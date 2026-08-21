# Dataset Manifests

This directory stores metadata for external datasets, not the datasets themselves. Raw LRO,
LOLA, NAC, SPICE, derived tiles, and caches belong under `data/`, which is ignored by Git.

Phase 1 does not require any external dataset. The manifests in this directory record
candidate Phase 2 product families and official source pages without implying that data has
been downloaded, labels have been inspected, or checksums have been verified.

`manifests/rois/` may contain narrower ROI-specific manifests with exact product file URLs
and local cache paths. Those records still do not download data automatically, and a null
checksum means the product remains unresolved for readiness purposes.

Validate manifests:

```bash
seeingbench datasets validate-manifest manifests/*.json
```

Fetch only declared metadata/index documents:

```bash
seeingbench datasets fetch-metadata manifests/lro_spice_archive.json --output-root data/cache
```

Fetch only declared product labels:

```bash
seeingbench datasets fetch-labels manifests/rois/copernicus_wac_gld100.json --output-root .
```

Write declared ROI product URLs and destinations without downloading products:

```bash
seeingbench datasets roi-download-plan \
  --roi configs/rois/copernicus-100m.json \
  --cache-root . \
  --manifest-root .
```

Extract supported ROI windows from products that already exist locally and verify against
declared or label-derived size/checksum metadata:

```bash
seeingbench datasets extract-roi \
  --roi configs/rois/copernicus-100m.json \
  --cache-root . \
  --manifest-root . \
  --output-root outputs/copernicus-roi
```

Inspect local ROI readiness without downloading bulk products:

```bash
seeingbench datasets roi-readiness \
  --roi configs/rois/copernicus-100m.json \
  --cache-root . \
  --manifest-root .
```
