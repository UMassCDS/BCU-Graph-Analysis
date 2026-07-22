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

cd /work/pi_plunkett_umass_edu/bcu/BCU-Graph-Analysis

source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate bcu

echo "Job ID: ${SLURM_JOB_ID}"
echo "Host: $(hostname)"
echo "Started: $(date)"
echo "Commit: $(git rev-parse HEAD)"

python -m bcu_analysis.node_accessibility.run_all_nodes \
  --progress-every 100 \
  --cost-field cost_typical_adult_Baseline \
  --cutoff-miles 1.5 \
  --output-path /work/pi_plunkett_umass_edu/bcu/data/processed/accessibility/greater_boston_node_accessibility_typical_adult.csv \
  --failure-path /work/pi_plunkett_umass_edu/bcu/data/processed/accessibility/greater_boston_node_accessibility_typical_adult_failures.csv

echo "Finished: $(date)"
