# Census-to-node population assignment

This workflow assigns Census tract population to graph nodes using deterministic
Voronoi-style area shares.

## Region-selectable CLI

Use one command for either a single municipality or the combined four-city study
area:

```bash
python src/bcu_analysis/census/run_census_assignment.py \
  --region REGION \
  --graph-path /path/to/graph.graphml
```

Supported region values are:

- `boston`
- `brookline`
- `cambridge`
- `somerville`
- `greater-boston`

`greater-boston` means Boston, Brookline, Cambridge, and Somerville combined.

The graph path is required. This keeps graph provenance explicit and avoids
silently treating a legacy or locally generated graph as the canonical input.

Examples:

```bash
# Combined four-city assignment using the pruned analysis graph
python src/bcu_analysis/census/run_census_assignment.py \
  --region greater-boston \
  --graph-path /path/to/greater_boston_6_cost_simplified_pruned.graphml \
  --tract-path /path/to/ma_tracts_population.geojson \
  --output-directory /path/to/results \
  --output-prefix greater_boston_pruned

# Boston tracts assigned to nodes from the same supplied graph
python src/bcu_analysis/census/run_census_assignment.py \
  --region boston \
  --graph-path /path/to/greater_boston_6_cost_simplified_pruned.graphml \
  --tract-path /path/to/ma_tracts_population.geojson \
  --output-directory /path/to/results \
  --output-prefix boston_pruned
```

Alternative tract and output locations can be supplied explicitly:

```bash
python src/bcu_analysis/census/run_census_assignment.py \
  --region cambridge \
  --graph-path /path/to/graph.graphml \
  --tract-path /path/to/ma_tracts_population.geojson \
  --output-directory /path/to/results \
  --output-prefix cambridge_analysis
```

## Region and graph scope

`--region` controls which municipal boundary is used to retain Census tracts.
It does not crop the supplied graph.

The allocation CSV contains only node-tract allocation rows for retained tracts.
The node spatial outputs retain every node in the supplied graph. Nodes that do
not receive an allocation remain in those node outputs with assigned population
equal to zero.

This distinction allows one graph to be reused for localized analyses while
keeping the graph input explicit.

## Output naming

If `--output-prefix` is omitted, output filenames use the selected region, such
as `greater_boston_node_tract_allocation.csv`.

Use an explicit prefix when the graph has an important processing state:

- `greater_boston_pruned`
- `greater_boston_unpruned`
- `boston_pruned`

The program does not infer that a graph is pruned from the region selection.

## Inputs

The default Census tract input on Unity is:

- `ma_tracts_population.geojson`

The tract file must contain:

- `GEOID`
- `population`
- tract geometry

The graph is always supplied through `--graph-path`.

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

For a run with `--output-prefix greater_boston_pruned`, the generated files are:

- `greater_boston_pruned_node_tract_allocation.csv`
- `greater_boston_pruned_node_tract_allocation.parquet`
- `greater_boston_pruned_nodes_with_population.gpkg`
- `greater_boston_pruned_nodes_with_population.parquet`
- `greater_boston_pruned_nodes_with_population_web.geojson`
- `greater_boston_four_city_boundary.geojson`

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
