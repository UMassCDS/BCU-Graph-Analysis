import pandas as pd
import osmnx as ox
from pathlib import Path

import lts_functions as lts
# Import from config.py
from config import DATA_FOLDER, RAW_OSM_DIR, PROCESSED_OSM_DIR, PARAMETERS_DIR, NO_ACCESS_WEIGHT, PROFILES_TO_APPLY

OVERWRITE = False

def lts_edges(region, gdf_edges):
    '''
    Calculate the LTS for all edges
    '''
    global OVERWRITE
    
    filepathAll = Path(PROCESSED_OSM_DIR) / f"{region}_all_lts.csv"

    if filepathAll.exists() and (OVERWRITE is False):
        print(f"Loading LTS for {region}")
        all_lts = lts.read_lts_csv(filepathAll)
    else:
        OVERWRITE = True
        rating_dict = lts.read_rating()
        tables = lts.read_tables()

        gdf_edges = lts.parking_present(gdf_edges, rating_dict)
        gdf_edges = lts.convert_both_tag(gdf_edges)
        gdf_edges = lts.parse_lanes(gdf_edges)
        gdf_edges = lts.get_prevailing_speed(gdf_edges, rating_dict)
        gdf_edges = lts.get_lanes(gdf_edges, default_lanes=2)
        gdf_edges = lts.get_centerlines(gdf_edges, rating_dict)
        gdf_edges = lts.width_ft(gdf_edges)
        
        gdf_edges = lts.define_narrow_wide(gdf_edges)
        gdf_edges = lts.define_adt(gdf_edges, rating_dict)
        gdf_edges = lts.LTS_separation(gdf_edges)

        lts.column_value_counts(gdf_edges)
        all_lts = lts.calculate_lts(gdf_edges, tables)
        gdf_edges = lts.define_zoom(gdf_edges, rating_dict)
        
        all_lts.to_csv(filepathAll)

    return all_lts

def build_cost_graph(city):
    graph_path = Path(RAW_OSM_DIR) / f"{city}_raw.graphml"
    lts_path = Path(PROCESSED_OSM_DIR) / f"{city}_all_lts.csv"
    cost_csv_path = Path(PARAMETERS_DIR) / "Cost first draft.csv" 

    if not graph_path.exists():
        raise FileNotFoundError(f"Graph not found: {graph_path}")
    if not lts_path.exists():
        raise FileNotFoundError(f"LTS data not found: {lts_path}")
    if not cost_csv_path.exists():
        raise FileNotFoundError(f"Cost CSV not found: {cost_csv_path}")

    print(f"Loading graph for {city}")
    G = ox.load_graphml(graph_path)

    print(f"Loading LTS data for {city}")
    lts_df = pd.read_csv(lts_path, usecols=['u', 'v', 'key', 'LTS'], low_memory=False)
    
    print("Loading dynamic profile costs...")
    df_costs = pd.read_csv(cost_csv_path)

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
        for user_group, scenario in PROFILES_TO_APPLY:
            attr_name = f"cost_{user_group}_{scenario.replace(' ', '_')}"
            if is_no_access:
                data[attr_name] = length * NO_ACCESS_WEIGHT
            else:
                row = df_costs[(df_costs['user_group'] == user_group) & (df_costs['scenario'] == scenario)]
                if not row.empty:
                    weight_multiplier = float(row[f"lts{safe_lts}_weight"].iloc[0])
                    data[attr_name] = length * weight_multiplier

    print(f"Matched LTS for {matched} edges, {missing} edges had no LTS row")

    out_path = Path(PROCESSED_OSM_DIR) / f"{city}_cost.graphml"
    ox.save_graphml(G, out_path)
    print(f"Saved cost graph to {out_path}")

    return G

def simplify_cost_graph(city, G=None):
    if G is None:
        in_path = Path(PROCESSED_OSM_DIR) / f"{city}_cost.graphml"
        if not in_path.exists():
            raise FileNotFoundError(f"Cost graph not found: {in_path}")
        print(f"Loading cost graph for {city}")
        
        G = ox.load_graphml(in_path) 

    def max_lts(values):
        levels = []
        for v in values:
            try:
                if v == '' or pd.isna(v): continue
                levels.append(int(float(v)))
            except (ValueError, TypeError):
                continue
        return max(levels) if levels else ''

    for _, _, data in G.edges(data=True):
        data['max_lts'] = data.get('LTS', '')

    print(f"Simplifying graph ({G.number_of_edges()} edges)")
    
    edge_attr_aggs = {'length': sum, 'max_lts': max_lts}
    
    sample_edge = next(iter(G.edges(data=True)))[2]
    cost_cols = [col for col in sample_edge.keys() if col.startswith('cost_')]
    for cost_col in cost_cols:
        edge_attr_aggs[cost_col] = sum

    G_simplified = ox.simplify_graph(
        G,
        edge_attr_aggs=edge_attr_aggs,
    )
    print(f"Simplified to {G_simplified.number_of_edges()} edges")

    out_path = Path(PROCESSED_OSM_DIR) / f"{city}_6_cost_simplified.graphml"
    ox.save_graphml(G_simplified, out_path)
    print(f"Saved simplified cost graph to {out_path}")

    return G_simplified
