# Census-to-node population assignment

This workflow assigns Census tract population to graph nodes using deterministic
Voronoi-style area shares.

## Region-selectable CLI

Use one command for either a single municipality or the combined four-city study
area:

```bash
python src/bcu_analysis/census/run_census_assignment.py \
  --region REGION
```

Supported values are:

- `boston`
- `brookline`
- `cambridge`
- `somerville`
- `greater-boston`

`greater-boston` means Boston, Brookline, Cambridge, and Somerville combined.

Examples:

```bash
# Combined four-city study area
python src/bcu_analysis/census/run_census_assignment.py \
  --region greater-boston

# Boston only
python src/bcu_analysis/census/run_census_assignment.py \
  --region boston

# Cambridge only
python src/bcu_analysis/census/run_census_assignment.py \
  --region cambridge
```

The graph, tract, and output paths can also be overridden:

```bash
python src/bcu_analysis/census/run_census_assignment.py \
  --region brookline \
  --graph-path /path/to/graph.graphml \
  --tract-path /path/to/ma_tracts_population.geojson \
  --output-directory /path/to/results
```

The selected `--region` controls which municipal boundary or combined boundary
is used to retain Census tracts. The graph is selected independently with
`--graph-path`. The default is the pruned four-city graph on Unity.

## Inputs

The default Unity inputs are:

- `greater_boston_6_cost_simplified_pruned.graphml`
- `ma_tracts_population.geojson`

The tract file must contain:

- `GEOID`
- `population`
- tract geometry

## Assignment method

For each retained Census tract, the shared assignment function:

1. Projects graph nodes and tracts to `EPSG:26986`.
2. Keeps tracts meeting the selected region-overlap threshold.
3. Finds graph nodes inside or near each tract.
4. Builds Voronoi-style nearest-node regions.
5. Clips those regions to the tract.
6. Computes each node's area share.
7. Normalizes area shares so each tract sums to 1.
8. Assigns tract population proportionally to those normalized shares.

Default parameters are:

- candidate-node buffer: 100 meters
- minimum tract overlap with the selected region: 0.50
- calculation CRS: `EPSG:26986`
- web output CRS: `EPSG:4326`

These can be changed with:

- `--candidate-buffer-m`
- `--min-region-overlap-share`

## Outputs

Output filenames include the selected region. For example,
`--region greater-boston` creates:

- `greater_boston_pruned_node_tract_allocation.csv`
- `greater_boston_pruned_node_tract_allocation.parquet`
- `greater_boston_pruned_nodes_with_population.gpkg`
- `greater_boston_pruned_nodes_with_population.parquet`
- `greater_boston_pruned_nodes_with_population_web.geojson`
- `greater_boston_four_city_boundary.geojson`

A Boston-only run uses the same pattern with the `boston_pruned` prefix.

The allocation table includes:

- `area_share`
- `raw_area_share`
- `tract_coverage_ratio`
- `assigned_population`

The command prints node, tract, population, and area-share validation summaries
after each run.

Large generated outputs should not be committed to Git unless the team decides
to track data with Git LFS or DVC.

## Limitations

This is an area-based approximation. It does not use building-level, parcel-level,
or household-level residential locations.

The overlap threshold retains or removes whole Census tracts. It does not
proportionally reduce a tract's population when only part of the tract lies inside
the selected municipal boundary.
