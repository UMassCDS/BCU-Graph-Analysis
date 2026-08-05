"""Replace accessibility quartile screening with weighted regressions."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=("Run population-weighted node-level accessibility regressions."))

    parser.add_argument(
        "--input-path",
        type=Path,
        required=True,
        help=("Node-level CSV containing accessibility, population weights, and demographic values."),
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory for regression results and summaries.",
    )

    return parser.parse_args()


DEMOGRAPHIC_HINTS = (
    "age",
    "asian",
    "black",
    "white",
    "hispanic",
    "latino",
    "native",
    "pacific",
    "multiracial",
    "race",
    "color",
    "poverty",
    "renter",
    "vehicle",
    "disab",
    "english",
    "income",
    "household",
    "minority",
)

EXCLUDE_HINTS = (
    "accessibility",
    "coverage",
    "area_share",
    "longitude",
    "latitude",
    "geometry",
    "node_id",
    "geoid",
    "status",
    "distance",
    "absolute",
)


def clean_name(name: str) -> str:
    """Normalize a column name for pattern matching."""
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def numeric(series: pd.Series) -> pd.Series:
    """Convert values to numeric, replacing invalid values with NaN."""
    return pd.to_numeric(series, errors="coerce")


def looks_demographic(name: str) -> bool:
    """Return whether a column appears to represent a demographic measure."""
    cleaned = clean_name(name)

    has_demographic_hint = any(hint in cleaned for hint in DEMOGRAPHIC_HINTS)
    has_excluded_hint = any(hint in cleaned for hint in EXCLUDE_HINTS)

    return has_demographic_hint and not has_excluded_hint


def find_first(
    columns: list[str],
    required_tokens: tuple[str, ...],
) -> str | None:
    """Find the first column containing all required name tokens."""
    for column in columns:
        cleaned = clean_name(column)

        if all(token in cleaned for token in required_tokens):
            return column

    return None


def prepare_predictors(
    data: pd.DataFrame,
) -> dict[str, tuple[pd.Series, str]]:
    """Find and scale demographic regression predictors."""
    predictors: dict[str, tuple[pd.Series, str]] = {}

    # Prefer percentage, rate, proportion, or share columns that
    # were already calculated by the Census workflow.
    for column in data.columns:
        cleaned = clean_name(column)

        if not looks_demographic(column):
            continue

        is_share = any(
            token in cleaned
            for token in (
                "pct",
                "percent",
                "share",
                "rate",
                "proportion",
            )
        )

        if not is_share:
            continue

        values = numeric(data[column])
        finite = values[np.isfinite(values)]

        if finite.empty:
            continue

        percentile_99 = float(finite.quantile(0.99))

        # Convert percentages represented from 0 to 100 into 0 to 1.
        if 1.5 < percentile_99 <= 100.5:
            values = values / 100.0

        # Values substantially above 100 are probably counts rather
        # than percentages and should not be used here.
        elif percentile_99 > 100.5:
            continue

        # Dividing by 0.10 makes the coefficient represent a
        # 10-percentage-point increase.
        predictors[column] = (
            values / 0.10,
            "10 percentage-point increase",
        )

    # Add median household income, measured per $10,000.
    for column in data.columns:
        cleaned = clean_name(column)

        if "median" in cleaned and "income" in cleaned:
            predictors[column] = (
                numeric(data[column]) / 10000.0,
                "$10,000 increase",
            )
            break

    # Add population density using a log transformation.
    for column in data.columns:
        cleaned = clean_name(column)

        if "population" in cleaned and "density" in cleaned:
            values = numeric(data[column]).clip(lower=0)

            predictors[column] = (
                np.log1p(values),
                "one-unit increase in log(1 + population density)",
            )
            break

    # Fallback for person-count variables when no percentage column
    # was created. This uses assigned population as the denominator.
    population_column = find_first(
        list(data.columns),
        ("assigned", "population"),
    )

    if population_column is None:
        population_column = find_first(
            list(data.columns),
            ("total", "population"),
        )

    if population_column is not None:
        denominator = numeric(data[population_column]).replace(
            0,
            np.nan,
        )

        person_count_hints = (
            "asian",
            "black",
            "white",
            "hispanic",
            "latino",
            "native",
            "pacific",
            "multiracial",
            "under_18",
            "age_65",
            "disab",
        )

        for column in data.columns:
            cleaned = clean_name(column)

            if column == population_column:
                continue

            if column in predictors:
                continue

            if not looks_demographic(column):
                continue

            if not any(token in cleaned for token in person_count_hints):
                continue

            values = numeric(data[column]) / denominator
            finite = values[np.isfinite(values)]

            if finite.empty:
                continue

            if float(finite.quantile(0.99)) > 1.2:
                continue

            predictor_name = f"derived_share__{column}"

            predictors[predictor_name] = (
                values / 0.10,
                "10 percentage-point increase",
            )

    return predictors


def fit_one_regression(
    data: pd.DataFrame,
    predictor_name: str,
    predictor: pd.Series,
    effect_unit: str,
) -> dict[str, object] | None:
    """Fit one population-weighted linear regression."""
    frame = pd.DataFrame(
        {
            "outcome": numeric(data["relative_accessibility"]),
            "predictor": predictor,
            "population_weight": numeric(data["assigned_total_population"]),
        }
    )

    frame = frame.replace(
        [np.inf, -np.inf],
        np.nan,
    ).dropna()

    frame = frame[frame["outcome"].between(0, 1) & (frame["population_weight"] > 0)].copy()

    if len(frame) < 30:
        return None

    if frame["predictor"].nunique() < 3:
        return None

    represented_population = float(frame["population_weight"].sum())

    # Normalize weights so that their mean is 1. This preserves
    # relative population weighting without pretending that each
    # resident is a separate independent observation.
    frame["population_weight"] = frame["population_weight"] / frame["population_weight"].mean()

    design = sm.add_constant(
        frame[["predictor"]],
        has_constant="add",
    )

    model = sm.WLS(
        frame["outcome"],
        design,
        weights=frame["population_weight"],
    )

    result = model.fit(cov_type="HC3")

    coefficient = float(result.params["predictor"])
    standard_error = float(result.bse["predictor"])
    p_value = float(result.pvalues["predictor"])

    confidence_interval = result.conf_int().loc["predictor"]

    confidence_low = float(confidence_interval.iloc[0])
    confidence_high = float(confidence_interval.iloc[1])

    return {
        "predictor": predictor_name,
        "effect_unit": effect_unit,
        "coefficient": coefficient,
        "coefficient_accessibility_percentage_points": (coefficient * 100.0),
        "standard_error": standard_error,
        "ci_95_low": confidence_low,
        "ci_95_high": confidence_high,
        "ci_95_low_accessibility_percentage_points": (confidence_low * 100.0),
        "ci_95_high_accessibility_percentage_points": (confidence_high * 100.0),
        "p_value": p_value,
        "n_nodes": len(frame),
        "represented_population": represented_population,
        "r_squared": float(result.rsquared),
        "direction": ("higher accessibility" if coefficient > 0 else "lower accessibility"),
    }


def main() -> None:
    """Load the analytical data and run the regressions."""
    args = parse_args()

    if not args.input_path.exists():
        raise FileNotFoundError(f"Input file not found: {args.input_path}")

    args.output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    print(f"Loading: {args.input_path}")

    data = pd.read_csv(
        args.input_path,
        low_memory=False,
    )

    print(f"Rows loaded: {len(data):,}")

    required_columns = {
        "relative_accessibility",
        "assigned_total_population",
    }

    missing_columns = sorted(required_columns.difference(data.columns))

    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    if "accessibility_status" in data.columns:
        successful = data["accessibility_status"].astype(str).str.lower().eq("success")

        if successful.any():
            data = data[successful].copy()

    predictors = prepare_predictors(data)

    print(f"Regression predictors found: {len(predictors)}")

    for predictor_name in predictors:
        print(f"- {predictor_name}")

    if not predictors:
        print("\nNo usable demographic predictors were automatically detected.")
        print("\nAvailable columns:\n")

        for column in data.columns:
            print(column)

        raise RuntimeError("No demographic predictors detected.")

    regression_rows = []

    for predictor_name, (
        predictor,
        effect_unit,
    ) in predictors.items():
        regression_row = fit_one_regression(
            data=data,
            predictor_name=predictor_name,
            predictor=predictor,
            effect_unit=effect_unit,
        )

        if regression_row is not None:
            regression_rows.append(regression_row)

    if not regression_rows:
        raise RuntimeError("Predictors were detected, but no regression had enough valid observations.")

    results = pd.DataFrame(regression_rows)

    results["fdr_adjusted_p_value"] = multipletests(
        results["p_value"].to_numpy(),
        method="fdr_bh",
    )[1]

    results["statistically_significant_fdr_0_05"] = results["fdr_adjusted_p_value"] < 0.05

    results = results.sort_values(
        [
            "fdr_adjusted_p_value",
            "coefficient_accessibility_percentage_points",
        ],
        ascending=[True, False],
    ).reset_index(drop=True)

    csv_path = args.output_dir / "population_weighted_node_regressions.csv"

    summary_path = args.output_dir / "population_weighted_node_regression_summary.txt"

    results.to_csv(
        csv_path,
        index=False,
    )

    display_columns = [
        "predictor",
        "effect_unit",
        "coefficient_accessibility_percentage_points",
        "ci_95_low_accessibility_percentage_points",
        "ci_95_high_accessibility_percentage_points",
        "p_value",
        "fdr_adjusted_p_value",
        "n_nodes",
        "represented_population",
        "r_squared",
    ]

    summary_lines = [
        "Population-weighted node accessibility regressions",
        "==================================================",
        "",
        "Outcome: relative_accessibility, ranging from 0 to 1",
        "Weights: assigned_total_population, normalized to mean 1",
        "Uncertainty: HC3 robust standard errors",
        "Multiple testing: Benjamini-Hochberg FDR correction",
        "Interpretation: descriptive association, not causation",
        "",
        results[display_columns].to_string(index=False),
        "",
        f"Detailed CSV: {csv_path}",
    ]

    summary_path.write_text(
        "\n".join(summary_lines),
        encoding="utf-8",
    )

    print("\nTOP REGRESSION RESULTS")
    print("======================")

    print(results[display_columns].head(20).to_string(index=False))

    print(f"\nSaved: {csv_path}")
    print(f"Saved: {summary_path}")


if __name__ == "__main__":
    main()
