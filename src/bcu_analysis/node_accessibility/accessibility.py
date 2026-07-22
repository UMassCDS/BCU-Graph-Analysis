"""Core bounded node-accessibility calculations."""

from __future__ import annotations

import ast
import heapq
import math
from dataclasses import dataclass
from typing import Hashable, Iterable

import networkx as nx


METERS_PER_MILE = 1609.344
DEFAULT_CUTOFF_MILES = 1.5

EdgeId = tuple[Hashable, Hashable, Hashable]
PhysicalSegmentId = tuple


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


@dataclass(frozen=True)
class PhysicalRoadResult:
    """Summary of reachable physical road segments."""

    physical_segment_lengths: dict[PhysicalSegmentId, float]

    @property
    def physical_segment_count(self) -> int:
        return len(self.physical_segment_lengths)

    @property
    def total_physical_length(self) -> float:
        return sum(self.physical_segment_lengths.values())


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


def _normalize_osmid(value) -> tuple[str, ...]:
    """Convert an OSM ID value into a stable sorted tuple of strings."""
    if value is None:
        return ()

    parsed = value

    if isinstance(value, str):
        stripped = value.strip()

        if not stripped:
            return ()

        try:
            parsed = ast.literal_eval(stripped)
        except (ValueError, SyntaxError):
            parsed = stripped

    if isinstance(parsed, (list, tuple, set)):
        return tuple(sorted(str(item) for item in parsed))

    return (str(parsed),)


def _normalize_geometry(value) -> str:
    """Return a direction-independent geometry representation."""
    if value is None:
        return ""

    if hasattr(value, "coords"):
        coordinates = tuple(
            (round(float(x), 7), round(float(y), 7))
            for x, y, *rest in value.coords
        )

        reversed_coordinates = tuple(reversed(coordinates))
        canonical = min(coordinates, reversed_coordinates)
        return repr(canonical)

    geometry_text = str(value).strip()

    if not geometry_text:
        return ""

    return geometry_text


def physical_segment_id(
    graph: nx.MultiDiGraph,
    edge_id: EdgeId,
) -> PhysicalSegmentId:
    """Create a canonical identifier for one physical road segment.

    Opposite directed edges are merged when they have:

    - the same unordered endpoint pair;
    - the same normalized OSM ID;
    - effectively the same physical length.

    The edge key is included only as a fallback when no OSM ID exists. This
    preserves separate parallel edges more safely than using endpoints alone.
    """
    u, v, key = edge_id
    data = graph.get_edge_data(u, v, key)

    if data is None:
        raise KeyError(f"Edge {edge_id} is not present in the graph.")

    endpoint_pair = tuple(sorted((str(u), str(v))))
    osmid = _normalize_osmid(data.get("osmid"))
    length = round(_numeric_edge_value(data, "length", edge_id), 3)
    geometry = _normalize_geometry(data.get("geometry"))

    if osmid:
        return (
            "osmid",
            endpoint_pair,
            osmid,
            length,
            geometry,
        )

    return (
        "fallback",
        endpoint_pair,
        str(key),
        length,
        geometry,
    )


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

            # Full-edge boundary method.
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


def collect_physical_road_segments(
    graph: nx.MultiDiGraph,
    reachable_edges: Iterable[EdgeId],
) -> PhysicalRoadResult:
    """Deduplicate reachable directed edges into physical road segments."""
    physical_segment_lengths: dict[PhysicalSegmentId, float] = {}

    for edge_id in reachable_edges:
        u, v, key = edge_id
        data = graph.get_edge_data(u, v, key)

        if data is None:
            raise KeyError(f"Edge {edge_id} is not present in the graph.")

        segment_id = physical_segment_id(graph, edge_id)
        length = _numeric_edge_value(data, "length", edge_id)

        existing_length = physical_segment_lengths.get(segment_id)

        if existing_length is None:
            physical_segment_lengths[segment_id] = length
        else:
            physical_segment_lengths[segment_id] = max(
                existing_length,
                length,
            )

    return PhysicalRoadResult(
        physical_segment_lengths=physical_segment_lengths
    )


def sum_reachable_directed_edge_lengths(
    graph: nx.MultiDiGraph,
    reachable_edges: Iterable[EdgeId],
    length_attribute: str = "length",
) -> float:
    """Sum physical lengths without merging opposite directions."""
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
    """Calculate physical-road accessibility for one origin node."""
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

    weighted_physical = collect_physical_road_segments(
        graph,
        weighted_result.reachable_edges,
    )

    distance_physical = collect_physical_road_segments(
        graph,
        distance_result.reachable_edges,
    )

    weighted_directed_meters = sum_reachable_directed_edge_lengths(
        graph,
        weighted_result.reachable_edges,
    )

    distance_directed_meters = sum_reachable_directed_edge_lengths(
        graph,
        distance_result.reachable_edges,
    )

    absolute_miles = (
        weighted_physical.total_physical_length / METERS_PER_MILE
    )
    distance_miles = (
        distance_physical.total_physical_length / METERS_PER_MILE
    )

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
        "cutoff_meters": cutoff_meters,
        "absolute_accessibility_miles": absolute_miles,
        "distance_reachable_road_miles": distance_miles,
        "relative_accessibility": relative_accessibility,
        "weighted_reachable_directed_edge_count": (
            weighted_result.reachable_directed_edge_count
        ),
        "distance_reachable_directed_edge_count": (
            distance_result.reachable_directed_edge_count
        ),
        "weighted_reachable_physical_segment_count": (
            weighted_physical.physical_segment_count
        ),
        "distance_reachable_physical_segment_count": (
            distance_physical.physical_segment_count
        ),
        "weighted_directed_edge_miles_debug": (
            weighted_directed_meters / METERS_PER_MILE
        ),
        "distance_directed_edge_miles_debug": (
            distance_directed_meters / METERS_PER_MILE
        ),
        "weighted_processed_node_count": (
            weighted_result.processed_node_count
        ),
        "distance_processed_node_count": (
            distance_result.processed_node_count
        ),
        "boundary_method": "full_edge",
        "edge_counting_method": "physical_segment_deduplicated",
        "calculation_status": status,
    }
