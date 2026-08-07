#!/bin/bash
#SBATCH --job-name=road_usage_analysis      # job name
#SBATCH -p cpu,cpu-preempt                  #partition (cpu or gpu)
#SBATCH -N 1                                #number of nodes
#SBATCH -c 16                               #number of cores
#SBATCH --mem=32G                           #memory (G is for GB)
#SBATCH --time=2:00:00                      #maximum run time
#SBATCH --output=scripts/errors/road_usage_analysis-%j.out       #standard output file
#SBATCH --error=scripts/errors/road_usage_analysis-%j.err        #standard error file

module load conda/latest
conda activate bcu_graph_analysis

#-u is for unbuffered outputs (outputs as file runs)
python -u src/bcu_analysis/road_usage/path_count.py \
    /work/pi_plunkett_umass_edu/bcu/final \
    1 \
    1 \
    All

python -u src/bcu_analysis/road_usage/metrics.py \
    /work/pi_plunkett_umass_edu/bcu/final \
    1 \
    1 \
    All

python -u src/bcu_analysis/road_usage/Distributions.py \
    /work/pi_plunkett_umass_edu/bcu/final \
    All \
    1 \
    1

python -u src/bcu_analysis/road_usage/svgs/HeatmapLog.py \
    /work/pi_plunkett_umass_edu/bcu/final \
    All \
    1 \
    1 \
    usage \
    1 \
    500

python -u src/bcu_analysis/road_usage/svgs/HeatmapLog.py \
    /work/pi_plunkett_umass_edu/bcu/final \
    All \
    1 \
    1 \
    usage_stress \
    1 \
    750

python -u src/bcu_analysis/road_usage/svgs/HeatmapLog.py \
    /work/pi_plunkett_umass_edu/bcu/final \
    All \
    1 \
    1 \
    potential_improvement \
    100 \
    20000

python -u src/bcu_analysis/road_usage/svgs/HeatmapLog.py \
    /work/pi_plunkett_umass_edu/bcu/final \
    All \
    1 \
    1 \
    usage_stress \
    1 \
    750 \
    --onlyLTS3and4

python -u src/bcu_analysis/road_usage/svgs/HeatmapLog.py \
    /work/pi_plunkett_umass_edu/bcu/final \
    All \
    1 \
    1 \
    potential_improvement \
    100 \
    20000 \
    --onlyLTS3and4