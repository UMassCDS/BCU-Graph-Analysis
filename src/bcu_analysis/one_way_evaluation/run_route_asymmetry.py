import argparse
import os
import time

import pandas as pd

from bcu_analysis.graph_builder.build_cost_graph import CITY_OPTIONS, resolve_area
from bcu_analysis.one_way_evaluation.route_asymmetry import (
    accumulate_asymmetry,
    asymmetry_edges_df,
    load_cost_graph,
)


def main(
    area,
    cost_scenario,
    demand_scenario=1,
    data_dir=None,
    out_csv=None,
    workers=None,
):
    """
    Route every OD pair both ways, accumulate route asymmetry onto the cheaper
    route's segments, and write a per-edge CSV of scores to disk.

    Inputs are derived from the area and the scenario ids, matching the layout written
    by graph_builder/build_cost_graph.py and od_generation/generate_od_demand.py: the
    simplified graph under ``output/cost_scenarios/cost_scenario_{cost_scenario}/`` and
    the combined OD pairs under
    ``output/demand_scenarios/demand_scenario_{demand_scenario}/``. Scores depend on
    both scenarios, so the output filename carries both ids.

    The CSV is keyed by the edge (u, v, key) so it can be joined back to the graph
    for geometry when plotting, without persisting the full geometry.

    Parameters:
    - area (str): Municipality key or 'greater_boston'; resolved to a region name by
      graph_builder.build_cost_graph.resolve_area so it matches the graph on disk.
    - cost_scenario (int): Cost scenario id whose simplified graph is routed on.
    - demand_scenario (int | str): Demand scenario id whose OD pairs are routed.
    - data_dir (str): Root data directory (the parent of raw/, processed/, output/).
    - out_csv (str | None): Override for the scores CSV; derived from the scenarios
      when None.
    - workers (int | None): Number of routing processes; defaults to the CPU count.

    Returns:
    - pd.DataFrame: per-edge scores, one row per graph edge.
    """
    if data_dir is None:
        raise ValueError("data_dir is required.")

    region_name, _ = resolve_area(area)

    data_dir = data_dir.rstrip("/")
    cost_dir = f"{data_dir}/output/cost_scenarios/cost_scenario_{cost_scenario}"
    demand_dir = f"{data_dir}/output/demand_scenarios/demand_scenario_{demand_scenario}"

    graph_path = f"{cost_dir}/{region_name}_cost_scenario_{cost_scenario}_simplified.graphml"
    od_path = f"{demand_dir}/{region_name}_all_pairs_demand_scenario_{demand_scenario}.csv"
    if out_csv is None:
        out_csv = (
            f"{data_dir}/processed/one_way_evaluation/"
            f"{region_name}_route_asymmetry_DS{demand_scenario}_CS{cost_scenario}.csv"
        )

    if not os.path.exists(graph_path):
        raise FileNotFoundError(
            f"Cost graph not found: {graph_path}. Build it first with "
            f"'python src/bcu_analysis/graph_builder/build_cost_graph.py {cost_scenario} {area} "
            f"--data-dir {data_dir}'."
        )
    if not os.path.exists(od_path):
        raise FileNotFoundError(
            f"OD pairs not found: {od_path}. Generate them first with "
            f"'python src/bcu_analysis/od_generation/generate_od_demand.py {cost_scenario} {area} "
            f"--demand-scenario {demand_scenario} --data-dir {data_dir}'."
        )

    if workers is None:
        workers = os.cpu_count() or 1

    print(f"Region {region_name}, cost scenario {cost_scenario}, demand scenario {demand_scenario}")
    print(f"Loading cost graph from {graph_path}")
    load_start = time.perf_counter()
    G = load_cost_graph(graph_path)
    print(f"  loaded {G.number_of_edges()} edges in {time.perf_counter() - load_start:.1f}s")

    print(f"Loading OD pairs from {od_path}")
    od_df = pd.read_csv(od_path, usecols=["origin_node", "destination_node"])

    G = accumulate_asymmetry(G, od_df, workers=workers)

    edges = asymmetry_edges_df(G)

    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    print(f"Saving {len(edges)} edge scores to {out_csv}")
    edges.to_csv(out_csv, index=False)

    top = edges.sort_values("asymmetry", ascending=False).head(15)
    print("Top asymmetric segments:")
    print(
        top[["u", "v", "key", "asymmetry", "trip_count", "blame_count", "max_lts", "length"]]
        .to_string(index=False)
    )
    return edges


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Score street segments by OD/DO route-cost asymmetry (contra-flow candidates)."
    )
    parser.add_argument(
        "cost_scenario",
        type=int,
        help="Cost scenario id whose simplified graph should be routed on",
    )
    parser.add_argument(
        "area",
        choices=CITY_OPTIONS,
        help="Municipality to score, or 'greater_boston' for all of them combined.",
    )
    parser.add_argument(
        "--demand-scenario",
        type=int,
        default=1,
        help="Demand scenario id whose OD pairs should be routed",
    )
    parser.add_argument(
        "--data-dir",
        required=True,
        help="Root data directory",
    )
    parser.add_argument(
        "--out-csv",
        default=None,
        help="Override the derived path for the per-edge scores CSV",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of routing processes (default: all CPU cores). Use 1 for serial.",
    )
    args = parser.parse_args()
    main(
        area=args.area,
        cost_scenario=args.cost_scenario,
        demand_scenario=args.demand_scenario,
        data_dir=args.data_dir,
        out_csv=args.out_csv,
        workers=args.workers,
    )
