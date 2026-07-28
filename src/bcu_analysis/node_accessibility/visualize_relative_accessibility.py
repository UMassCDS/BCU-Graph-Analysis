"""Create an interactive map of relative bicycle accessibility."""

from pathlib import Path

import branca.colormap as cm
import folium
import pandas as pd


INPUT_PATH = Path(
    "/work/pi_plunkett_umass_edu/bcu/data/processed/accessibility/"
    "greater_boston_node_accessibility_typical_adult_final.csv"
)

OUTPUT_PATH = Path(
    "/work/pi_plunkett_umass_edu/bcu/data/processed/accessibility/"
    "greater_boston_relative_accessibility_map.html"
)

# Roughly 200-meter cells around Boston.
GRID_SIZE = 0.002


def main() -> None:
    print(f"Reading: {INPUT_PATH}")

    data = pd.read_csv(INPUT_PATH)

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

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    accessibility_map.save(OUTPUT_PATH)

    print(f"Saved map: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
