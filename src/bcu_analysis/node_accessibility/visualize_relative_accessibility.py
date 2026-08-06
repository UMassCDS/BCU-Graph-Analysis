"""Create an interactive map of relative bicycle accessibility."""

import argparse
from pathlib import Path

import branca.colormap as cm
import folium
import pandas as pd


def parse_args() -> argparse.Namespace:
    """Parse visualization input and output locations."""
    parser = argparse.ArgumentParser(
        description=(
            "Create an interactive map of relative bicycle accessibility."
        )
    )

    parser.add_argument(
        "--input-path",
        type=Path,
        required=True,
        help="Node-accessibility results CSV.",
    )

    parser.add_argument(
        "--output-path",
        type=Path,
        required=True,
        help="Location for the generated HTML map.",
    )

    return parser.parse_args()


# Roughly 200-meter cells around Boston.
GRID_SIZE = 0.002


def main() -> None:
    args = parse_args()

    print(f"Reading: {args.input_path}")

    data = pd.read_csv(args.input_path)

    required_columns = {
        "node_id",
        "longitude",
        "latitude",
        "relative_accessibility",
        "calculation_status",
    }

    missing_columns = required_columns - set(data.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    # Remove rows where relative accessibility cannot be calculated.
    valid = data.loc[
        data["relative_accessibility"].notna()
        & data["longitude"].notna()
        & data["latitude"].notna()
    ].copy()

    # Correct tiny floating-point values outside the expected 0–1 range.
    valid["relative_accessibility"] = (
        valid["relative_accessibility"].clip(0.0, 1.0)
    )

    print(f"Total rows: {len(data):,}")
    print(f"Valid accessibility rows: {len(valid):,}")
    print(f"Excluded rows: {len(data) - len(valid):,}")

    # Group nearby nodes so the browser does not need to render
    # almost 100,000 separate markers.
    valid["grid_lat"] = (
        valid["latitude"] / GRID_SIZE
    ).round() * GRID_SIZE

    valid["grid_lon"] = (
        valid["longitude"] / GRID_SIZE
    ).round() * GRID_SIZE

    grid = (
        valid.groupby(
            ["grid_lat", "grid_lon"],
            as_index=False,
        )
        .agg(
            median_accessibility=(
                "relative_accessibility",
                "median",
            ),
            mean_accessibility=(
                "relative_accessibility",
                "mean",
            ),
            node_count=(
                "node_id",
                "count",
            ),
        )
    )

    print(f"Map cells: {len(grid):,}")

    map_center = [
        valid["latitude"].median(),
        valid["longitude"].median(),
    ]

    accessibility_map = folium.Map(
        location=map_center,
        zoom_start=10,
        tiles="CartoDB positron",
        control_scale=True,
        prefer_canvas=True,
    )

    colormap = cm.LinearColormap(
        colors=[
            "#b2182b",
            "#ef8a62",
            "#fddbc7",
            "#d9f0d3",
            "#67a9cf",
            "#2166ac",
        ],
        vmin=0.0,
        vmax=1.0,
        caption=(
            "Median relative accessibility "
            "(0 = lowest, 1 = highest)"
        ),
    )

    accessibility_layer = folium.FeatureGroup(
        name="Relative accessibility",
        show=True,
    )

    for row in grid.itertuples(index=False):
        value = float(row.median_accessibility)

        tooltip = folium.Tooltip(
            (
                f"<b>Median relative accessibility:</b> "
                f"{value:.3f}<br>"
                f"<b>Mean relative accessibility:</b> "
                f"{row.mean_accessibility:.3f}<br>"
                f"<b>Nodes represented:</b> "
                f"{row.node_count:,}"
            )
        )

        folium.CircleMarker(
            location=[
                row.grid_lat,
                row.grid_lon,
            ],
            radius=4,
            color=colormap(value),
            fill=True,
            fill_color=colormap(value),
            fill_opacity=0.78,
            weight=0.5,
            tooltip=tooltip,
        ).add_to(accessibility_layer)

    accessibility_layer.add_to(accessibility_map)
    colormap.add_to(accessibility_map)

    folium.LayerControl(
        collapsed=False,
    ).add_to(accessibility_map)

    accessibility_map.fit_bounds(
        [
            [
                valid["latitude"].min(),
                valid["longitude"].min(),
            ],
            [
                valid["latitude"].max(),
                valid["longitude"].max(),
            ],
        ]
    )

    args.output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    accessibility_map.save(args.output_path)

    print(f"Saved map: {args.output_path}")


if __name__ == "__main__":
    main()
