import pandas as pd
import geopandas as gpd
import osmnx as ox
import numpy as np
import os
import random
from bcu_analysis.od_generation.poi_destination_choice import choose_destination



# POI categories keyed by the demand-scenario config keys (see config/demand_parameters.csv).
# Each entry maps to its destination coordinate CSV and the destination-choice rule.
CATEGORY_CONFIGS = {
    "home_school": {"file": r"/work/pi_plunkett_umass_edu/bcu/data/processed/osm/BostonSchool_Coordinates.csv", "rule": "closest_only"},
    "home_healthcare": {"file": r"/work/pi_plunkett_umass_edu/bcu/data/processed/osm/BostonHealthcare_Coordinates.csv", "rule": "closest_only"},
    "home_transit": {"file": r"/work/pi_plunkett_umass_edu/bcu/data/processed/osm/BostonTransitStation_Coordinates.csv", "rule": "lognormal"},
    "home_store": {"file": r"/work/pi_plunkett_umass_edu/bcu/data/processed/osm/BostonStore_Coordinates.csv", "rule": "lognormal"},
    "home_greenspace": {"file": r"/work/pi_plunkett_umass_edu/bcu/data/processed/osm/BostonGreenspace_Coordinates.csv", "rule": "lognormal"},
}


def build_poi_od_pairs(
    category_counts=None,
    graph_path="/work/pi_plunkett_umass_edu/bcu/data/processed/osm/greater_boston_cost_simplified.graphml",
    pop_geojson_path=r"/work/pi_plunkett_umass_edu/bcu/data/processed/census/results/Boston_nodes_with_population_web.geojson",
    output_path=None,
):
    """
    Generate POI origin-destination pairs with a per-pair draw count.

    Parameters:
    - category_counts (dict | None): {category_key: n_homes} for the POI categories to
      draw (keys from CATEGORY_CONFIGS). Categories with no/zero count are skipped.
      Defaults to 100 homes for every category.
    - graph_path (str): GraphML used to snap homes and destinations to nodes.
    - pop_geojson_path (str): Population-weighted node geojson used to sample homes.
    - output_path (str | None): If given, also write the pairs to this CSV.

    Returns:
    - pd.DataFrame: columns origin_node, destination_node, category, count.
    """
    print("Starting POI Origin-Destination Generation...")

    if category_counts is None:
        category_counts = {category: 100 for category in CATEGORY_CONFIGS}

    G = ox.load_graphml(graph_path)

    pop_data = gpd.read_file(pop_geojson_path)
    pop_nodes = ox.distance.nearest_nodes(G, X=pop_data.geometry.x, Y=pop_data.geometry.y)

    def sample_homes(num_homes):
        return random.choices(pop_nodes, weights=pop_data['assigned_population'].values, k=num_homes)

    def load_and_snap_csv(filepath):
        if not os.path.exists(filepath):
            print(f"WARNING: destination file not found, skipping: {filepath}")
            return []
        df = pd.read_csv(filepath)
        if df.empty:
            print(f"WARNING: destination file is empty, skipping: {filepath}")
            return []
        snapped = ox.distance.nearest_nodes(G, X=df['longitude'].values, Y=df['latitude'].values)
        return list(set(snapped))

    od_pairs = {}
    for category, config in CATEGORY_CONFIGS.items():
        n_homes = int(category_counts.get(category, 0) or 0)
        if n_homes <= 0:
            continue

        dest_nodes = load_and_snap_csv(config["file"])
        if not dest_nodes: continue

        home_nodes = sample_homes(n_homes)
        for origin in home_nodes:
            chosen_dest = choose_destination(origin, dest_nodes, G, rule=config["rule"])

            key = (origin, chosen_dest, category)
            if key in od_pairs:
                od_pairs[key]["count"] += 1
            else:
                od_pairs[key] = {
                    "origin_node": origin,
                    "destination_node": chosen_dest,
                    "category": category,
                    "count": 1
                }

    pairs_df = pd.DataFrame(
        list(od_pairs.values()),
        columns=["origin_node", "destination_node", "category", "count"],
    )
    print(f"Generated {len(pairs_df)} POI pairs.")

    if output_path is not None:
        pairs_df.to_csv(output_path, index=False)

    return pairs_df

if __name__ == "__main__":
    build_poi_od_pairs(output_path="/work/pi_plunkett_umass_edu/bcu/data/processed/osm/poi_od_pairs.csv")