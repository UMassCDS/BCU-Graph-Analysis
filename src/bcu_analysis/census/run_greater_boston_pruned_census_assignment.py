"""Assign Census tract population to nodes in the pruned Greater Boston graph."""

from pathlib import Path

import geopandas as gpd
import osmnx as ox
import pandas as pd

from bcu_analysis.census.assignment import (
    assign_population_to_nodes_by_tract_area,
)


GRAPH_PATH = Path(
    "/work/pi_plunkett_umass_edu/bcu/data/processed/osm/"
    "greater_boston_6_cost_simplified_pruned.graphml"
)

TRACT_PATH = Path(
    "/work/pi_plunkett_umass_edu/bcu/data/processed/census/"
    "ma_tracts_population.geojson"
)

OUTPUT_DIRECTORY = Path(
    "/work/pi_plunkett_umass_edu/bcu/data/processed/census/results"
)

OUTPUT_ALLOC_CSV = (
    OUTPUT_DIRECTORY
    / "greater_boston_pruned_node_tract_allocation.csv"
)

OUTPUT_ALLOC_PARQUET = (
    OUTPUT_DIRECTORY
    / "greater_boston_pruned_node_tract_allocation.parquet"
)

OUTPUT_NODES_PARQUET = (
    OUTPUT_DIRECTORY
    / "greater_boston_pruned_nodes_with_population.parquet"
)

OUTPUT_NODES_WEB_GEOJSON = (
    OUTPUT_DIRECTORY
    / "greater_boston_pruned_nodes_with_population_web.geojson"
)

OUTPUT_BOUNDARY_GEOJSON = (
    OUTPUT_DIRECTORY
    / "greater_boston_four_city_boundary.geojson"
)


PLACES = [
    "Boston, Massachusetts, USA",
    "Brookline, Massachusetts, USA",
    "Cambridge, Massachusetts, USA",
    "Somerville, Massachusetts, USA",
]


def load_combined_boundary() -> gpd.GeoDataFrame:
    """Download and combine the four municipal boundaries."""

    boundaries = []

    for place in PLACES:
        print(f"Loading boundary: {place}")

        boundary = ox.geocode_to_gdf(place)

        if boundary.empty:
            raise RuntimeError(
                f"No municipal boundary returned for {place}"
            )

        boundary = boundary[
            ["display_name", "geometry"]
        ].copy()

        boundary["requested_place"] = place

        boundaries.append(boundary)

    combined = gpd.GeoDataFrame(
        pd.concat(
            boundaries,
            ignore_index=True,
        ),
        crs=boundaries[0].crs,
    )

    union_geometry = combined.geometry.union_all()

    return gpd.GeoDataFrame(
        {
            "region_name": [
                "Boston, Brookline, Cambridge, and Somerville"
            ],
            "geometry": [union_geometry],
        },
        crs=combined.crs,
    )


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Loading pruned graph...")
    graph = ox.load_graphml(GRAPH_PATH)

    print(
        f"Graph: {graph.number_of_nodes():,} nodes, "
        f"{graph.number_of_edges():,} edges"
    )

    print("Converting graph nodes to GeoDataFrame...")
    nodes, _ = ox.graph_to_gdfs(graph)

    print("Loading Census tracts...")
    tracts = gpd.read_file(TRACT_PATH)

    tracts["GEOID"] = (
        tracts["GEOID"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(11)
    )

    tracts["population"] = pd.to_numeric(
        tracts["population"],
        errors="coerce",
    )

    print(f"Massachusetts tracts loaded: {len(tracts):,}")

    print("Building four-city boundary...")
    region_boundary = load_combined_boundary()

    region_boundary.to_file(
        OUTPUT_BOUNDARY_GEOJSON,
        driver="GeoJSON",
    )

    print("Running tract-to-node allocation...")

    nodes_with_population, allocation = (
        assign_population_to_nodes_by_tract_area(
            nodes_gdf=nodes,
            tracts_gdf=tracts,
            population_col="population",
            tract_id_col="GEOID",
            projected_crs="EPSG:26986",
            candidate_buffer_m=100,
            tract_filter_method="none",
            region_boundary_gdf=region_boundary,
            min_region_overlap_share=0.50,
            verbose=True,
        )
    )

    print("Saving allocation outputs...")

    allocation["node_id"] = (
        allocation["node_id"].astype(str)
    )

    allocation["GEOID"] = (
        allocation["GEOID"].astype(str).str.zfill(11)
    )

    allocation.to_csv(
        OUTPUT_ALLOC_CSV,
        index=False,
    )

    allocation.to_parquet(
        OUTPUT_ALLOC_PARQUET,
        index=False,
    )

    nodes_with_population["node_id"] = (
        nodes_with_population["node_id"].astype(str)
    )

    nodes_with_population.to_parquet(
        OUTPUT_NODES_PARQUET
    )

    nodes_web = nodes_with_population.to_crs(
        "EPSG:4326"
    )

    nodes_web.to_file(
        OUTPUT_NODES_WEB_GEOJSON,
        driver="GeoJSON",
    )

    share_sums = (
        allocation.groupby("GEOID")["area_share"]
        .sum()
    )

    assigned_nodes = set(
        allocation["node_id"]
    )

    graph_nodes = {
        str(node_id)
        for node_id in graph.nodes
    }

    assigned_tracts = set(
        allocation["GEOID"]
    )

    assigned_tract_population = (
        tracts.loc[
            tracts["GEOID"].isin(assigned_tracts),
            "population",
        ].sum()
    )

    county_summary = (
        allocation.assign(
            county_code=allocation["GEOID"].str[2:5]
        )
        [["GEOID", "county_code"]]
        .drop_duplicates()
        ["county_code"]
        .value_counts()
        .sort_index()
    )

    print()
    print("ALLOCATION SUMMARY")
    print("==================")
    print(f"Graph nodes: {len(graph_nodes):,}")
    print(f"Allocation rows: {len(allocation):,}")
    print(
        f"Unique allocated nodes: "
        f"{len(assigned_nodes):,}"
    )
    print(
        f"Graph nodes without allocation rows: "
        f"{len(graph_nodes - assigned_nodes):,}"
    )
    print(
        f"Share of graph nodes represented: "
        f"{100 * len(assigned_nodes) / len(graph_nodes):.2f}%"
    )
    print(
        f"Assigned Census tracts: "
        f"{len(assigned_tracts):,}"
    )
    print(
        f"Assigned tract population total: "
        f"{assigned_tract_population:,.3f}"
    )
    print(
        f"Assigned node population total: "
        f"{nodes_with_population['assigned_population'].sum():,.3f}"
    )

    print()
    print("TRACT SHARE VALIDATION")
    print("======================")
    print(share_sums.describe().to_string())
    print(
        "Tracts not summing near 1:",
        (
            ~share_sums.between(
                0.999999,
                1.000001,
            )
        ).sum(),
    )

    print()
    print("COUNTY CODES")
    print("============")
    print(county_summary.to_string())

    print()
    print("Saved:")
    print(OUTPUT_ALLOC_CSV)
    print(OUTPUT_ALLOC_PARQUET)
    print(OUTPUT_NODES_PARQUET)
    print(OUTPUT_NODES_WEB_GEOJSON)
    print(OUTPUT_BOUNDARY_GEOJSON)


if __name__ == "__main__":
    main()
