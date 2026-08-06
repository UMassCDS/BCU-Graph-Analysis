#!/bin/bash
#SBATCH --job-name=path_count           # job name
#SBATCH -p cpu                          #partition (cpu or gpu)
#SBATCH -N 1                            #number of nodes
#SBATCH -c 16                           #number of cores
#SBATCH --mem=32G                       #memory (G is for GB)
#SBATCH --time=2:00:00                  #maximum run time
#SBATCH --output=scripts/errors/path_count-%j.out       #standard output file
#SBATCH --error=scripts/errors/path_count-%j.err        #standard error file 

module load conda/latest
conda activate graph_analysis

#-u is for unbuffered outputs (outputs as file runs)
python -u src/bcu_analysis/road_usage/path_count.py \
    /work/pi_plunkett_umass_edu/data \
    1 \
    1 \
    All