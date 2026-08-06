"""Create a separate graph with structurally inadequate components removed."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import networkx as nx
import osmnx as ox
import pandas as pd

from bcu_analysis.node_accessibility.accessibility import (
    METERS_PER_MILE,
    physical_segment_id,
)


def parse_args(
    argv: Sequence[str] | None = None,
) -> argparse.Namespace:
    """Parse graph-pruning command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Remove structurally inadequate components from an "
            "analysis graph and write reproducible audit outputs."
        )
    )

    parser.add_argument(
        "--input-graph-path",
        type=Path,
        required=True,
        help="GraphML file to prune.",
    )

    parser.add_argument(
        "--output-graph-path",
        type=Path,
        required=True,
        help="Location for the pruned GraphML file.",
    )

    parser.add_argument(
        "--audit-directory",
        type=Path,
        required=True,
        help="Directory for pruning inventories and summary files.",
    )

    return parser.parse_args(argv)


# Components shorter than this cannot provide enough road mileage
# for a stable and interpretable relative-accessibility denominator.
MIN_COMPONENT_MILES = 0.25


def numeric_length(value) -> float:
    """Return a validated nonnegative edge length."""
    length = float(value)

    if length < 0:
        raise ValueError(f"Encountered negative edge length: {length}")

    return length


def component_physical_segments(
    graph: nx.MultiDiGraph,
    component_nodes: set,
) -> dict:
    """Return unique physical segments contained in one component."""
    segment_lengths = {}

    for u, v, key in graph.edges(
        component_nodes,
        keys=True,
    ):
        edge_id = (u, v, key)
        edge_data = graph.get_edge_data(
            u,
            v,
            key,
        )

        if edge_data is None:
            raise KeyError(f"Missing graph edge data for {edge_id}")

        segment_id = physical_segment_id(
            graph,
            edge_id,
        )

        length = numeric_length(edge_data.get("length", 0.0))

        previous_length = segment_lengths.get(segment_id)

        if previous_length is None:
            segment_lengths[segment_id] = length
        else:
            segment_lengths[segment_id] = max(
                previous_length,
                length,
            )

    return segment_lengths


def component_bounds(
    graph: nx.MultiDiGraph,
    component_nodes: set,
) -> dict:
    """Calculate the coordinate bounds of a component."""
    longitudes = []
    latitudes = []

    for node in component_nodes:
        node_data = graph.nodes[node]

        longitude = node_data.get("x")
        latitude = node_data.get("y")

        if longitude is not None:
            longitudes.append(float(longitude))

        if latitude is not None:
            latitudes.append(float(latitude))

    return {
        "min_longitude": (min(longitudes) if longitudes else None),
        "max_longitude": (max(longitudes) if longitudes else None),
        "min_latitude": (min(latitudes) if latitudes else None),
        "max_latitude": (max(latitudes) if latitudes else None),
    }


def classify_component(
    component_id: int,
    node_count: int,
    physical_segment_count: int,
    total_physical_miles: float,
) -> tuple[bool, str]:
    """Return whether a component provides meaningful mileage support."""
    # Protect the largest component from accidental removal.
    if component_id == 0:
        return True, "largest_component"

    if node_count <= 1:
        return False, "isolated_node"

    if physical_segment_count == 0:
        return False, "no_physical_segments"

    if total_physical_miles < MIN_COMPONENT_MILES:
        return False, "less_than_minimum_component_miles"

    return True, "meets_minimum_component_miles"


def main(
    argv: Sequence[str] | None = None,
) -> None:
    args = parse_args(argv)

    input_graph_path = args.input_graph_path
    output_graph_path = args.output_graph_path
    audit_directory = args.audit_directory

    component_inventory_path = (
        audit_directory
        / "component_inventory.csv"
    )

    removed_components_path = (
        audit_directory
        / "removed_components.csv"
    )

    removed_nodes_path = (
        audit_directory
        / "removed_nodes.csv"
    )

    summary_path = (
        audit_directory
        / "graph_pruning_summary.txt"
    )

    if not input_graph_path.is_file():
        raise FileNotFoundError(
            f"Input graph not found: {input_graph_path}"
        )

    print(f"Loading original graph: {input_graph_path}")
    graph = ox.load_graphml(input_graph_path)

    original_node_count = graph.number_of_nodes()
    original_edge_count = graph.number_of_edges()

    print(f"Original graph: {original_node_count:,} nodes, {original_edge_count:,} directed edges")

    components = sorted(
        nx.weakly_connected_components(graph),
        key=len,
        reverse=True,
    )

    print(f"Weakly connected components: {len(components):,}")

    inventory_records = []
    removed_node_records = []
    nodes_to_remove = set()

    for component_id, component in enumerate(components):
        component_nodes = set(component)

        directed_edge_count = graph.subgraph(component_nodes).number_of_edges()

        physical_segments = component_physical_segments(
            graph,
            component_nodes,
        )

        physical_segment_count = len(physical_segments)

        total_physical_meters = sum(physical_segments.values())

        total_physical_miles = total_physical_meters / METERS_PER_MILE

        keep_component, decision_reason = classify_component(
            component_id=component_id,
            node_count=len(component_nodes),
            physical_segment_count=(physical_segment_count),
            total_physical_miles=(total_physical_miles),
        )

        bounds = component_bounds(
            graph,
            component_nodes,
        )

        inventory_records.append(
            {
                "component_id": component_id,
                "keep_component": keep_component,
                "decision_reason": decision_reason,
                "node_count": len(component_nodes),
                "directed_edge_count": (directed_edge_count),
                "physical_segment_count": (physical_segment_count),
                "total_physical_meters": (total_physical_meters),
                "total_physical_miles": (total_physical_miles),
                **bounds,
            }
        )

        if not keep_component:
            nodes_to_remove.update(component_nodes)

            for node in component_nodes:
                node_data = graph.nodes[node]

                removed_node_records.append(
                    {
                        "node_id": node,
                        "component_id": component_id,
                        "decision_reason": (decision_reason),
                        "component_node_count": (len(component_nodes)),
                        "component_physical_segment_count": (physical_segment_count),
                        "component_total_physical_miles": (total_physical_miles),
                        "longitude": node_data.get("x"),
                        "latitude": node_data.get("y"),
                    }
                )

    inventory = pd.DataFrame(inventory_records)

    removed_components = inventory.loc[~inventory["keep_component"]].copy()

    removed_nodes = pd.DataFrame(removed_node_records)

    print(f"Components retained: {inventory['keep_component'].sum():,}")

    print(f"Components removed: {len(removed_components):,}")

    print(f"Nodes scheduled for removal: {len(nodes_to_remove):,}")

    pruned_graph = graph.copy()
    pruned_graph.remove_nodes_from(nodes_to_remove)

    pruned_node_count = pruned_graph.number_of_nodes()

    pruned_edge_count = pruned_graph.number_of_edges()

    if pruned_node_count == 0:
        raise RuntimeError("Pruning removed every graph node.")

    if not nx.is_weakly_connected(pruned_graph):
        retained_component_count = nx.number_weakly_connected_components(pruned_graph)
    else:
        retained_component_count = 1

    pruned_graph.graph["pruning_method"] = "remove weak components with insufficient total physical-road mileage"

    pruned_graph.graph["minimum_component_miles"] = str(MIN_COMPONENT_MILES)

    pruned_graph.graph["source_graph"] = str(input_graph_path)

    output_graph_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    audit_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    inventory.to_csv(
        component_inventory_path,
        index=False,
    )

    removed_components.to_csv(
        removed_components_path,
        index=False,
    )

    removed_nodes.to_csv(
        removed_nodes_path,
        index=False,
    )

    print(f"Saving pruned graph: {output_graph_path}")

    ox.save_graphml(
        pruned_graph,
        output_graph_path,
    )

    removed_node_count = original_node_count - pruned_node_count

    removed_edge_count = original_edge_count - pruned_edge_count

    node_removal_percent = 100.0 * removed_node_count / original_node_count

    edge_removal_percent = 100.0 * removed_edge_count / original_edge_count

    summary_lines = [
        "Greater Boston graph-pruning summary",
        "====================================",
        "",
        f"Input graph: {input_graph_path}",
        f"Output graph: {output_graph_path}",
        "",
        "Retention rule:",
        (f"A component is removed when it contains less than {MIN_COMPONENT_MILES:.2f} physical road miles."),
        ("Physical-segment counts are recorded for auditing but do not control pruning."),
        "",
        f"Original nodes: {original_node_count:,}",
        f"Pruned nodes: {pruned_node_count:,}",
        (f"Removed nodes: {removed_node_count:,} ({node_removal_percent:.3f}%)"),
        "",
        (f"Original directed edges: {original_edge_count:,}"),
        (f"Pruned directed edges: {pruned_edge_count:,}"),
        (f"Removed directed edges: {removed_edge_count:,} ({edge_removal_percent:.3f}%)"),
        "",
        (f"Original weak components: {len(components):,}"),
        (f"Retained weak components: {retained_component_count:,}"),
        (f"Removed weak components: {len(removed_components):,}"),
        "",
        f"Component inventory: {component_inventory_path}",
        f"Removed components: {removed_components_path}",
        f"Removed nodes: {removed_nodes_path}",
    ]

    summary_path.write_text(
        "\n".join(summary_lines) + "\n",
        encoding="utf-8",
    )

    print()
    print("\n".join(summary_lines))
    print(f"Summary saved: {summary_path}")


if __name__ == "__main__":
    main()
