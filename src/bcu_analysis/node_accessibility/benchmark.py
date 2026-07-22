"""Benchmark node accessibility on a reproducible graph-node sample."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import osmnx as ox
import pandas as pd

from bcu_analysis.node_accessibility.accessibility import (
    calculate_node_accessibility,
)


DEFAULT_GRAPH_PATH = Path(
    "/work/pi_plunkett_umass_edu/bcu/data/processed/osm/"
    "greater_boston_6_cost_simplified.graphml"
)

DEFAULT_OUTPUT_PATH = Path(
    "/work/pi_plunkett_umass_edu/bcu/data/processed/accessibility/"
    "node_accessibility_benchmark.csv"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--graph-path",
        type=Path,
        default=DEFAULT_GRAPH_PATH,
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=25,
    )
    parser.add_argument(
        "--cost-field",
        default="cost_typical_adult_Baseline",
    )
    parser.add_argument(
        "--cutoff-miles",
        type=float,
        default=1.5,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.sample_size <= 0:
        raise ValueError("--sample-size must be positive.")

    print(f"Loading graph: {args.graph_path}")
    graph = ox.load_graphml(args.graph_path)

    origins = list(graph.nodes)[: args.sample_size]
    results = []

    total_start = time.perf_counter()

    for index, origin in enumerate(origins, start=1):
        node_start = time.perf_counter()

        result = calculate_node_accessibility(
            graph=graph,
            origin_node=origin,
            cutoff_miles=args.cutoff_miles,
            cost_field=args.cost_field,
        )

        elapsed = time.perf_counter() - node_start
        result["runtime_seconds"] = elapsed
        results.append(result)

        print(
            f"{index}/{len(origins)} "
            f"node={origin} "
            f"runtime={elapsed:.3f}s"
        )

    total_elapsed = time.perf_counter() - total_start

    frame = pd.DataFrame(results)
    args.output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    frame.to_csv(args.output_path, index=False)

    average = frame["runtime_seconds"].mean()
    median = frame["runtime_seconds"].median()
    maximum = frame["runtime_seconds"].max()

    estimated_hours = (
        average * graph.number_of_nodes() / 3600
    )

    print()
    print(f"Processed nodes: {len(frame)}")
    print(f"Total runtime: {total_elapsed:.2f}s")
    print(f"Average per node: {average:.3f}s")
    print(f"Median per node: {median:.3f}s")
    print(f"Maximum per node: {maximum:.3f}s")
    print(
        "Estimated sequential full-graph runtime: "
        f"{estimated_hours:.2f} hours"
    )
    print(f"Saved: {args.output_path}")


if __name__ == "__main__":
    main()
