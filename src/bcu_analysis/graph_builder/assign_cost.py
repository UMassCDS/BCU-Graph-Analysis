import os
import pandas as pd
import osmnx as ox

import lts_functions as lts

OVERWRITE = False

dataFolder = '/work/pi_plunkett_umass_edu/bcu/data'
NO_ACCESS_WEIGHT = 100.0

# Set the single target profile here. 
# The script will only calculate this profile's weight and store it strictly as cost.
TARGET_PROFILE_USER = 'typical_adult'
TARGET_PROFILE_SCENARIO = 'Baseline'

def lts_edges(region, gdf_edges):
    '''
    Calculate the LTS for all edges
    '''
    global OVERWRITE
    
    filepathAll = f"{dataFolder}/processed/osm/{region}_all_lts.csv"
    #load graph
    if os.path.exists(filepathAll) and (OVERWRITE is False):
        print(f"Loading LTS for {region}")
        all_lts = lts.read_lts_csv(filepathAll)
        # print(f'{all_lts['LTS'].unique()=}')
    else:
        OVERWRITE = True
         # Load the configuration files to caluclate ratings
        rating_dict = lts.read_rating()
        tables = lts.read_tables()
         # Process features where side is more important than direction
        gdf_edges = lts.parking_present(gdf_edges, rating_dict)
        # Convert schema to focus on direction
        gdf_edges = lts.convert_both_tag(gdf_edges)
        # Process bike lanes
        gdf_edges = lts.parse_lanes(gdf_edges)
        # Process non-directional data
        gdf_edges = lts.get_prevailing_speed(gdf_edges, rating_dict)
        gdf_edges = lts.get_lanes(gdf_edges, default_lanes=2)
        gdf_edges = lts.get_centerlines(gdf_edges, rating_dict)
        gdf_edges = lts.width_ft(gdf_edges)
        
        gdf_edges = lts.define_narrow_wide(gdf_edges)
        gdf_edges = lts.define_adt(gdf_edges, rating_dict)
        gdf_edges = lts.LTS_separation(gdf_edges)

        lts.column_value_counts(gdf_edges) # Useful for debugging
        all_lts = lts.calculate_lts(gdf_edges, tables)
        gdf_edges = lts.define_zoom(gdf_edges, rating_dict)
        # print(f'{all_lts['LTS'].unique()=}')
        # print(f'Saving LTS for {region}')
        all_lts.to_csv(filepathAll)
        # https://geopandas.org/en/stable/docs/reference/api/geopandas.GeoDataFrame.to_file.html

    return all_lts

def build_cost_graph(city):
    graph_path = f"{dataFolder}/raw/osm/{city}_raw.graphml"
    lts_path = f"{dataFolder}/processed/osm/{city}_all_lts.csv"
    cost_csv_path = f"{dataFolder}/processed/Cost.csv" 

    if not os.path.exists(graph_path):
        raise FileNotFoundError(f"Graph not found: {graph_path}")
    if not os.path.exists(lts_path):
        raise FileNotFoundError(f"LTS data not found: {lts_path}")
    if not os.path.exists(cost_csv_path):
        raise FileNotFoundError(f"Cost CSV not found: {cost_csv_path}")

    print(f"Loading graph for {city}")
    G = ox.load_graphml(graph_path)

    print(f"Loading LTS data for {city}")
    lts_df = pd.read_csv(lts_path, usecols=['u', 'v', 'key', 'LTS'], low_memory=False)
    
    print("Loading dynamic profile costs...")
    df_costs = pd.read_csv(cost_csv_path, sep='\t')

# Map each (u, v, key) edge to its LTS for fast lookup against the graph.
    lts_by_edge = {
        (int(row.u), int(row.v), int(row.key)): row.LTS
        for row in lts_df.itertuples(index=False)
    }

    matched = 0
    missing = 0
    
    for u, v, k, data in G.edges(keys=True, data=True):
        lts_val = lts_by_edge.get((u, v, k))
        if lts_val is None: missing += 1
        else: matched += 1

        length = float(data.get('length', 0.0))
        data['LTS'] = '' if lts_val is None or pd.isna(lts_val) else int(lts_val)

        is_no_access = lts_val is None or pd.isna(lts_val) or int(lts_val) == 0
        if not is_no_access:
            safe_lts = max(1, min(4, int(lts_val)))
            
        # these values are pulled from config.py 
        # (Modified strictly for a single user_group profile 'cost' attribute)
        if is_no_access:
            data['cost'] = length * NO_ACCESS_WEIGHT
        else:
            row = df_costs[(df_costs['user_group'] == TARGET_PROFILE_USER) & (df_costs['scenario'] == TARGET_PROFILE_SCENARIO)]
            if not row.empty:
                weight_multiplier = float(row[f"lts{safe_lts}_weight"].iloc[0])
                data['cost'] = length * weight_multiplier
            else:
                data['cost'] = length * NO_ACCESS_WEIGHT

    print(f"Matched LTS for {matched} edges, {missing} edges had no LTS row")

    out_path = f"{dataFolder}/processed/osm/{city}_cost.graphml"
    ox.save_graphml(G, out_path)
    print(f"Saved cost graph to {out_path}")

    return G

def simplify_cost_graph(city, G=None):
    """
    Simplify the cost graph, merging chains of edges between intersections
    into single edges. The merged edge's "cost" (and "length") is the sum of
    the costs of the constituent edges that were merged, and "max_lts" is the
    worst (max) stress level along the merged edge.

    If G is not supplied the un-simplified cost graph is loaded from
    data/{city}_5_cost.graphml. The result is saved to
    data/{city}_6_cost_simplified.graphml.
    """
    if G is None:
        in_path = f"{dataFolder}/processed/osm/{city}_cost.graphml"
        if not os.path.exists(in_path):
            raise FileNotFoundError(f"Cost graph not found: {in_path}")
        print(f"Loading cost graph for {city}")
        
        G = ox.load_graphml(in_path) 

    def max_lts(values):
        """Worst (max) stress level among merged segments; ignores unknowns."""
        levels = []
        for v in values:
            try:
                if v == '' or pd.isna(v): continue
                levels.append(int(float(v)))
            except (ValueError, TypeError):
                continue
        return max(levels) if levels else ''
# Seed max_lts from each edge's LTS so the aggregation has it to merge.
    for _, _, data in G.edges(data=True):
        data['max_lts'] = data.get('LTS', '')

    print(f"Simplifying graph ({G.number_of_edges()} edges)")
    # Sum cost and length across the merged segments, and take the worst LTS.
    edge_attr_aggs = {'length': sum, 'max_lts': max_lts, 'cost': sum}
    
    G_simplified = ox.simplify_graph(
        G,
        edge_attr_aggs=edge_attr_aggs,
    )
    print(f"Simplified to {G_simplified.number_of_edges()} edges")

    out_path = f"{dataFolder}/processed/osm/{city}_cost_simplified.graphml"
    ox.save_graphml(G_simplified, out_path)
    print(f"Saved simplified cost graph to {out_path}")

    return G_simplified
