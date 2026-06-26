import pandas as pd
from shapely.geometry import MultiPoint
from shapely.ops import voronoi_diagram
from scipy.spatial import cKDTree


def assign_population_to_nodes_by_tract_area(
    nodes_gdf,
    tracts_gdf,
    population_col="population",
    tract_id_col="GEOID",
    projected_crs="EPSG:26986",
    verbose=False,
):
    """
    Assign census tract population to graph nodes deterministically.

    For each tract:
    1. Find graph nodes inside/intersecting the tract using a spatial index.
    2. Build Voronoi-style nearest-node regions.
    3. Clip each Voronoi region to the tract.
    4. Assign each clipped region to its nearest node using a KDTree.
    5. Normalize area shares so each tract sums exactly to 1.
    6. Assign population proportionally by normalized area share.
    """

    nodes = nodes_gdf.copy()
    tracts = tracts_gdf.copy()

    nodes["node_id"] = nodes.index

    nodes = nodes.to_crs(projected_crs)
    tracts = tracts.to_crs(projected_crs)

    # Filter to only tracts touching the graph/node extent.
    node_extent = nodes.geometry.union_all().envelope
    tracts = tracts[tracts.geometry.intersects(node_extent)].copy()

    node_sindex = nodes.sindex
    allocation_rows = []

    total_tracts = len(tracts)

    for tract_counter, (_, tract) in enumerate(tracts.iterrows(), start=1):
        if verbose and (tract_counter == 1 or tract_counter % 25 == 0):
            print(f"Processing tract {tract_counter}/{total_tracts}")

        tract_geom = tract.geometry

        if tract_geom is None or tract_geom.is_empty:
            continue

        tract_area = tract_geom.area

        if tract_area == 0:
            continue

        # Fast lookup of nodes whose bounding boxes intersect this tract.
        candidate_idx = list(node_sindex.query(tract_geom, predicate="intersects"))
        tract_nodes = nodes.iloc[candidate_idx].copy()

        if tract_nodes.empty:
            continue

        # Keep only points that actually intersect the tract polygon.
        tract_nodes = tract_nodes[tract_nodes.geometry.intersects(tract_geom)].copy()

        if tract_nodes.empty:
            continue

        tract_nodes = tract_nodes.sort_values("node_id")

        tract_rows = []

        if len(tract_nodes) == 1:
            tract_rows.append({
                "node_id": tract_nodes.iloc[0]["node_id"],
                tract_id_col: tract[tract_id_col],
                "area_share": 1.0,
            })

        else:
            points = list(tract_nodes.geometry)
            multipoint = MultiPoint(points)

            vor = voronoi_diagram(
                multipoint,
                envelope=tract_geom.envelope,
                edges=False
            )

            # KDTree for fast nearest-node lookup.
            node_ids = list(tract_nodes["node_id"])
            coords = [(point.x, point.y) for point in points]
            tree = cKDTree(coords)

            # Accumulate areas by nearest node.
            area_by_node = {}

            for cell in vor.geoms:
                clipped = cell.intersection(tract_geom)

                if clipped.is_empty:
                    continue

                clipped_area = clipped.area

                if clipped_area == 0:
                    continue

                rep = clipped.representative_point()
                _, nearest_pos = tree.query((rep.x, rep.y))
                node_id = node_ids[nearest_pos]

                area_by_node[node_id] = area_by_node.get(node_id, 0.0) + clipped_area

            for node_id, clipped_area in area_by_node.items():
                tract_rows.append({
                    "node_id": node_id,
                    tract_id_col: tract[tract_id_col],
                    "area_share": clipped_area / tract_area,
                })

        share_total = sum(row["area_share"] for row in tract_rows)

        if share_total == 0:
            continue

        for row in tract_rows:
            normalized_share = row["area_share"] / share_total
            row["area_share"] = normalized_share
            row["assigned_population"] = tract[population_col] * normalized_share
            allocation_rows.append(row)

    allocation = pd.DataFrame(allocation_rows)

    if allocation.empty:
        output = nodes.copy()
        output["assigned_population"] = 0
        return output, allocation

    node_population = (
        allocation
        .groupby("node_id", as_index=False)["assigned_population"]
        .sum()
    )

    output = nodes.merge(node_population, on="node_id", how="left")
    output["assigned_population"] = output["assigned_population"].fillna(0)

    return output, allocation
