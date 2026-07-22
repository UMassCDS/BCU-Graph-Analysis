"""Benchmark node accessibility on a reproducible random node sample."""

from __future__ import annotations

import argparse
import random
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
    "node_accessibility_benchmark_random.csv"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark accessibility on random graph nodes."
    )
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
        default=100,
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
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
    graph_load_start = time.perf_counter()
    graph = ox.load_graphml(args.graph_path)
    graph_load_seconds = time.perf_counter() - graph_load_start

    all_nodes = list(graph.nodes)

    if args.sample_size > len(all_nodes):
        raise ValueError(
            f"Requested {args.sample_size} nodes, but graph has "
            f"{len(all_nodes)} nodes."
        )

    random_generator = random.Random(args.seed)
    origins = random_generator.sample(
        all_nodes,
        args.sample_size,
    )

    results = []
    calculation_start = time.perf_counter()

    for index, origin in enumerate(origins, start=1):
        node_start = time.perf_counter()

        try:
            result = calculate_node_accessibility(
                graph=graph,
                origin_node=origin,
                cutoff_miles=args.cutoff_miles,
                cost_field=args.cost_field,
            )
        except Exception as exc:
            node_data = graph.nodes[origin]
            result = {
                "node_id": origin,
                "longitude": node_data.get("x"),
                "latitude": node_data.get("y"),
                "profile_cost_field": args.cost_field,
                "cutoff_miles": args.cutoff_miles,
                "calculation_status": "failed",
                "error": str(exc),
            }

        runtime_seconds = time.perf_counter() - node_start
        result["runtime_seconds"] = runtime_seconds
        results.append(result)

        print(
            f"{index}/{len(origins)} "
            f"node={origin} "
            f"status={result['calculation_status']} "
            f"runtime={runtime_seconds:.3f}s"
        )

    calculation_seconds = (
        time.perf_counter() - calculation_start
    )

    frame = pd.DataFrame(results)
    args.output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    frame.to_csv(args.output_path, index=False)

    successful = frame[
        frame["calculation_status"] == "success"
    ]

    if successful.empty:
        raise RuntimeError(
            "No sampled nodes completed successfully."
        )

    average = successful["runtime_seconds"].mean()
    median = successful["runtime_seconds"].median()
    percentile_95 = successful["runtime_seconds"].quantile(0.95)
    maximum = successful["runtime_seconds"].max()

    estimated_hours = (
        average * graph.number_of_nodes() / 3600
    )

    print()
    print(f"Graph load time: {graph_load_seconds:.2f}s")
    print(f"Sample calculation time: {calculation_seconds:.2f}s")
    print(f"Sampled nodes: {len(frame)}")
    print(f"Successful nodes: {len(successful)}")
    print(f"Failed nodes: {len(frame) - len(successful)}")
    print(f"Average per successful node: {average:.3f}s")
    print(f"Median per successful node: {median:.3f}s")
    print(f"95th percentile: {percentile_95:.3f}s")
    print(f"Maximum: {maximum:.3f}s")
    print(
        "Estimated sequential full-graph runtime: "
        f"{estimated_hours:.2f} hours"
    )
    print(f"Saved: {args.output_path}")


if __name__ == "__main__":
    main()
