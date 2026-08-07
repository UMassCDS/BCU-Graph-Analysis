#!/bin/bash
#SBATCH --job-name=census_assignment
#SBATCH -p cpu,cpu-preempt
#SBATCH -N 1
#SBATCH -c 1
#SBATCH --mem=16G
#SBATCH --time=8:00:00
#SBATCH --output=scripts/errors/census_assignment-%j.out
#SBATCH --error=scripts/errors/census_assignment-%j.err

set -euo pipefail

module load conda/latest

CONDA_ENV="${BCU_CONDA_ENV:-bcu_graph_analysis}"
conda activate "$CONDA_ENV"

if [[ -n "${SLURM_JOB_ID:-}" && -n "${SLURM_SUBMIT_DIR:-}" && -d "${SLURM_SUBMIT_DIR:-}" ]]; then
    REPO_ROOT="$SLURM_SUBMIT_DIR"
else
    REPO_ROOT="$PWD"
fi

cd "$REPO_ROOT"

if [[ ! -f pyproject.toml ]]; then
    echo "Error: submit or run this script from the BCU-Graph-Analysis repository root." >&2
    exit 2
fi

export PYTHONPATH="$REPO_ROOT/src:${PYTHONPATH:-}"

DATA_ROOT="/work/pi_plunkett_umass_edu/bcu/final"

GRAPH_PATH="$DATA_ROOT/output/cost_scenarios/cost_scenario_1/greater_boston_cost_scenario_1_simplified.graphml"
TRACT_PATH="$DATA_ROOT/ma_tracts_population.geojson"
OUTPUT_DIR="$DATA_ROOT/census_results"

[[ -f "$GRAPH_PATH" ]] || {
    echo "Missing graph: $GRAPH_PATH" >&2
    exit 1
}

[[ -f "$TRACT_PATH" ]] || {
    echo "Missing Census tract file: $TRACT_PATH" >&2
    exit 1
}

mkdir -p "$OUTPUT_DIR"

echo "Job ID: ${SLURM_JOB_ID:-N/A}"
echo "Host: $(hostname)"
echo "Started: $(date)"
echo "Repository: $REPO_ROOT"
echo "Conda environment: $CONDA_ENV"
echo "Graph: $GRAPH_PATH"
echo "Census tracts: $TRACT_PATH"
echo "Output directory: $OUTPUT_DIR"

python -u -m bcu_analysis.census.run_census_assignment \
    --region greater-boston \
    --graph-path "$GRAPH_PATH" \
    --tract-path "$TRACT_PATH" \
    --output-directory "$OUTPUT_DIR" \
    --output-prefix greater_boston_cost_scenario_1

echo "Finished: $(date)"
