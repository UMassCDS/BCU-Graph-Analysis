"""Core bounded node-accessibility calculations."""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Hashable

import networkx as nx


METERS_PER_MILE = 1609.344
DEFAULT_CUTOFF_MILES = 1.5

EdgeId = tuple[Hashable, Hashable, Hashable]


@dataclass(frozen=True)
class ExpansionResult:
    """Results of one outward expansion from an origin node."""

    origin_node: Hashable
    weight_attribute: str
    budget: float
    reachable_edges: frozenset[EdgeId]
    best_cost_to_node: dict[Hashable, float]
    processed_node_count: int

    @property
    def reachable_directed_edge_count(self) -> int:
        return len(self.reachable_edges)


def _numeric_edge_value(
    data: dict,
    attribute: str,
    edge_id: EdgeId,
) -> float:
    """Return one validated numeric edge attribute."""
    if attribute not in data:
        raise KeyError(
            f"Edge {edge_id} is missing required attribute "
            f"{attribute!r}."
        )

    try:
        value = float(data[attribute])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Edge {edge_id} has non-numeric {attribute!r}: "
            f"{data[attribute]!r}."
        ) from exc

    if not math.isfinite(value):
        raise ValueError(
            f"Edge {edge_id} has non-finite {attribute!r}: {value}."
        )

    if value < 0:
        raise ValueError(
            f"Edge {edge_id} has negative {attribute!r}: {value}."
        )

    return value


def expand_reachable_edges(
    graph: nx.MultiDiGraph,
    origin_node: Hashable,
    budget: float,
    weight_attribute: str,
) -> ExpansionResult:
    """Expand through every fully traversable edge within a cost budget."""
    if origin_node not in graph:
        raise nx.NodeNotFound(
            f"Origin node {origin_node!r} is not in the graph."
        )

    try:
        numeric_budget = float(budget)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Budget must be numeric, received {budget!r}."
        ) from exc

    if not math.isfinite(numeric_budget) or numeric_budget < 0:
        raise ValueError(
            f"Budget must be finite and nonnegative, received {budget!r}."
        )

    best_cost_to_node: dict[Hashable, float] = {origin_node: 0.0}
    reachable_edges: set[EdgeId] = set()
    queue: list[tuple[float, Hashable]] = [(0.0, origin_node)]
    processed_node_count = 0

    while queue:
        accumulated_cost, current_node = heapq.heappop(queue)

        if accumulated_cost > best_cost_to_node[current_node]:
            continue

        processed_node_count += 1

        for _, next_node, edge_key, data in graph.out_edges(
            current_node,
            keys=True,
            data=True,
        ):
            edge_id = (current_node, next_node, edge_key)
            edge_cost = _numeric_edge_value(
                data,
                weight_attribute,
                edge_id,
            )

            new_cost = accumulated_cost + edge_cost

            # Initial implementation uses full-edge boundary handling.
            if new_cost > numeric_budget:
                continue

            reachable_edges.add(edge_id)

            previous_best = best_cost_to_node.get(next_node)

            if previous_best is None or new_cost < previous_best:
                best_cost_to_node[next_node] = new_cost
                heapq.heappush(queue, (new_cost, next_node))

    return ExpansionResult(
        origin_node=origin_node,
        weight_attribute=weight_attribute,
        budget=numeric_budget,
        reachable_edges=frozenset(reachable_edges),
        best_cost_to_node=best_cost_to_node,
        processed_node_count=processed_node_count,
    )


def sum_reachable_directed_edge_lengths(
    graph: nx.MultiDiGraph,
    reachable_edges: frozenset[EdgeId] | set[EdgeId],
    length_attribute: str = "length",
) -> float:
    """Sum physical lengths of unique reachable directed edges."""
    total_length = 0.0

    for edge_id in reachable_edges:
        u, v, key = edge_id
        data = graph.get_edge_data(u, v, key)

        if data is None:
            raise KeyError(f"Edge {edge_id} is not present in the graph.")

        total_length += _numeric_edge_value(
            data,
            length_attribute,
            edge_id,
        )

    return total_length


def calculate_node_accessibility(
    graph: nx.MultiDiGraph,
    origin_node: Hashable,
    cutoff_miles: float = DEFAULT_CUTOFF_MILES,
    cost_field: str = "cost_typical_adult_Baseline",
) -> dict:
    """Calculate initial weighted and ordinary accessibility for one node."""
    cutoff_miles = float(cutoff_miles)

    if not math.isfinite(cutoff_miles) or cutoff_miles < 0:
        raise ValueError(
            "cutoff_miles must be finite and nonnegative."
        )

    cutoff_meters = cutoff_miles * METERS_PER_MILE

    weighted_result = expand_reachable_edges(
        graph=graph,
        origin_node=origin_node,
        budget=cutoff_meters,
        weight_attribute=cost_field,
    )

    distance_result = expand_reachable_edges(
        graph=graph,
        origin_node=origin_node,
        budget=cutoff_meters,
        weight_attribute="length",
    )

    weighted_meters = sum_reachable_directed_edge_lengths(
        graph,
        weighted_result.reachable_edges,
    )

    distance_meters = sum_reachable_directed_edge_lengths(
        graph,
        distance_result.reachable_edges,
    )

    absolute_miles = weighted_meters / METERS_PER_MILE
    distance_miles = distance_meters / METERS_PER_MILE

    if distance_miles == 0:
        relative_accessibility = math.nan
        status = "zero_distance_denominator"
    else:
        relative_accessibility = absolute_miles / distance_miles
        status = "success"

    node_data = graph.nodes[origin_node]

    return {
        "node_id": origin_node,
        "longitude": node_data.get("x"),
        "latitude": node_data.get("y"),
        "profile_cost_field": cost_field,
        "cutoff_miles": cutoff_miles,
        "absolute_accessibility_miles": absolute_miles,
        "distance_reachable_road_miles": distance_miles,
        "relative_accessibility": relative_accessibility,
        "weighted_reachable_directed_edge_count": (
            weighted_result.reachable_directed_edge_count
        ),
        "distance_reachable_directed_edge_count": (
            distance_result.reachable_directed_edge_count
        ),
        "calculation_status": status,
    }
