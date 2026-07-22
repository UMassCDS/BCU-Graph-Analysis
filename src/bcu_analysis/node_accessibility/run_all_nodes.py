"""Calculate accessibility for all graph nodes with checkpointing and resume."""

from __future__ import annotations

import argparse
import csv
import time
from pathlib import Path

import osmnx as ox

from bcu_analysis.node_accessibility.accessibility import (
    calculate_node_accessibility,
)


DEFAULT_GRAPH_PATH = Path(
    "/work/pi_plunkett_umass_edu/bcu/data/processed/osm/"
    "greater_boston_6_cost_simplified.graphml"
)

DEFAULT_OUTPUT_PATH = Path(
    "/work/pi_plunkett_umass_edu/bcu/data/processed/accessibility/"
    "greater_boston_node_accessibility_typical_adult.csv"
)

DEFAULT_FAILURE_PATH = Path(
    "/work/pi_plunkett_umass_edu/bcu/data/processed/accessibility/"
    "failed_accessibility_nodes.csv"
)


RESULT_FIELDS = [
    "node_id",
    "longitude",
    "latitude",
    "profile_cost_field",
    "cutoff_miles",
    "cutoff_meters",
    "absolute_accessibility_miles",
    "distance_reachable_road_miles",
    "relative_accessibility",
    "weighted_reachable_directed_edge_count",
    "distance_reachable_directed_edge_count",
    "weighted_reachable_physical_segment_count",
    "distance_reachable_physical_segment_count",
    "weighted_directed_edge_miles_debug",
    "distance_directed_edge_miles_debug",
    "weighted_processed_node_count",
    "distance_processed_node_count",
    "boundary_method",
    "edge_counting_method",
    "calculation_status",
    "runtime_seconds",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Calculate node accessibility for every node, with "
            "checkpointing and resume support."
        )
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
        "--failure-path",
        type=Path,
        default=DEFAULT_FAILURE_PATH,
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
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional number of remaining nodes to process.",
    )
    return parser.parse_args()


def load_completed_node_ids(
    output_path: Path,
) -> set[str]:
    """Read node IDs already written to the output CSV."""
    if not output_path.exists():
        return set()

    completed: set[str] = set()

    with output_path.open(
        "r",
        newline="",
        encoding="utf-8",
    ) as file:
        reader = csv.DictReader(file)

        if "node_id" not in (reader.fieldnames or []):
            raise ValueError(
                f"Existing output lacks node_id: {output_path}"
            )

        for row in reader:
            node_id = row.get("node_id")

            if node_id:
                completed.add(str(node_id))

    return completed


def append_result(
    output_path: Path,
    result: dict,
) -> None:
    """Append one result record and flush it to disk."""
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_exists = output_path.exists()
    file_has_content = (
        file_exists and output_path.stat().st_size > 0
    )

    with output_path.open(
        "a",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=RESULT_FIELDS,
            extrasaction="ignore",
        )

        if not file_has_content:
            writer.writeheader()

        writer.writerow(result)
        file.flush()


def append_failure(
    failure_path: Path,
    origin,
    error: Exception,
) -> None:
    """Append one failed origin to the failure log."""
    failure_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_has_content = (
        failure_path.exists()
        and failure_path.stat().st_size > 0
    )

    with failure_path.open(
        "a",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "node_id",
                "error_type",
                "error_message",
            ],
        )

        if not file_has_content:
            writer.writeheader()

        writer.writerow(
            {
                "node_id": origin,
                "error_type": type(error).__name__,
                "error_message": str(error),
            }
        )
        file.flush()


def main() -> None:
    args = parse_args()

    if args.progress_every <= 0:
        raise ValueError(
            "--progress-every must be positive."
        )

    print(f"Loading graph: {args.graph_path}")
    graph_load_start = time.perf_counter()
    graph = ox.load_graphml(args.graph_path)
    graph_load_seconds = time.perf_counter() - graph_load_start

    print(
        f"Loaded {graph.number_of_nodes():,} nodes and "
        f"{graph.number_of_edges():,} edges "
        f"in {graph_load_seconds:.2f}s."
    )

    completed_ids = load_completed_node_ids(
        args.output_path
    )

    all_nodes = list(graph.nodes)
    remaining_nodes = [
        node
        for node in all_nodes
        if str(node) not in completed_ids
    ]

    if args.limit is not None:
        if args.limit <= 0:
            raise ValueError("--limit must be positive.")

        remaining_nodes = remaining_nodes[: args.limit]

    print(f"Already completed: {len(completed_ids):,}")
    print(f"Nodes selected this run: {len(remaining_nodes):,}")
    print(f"Output: {args.output_path}")

    run_start = time.perf_counter()
    successful_this_run = 0
    failed_this_run = 0

    for index, origin in enumerate(
        remaining_nodes,
        start=1,
    ):
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

            append_result(
                args.output_path,
                result,
            )
            successful_this_run += 1

        except Exception as error:
            append_failure(
                args.failure_path,
                origin,
                error,
            )
            failed_this_run += 1

        if (
            index == 1
            or index % args.progress_every == 0
            or index == len(remaining_nodes)
        ):
            elapsed = time.perf_counter() - run_start
            average = elapsed / index
            remaining = len(remaining_nodes) - index
            estimated_remaining_hours = (
                average * remaining / 3600
            )

            print(
                f"Progress: {index:,}/{len(remaining_nodes):,} | "
                f"success={successful_this_run:,} | "
                f"failed={failed_this_run:,} | "
                f"avg={average:.3f}s/node | "
                f"ETA={estimated_remaining_hours:.2f}h"
            )

    total_seconds = time.perf_counter() - run_start

    print()
    print("Run complete")
    print(f"Successful: {successful_this_run:,}")
    print(f"Failed: {failed_this_run:,}")
    print(f"Runtime: {total_seconds / 3600:.2f} hours")
    print(f"Results: {args.output_path}")
    print(f"Failures: {args.failure_path}")


if __name__ == "__main__":
    main()
