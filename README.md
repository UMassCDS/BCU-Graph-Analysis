# BCU Graph Analysis

Analysis of bicycle connectivity and Level of Traffic Stress (LTS) for
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

### Building the graph

1. Run:
   ```
   python src/bcu_analysis/graph_builder/build_cost_graph.py COST_SCENARIO_ID REGION --data-dir FOLDER
   ```
   - `COST_SCENARIO_ID` should be replaced with the specific ID number for the cost scenario of interest (please see
     `src/bcu_analysis/graph_builder/config/cost_parameters.csv` to view cost scenarios)
   - `REGION` should be replaced with the region of interest (boston, brookline, cambridge, somerville, greater_boston)
   - `FOLDER` should be replaced with the path to the folder where the data will be stored 

This will build the cost graph (with the specified cost scenario).

### Generating OD demand

2. Run:
   ```
   python src/bcu_analysis/destination_csvs/csv_maker.py FOLDER REGION`
   ````
   followed by:
   ```
   python src/bcu_analysis/destination_csvs/combining_csvs.py FOLDER REGION
   ```
   - `REGION` should be replaced with the region of interest (Boston, Brookline, Cambridge, Somerville, or All). Note that the `csv_maker.py` script only processes 1 city
     at a time, so to generate destinations for all of Greater Boston, run the first command 4 times (once for each city) and then run the second command with region as All.
   - `FOLDER` should be replaced with the path to the folder where the data is stored

This will generate a list of all destination points and their locations.

3. Run:
   ```
   python bcu_analysis.census.run_census_assignment --region REGION --graph-path GRAPH_PATH --tract-path TRACT_PATH --output-directory OUTPUT_PATH --output-prefix
   OUTPUT_PREFIX
   ```
      - `REGION` should be replaced with the region of interest (boston, brookline, cambridge, somerville, or greater-boston)
      - `GRAPH_PATH` should be your root directory + `/output/cost_scenarios/cost_scenario_#/REGION_cost_scenario_#_simplified.graphml` where the # is replaced with the ID
        number of the cost scenario of interest and REGION is replaced with the region of interest (boston, brookline, cambridge, somerville, or greater_boston)
      - `TRACT_PATH` should be your root directory + `/ma_tracts_population.geojson`
      - `OUTPUT_PATH` should be your root directory + `/census_results`
      - `OUTPUT_PREFIX` should be `REGION_cost_scenario_#` where the # is replaced with the ID number of the cost scenario of interest and REGION is replaced with the
        region of interest (boston, brookline, cambridge, somerville, or greater_boston)

This will assign population counts to each node in the cost graph (which represent origin points, or points where people are coming from)

4. Run:
   ```
   python src/bcu_analysis/od_generation/generate_od_demand.py COST_SCENARIO_ID REGION --demand-scenario DEMAND_SCENARIO_ID --data-dir FOLDER --pop-geojson-path PATH
   ```
   - `COST_SCENARIO_ID` should be replaced with the ID number for the cost scenario of interest 
   - `REGION` should be replaced with the region of interest (boston, brookline, cambridge, somerville, or greater_boston)
   - `DEMAND_SCENARIO_ID` should be replaced with the ID number for the demand scenario of interest (please see
     `src/bcu_analysis/od_generation/config/demand_parameters.csv` to view demand scenarios)
   - `FOLDER` should be replaced with the path to the folder where the data is stored
   - `PATH` should be your root directory (`FOLDER`) + `/census_results/REGION_cost_scenario_#_nodes_with_population_web.geojson` where the # is replaced with the ID
     number of the cost scenario of interest and REGION is replaced with the region of interest (boston, brookline, cambridge, somerville, or greater_boston)

This will generate a list of origin-destination pairs that estimate starting and ending points of popular trips taken on the network. 

### Road Usage Analysis 

1. Run:
   ```
   python src/bcu_analysis/road_usage/path_count.py FOLDER DEMAND_SCENARIO_ID COST_SCENARIO_ID REGION
   ```
   - `FOLDER` should be replaced with the path to the folder where the data is stored
   - `DEMAND_SCENARIO_ID` should be replaced with the ID number for the demand scenario of interest
   - `COST_SCENARIO_ID` should be replaced with the ID number for the cost scenario of interest 
   - `REGION` should be replaced with the region of interest (Boston, Brookline, Cambridge, Somerville, or All)

This will generate the least-cost route for each origin-destination pair and add a new attribute called `path_count` to the edges of the cost graph. `path_count` is the 
number of least-cost paths that cross through a given edge.

**WARNING:** If this file is throwing an error relating to cpu core count, it is likely related to the following code, which sets the value for the requested number of cpus 
for multicore processing...
   ```
   requested_workers = int(
            os.environ.get(
                "SLURM_CPUS_PER_TASK"
                os.cpu_count() or 1,
            )
        )
   ```

2. Run:
   ```
   python src/bcu_analysis/road_usage/metrics.py FOLDER DEMAND_SCENARIO_ID COST_SCENARIO_ID REGION
   ```
   - `FOLDER` should be replaced with the path to the folder where the data is stored
   - `DEMAND_SCENARIO_ID` should be replaced with the ID number for the demand scenario of interest
   - `COST_SCENARIO_ID` should be replaced with the ID number for the cost scenario of interest 
   - `REGION` should be replaced with the region of interest (Boston, Brookline, Cambridge, Somerville, or All)

This will add two attributes to the edges of the cost graph: `usage_stress` and `potential_Dbenefit` (please see the **`/road_usage/`** section under **Modules** for 
further clarification). 

3. (Optional) Run:
   ```
   python src/bcu_analysis/road_usage/Distributions.py FOLDER REGION DEMAND_SCENARIO_ID COST_SCENARIO_ID
   ```
   - `FOLDER` should be replaced with the path to the folder where the data is stored
   - `REGION` should be replaced with the region of interest (Boston, Brookline, Cambridge, Somerville, or All)
   - `DEMAND_SCENARIO_ID` should be replaced with the ID number for the demand scenario of interest
   - `COST_SCENARIO_ID` should be replaced with the ID number for the cost scenario of interest
  
This will report the 5-number summary (minimum, 1st quartile, median, 3rd quartile, and maximum) for the following edge attributes of the cost graph: `usage_stress`, 
`potential_Dbenefit`, `path_count`, `distance`, `max_lts`, and `cost`. Optional flags to add to the command include:
   - `--no_path_count` : If written, will not report on the `path_count` attribute 
   - `--no_distance` : If written, will not report on the `distance` attribute 
   - `--no_max_lts` : If written, will not report on the `max_lts` attribute 
   - `--no_cost` : If written, will not report on the `cost` attribute 
   - `--no_usage_stress` : If written, will not report on the `usage_stress` attribute 
   - `--no_potential_Dbenefit` : If written, will not report on the `potential_Dbenefit` attribute 

4. Run:
   ```
   python -u src/bcu_analysis/road_usage/svgs/HeatmapLog.py FOLDER REGION DEMAND_SCENARIO_ID COST_SCENARIO_ID ATTRIBUTE LOWER_THRESHOLD UPPER_THRESHOLD
   ```
   - `FOLDER` should be replaced with the path to the folder where the data is stored
   - `REGION` should be replaced with the region of interest (Boston, Brookline, Cambridge, Somerville, or All)
   - `DEMAND_SCENARIO_ID` should be replaced with the ID number for the demand scenario of interest
   - `COST_SCENARIO_ID` should be replaced with the ID number for the cost scenario of interest
   
    --onlyLTS3and4
### One-Way Analysis
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
### Node Accessibility Analysis 

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
