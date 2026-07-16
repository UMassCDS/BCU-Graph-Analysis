# Census-to-node population assignment

This workflow assigns census tract population to graph nodes using deterministic area-based allocation.

## Inputs

The workflow uses:

- A processed graph file, currently `data/processed/osm/greater_boston_cost_simplified.graphml`
- Official Massachusetts 2024 Census/TIGER tract geometries
- ACS population data
- A processed tract population GeoJSON with population joined to tract geometries

The project does not create custom tract boundaries. It uses official census tract geometries and attaches population values to them.

## Main algorithm

For each census tract, the assignment function:

1. Projects graph nodes and tracts to `EPSG:26986`.
2. Filters tracts to the Boston region.
3. Finds candidate graph nodes inside or near the tract.
4. Builds Voronoi regions from candidate nodes.
5. Clips each Voronoi region to the tract polygon.
6. Computes each node's clipped tract area share.
7. Assigns tract population proportionally by area share.
8. Normalizes area shares so each tract sums to 1.
9. Saves diagnostic columns for validation.
10. Sorts output by tract ID and node ID for deterministic results.

## Main parameters

The final Boston run used:

- `candidate_buffer_m=100`
- `tract_filter_method="convex_hull"`
- Boston boundary from OSMnx
- `min_region_overlap_share=0.50`
- calculation CRS: `EPSG:26986`
- web output CRS: `EPSG:4326`


## Processed graph choice

The workflow was tested with both the older `Boston_3.graphml` graph and the processed simplified graph.

The processed simplified graph is now preferred because it preserves the same assigned tract count and population total while using fewer graph nodes and producing fewer allocation rows.

Comparison:

- Old `Boston_3.graphml`
  - nodes: 241,429
  - assigned nodes: 232,039
  - allocation rows: 267,991
  - assigned tracts: 206
  - total assigned population: 666,442.0

- New `greater_boston_cost_simplified.graphml`
  - nodes: 97,850
  - assigned nodes: 63,652
  - allocation rows: 76,488
  - assigned tracts: 206
  - total assigned population: 666,442.0

Validation with the processed simplified graph:

- negative populations: 0
- one-node tracts: 0
- bad area-share sums: 0
- coverage ratio approximately 1.0

## Outputs

Typical generated outputs include:

- `Boston_nodes_with_population_web.geojson`
- `Boston_node_tract_allocation.csv`
- `Boston_census_assignment_map.html`

Large generated outputs should not be committed to Git unless the team decides to track data with Git LFS or DVC.

The runnable census workflow files live under `src/bcu_analysis/census/`.

## Diagnostics

The allocation table includes:

- `area_share`
- `raw_area_share`
- `tract_coverage_ratio`
- `assigned_population`

These columns help verify that Voronoi cells cover each tract and that population is conserved.

## Limitations

This is an area-based approximation. It does not know actual building-level or parcel-level residential distribution inside each tract.

The current workflow keeps or removes whole tracts based on Boston boundary overlap. It does not clip tract population to only the part of a tract inside Boston.
