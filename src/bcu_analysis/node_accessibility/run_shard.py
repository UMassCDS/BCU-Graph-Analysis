"""Run one independent shard of the node accessibility calculation."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import osmnx as ox

from bcu_analysis.node_accessibility.accessibility import (
    calculate_node_accessibility,
)
from bcu_analysis.node_accessibility.run_all_nodes import (
    append_failure,
    append_result,
    load_completed_node_ids,
)


DEFAULT_GRAPH_PATH = Path(
    "/work/pi_plunkett_umass_edu/bcu/data/processed/osm/"
    "greater_boston_6_cost_simplified.graphml"
)

DEFAULT_EXISTING_RESULTS = Path(
    "/work/pi_plunkett_umass_edu/bcu/data/processed/accessibility/"
    "greater_boston_node_accessibility_typical_adult.csv"
)

DEFAULT_OUTPUT_DIR = Path(
    "/work/pi_plunkett_umass_edu/bcu/data/processed/accessibility/shards"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--graph-path",
        type=Path,
        default=DEFAULT_GRAPH_PATH,
    )
    parser.add_argument(
        "--existing-results",
        type=Path,
        default=DEFAULT_EXISTING_RESULTS,
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--shard-index",
        type=int,
        required=True,
    )
    parser.add_argument(
        "--num-shards",
        type=int,
        required=True,
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
    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.num_shards <= 0:
        raise ValueError("--num-shards must be positive.")

    if not 0 <= args.shard_index < args.num_shards:
        raise ValueError(
            "--shard-index must be between 0 and num-shards - 1."
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)

    output_path = (
        args.output_dir
        / f"typical_adult_shard_{args.shard_index:02d}.csv"
    )

    failure_path = (
        args.output_dir
        / f"typical_adult_shard_{args.shard_index:02d}_failures.csv"
    )

    print(f"Loading graph: {args.graph_path}", flush=True)
    graph = ox.load_graphml(args.graph_path)

    completed_ids = load_completed_node_ids(
        args.existing_results
    )

    shard_completed_ids = load_completed_node_ids(
        output_path
    )

    nodes = list(graph.nodes)

    shard_nodes = [
        node
        for position, node in enumerate(nodes)
        if position % args.num_shards == args.shard_index
        and str(node) not in completed_ids
        and str(node) not in shard_completed_ids
    ]

    print(
        f"Shard {args.shard_index}/{args.num_shards}: "
        f"{len(shard_nodes):,} nodes selected",
        flush=True,
    )

    start = time.perf_counter()
    successful = 0
    failed = 0

    for index, origin in enumerate(shard_nodes, start=1):
        node_start = time.perf_counter()

        try:
            result = calculate_node_accessibility(
                graph=graph,
                origin_node=origin,
                cutoff_miles=args.cutoff_miles,
                cost_field=args.cost_field,
            )

            result["runtime_seconds"] = (
                time.perf_counter() - node_start
            )

            append_result(output_path, result)
            successful += 1

        except Exception as error:
            append_failure(
                failure_path,
                origin,
                error,
            )
            failed += 1

        if (
            index == 1
            or index % args.progress_every == 0
            or index == len(shard_nodes)
        ):
            elapsed = time.perf_counter() - start
            average = elapsed / index
            remaining = len(shard_nodes) - index
            eta_hours = average * remaining / 3600

            print(
                f"Shard {args.shard_index}: "
                f"{index:,}/{len(shard_nodes):,} | "
                f"success={successful:,} | "
                f"failed={failed:,} | "
                f"avg={average:.3f}s | "
                f"ETA={eta_hours:.2f}h",
                flush=True,
            )

    elapsed = time.perf_counter() - start

    print(
        f"Shard {args.shard_index} complete: "
        f"success={successful:,}, failed={failed:,}, "
        f"runtime={elapsed / 3600:.2f}h",
        flush=True,
    )


if __name__ == "__main__":
    main()
