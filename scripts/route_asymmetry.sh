#!/bin/bash
#SBATCH --job-name=bcu_asymmetry
#SBATCH -p cpu,cpu-preempt
#SBATCH -N 1
#SBATCH -c 16
#SBATCH --mem=64G
#SBATCH --time=8:00:00
#SBATCH --output=scripts/errors/route_asymmetry-%j.out
#SBATCH --error=scripts/errors/route_asymmetry-%j.err

module load conda/latest
conda activate bcu_graph_analysis

python -u src/bcu_analysis/one_way_evaluation/run_route_asymmetry.py \
    1 \
    greater_boston \
    --demand-scenario 1 \
    --data-dir /work/pi_plunkett_umass_edu/bcu/final \
    --workers ${SLURM_CPUS_PER_TASK:-16}
