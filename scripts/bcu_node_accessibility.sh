#!/bin/bash
#SBATCH --job-name=node_accessibility
#SBATCH -p cpu,cpu-preempt
#SBATCH -N 1
#SBATCH -c 1
#SBATCH --mem=16G
#SBATCH --time=24:00:00
#SBATCH --output=scripts/errors/node_accessibility-%j.out
#SBATCH --error=scripts/errors/node_accessibility-%j.err

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
OUTPUT_DIR="$DATA_ROOT/accessibility_results"
OUTPUT_PATH="$OUTPUT_DIR/greater_boston_cost_scenario_1_node_accessibility_1p5mi.csv"
FAILURE_PATH="$OUTPUT_DIR/greater_boston_cost_scenario_1_node_accessibility_1p5mi_failures.csv"

[[ -f "$GRAPH_PATH" ]] || {
    echo "Missing graph: $GRAPH_PATH" >&2
    exit 1
}

mkdir -p "$OUTPUT_DIR"

echo "Job ID: ${SLURM_JOB_ID:-N/A}"
echo "Host: $(hostname)"
echo "Started: $(date)"
echo "Repository: $REPO_ROOT"
echo "Conda environment: $CONDA_ENV"
echo "Graph: $GRAPH_PATH"
echo "Cost field: cost"
echo "Cutoff: 1.5 miles"
echo "Output: $OUTPUT_PATH"
echo "Failures: $FAILURE_PATH"

# Results are checkpointed after every completed node.
# Re-running the job resumes by skipping node IDs already present in OUTPUT_PATH.
python -u -m bcu_analysis.node_accessibility.run_all_nodes \
    --graph-path "$GRAPH_PATH" \
    --progress-every 100 \
    --cost-field cost \
    --cutoff-miles 1.5 \
    --output-path "$OUTPUT_PATH" \
    --failure-path "$FAILURE_PATH"

echo "Finished: $(date)"
