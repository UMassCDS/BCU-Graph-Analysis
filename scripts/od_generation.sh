#!/bin/bash
#SBATCH --job-name=bcu_graph
#SBATCH -p cpu,cpu-preempt
#SBATCH -N 1
#SBATCH -c 1
#SBATCH --mem=32G
#SBATCH --time=2:00:00
#SBATCH --output=scripts/errors/path_count-%j.out
#SBATCH --error=scripts/errors/path_count-%j.err 

module load conda/latest
conda activate bcu_graph_analysis

python -u src/bcu_analysis/od_generation/generate_od_demand.py \
    1 \
    greater_boston \
    --demand_scenario 1 \
    --data-dir /work/pi_plunkett_umass_edu/bcu/final \
    --pop-geojson-path