#!/bin/bash
#SBATCH --job-name=corridor_analysis    # Job name
#SBATCH -p cpu,cpu-preempt               # Partition (cpu or gpu)
#SBATCH -N 1                             # Number of nodes
#SBATCH -c 1                             # Number of cores
#SBATCH --mem=8G                         # Memory (GB)
#SBATCH --time=1:00:00                   # Maximum run time
#SBATCH --output=scripts/errors/corridors-%j.out
#SBATCH --error=scripts/errors/corridors-%j.err

module load conda/latest
conda activate bcu_graph_analysis

# Directory definitions
GRAPH_DIR="/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis"
POI_DIR="/work/pi_plunkett_umass_edu/bcu/data/processed/osm"
OUTPUT_DIR="/work/pi_plunkett_umass_edu/bcu/final/corridor_analysis"
SCRIPT_PATH="/home/tyuvarajsah_umass_edu/BCU-Graph-Analysis/src/bcu_analysis/corridor_analysis/run_corridors.py"

export PYTHONPATH="/home/tyuvarajsah_umass_edu/BCU-Graph-Analysis/src:$PYTHONPATH"

DS=1
CS=1

# Run individual cities
# python -u "$SCRIPT_PATH" boston \
#     --graph-dir "$GRAPH_DIR" \
#     --poi-dir "$POI_DIR" \
#     --output-dir "$OUTPUT_DIR" \
#     --demand-scenario $DS \
#     --cost-scenario $CS

# python -u "$SCRIPT_PATH" brookline \
#     --graph-dir "$GRAPH_DIR" \
#     --poi-dir "$POI_DIR" \
#     --output-dir "$OUTPUT_DIR" \
#     --demand-scenario $DS \
#     --cost-scenario $CS

# python -u "$SCRIPT_PATH" cambridge \
#     --graph-dir "$GRAPH_DIR" \
#     --poi-dir "$POI_DIR" \
#     --output-dir "$OUTPUT_DIR" \
#     --demand-scenario $DS \
#     --cost-scenario $CS

# python -u "$SCRIPT_PATH" somerville \
#     --graph-dir "$GRAPH_DIR" \
#     --poi-dir "$POI_DIR" \
#     --output-dir "$OUTPUT_DIR" \
#     --demand-scenario $DS \
#     --cost-scenario $CS

# Run combined 4-city region
python -u "$SCRIPT_PATH" greater_boston \
    --graph-dir "$GRAPH_DIR" \
    --poi-dir "$POI_DIR" \
    --output-dir "$OUTPUT_DIR" \
    --demand-scenario $DS \
    --cost-scenario $CS
