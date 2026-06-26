import hashlib
from datetime import datetime

import pandas as pd
import geopandas as gpd


def build_census_assignment_validation_report(
    allocation_path,
    tracts_path,
    nodes_path,
    tract_id_col="GEOID",
    population_col="population",
    assigned_population_col="assigned_population",
    output_report_path=None,
):
    allocation = pd.read_csv(allocation_path)
    tracts = gpd.read_file(tracts_path)

    if nodes_path.endswith(".parquet"):
        nodes = gpd.read_parquet(nodes_path)
    else:
        nodes = gpd.read_file(nodes_path)

    allocation[tract_id_col] = allocation[tract_id_col].astype(str)
    tracts[tract_id_col] = tracts[tract_id_col].astype(str)

    report_lines = []

    def add(text=""):
        report_lines.append(str(text))

    add("CENSUS ASSIGNMENT VALIDATION REPORT")
    add("=" * 50)
    add(f"Generated at: {datetime.now()}")
    add()

    add("FILES")
    add("-" * 50)
    add(f"Allocation file: {allocation_path}")
    add(f"Tracts file: {tracts_path}")
    add(f"Nodes file: {nodes_path}")
    add()

    add("BASIC CHECKS")
    add("-" * 50)
    add(f"Allocation rows: {len(allocation)}")
    add(f"Node rows: {len(nodes)}")
    add(f"Nodes with positive assigned population: {(nodes[assigned_population_col] > 0).sum()}")
    add(f"Nodes with zero assigned population: {(nodes[assigned_population_col] == 0).sum()}")
    add(f"Negative node populations: {(nodes[assigned_population_col] < 0).sum()}")
    add(f"Total assigned node population: {nodes[assigned_population_col].sum()}")
    add()

    add("NODE POPULATION DISTRIBUTION")
    add("-" * 50)
    add(nodes[assigned_population_col].describe().to_string())
    add()

    add("AREA SHARE CHECK")
    add("-" * 50)
    tract_share = allocation.groupby(tract_id_col)["area_share"].sum()
    far_from_one = ((tract_share < 0.999) | (tract_share > 1.001)).sum()
    add(tract_share.describe().to_string())
    add(f"Tracts with area_share far from 1: {far_from_one}")
    add()

    add("POPULATION CONSERVATION CHECK")
    add("-" * 50)
    assigned_by_tract = (
        allocation
        .groupby(tract_id_col)[assigned_population_col]
        .sum()
        .reset_index()
    )

    check = assigned_by_tract.merge(
        tracts[[tract_id_col, population_col]],
        on=tract_id_col,
        how="left"
    )

    check["difference"] = check[assigned_population_col] - check[population_col]

    add(check["difference"].describe().to_string())
    add(f"Max absolute population difference: {check['difference'].abs().max()}")
    add()

    add("WORST TRACT DIFFERENCES")
    add("-" * 50)
    worst = check.reindex(
        check["difference"].abs().sort_values(ascending=False).index
    ).head(10)
    add(worst.to_string(index=False))
    add()

    add("HIGH-POPULATION NODE DIAGNOSTICS")
    add("-" * 50)
    node_summary = (
        allocation
        .groupby("node_id")
        .agg(
            total_population=(assigned_population_col, "sum"),
            contributing_tracts=(tract_id_col, "nunique"),
            max_single_tract_assignment=(assigned_population_col, "max"),
        )
        .reset_index()
        .sort_values("total_population", ascending=False)
    )

    add("Top 20 nodes by assigned population:")
    add(node_summary.head(20).to_string(index=False))
    add()

    add("Large assigned-population node counts:")
    for threshold in [100, 250, 500, 1000, 2000, 5000]:
        count = (node_summary["total_population"] >= threshold).sum()
        add(f"Nodes with assigned population >= {threshold}: {count}")
    add()

    add("TRACT NODE-COUNT DIAGNOSTICS")
    add("-" * 50)
    tract_node_summary = (
        allocation
        .groupby(tract_id_col)
        .agg(
            assigned_nodes=("node_id", "nunique"),
            tract_population=(assigned_population_col, "sum"),
            max_node_population=(assigned_population_col, "max"),
            max_area_share=("area_share", "max"),
        )
        .reset_index()
    )

    tract_node_summary["max_node_percent"] = (
        tract_node_summary["max_node_population"]
        / tract_node_summary["tract_population"]
        * 100
    )

    add("Distribution of assigned node counts per tract:")
    add(tract_node_summary["assigned_nodes"].describe().to_string())
    add()
    add(f"Tracts assigned to only 1 node: {(tract_node_summary['assigned_nodes'] == 1).sum()}")
    add(f"Tracts assigned to <= 5 nodes: {(tract_node_summary['assigned_nodes'] <= 5).sum()}")
    add(f"Tracts assigned to <= 10 nodes: {(tract_node_summary['assigned_nodes'] <= 10).sum()}")
    add()

    add("Tracts with few assigned nodes:")
    few_nodes = tract_node_summary.sort_values(
        ["assigned_nodes", "tract_population"],
        ascending=[True, False]
    ).head(20)
    add(few_nodes.to_string(index=False))
    add()

    add("DETERMINISM CHECKSUM")
    add("-" * 50)
    with open(allocation_path, "rb") as f:
        checksum = hashlib.md5(f.read()).hexdigest()
    add(f"Allocation file MD5 checksum: {checksum}")

    report = "\n".join(report_lines)
    print(report)

    if output_report_path:
        with open(output_report_path, "w") as f:
            f.write(report)
        print()
        print(f"Saved validation report to: {output_report_path}")

    return report


if __name__ == "__main__":
    build_census_assignment_validation_report(
        allocation_path="data/census/Boston_node_tract_allocation.csv",
        tracts_path="data/census/ma_tracts_population.geojson",
        nodes_path="data/census/Boston_nodes_with_population.parquet",
        tract_id_col="GEOID",
        population_col="population",
        assigned_population_col="assigned_population",
        output_report_path="data/census/Boston_census_assignment_validation_report.txt",
    )
