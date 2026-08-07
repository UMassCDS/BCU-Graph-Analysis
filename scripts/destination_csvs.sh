#!/bin/bash
#SBATCH --job-name=path_count       # job name
#SBATCH -p cpu,cpu-preempt          #partition (cpu or gpu)
#SBATCH -N 1                        #number of nodes
#SBATCH -c 1                       #number of cores
#SBATCH --mem=8G                   #memory (G is for GB)
#SBATCH --time=1:00:00              #maximum run time
#SBATCH --output=scripts/errors/path_count-%j.out       #standard output file
#SBATCH --error=scripts/errors/path_count-%j.err        #standard error file

module load conda/latest
conda activate bcu_graph_analysis

#-u is for unbuffered outputs (outputs as file runs)
python -u src/bcu_analysis/destination_csvs/csv_maker.py \
    /work/pi_plunkett_umass_edu/bcu/final \
    Boston

python -u src/bcu_analysis/destination_csvs/csv_maker.py \
    /work/pi_plunkett_umass_edu/bcu/final \
    Brookline

python -u src/bcu_analysis/destination_csvs/csv_maker.py \
    /work/pi_plunkett_umass_edu/bcu/final \
    Cambridge

python -u src/bcu_analysis/destination_csvs/csv_maker.py \
    /work/pi_plunkett_umass_edu/bcu/final \
    Somerville

python -u src/bcu_analysis/destination_csvs/combining_csvs.py \
    /work/pi_plunkett_umass_edu/bcu/final \
    All