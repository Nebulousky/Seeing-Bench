# Research: Phase 2 LRO Dataset Starting Points

```yaml
Status: Complete
Date: 2026-08-20
Sources examined: 7
Informs: Phase 2 LROC WAC + LOLA dataset integration
```

## 1. Question

Which official LRO/LROC/LOLA/SPICE data products should SeeingBench target first for
approximately 100 m/pixel lunar reference construction, and what provenance/checksum work
must happen before implementation?

## 2. Scope

This research identified candidate official data sources and product families only. It did
not download bulk products, inspect PDS labels tile-by-tile, verify checksums, or choose the
final coordinate convention. Evidence is current as checked on 2026-08-20.

## 3. Sources Examined

Primary or official sources:

- PDS Geosciences Node LRO mission page:
  https://pds-geosciences.wustl.edu/missions/lro/default.htm
- PDS Geosciences Node LOLA page:
  https://pds-geosciences.wustl.edu/missions/lro/lola.htm
- LROC WAC Global Morphologic Map RDR page:
  https://data.lroc.im-ldi.com/lroc/view_rdr/WAC_GLOBAL
- LROC WAC Empirically Normalized Mosaic RDR page:
  https://data.lroc.im-ldi.com/lroc/view_rdr/WAC_EMP
- LROC GLD100 WAC Global DTM RDR page:
  https://data.lroc.im-ldi.com/lroc/view_rdr/WAC_GLD100
- NAIF LRO SPICE archive aareadme:
  https://naif.jpl.nasa.gov/pub/naif/pds/data/lro-l-spice-6-v1.0/lrosp_1000/aareadme.htm
- USGS page for the WAC Global Morphology Mosaic:
  https://www.usgs.gov/media/images/moon-lro-lroc-wac-global-morphology-mosaic-100-m

## 4. Findings

The PDS Geosciences Node identifies ODE as the search/display/download route for LRO data,
and lists the LROC archive at the LROC Data Node, LOLA archive at the Geosciences/LOLA data
nodes, and SPICE archive at NAIF. The same page notes that most LRO instrument teams release
data every three months while LROC releases monthly, so manifests must record the release or
product label actually used.

The LROC WAC Global Morphologic Map is the best first imagery candidate for structural
benchmark reference. The product page states it uses the WAC 643 nm band, is built from more
than 15,000 images, and is archived in ten regional tiles at 100 meters/pixel plus 256 and
128 pixels/degree alternatives. Eight tiles are equirectangular 60 degree by 90 degree
regions; the two pole products are polar stereographic. The same page documents product
name structure and east-longitude tile ranges.

The LROC WAC Empirically Normalized Mosaic is a candidate for albedo/reflectance workflows.
It covers 60 degrees south to 60 degrees north in seven WAC bands and is photometrically
normalized to a standard geometry. The 643 nm archive is available at 304 pixels/degree,
approximately 100 meters/pixel, while all seven bands are available at 64 pixels/degree.
This should not replace morphology reference by default, but it is valuable when reducing
illumination-driven photometric disagreement.

The GLD100 WAC Global DTM is the first terrain/shape candidate outside the poles. The source
states it covers 98.2% of the lunar surface from 79 degrees south to 79 degrees north, was
computed from WAC stereo models, and is available in original 100 meters/pixel ten-tile
format. It also warns that surface details at the 100 m scale are not fully resolved and
that formal resolution is probably closer to 300 m, with elevation accuracy estimated around
10 to 20 m. That limitation must be recorded in uncertainty metadata.

LOLA should be used for topography products and especially polar support. The PDS LOLA page
identifies derived RDR, RADR, GDR, SHADR, and SLDEM products and points users who need the
most recent LOLA data to ODE and the LOLA Data Node. For Phase 2, the correct next step is
to inspect GDR and SLDEM labels/SIS files and choose products matching the desired grid,
projection, coordinate frame, and resolution.

The NAIF LRO SPICE archive is the correct geometry-kernel source for spacecraft and
observation geometry. Its archive readme states that SPICE kernels contain geometry and
ancillary information and must be accessed with the NAIF SPICE Toolkit. The volume includes
kernel directories for CK, FK, IK, LSK, PCK, SCLK, and SPK, plus index files including
`checksum.tab`. SeeingBench should use `spiceypy` rather than implementing geometry from
scratch, but adding that dependency should wait until the SPICE implementation task.

The USGS-hosted WAC Global Morphology Mosaic page marks that media item Public Domain and
states the image was orthorectified on LOLA and WAC DEMs. This supports permissive use of
that media page, but code must still verify product-level PDS labels before distributing
downloaded products or derived bundles.

## 5. Conclusions and Confidence

High confidence: Phase 2 should begin with metadata/download support for LROC
`WAC_GLOBAL`, LROC `WAC_EMP`, LROC `WAC_GLD100`, LOLA GDR/SLDEM, and the NAIF LRO SPICE
archive. These are official sources and align with the project spec's approximately
100 m/pixel target.

Medium confidence: `WAC_GLOBAL` 100 m/pixel 643 nm should be the first structural texture
source, with `WAC_EMP` used later where photometric normalization matters. The evidence
supports the product roles, but the final choice depends on renderer scoring experiments.

High confidence: checksum and licence/provenance fields cannot be finalized from the summary
pages alone. The implementation must read per-product PDS labels and index/checksum files,
not hard-code values from web page summaries.

## 6. Limits of the Evidence

This note did not validate downloaded files, file sizes, exact checksums, PDS label fields,
or all available map projections. It also did not decide whether the internal lunar
coordinate convention should be east-positive or west-positive; it only observed that the
LROC product naming uses east-longitude tile identifiers.

## 7. Negative and Null Results

No bulk download was attempted. No official single-page source was found that provided all
required manifest fields for every desired product family, especially exact checksums and
sizes. Therefore the downloader must inspect archive indexes and labels programmatically.

## 8. Open Questions

- Which exact PDS label fields should be canonical for licence/provenance in each product
  family?
- Which LOLA GDR or SLDEM product provides the cleanest approximately 100-120 m/pixel
  internal DEM target?
- Should Phase 2 standardize internally on east-positive longitude immediately, or preserve
  source longitude conventions until a projection module performs explicit conversion?
- Which subset of global WAC/GLD100 tiles is small enough for CI or a sample ROI test
  without committing data?

## 9. What This Changes

This note created specific metadata-only manifests in `manifests/` for:

- `lroc_wac_global_morphology.json`
- `lroc_wac_empirical_reflectance.json`
- `lroc_wac_gld100.json`
- `lola_gdr_sldem.json`
- `lro_spice_archive.json`

Phase 2 implementation should start by building a downloader/validator around these
manifest records, with per-product labels and checksums resolved before any data-processing
code depends on the products.
