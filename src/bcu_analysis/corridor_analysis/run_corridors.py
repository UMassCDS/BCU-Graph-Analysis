import argparse
from pathlib import Path
from bcu_analysis.corridor_analysis import core_algorithms as core
from bcu_analysis.corridor_analysis import export_utils as export

CITIES = {
    'boston': 'Boston, Massachusetts',
    'cambridge': 'Cambridge, Massachusetts',
    'somerville': 'Somerville, Massachusetts',
    'brookline': 'Brookline, Massachusetts',
}
CITY_OPTIONS = list(CITIES) + ["greater_boston"]

def resolve_area(area):
    if area == "greater_boston":
        return "greater_boston"
    return f'{area}'

def main(area, data_dir, output_dir, min_island_size, link_complexity,demand_scenario, cost_scenario):
    region_name = resolve_area(area)
    graph_path = Path(data_dir) / f"{region_name}_cost_with_pathCount_DS{demand_scenario}_CS{cost_scenario}.graphml"
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Starting Corridor Analysis for {region_name}...")
    
    # 1. Process Logic
    G = core.load_graph(graph_path)
    G_safe, top_islands, node_to_island = core.process_islands(G, min_island_size, max_islands=15)
    proposed_corridors, missing_edges = core.compute_missing_links(G, top_islands, link_complexity)
    base_size, new_size, roi = core.calculate_roi(G_safe, G, missing_edges)
    
    print("\n--- ROI METRICS ---")
    print(f"Baseline Safe Network Nodes: {base_size}")
    print(f"Upgraded Safe Network Nodes: {new_size}")
    print(f"Network Expansion: +{roi:.1f}%\n")
    
# 2. Exports
    deck = export.build_pydeck_map(G, node_to_island, proposed_corridors, missing_edges)
    
    html_out = out_dir / f"{region_name}_corridors.html"
    gpkg_out = out_dir / f"{region_name}_corridors.gpkg"  
    graphml_out = out_dir / f"{region_name}_updated.graphml"
    
    export.export_to_html(deck, html_out)
    
    export.export_to_gis(G, proposed_corridors, gpkg_out, format="geopackage") 
    
    export.export_to_graphml(G, missing_edges, graphml_out)
    
    print("Corridor pipeline execution complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run continuous corridor bridging analysis on an LTS graph.")
    parser.add_argument("area", choices=CITY_OPTIONS, help="Municipality to process (e.g., 'boston'), or 'greater_boston'.")
    parser.add_argument("--data-dir", required=True, help="Root directory containing input graphml and CSVs.")
    parser.add_argument("--output-dir", default="./outputs", help="Directory to save HTML, GeoJSON, and GraphML exports.")
    parser.add_argument("--min-island-size", type=int, default=20, help="Minimum edges required to consider a safe network an 'island'.")
    parser.add_argument("--link-complexity", type=int, default=10, help="Bridging depth (number of top islands to connect).")
    
    # New arguments for the scenarios
    parser.add_argument("--demand-scenario", type=int, default=1, help="Demand Scenario (DS) ID number.")
    parser.add_argument("--cost-scenario", type=int, default=1, help="Cost Scenario (CS) ID number.")
    
    args = parser.parse_args()
    main(area=args.area, data_dir=args.data_dir, output_dir=args.output_dir, 
         min_island_size=args.min_island_size, link_complexity=args.link_complexity,
         demand_scenario=args.demand_scenario, cost_scenario=args.cost_scenario)
