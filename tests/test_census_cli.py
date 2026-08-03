from pathlib import Path

import pytest

from bcu_analysis.census.run_census_assignment import (
    REGIONS,
    output_paths,
    parse_args,
)


@pytest.mark.parametrize("region", sorted(REGIONS))
def test_cli_accepts_each_supported_region(region):
    args = parse_args(
        [
            "--region",
            region,
            "--graph-path",
            "example.graphml",
        ]
    )

    assert args.region == region
    assert args.graph_path == Path("example.graphml")


def test_cli_requires_graph_path():
    with pytest.raises(SystemExit):
        parse_args(["--region", "boston"])


def test_cli_rejects_unknown_region():
    with pytest.raises(SystemExit):
        parse_args(
            [
                "--region",
                "quincy",
                "--graph-path",
                "example.graphml",
            ]
        )


def test_default_output_prefix_does_not_assume_pruned():
    paths = output_paths(
        Path("/tmp/results"),
        "greater-boston",
    )

    assert paths["allocation_csv"].name == (
        "greater_boston_node_tract_allocation.csv"
    )
    assert paths["nodes_web"].name == (
        "greater_boston_nodes_with_population_web.geojson"
    )


def test_explicit_output_prefix_records_graph_state():
    paths = output_paths(
        Path("/tmp/results"),
        "greater-boston",
        "greater_boston_pruned",
    )

    assert paths["allocation_csv"].name == (
        "greater_boston_pruned_node_tract_allocation.csv"
    )
    assert paths["nodes_gpkg"].name == (
        "greater_boston_pruned_nodes_with_population.gpkg"
    )


def test_greater_boston_region_contains_the_four_project_cities():
    assert REGIONS["greater-boston"] == (
        "Boston, Massachusetts, USA",
        "Brookline, Massachusetts, USA",
        "Cambridge, Massachusetts, USA",
        "Somerville, Massachusetts, USA",
    )
