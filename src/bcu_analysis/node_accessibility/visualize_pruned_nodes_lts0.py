"""Visualize relative accessibility on the pruned graph excluding LTS 0."""

from __future__ import annotations

import argparse
from pathlib import Path

import folium
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from folium.plugins import FastMarkerCluster


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Create static and interactive node-level relative-accessibility maps for a pruned graph.")
    )

    parser.add_argument(
        "--input-path",
        type=Path,
        required=True,
        help="Node-accessibility CSV.",
    )

    parser.add_argument(
        "--output-html",
        type=Path,
        required=True,
        help="Output interactive HTML file.",
    )

    parser.add_argument(
        "--output-png",
        type=Path,
        required=True,
        help="Output static PNG file.",
    )

    parser.add_argument(
        "--title",
        default=("Greater Boston Relative Bicycle Accessibility\nPruned Graph Excluding LTS 0 — Typical Adult"),
    )

    parser.add_argument(
        "--layer-name",
        default="Relative accessibility excluding LTS 0",
    )

    return parser.parse_args()


def load_valid_nodes(
    input_path: Path,
) -> tuple[pd.DataFrame, int, int]:
    if not input_path.exists():
        raise FileNotFoundError(input_path)

    data = pd.read_csv(
        input_path,
        dtype={"node_id": "string"},
    )

    required_columns = {
        "node_id",
        "longitude",
        "latitude",
        "relative_accessibility",
    }

    missing_columns = required_columns - set(data.columns)

    if missing_columns:
        raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

    numeric_columns = [
        "longitude",
        "latitude",
        "relative_accessibility",
    ]

    for column in numeric_columns:
        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    valid_mask = (
        data["longitude"].between(-180, 180)
        & data["latitude"].between(-90, 90)
        & data["relative_accessibility"].between(0, 1)
    )

    valid = data.loc[valid_mask].copy()

    if valid["node_id"].duplicated().any():
        raise ValueError("Duplicate node IDs found in valid map data.")

    total_count = len(data)
    omitted_count = total_count - len(valid)

    return valid, total_count, omitted_count


def create_static_map(
    data: pd.DataFrame,
    output_path: Path,
    title: str,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    figure, axis = plt.subplots(
        figsize=(14, 14),
    )

    points = axis.scatter(
        data["longitude"],
        data["latitude"],
        c=data["relative_accessibility"],
        cmap="RdYlBu",
        vmin=0,
        vmax=1,
        s=0.55,
        alpha=0.85,
        linewidths=0,
        rasterized=True,
    )

    mean_latitude = data["latitude"].mean()

    axis.set_aspect(1 / np.cos(np.deg2rad(mean_latitude)))

    axis.set_title(
        title,
        fontsize=16,
    )

    axis.set_xlabel("Longitude")
    axis.set_ylabel("Latitude")

    colorbar = figure.colorbar(
        points,
        ax=axis,
        fraction=0.035,
        pad=0.02,
    )

    colorbar.set_label(
        "Relative accessibility",
        rotation=270,
        labelpad=18,
    )

    axis.text(
        0.01,
        0.01,
        (f"Valid nodes shown: {len(data):,}\nLow accessibility = red\nHigh accessibility = blue"),
        transform=axis.transAxes,
        fontsize=10,
        verticalalignment="bottom",
        bbox={
            "boxstyle": "round",
            "facecolor": "white",
            "alpha": 0.85,
        },
    )

    axis.grid(
        alpha=0.15,
        linewidth=0.4,
    )

    figure.tight_layout()

    figure.savefig(
        output_path,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(figure)


def create_interactive_map(
    data: pd.DataFrame,
    output_path: Path,
    layer_name: str,
    omitted_count: int,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    center = [
        float(data["latitude"].mean()),
        float(data["longitude"].mean()),
    ]

    map_object = folium.Map(
        location=center,
        zoom_start=10,
        tiles="CartoDB positron",
        prefer_canvas=True,
        control_scale=True,
    )

    marker_data = data[
        [
            "latitude",
            "longitude",
            "relative_accessibility",
            "node_id",
        ]
    ].values.tolist()

    callback = """
    function (row) {
        var score = Number(row[2]);

        function scoreColor(value) {
            if (value <= 0.20) return "#d73027";
            if (value <= 0.40) return "#fc8d59";
            if (value <= 0.60) return "#fee090";
            if (value <= 0.80) return "#91bfdb";
            return "#4575b4";
        }

        var marker = L.circleMarker(
            new L.LatLng(row[0], row[1]),
            {
                radius: 2.5,
                stroke: false,
                fillColor: scoreColor(score),
                fillOpacity: 0.82
            }
        );

        marker.bindTooltip(
            "Node: " + row[3]
            + "<br>Relative accessibility: "
            + score.toFixed(4)
        );

        return marker;
    }
    """

    FastMarkerCluster(
        data=marker_data,
        callback=callback,
        options={
            "disableClusteringAtZoom": 13,
            "maxClusterRadius": 25,
            "spiderfyOnMaxZoom": False,
        },
        name=layer_name,
    ).add_to(map_object)

    legend = f"""
    <div style="
        position: fixed;
        bottom: 35px;
        right: 25px;
        z-index: 9999;
        background: white;
        border: 1px solid #777;
        border-radius: 5px;
        padding: 10px 12px;
        font-size: 13px;
        line-height: 20px;
    ">
        <strong>Relative accessibility</strong><br>
        <span style="color:#d73027;">●</span> 0.00–0.20<br>
        <span style="color:#fc8d59;">●</span> 0.20–0.40<br>
        <span style="color:#fee090;">●</span> 0.40–0.60<br>
        <span style="color:#91bfdb;">●</span> 0.60–0.80<br>
        <span style="color:#4575b4;">●</span> 0.80–1.00<br>
        <hr style="margin:6px 0;">
        Valid nodes: {len(data):,}<br>
        Nodes without valid values: {omitted_count:,}<br>
        LTS 0 paths excluded
    </div>
    """

    map_object.get_root().html.add_child(folium.Element(legend))

    folium.LayerControl(collapsed=False).add_to(map_object)

    map_object.save(output_path)


def main() -> None:
    args = parse_args()

    print(f"Loading: {args.input_path}")

    data, total_count, omitted_count = load_valid_nodes(args.input_path)

    print(f"Total rows: {total_count:,}")
    print(f"Valid nodes: {len(data):,}")
    print(f"Omitted nodes: {omitted_count:,}")

    print(f"Creating static map: {args.output_png}")

    create_static_map(
        data=data,
        output_path=args.output_png,
        title=args.title,
    )

    print(f"Creating interactive map: {args.output_html}")

    create_interactive_map(
        data=data,
        output_path=args.output_html,
        layer_name=args.layer_name,
        omitted_count=omitted_count,
    )

    print()
    print("Created:")
    print(args.output_png.resolve())
    print(args.output_html.resolve())


if __name__ == "__main__":
    main()
