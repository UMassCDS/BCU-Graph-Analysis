import pandas as pd
import geopandas as gpd
import osmnx as ox
import numpy as np
import random
from pathlib import Path
from trip_sampler import sample_trips

from config import DATA_FOLDER, PROCESSED_OSM_DIR

def build_poi_od_pairs():
    print("Starting POI Origin-Destination Generation...")
    graph_path = Path(PROCESSED_OSM_DIR) / "Boston_6_cost_simplified.graphml"
    G = ox.load_graphml(graph_path)

    pop_geojson_path = Path(DATA_FOLDER) / "processed" / "census" / "results" / "Boston_nodes_with_population_web.geojson" 
    pop_data = gpd.read_file(pop_geojson_path)
    pop_nodes = ox.distance.nearest_nodes(G, X=pop_data.geometry.x, Y=pop_data.geometry.y)

    pop_lookup = dict(zip(pop_nodes, pop_data['assigned_population'].values))

    NUM_HOMES = 500
    home_nodes = random.choices(pop_nodes, weights=pop_data['assigned_population'].values, k=NUM_HOMES)

    def load_and_snap_csv(filepath):
        if not filepath.exists(): return []
        df = pd.read_csv(filepath)
        snapped = ox.distance.nearest_nodes(G, X=df['longitude'].values, Y=df['latitude'].values)
        return list(set(snapped))

    category_configs = {
        "Home to elementary school": {"file": Path(PROCESSED_OSM_DIR) / "BostonSchools_Coordinates.csv", "rule": "closest_only"},
        "Home to healthcare": {"file": Path(PROCESSED_OSM_DIR) / "BostonHealthcare_Coordinates.csv", "rule": "closest_only"},
        "Home to office": {"file": Path(PROCESSED_OSM_DIR) / "BostonOffice_Coordinates.csv", "rule": "lognormal"},
        "Home to transit": {"file": Path(PROCESSED_OSM_DIR) / "BostonBusStations_Coordinates.csv", "rule": "lognormal"},
        "Home to stores": {"file": Path(PROCESSED_OSM_DIR) / "BostonStore_Coordinates.csv", "rule": "lognormal"},
        "Home to greenspaces": {"file": Path(PROCESSED_OSM_DIR) / "BostonGreenspace_Coordinates.csv", "rule": "lognormal"},
    }
    
    od_pairs = []
    for category, config in category_configs.items():
        dest_nodes = load_and_snap_csv(config["file"])
        if not dest_nodes: continue
            
        for origin in home_nodes:
            chosen_dest = sample_trips(origin, dest_nodes, G, rule=config["rule"])
            
            od_pairs.append({
                "origin_node": origin,
                "destination_node": chosen_dest,
                "category": category,
                "assigned_population": pop_lookup.get(origin, 0) 
            })

    out_path = Path(PROCESSED_OSM_DIR) / "poi_od_pairs.csv"
    pd.DataFrame(od_pairs).to_csv(out_path, index=False)
    print(f"Generated {len(od_pairs)} pairs.")

if __name__ == "__main__":
    build_poi_od_pairs()
