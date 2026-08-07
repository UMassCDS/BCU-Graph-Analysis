#!/bin/bash
#SBATCH --job-name=bcu_graph
#SBATCH -p cpu,cpu-preempt
#SBATCH -N 1
#SBATCH -c 1
#SBATCH --mem=32G
#SBATCH --time=2:00:00
#SBATCH --output=scripts/errors/bcu_graph-%j.out
#SBATCH --error=scripts/errors/bcu_graph-%j.err 

module load conda/latest
conda activate bcu_graph_analysis

python -u src/bcu_analysis/graph_builder/build_cost_graph.py \
    1 \
    greater_boston \
    --data-dir /work/pi_plunkett_umass_edu/bcu/final