import osmnx as ox
import geopandas as gpd

from census_assignment import assign_population_to_nodes_by_tract_area

GRAPH_PATH = "data/Boston_3.graphml"
TRACT_PATH = "data/census/ma_tracts_population.geojson"

OUTPUT_NODES_GPKG = "data/census/Boston_nodes_with_population.gpkg"
OUTPUT_NODES_PARQUET = "data/census/Boston_nodes_with_population.parquet"
OUTPUT_ALLOC_CSV = "data/census/Boston_node_tract_allocation.csv"
OUTPUT_ALLOC_PARQUET = "data/census/Boston_node_tract_allocation.parquet"

print("Loading graph...")
G = ox.load_graphml(GRAPH_PATH)

print("Converting graph to nodes...")
nodes, edges = ox.graph_to_gdfs(G)

print("Loading census tracts...")
tracts = gpd.read_file(TRACT_PATH)

print("Running census assignment...")
nodes_with_pop, allocation = assign_population_to_nodes_by_tract_area(
    nodes,
    tracts,
    population_col="population",
    tract_id_col="GEOID",
    projected_crs="EPSG:26986",
    verbose=True,
)

print("Saving outputs...")
nodes_with_pop.to_file(OUTPUT_NODES_GPKG, driver="GPKG")
nodes_with_pop.to_parquet(OUTPUT_NODES_PARQUET)

allocation.to_csv(OUTPUT_ALLOC_CSV, index=False)
allocation.to_parquet(OUTPUT_ALLOC_PARQUET, index=False)

print("Done.")
print("Original tract population total:", tracts["population"].sum())
print("Assigned node population total:", nodes_with_pop["assigned_population"].sum())
print("Number of allocation rows:", len(allocation))
print("Nodes with assigned population:", (nodes_with_pop["assigned_population"] > 0).sum())

print("Saved:", OUTPUT_NODES_GPKG)
print("Saved:", OUTPUT_NODES_PARQUET)
print("Saved:", OUTPUT_ALLOC_CSV)
print("Saved:", OUTPUT_ALLOC_PARQUET)
