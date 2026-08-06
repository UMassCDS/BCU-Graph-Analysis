#!/bin/bash
#SBATCH --job-name=bcu-access
#SBATCH --partition=cpu
#SBATCH --account=pi_plunkett_umass_edu
#SBATCH --output=logs/bcu-access-%j.out
#SBATCH --error=logs/bcu-access-%j.err
#SBATCH --time=24:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G

set -euo pipefail

REPO_ROOT="${SLURM_SUBMIT_DIR:?Submit this job from the repository root.}"
DATA_ROOT="${BCU_DATA_ROOT:?Set BCU_DATA_ROOT before submitting this job.}"
CONDA_ENV="${BCU_CONDA_ENV:-bcu}"

cd "$REPO_ROOT"

if [[ ! -f pyproject.toml ]]; then
  echo "Not a repository root: $REPO_ROOT" >&2
  exit 2
fi

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$CONDA_ENV"

echo "Job ID: ${SLURM_JOB_ID}"
echo "Host: $(hostname)"
echo "Started: $(date)"
echo "Repository: $REPO_ROOT"
echo "Data root: $DATA_ROOT"
echo "Commit: $(git rev-parse HEAD)"

python -m \
  bcu_analysis.node_accessibility.run_all_nodes \
  --graph-path \
    "$DATA_ROOT/processed/osm/greater_boston_6_cost_simplified.graphml" \
  --progress-every 100 \
  --cost-field cost_typical_adult_Baseline \
  --cutoff-miles 1.5 \
  --output-path \
    "$DATA_ROOT/processed/accessibility/greater_boston_node_accessibility_typical_adult.csv" \
  --failure-path \
    "$DATA_ROOT/processed/accessibility/greater_boston_node_accessibility_typical_adult_failures.csv"

echo "Finished: $(date)"
