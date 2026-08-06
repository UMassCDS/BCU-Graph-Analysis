import argparse
import os
import time

import pandas as pd

from bcu_analysis.one_way_evaluation.route_asymmetry import (
    accumulate_asymmetry,
    asymmetry_edges_df,
    load_cost_graph,
)


def main(
    graph_path,
    od_path,
    out_csv,
    workers=None,
):
    """
    Route every OD pair both ways, accumulate route asymmetry onto the cheaper
    route's segments, and write a per-edge CSV of scores to disk.

    The CSV is keyed by the edge (u, v, key) so it can be joined back to the graph
    for geometry when plotting, without persisting the full geometry.

    workers defaults to the CPU count; routing is parallelised across processes.
    """
    if workers is None:
        workers = os.cpu_count() or 1

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
        "--graph-path",
        required=True,
        help="Simplified LTS cost GraphML file.",
    )
    parser.add_argument(
        "--od-path",
        required=True,
        help="CSV containing origin and destination nodes.",
    )
    parser.add_argument(
        "--out-csv",
        required=True,
        help="Output CSV for per-edge asymmetry scores.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of routing processes (default: all CPU cores). Use 1 for serial.",
    )
    args = parser.parse_args()
    main(
        graph_path=args.graph_path,
        od_path=args.od_path,
        out_csv=args.out_csv,
        workers=args.workers,
    )
