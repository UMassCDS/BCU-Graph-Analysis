import argparse
import os

import pandas as pd

from bcu_analysis.od_generation.build_poi_od_pairs import build_poi_od_pairs
from bcu_analysis.od_generation.lodes_pairs import generate_lodes_pairs
from bcu_analysis.od_generation.lodes_sampling import sample_lodes_trips

# The LODES home->work commute pipeline is driven by this demand category; every other
# category is handled by the population-weighted POI pipeline.
LODES_CATEGORY = "home_office"

DEFAULT_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "config", "demand_parameters.csv"
)


def load_demand(scenario_id=1, config_path=DEFAULT_CONFIG_PATH):
    """
    Read per-category trip counts for a demand scenario from demand_parameters.csv.

    The config's first column holds the category names (home_office, home_school, ...)
    plus a TOTAL row; each remaining column is a scenario, headed by its scenario id.

    Parameters:
    - scenario_id (int | str): Which scenario column to read.
    - config_path (str): Path to demand_parameters.csv.

    Returns:
    - dict: {category_key: int_count} for categories with a positive count in the
      selected scenario (the TOTAL row and blank/NaN entries are dropped).
    """
    config = pd.read_csv(config_path, dtype=str)
    category_col = config.columns[0]
    scenario_col = str(scenario_id)
    if scenario_col not in config.columns:
        raise ValueError(
            f"scenario_id {scenario_id!r} not found in {config_path}; "
            f"available: {list(config.columns[1:])}"
        )

    counts = {}
    for _, row in config.iterrows():
        category = row[category_col]
        if category == "TOTAL":
            continue
        value = row[scenario_col]
        if pd.isna(value) or str(value).strip() == "":
            continue
        count = int(float(value))
        if count > 0:
            counts[category] = count
    return counts


def main(
    scenario_id=1,
    config_path=DEFAULT_CONFIG_PATH,
    output_path="/work/pi_plunkett_umass_edu/bcu/data/processed/census/greater_boston_od_demand.csv",
    random_seed=None,
):
    """
    Run both OD generators for a demand scenario and write a single combined CSV.

    Output columns: origin_node, destination_node, category, count.
    """
    counts = load_demand(scenario_id, config_path=config_path)
    print(f"Demand scenario {scenario_id}: {counts}")

    frames = []

    # LODES commute trips (home_office): build the base pairs then draw the scenario's
    # number of trips, tagging them with the category.
    lodes_count = counts.get(LODES_CATEGORY)
    if lodes_count:
        generate_lodes_pairs()
        lodes = sample_lodes_trips(n_trips=lodes_count, random_seed=random_seed)
        lodes = lodes[["origin_node", "destination_node", "count"]].copy()
        lodes["category"] = LODES_CATEGORY
        frames.append(lodes)

    # POI trips for every other category.
    poi_counts = {k: v for k, v in counts.items() if k != LODES_CATEGORY}
    if poi_counts:
        poi = build_poi_od_pairs(category_counts=poi_counts)
        if not poi.empty:
            frames.append(poi)

    if not frames:
        raise ValueError(f"No trips generated for scenario {scenario_id}.")

    combined = pd.concat(frames, ignore_index=True)
    combined = combined[["origin_node", "destination_node", "category", "count"]]

    combined.to_csv(output_path, index=False)
    print(f"Wrote {len(combined):,} combined OD pairs to {output_path}")
    print(combined.groupby("category")["count"].sum())
    return combined


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Combine LODES + POI OD pairs for a demand scenario.")
    parser.add_argument("--scenario-id", default=1, help="Scenario column in demand_parameters.csv")
    parser.add_argument("--config-path", default=DEFAULT_CONFIG_PATH)
    parser.add_argument(
        "--output-path",
        default="/work/pi_plunkett_umass_edu/bcu/data/processed/census/greater_boston_od_demand.csv",
    )
    parser.add_argument("--random-seed", type=int, default=None)
    args = parser.parse_args()
    main(
        scenario_id=args.scenario_id,
        config_path=args.config_path,
        output_path=args.output_path,
        random_seed=args.random_seed,
    )
