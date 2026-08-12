# BCU Graph Analysis

Analysis of bicycle connectivity with regards to difficulty of use of the network and Level of Traffic Stress (LTS) for
the Greater Boston area, built by the DS4CG Boston Cyclists Union Team.

The project builds a routable street network graph from OpenStreetMap in which each
edge's- or road segment's- travel "cost" reflects how difficult it is to bike (edge length scaled by a stress rating), attaches census population, and models travel demand to the network. The future goal is to utilize this graph representation to identify which road segments would be most beneficial to improve.

## Modules

The analysis is organized in stages, each as a sub-package under `src/bcu_analysis/`. Each step depends on the previous, so they should normally be run in order.

1. **`graph_builder/`** — Download OpenStreetMap data for the region (Boston,
   Cambridge, Somerville, Brookline, or All four cities), determine a Level of Traffic
   Stress (LTS) rating for every edge, and build a routable "cost" graph where
   `cost = length × LTS stress multiplier` (the LTS stress multipliers are modifiable
   for different scenarios). Higher-stress edges are penalized so
   routing prefers low-stress streets. The graph is then simplified for faster
   routing.

2. **`destination_csvs/`** — Query OSM (via the Overpass API) over the region of choice
   (Boston, Brookline, Cambridge, Somerville, or All four cities) for destination points
   of interest including schools, healthcare facilities, transit stations, stores, and
   greenspaces and write these locations of interest to coordinate CSVs. Multiple separate
   CSVs are created for each type of destination (ex. schools, transit stations, etc.),
   which are then combined into a master CSV containing all destinations for the given region. 

3. **`census/`** — Assign census-tract population to graph nodes using deterministic,
   area-weighted Voronoi allocation. `build_census_tracts.py` joins the population value of a tract to
   the associated tract geometry; `assignment.py` performs the allocation of population to nodes
   (or intersections) on the graph; and `run_census_assignment.py` is the runner.

4. **`od_generation/`** — Generate travel demand as a set of Origin Destination (OD) pairs over the
   graph. Two generators feed a single combined demand file:
   - **LODES commutes** (`lodes_io.py`, `lodes_pairs.py`, `lodes_sampling.py`):
     home→work trips built from Census LODES data, sampled to favor shorter, more bikeable trips.
   - **Population-weighted POI trips** (`build_poi_od_pairs.py`, `poi_destination_choice.py`):
     Homes (nodes on the graph) are drawn in proportion to assigned population so higher-population points are more likely
     to be chosen (see census module). Destination points (from the `destination_csvs/` module) are snapped to the closest
     node on the graph. Homes are then paired to destination POIs, or points of interest, by specific rules that vary by
     category.

   `generate_od_demand.py` combines both the **Population-weighted POI trips** and the **LODES commutes** for a demand
   scenario defined in `od_generation/config/demand_parameters.csv`, writing columns
   `origin_node, destination_node, category, count`.

5. **`road_usage/`** — Generates the least-costly path on the network for each origin-destination pair, and assigns the
   graph edges (road segments) 3 new metrics:
   - `path_count` : Measures traffic demand on the network
   - `usage_stress` (`path_count` * `max_lts`) : Highlights high-stress and high-use road segments
   - `potential_Dbenefit` (`path_count` * (`cost`-`distance`)) : Quantifies the potential improvement if the given road
     segment were to be improved (similar to `usage_stress` as high-stress & high-use roads would have a greater impact
     compared to less-popular or less-stressful road segments, however potential improvement is more directly effected by
     the length of the given road segment)

6. **`one_way_evaluation/`** — For the set of origin-destination pairs, maps the most efficient path for trips in both
   directions (ex. home→school and school→home) and highlights one-way road segments that cause disproportionately large
   detours in one direction compared to the other. The one-way road segments are then scored based on the severity of the
   detour and the frequency of affected trips

7. **`corridor_analysis/`** — Isolates connected low-stress (LTS 1 & 2) "safe zones" into discrete islands and computes the
   highest-ROI (highest return on investment) missing link corridors to bridge them. Generates interactive visualizations
   (PyDeck/Streamlit), an updated scenario of the network if the corridor road segments were improved (GraphML format), and
   GeoPackage (`.gpkg`) files for QGIS integration.

8. **`node_accessibility/`** — Each node (or intersection) in the graph is given a rating corresponding to the ratio of the
   current connectivity in the surrounding road network (considering the stress level ratings of the surrounding edges) and
   the potential connectivity (if all road segments had a stress level rating of LTS 1). These ratings are also compared
   with demographic information to investigate if there is a correlation between the two. 

## Getting Started

### Installing Dependencies and Packages

1. Set up a Conda environent:
   ```
   conda create -n bcu_graph_analysis python=3.12
   conda activate bcu_graph_analysis
   ```

2. Install the project:
   ```
   python -m pip install -e '.[test,dev]'
   ```

## Running the Pipeline

### Building the graph and destinations

`graph_builder/main.py` and `destination_csvs/csv_maker.py` are run as scripts to
build the cost graph and destination CSVs. These download from OSM/Overpass and
cache intermediate files under the data root, so they are only re-run when the
underlying inputs or LTS rules change.

### Generating OD demand

```
python src/bcu_analysis/od_generation/generate_od_demand.py --scenario-id 1
```

Reads the per-category trip counts for the chosen scenario from
`od_generation/config/demand_parameters.csv`, runs the LODES and POI generators, and
writes the combined OD demand CSV consumed by the one-way analysis.

### Running Corridor & Missing Link Analysis
The corridor analysis can be run via the command-line script for batch GIS exports or explored interactively via the Streamlit dashboard.

Run to generate (HTML maps, .gpkg, .graphml) via CLI:
```
python src/bcu_analysis/corridor_analysis/run_corridors.py boston --data-dir ./data --output-dir ./outputs
Note: You can replace boston with greater_boston(To view Boston, Cambridge, Somerville, and Brookline). Use the --help flag to adjust parameters like --min-island-size and --link-complexity.
```
To view the streamlit dashboard:
```
streamlit run src/bcu_analysis/corridor_analysis/dashboard.py
```

## Directory Structure

```
.
├── src
│   └── bcu_analysis                      # The importable Python package
│       ├── graph_builder                 # Build the LTS-weighted cost graph from OSM
│       │   ├── main.py                   #   Orchestrates the graph build
│       │   ├── osm_download.py           #   Overpass/OSMnx download of tags and graph
│       │   ├── assign_cost.py            #   cost = length × LTS stress multiplier
│       │   ├── lts_functions.py          #   Level of Traffic Stress computation
│       │   ├── config/                   #   LTS tables and OSM-tag parsing rules (yml)
│       │   └── query/greater_boston.query
│       ├── destination_csvs              # Overpass queries for destination POIs
│       │   ├── csv_maker.py
│       │   └── query/
│       ├── census                        # Assign census population to graph nodes
│       │   ├── build_census_tracts.py    #   Join TIGER geometry + ACS population
│       │   ├── assignment.py             #   Area-weighted Voronoi allocation
│       │   ├── run_census_assignment.py  #   Runner
│       │   └── visualize_census_assignment.py
│       └── od_generation                 # Origin–destination travel demand
│           ├── generate_od_demand.py     #   Combine LODES + POI demand for a scenario
│           ├── lodes_io.py / lodes_pairs.py / lodes_sampling.py   # LODES commutes
│           ├── build_poi_od_pairs.py / poi_destination_choice.py  # POI trips
│           └── config/demand_parameters.csv  
│       └── corridor_analysis             # Missing link computation and visualization
│              ├── run_corridors.py          #   CLI runner for batch processing and GIS export
│              ├── dashboard.py              #   Interactive Streamlit dashboard
│              ├── core_algorithms.py        #   Island detection and missing link logic
│              └── export_utils.py           #   PyDeck rendering and file export utilities
├── docs                                  # Documentation + Sphinx auto-doc setup
│   └── census_assignment.md
├── tests
│   └── test_census_assignment.py
├── pyproject.toml                        # Metadata, dependencies, build config
├── CHANGELOG.md
├── CONTRIBUTIONS.md
├── LICENSE.md
└── README.md                             # You are here
```
