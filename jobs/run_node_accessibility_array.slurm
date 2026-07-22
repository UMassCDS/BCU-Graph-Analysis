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

cd /work/pi_plunkett_umass_edu/bcu/BCU-Graph-Analysis

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate bcu

echo "Array job: ${SLURM_ARRAY_JOB_ID}"
echo "Shard: ${SLURM_ARRAY_TASK_ID}"
echo "Host: $(hostname)"
echo "Started: $(date)"
echo "Commit: $(git rev-parse HEAD)"

python -u -m bcu_analysis.node_accessibility.run_shard \
  --shard-index "${SLURM_ARRAY_TASK_ID}" \
  --num-shards 8 \
  --progress-every 100 \
  --cost-field cost_typical_adult_Baseline \
  --cutoff-miles 1.5 \
  --existing-results /work/pi_plunkett_umass_edu/bcu/data/processed/accessibility/greater_boston_node_accessibility_typical_adult.csv \
  --output-dir /work/pi_plunkett_umass_edu/bcu/data/processed/accessibility/shards

echo "Finished: $(date)"
