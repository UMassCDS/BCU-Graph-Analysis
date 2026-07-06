import osmnx as ox
import geopandas as gpd

from bcu_analysis.census.assignment import assign_population_to_nodes_by_tract_area

GRAPH_PATH = "data/Boston_3.graphml"
TRACT_PATH = "data/census/ma_tracts_population.geojson"

OUTPUT_NODES_GPKG = "data/census/Boston_nodes_with_population.gpkg"
OUTPUT_NODES_PARQUET = "data/census/Boston_nodes_with_population.parquet"
OUTPUT_NODES_WEB_GEOJSON = "data/census/Boston_nodes_with_population_web.geojson"

OUTPUT_ALLOC_CSV = "data/census/Boston_node_tract_allocation.csv"
OUTPUT_ALLOC_PARQUET = "data/census/Boston_node_tract_allocation.parquet"

print("Loading graph...")
G = ox.load_graphml(GRAPH_PATH)

print("Converting graph to nodes...")
nodes, edges = ox.graph_to_gdfs(G)

print("Loading census tracts...")
tracts = gpd.read_file(TRACT_PATH)

print("Loading Boston boundary...")
region_boundary = ox.geocode_to_gdf("Boston, Massachusetts, USA")

print("Running census assignment...")
nodes_with_pop, allocation = assign_population_to_nodes_by_tract_area(
    nodes,
    tracts,
    population_col="population",
    tract_id_col="GEOID",
    projected_crs="EPSG:26986",
    candidate_buffer_m=100,
    tract_filter_method="convex_hull",
    region_boundary_gdf=region_boundary,
    min_region_overlap_share=0.50,
    verbose=True,
)

print("Saving outputs...")

# Keep projected CRS output for GIS/area-based review.
nodes_with_pop.to_file(OUTPUT_NODES_GPKG, driver="GPKG")
nodes_with_pop.to_parquet(OUTPUT_NODES_PARQUET)

# Save a separate EPSG:4326 version for web maps, Folium, Mapbox, and GeoJSON viewers.
nodes_with_pop_web = nodes_with_pop.to_crs("EPSG:4326")
nodes_with_pop_web.to_file(OUTPUT_NODES_WEB_GEOJSON, driver="GeoJSON")

allocation.to_csv(OUTPUT_ALLOC_CSV, index=False)
allocation.to_parquet(OUTPUT_ALLOC_PARQUET, index=False)

assigned_tract_ids = set(allocation["GEOID"].astype(str))
assigned_tract_population = tracts[
    tracts["GEOID"].astype(str).isin(assigned_tract_ids)
]["population"].sum()

print("Done.")
print("Projected node CRS:", nodes_with_pop.crs)
print("Web map node CRS:", nodes_with_pop_web.crs)
print("Original loaded tract population total:", tracts["population"].sum())
print("Assigned tract population total:", assigned_tract_population)
print("Assigned node population total:", nodes_with_pop["assigned_population"].sum())
print("Number of assigned tracts:", allocation["GEOID"].nunique())
print("Number of allocation rows:", len(allocation))
print("Nodes with assigned population:", (nodes_with_pop["assigned_population"] > 0).sum())

print("Saved:", OUTPUT_NODES_GPKG)
print("Saved:", OUTPUT_NODES_PARQUET)
print("Saved:", OUTPUT_NODES_WEB_GEOJSON)
print("Saved:", OUTPUT_ALLOC_CSV)
print("Saved:", OUTPUT_ALLOC_PARQUET)
