import geopandas as gpd
from shapely.geometry import Point, box

from bcu_analysis.census.assignment import assign_population_to_nodes_by_tract_area


def test_population_is_conserved_for_simple_tract():
    nodes = gpd.GeoDataFrame(
        geometry=[Point(0, 0), Point(10, 0)],
        crs="EPSG:26986",
    )

    tracts = gpd.GeoDataFrame(
        {"GEOID": ["test"], "population": [100]},
        geometry=[box(-5, -5, 15, 5)],
        crs="EPSG:26986",
    )

    nodes_out, allocation = assign_population_to_nodes_by_tract_area(
        nodes,
        tracts,
        population_col="population",
        tract_id_col="GEOID",
        projected_crs="EPSG:26986",
        candidate_buffer_m=0,
        tract_filter_method="none",
    )

    assert round(allocation["assigned_population"].sum(), 10) == 100
    assert round(nodes_out["assigned_population"].sum(), 10) == 100
    assert round(allocation["area_share"].sum(), 10) == 1
    assert (allocation["assigned_population"] >= 0).all()
