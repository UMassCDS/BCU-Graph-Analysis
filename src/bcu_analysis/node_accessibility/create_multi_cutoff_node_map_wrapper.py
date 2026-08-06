"""Create an HTML wrapper for cutoff-specific node accessibility maps."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create one HTML page that switches among "
            "cutoff-specific node accessibility maps."
        )
    )

    parser.add_argument(
        "--map-root",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--title",
        default=(
            "Greater Boston Relative Bicycle Accessibility "
            "— Excluding LTS 0"
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    specifications = [
        ("1p5", 1.5),
        ("2p0", 2.0),
        ("2p5", 2.5),
    ]

    args.output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    scenarios = []

    for tag, miles in specifications:
        map_path = (
            args.map_root
            / f"cutoff_{tag}_miles"
            / "relative_accessibility.html"
        )

        if not map_path.is_file():
            raise FileNotFoundError(map_path)

        relative_path = map_path.relative_to(
            args.output_path.parent
        )

        scenarios.append(
            {
                "tag": tag,
                "miles": miles,
                "label": f"{miles:g} miles",
                "map_path": relative_path.as_posix(),
            }
        )

    scenario_json = json.dumps(
        scenarios,
        allow_nan=False,
    )

    title_html = html.escape(args.title)

    template = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta
  name="viewport"
  content="width=device-width, initial-scale=1"
>
<title>__TITLE__</title>

<style>
html,
body {
    width: 100%;
    height: 100%;
    margin: 0;
    font-family: Arial, Helvetica, sans-serif;
    color: #222;
}

#page {
    display: grid;
    grid-template-rows: auto 1fr;
    width: 100%;
    height: 100%;
}

#toolbar {
    display: flex;
    align-items: center;
    gap: 16px;
    box-sizing: border-box;
    padding: 11px 16px;
    border-bottom: 1px solid #ccc;
    background: white;
}

#title {
    flex: 1;
    font-size: 17px;
    font-weight: 700;
}

#cutoff-control {
    display: flex;
    align-items: center;
    gap: 8px;
}

label {
    font-size: 14px;
    font-weight: 700;
}

select {
    min-width: 130px;
    padding: 8px 10px;
    border: 1px solid #999;
    border-radius: 4px;
    background: white;
    font-size: 14px;
}

#map-frame {
    display: block;
    width: 100%;
    height: 100%;
    border: 0;
}

@media (max-width: 700px) {
    #toolbar {
        align-items: stretch;
        flex-direction: column;
    }

    #cutoff-control {
        width: 100%;
    }

    select {
        flex: 1;
    }
}
</style>
</head>

<body>
<div id="page">
    <header id="toolbar">
        <div id="title">__TITLE__</div>

        <div id="cutoff-control">
            <label for="cutoff-select">
                Distance limit
            </label>

            <select id="cutoff-select"></select>
        </div>
    </header>

    <iframe
      id="map-frame"
      title="Node accessibility map"
    ></iframe>
</div>

<script>
const scenarios = __SCENARIOS__;

const cutoffSelect = document.getElementById(
    "cutoff-select"
);

const mapFrame = document.getElementById(
    "map-frame"
);

function displayScenario(tag) {
    const scenario = scenarios.find(
        (candidate) => candidate.tag === tag
    );

    if (!scenario) {
        throw new Error(
            "Unknown cutoff: " + tag
        );
    }

    mapFrame.src = scenario.map_path;

    const url = new URL(window.location.href);
    url.searchParams.set("cutoff", scenario.tag);

    window.history.replaceState(
        {},
        "",
        url
    );
}

scenarios.forEach(
    (scenario) => {
        const option = document.createElement(
            "option"
        );

        option.value = scenario.tag;
        option.textContent = scenario.label;

        cutoffSelect.appendChild(option);
    }
);

const requestedTag = new URL(
    window.location.href
).searchParams.get("cutoff");

const initialScenario = scenarios.find(
    (scenario) => scenario.tag === requestedTag
) || scenarios[0];

cutoffSelect.value = initialScenario.tag;
displayScenario(initialScenario.tag);

cutoffSelect.addEventListener(
    "change",
    (event) => {
        displayScenario(event.target.value);
    }
);
</script>
</body>
</html>
"""

    rendered = template.replace(
        "__TITLE__",
        title_html,
    )

    rendered = rendered.replace(
        "__SCENARIOS__",
        scenario_json,
    )

    args.output_path.write_text(
        rendered,
        encoding="utf-8",
    )

    print(f"Cutoff scenarios: {len(scenarios)}")

    for scenario in scenarios:
        print(
            f"  {scenario['label']}: "
            f"{scenario['map_path']}"
        )

    print(f"Saved: {args.output_path}")


if __name__ == "__main__":
    main()
