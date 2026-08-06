#!/bin/bash
#SBATCH --job-name=bcu-access-array
#SBATCH --partition=cpu
#SBATCH --account=pi_plunkett_umass_edu
#SBATCH --array=0-7
#SBATCH --output=logs/bcu-access-array-%A-%a.out
#SBATCH --error=logs/bcu-access-array-%A-%a.err
#SBATCH --time=12:00:00
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G

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

echo "Array job: ${SLURM_ARRAY_JOB_ID}"
echo "Shard: ${SLURM_ARRAY_TASK_ID}"
echo "Host: $(hostname)"
echo "Started: $(date)"
echo "Repository: $REPO_ROOT"
echo "Data root: $DATA_ROOT"
echo "Commit: $(git rev-parse HEAD)"

python -u -m \
  bcu_analysis.node_accessibility.run_shard \
  --graph-path \
    "$DATA_ROOT/processed/osm/greater_boston_6_cost_simplified.graphml" \
  --shard-index "${SLURM_ARRAY_TASK_ID}" \
  --num-shards 8 \
  --progress-every 100 \
  --cost-field cost_typical_adult_Baseline \
  --cutoff-miles 1.5 \
  --existing-results \
    "$DATA_ROOT/processed/accessibility/greater_boston_node_accessibility_typical_adult.csv" \
  --output-dir \
    "$DATA_ROOT/processed/accessibility/shards"

echo "Finished: $(date)"
