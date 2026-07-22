import math

import networkx as nx
import pytest

from bcu_analysis.node_accessibility.accessibility import (
    calculate_node_accessibility,
    expand_reachable_edges,
    sum_reachable_directed_edge_lengths,
)


def build_branching_graph():
    graph = nx.MultiDiGraph()

    graph.add_node("A", x=-71.0, y=42.0)
    graph.add_node("B", x=-71.1, y=42.1)
    graph.add_node("C", x=-71.2, y=42.2)
    graph.add_node("D", x=-71.3, y=42.3)
    graph.add_node("E", x=-71.4, y=42.4)

    graph.add_edge(
        "A",
        "B",
        key=0,
        length=100.0,
        cost_typical_adult_Baseline=100.0,
    )
    graph.add_edge(
        "B",
        "C",
        key=0,
        length=100.0,
        cost_typical_adult_Baseline=100.0,
    )
    graph.add_edge(
        "B",
        "D",
        key=0,
        length=100.0,
        cost_typical_adult_Baseline=200.0,
    )
    graph.add_edge(
        "C",
        "E",
        key=0,
        length=200.0,
        cost_typical_adult_Baseline=250.0,
    )
    graph.add_edge(
        "C",
        "A",
        key=0,
        length=50.0,
        cost_typical_adult_Baseline=50.0,
    )

    return graph


def test_all_feasible_branches_are_explored():
    graph = build_branching_graph()

    result = expand_reachable_edges(
        graph=graph,
        origin_node="A",
        budget=300.0,
        weight_attribute="cost_typical_adult_Baseline",
    )

    assert ("A", "B", 0) in result.reachable_edges
    assert ("B", "C", 0) in result.reachable_edges
    assert ("B", "D", 0) in result.reachable_edges
    assert ("C", "A", 0) in result.reachable_edges
    assert ("C", "E", 0) not in result.reachable_edges


def test_loop_does_not_replace_cheaper_path():
    graph = build_branching_graph()

    result = expand_reachable_edges(
        graph=graph,
        origin_node="A",
        budget=300.0,
        weight_attribute="cost_typical_adult_Baseline",
    )

    assert result.best_cost_to_node["A"] == pytest.approx(0.0)
    assert result.best_cost_to_node["B"] == pytest.approx(100.0)
    assert result.best_cost_to_node["C"] == pytest.approx(200.0)
    assert result.best_cost_to_node["D"] == pytest.approx(300.0)


def test_boundary_edge_is_excluded_when_full_edge_does_not_fit():
    graph = nx.MultiDiGraph()
    graph.add_edge("A", "B", key=0, length=100.0, cost=100.0)
    graph.add_edge("B", "C", key=0, length=201.0, cost=201.0)

    result = expand_reachable_edges(
        graph=graph,
        origin_node="A",
        budget=300.0,
        weight_attribute="cost",
    )

    assert ("A", "B", 0) in result.reachable_edges
    assert ("B", "C", 0) not in result.reachable_edges


def test_shared_edges_are_counted_once():
    graph = build_branching_graph()

    result = expand_reachable_edges(
        graph=graph,
        origin_node="A",
        budget=300.0,
        weight_attribute="cost_typical_adult_Baseline",
    )

    assert len(result.reachable_edges) == 4


def test_reachable_directed_lengths_are_summed():
    graph = build_branching_graph()

    result = expand_reachable_edges(
        graph=graph,
        origin_node="A",
        budget=300.0,
        weight_attribute="cost_typical_adult_Baseline",
    )

    total = sum_reachable_directed_edge_lengths(
        graph,
        result.reachable_edges,
    )

    assert total == pytest.approx(350.0)


def test_weighted_and_distance_expansions_differ():
    graph = nx.MultiDiGraph()
    graph.add_node("A", x=-71.0, y=42.0)
    graph.add_node("B", x=-71.1, y=42.1)
    graph.add_node("C", x=-71.2, y=42.2)

    graph.add_edge(
        "A",
        "B",
        key=0,
        length=1000.0,
        cost_typical_adult_Baseline=1000.0,
    )
    graph.add_edge(
        "B",
        "C",
        key=0,
        length=1000.0,
        cost_typical_adult_Baseline=2000.0,
    )

    result = calculate_node_accessibility(
        graph=graph,
        origin_node="A",
        cutoff_miles=1.5,
        cost_field="cost_typical_adult_Baseline",
    )

    assert result["weighted_reachable_directed_edge_count"] == 1
    assert result["distance_reachable_directed_edge_count"] == 2
    assert result["relative_accessibility"] == pytest.approx(0.5)
    assert result["calculation_status"] == "success"


def test_missing_cost_field_raises_error():
    graph = nx.MultiDiGraph()
    graph.add_edge("A", "B", key=0, length=100.0)

    with pytest.raises(KeyError):
        expand_reachable_edges(
            graph=graph,
            origin_node="A",
            budget=300.0,
            weight_attribute="cost_typical_adult_Baseline",
        )


def test_isolated_node_returns_nan_ratio():
    graph = nx.MultiDiGraph()
    graph.add_node("A", x=-71.0, y=42.0)

    result = calculate_node_accessibility(
        graph=graph,
        origin_node="A",
        cutoff_miles=1.5,
        cost_field="cost_typical_adult_Baseline",
    )

    assert math.isnan(result["relative_accessibility"])
    assert result["calculation_status"] == "zero_distance_denominator"


def test_opposite_directions_are_one_physical_segment():
    graph = nx.MultiDiGraph()

    graph.add_edge(
        "A",
        "B",
        key=0,
        osmid=123,
        length=100.0,
        cost_typical_adult_Baseline=100.0,
    )
    graph.add_edge(
        "B",
        "A",
        key=0,
        osmid=123,
        length=100.0,
        cost_typical_adult_Baseline=100.0,
    )

    from bcu_analysis.node_accessibility.accessibility import (
        collect_physical_road_segments,
    )

    physical = collect_physical_road_segments(
        graph,
        {("A", "B", 0), ("B", "A", 0)},
    )

    assert physical.physical_segment_count == 1
    assert physical.total_physical_length == pytest.approx(100.0)


def test_different_osmids_remain_separate_segments():
    graph = nx.MultiDiGraph()

    graph.add_edge(
        "A",
        "B",
        key=0,
        osmid=123,
        length=100.0,
    )
    graph.add_edge(
        "B",
        "A",
        key=1,
        osmid=456,
        length=100.0,
    )

    from bcu_analysis.node_accessibility.accessibility import (
        collect_physical_road_segments,
    )

    physical = collect_physical_road_segments(
        graph,
        {("A", "B", 0), ("B", "A", 1)},
    )

    assert physical.physical_segment_count == 2
    assert physical.total_physical_length == pytest.approx(200.0)


def test_parallel_edges_without_osmid_remain_separate():
    graph = nx.MultiDiGraph()

    graph.add_edge(
        "A",
        "B",
        key=0,
        length=100.0,
    )
    graph.add_edge(
        "A",
        "B",
        key=1,
        length=100.0,
    )

    from bcu_analysis.node_accessibility.accessibility import (
        collect_physical_road_segments,
    )

    physical = collect_physical_road_segments(
        graph,
        {("A", "B", 0), ("A", "B", 1)},
    )

    assert physical.physical_segment_count == 2
    assert physical.total_physical_length == pytest.approx(200.0)


def test_accessibility_uses_deduplicated_physical_mileage():
    graph = nx.MultiDiGraph()
    graph.add_node("A", x=-71.0, y=42.0)
    graph.add_node("B", x=-71.1, y=42.1)

    graph.add_edge(
        "A",
        "B",
        key=0,
        osmid=123,
        length=100.0,
        cost_typical_adult_Baseline=100.0,
    )
    graph.add_edge(
        "B",
        "A",
        key=0,
        osmid=123,
        length=100.0,
        cost_typical_adult_Baseline=100.0,
    )

    result = calculate_node_accessibility(
        graph=graph,
        origin_node="A",
        cutoff_miles=1.5,
        cost_field="cost_typical_adult_Baseline",
    )

    assert result["weighted_reachable_directed_edge_count"] == 2
    assert result["weighted_reachable_physical_segment_count"] == 1
    assert result["absolute_accessibility_miles"] == pytest.approx(
        100.0 / 1609.344
    )
    assert result["weighted_directed_edge_miles_debug"] == pytest.approx(
        200.0 / 1609.344
    )


def test_reversed_geometries_are_one_physical_segment():
    from shapely.geometry import LineString

    from bcu_analysis.node_accessibility.accessibility import (
        collect_physical_road_segments,
    )

    graph = nx.MultiDiGraph()

    graph.add_edge(
        "A",
        "B",
        key=0,
        osmid=123,
        length=100.0,
        geometry=LineString(
            [(-71.0, 42.0), (-71.1, 42.1)]
        ),
    )

    graph.add_edge(
        "B",
        "A",
        key=0,
        osmid=123,
        length=100.0,
        geometry=LineString(
            [(-71.1, 42.1), (-71.0, 42.0)]
        ),
    )

    physical = collect_physical_road_segments(
        graph,
        {("A", "B", 0), ("B", "A", 0)},
    )

    assert physical.physical_segment_count == 1
    assert physical.total_physical_length == pytest.approx(100.0)
