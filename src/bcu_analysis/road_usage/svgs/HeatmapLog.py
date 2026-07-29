import networkx as nx
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
import numpy as np

def loadgraph(GraphPath='/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis/', Graph_File="boston_only_usage.graphml"):
    graphPath = GraphPath
    graph_file = Graph_File

    print("Loading graph...")
    G = nx.read_graphml(f"{graphPath}{graph_file}")
    print(f"Nodes: {G.number_of_nodes():,}")
    print(f"Edges: {G.number_of_edges():,}")

    return G





def categorizingEdges(G, attributeToGraph, lowerThreshold, upperThreshold, filter):
    zero_lines = []
    low_lines = []
    positive_lines = []
    positive_values = []
    high_lines = []

    # Logarithmic thresholds (Adjust these values based on data distribution)
    # NOTE: Log scales require values strictly greater than 0. 
    lower_threshold = lowerThreshold 
    upper_threshold = upperThreshold

    print("Categorizing road segments...")
    for u, v, data in G.edges(data=True):
        if "geometry" in data:
            geom = data["geometry"]
            if isinstance(geom, str):
                from shapely.wkt import loads
                geom = loads(geom)
            line = list(geom.coords)
        else:
            x1, y1 = float(G.nodes[u]["x"]), float(G.nodes[u]["y"])
            x2, y2 = float(G.nodes[v]["x"]), float(G.nodes[v]["y"])
            line = [(x1, y1), (x2, y2)]
    
        # Extract attribute (defaulting to 0 if missing)
        attribute = float(data.get(f"{attributeToGraph}", 0))
        # Some max_lts values are an empty string (for those instances, assigning a value of 0)
        max_lts = data.get("max_lts",0)
        if max_lts:
            max_lts = float(max_lts)
        else:
            max_lts = 0

        if filter:
            if max_lts < 3:
                # If the max lts is below a 3, we should not consider it when looking for roads to improve 
                zero_lines.append(line)
                continue
        if attribute < lower_threshold:
            if lower_threshold > 1:
                if attribute <= 0.001:
                    zero_lines.append(line)
                else:
                    low_lines.append(line)
            else:
                zero_lines.append(line)
        elif attribute <= upper_threshold:
            positive_lines.append(line)
            positive_values.append(attribute)
        else:
            high_lines.append(line)

    positive_values = np.array(positive_values)

    return [zero_lines, low_lines, positive_lines, positive_values, high_lines]





def generateImage(G, edges, attributeName, lowerThreshold, upperThreshold, OutputPath, outputName):

    outputPath = OutputPath

    zero_lines = edges[0]
    low_lines = edges[1]
    positive_lines = edges[2]
    positive_values = edges[3]
    high_lines = edges[4]

    print("Generating visualization...")
    fig, ax = plt.subplots(figsize=(14, 14))

    # Road segments ~= 0
    if len(zero_lines) > 0:
        zero_lc = LineCollection(
            zero_lines, colors="lightgray", linewidths=0.5, alpha=0.7
        )
        ax.add_collection(zero_lc)

    # Roads under the lowest threshold 
    if len(low_lines) > 0:
        low_lc = LineCollection(
            low_lines, colors="yellow", linewidths=0.5, alpha=0.7
        )
        ax.add_collection(low_lc)

    # Low <= road segemnts <= High (log-scale)
    if len(positive_lines) > 0:
        # Use LogNorm for logarithmic scaling
        norm = mpl.colors.LogNorm(
            vmin=lowerThreshold, vmax=upperThreshold
        )
        cmap = plt.cm.viridis_r
    
        positive_lc = LineCollection(
            positive_lines, cmap=cmap, norm=norm, linewidths=0.6, alpha=0.9
        )
        positive_lc.set_array(positive_values)
        ax.add_collection(positive_lc)

        # Add logarithmic colorbar
        cbar = fig.colorbar(positive_lc, ax=ax, shrink=0.4)
        cbar.set_label(
            f"{attributeName} ({lowerThreshold} ≤ {attributeName} ≤ {upperThreshold}) [Log Scale]", 
            fontsize=9
        )

    # Road segments above the upper threshold 
    if len(high_lines) > 0:
        high_lc = LineCollection(
            high_lines, colors="red", linewidths=0.6, alpha=0.9
        )
        ax.add_collection(high_lc)

    # Map extent
    all_x = [float(data["x"]) for node, data in G.nodes(data=True)]
    all_y = [float(data["y"]) for node, data in G.nodes(data=True)]
    ax.set_xlim(min(all_x), max(all_x))
    ax.set_ylim(min(all_y), max(all_y))

    # Lables
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    # Title should be Greater Boston, but using just Boston for now 
    ax.set_title(f"Boston Street Network by {attributeName}", fontsize=16)
    ax.set_aspect("equal")

    legend_handles = []
    if len(zero_lines) > 0:
        legend_handles.append(
            Line2D([], [], color="lightgray", lw=1.5, alpha=0.7, label=f"{attributeName} ~= 0")
        )
    if len(low_lines) > 0:
        legend_handles.append(
            Line2D([], [], color="yellow", lw=1.5, alpha=0.7, label=f"{attributeName} < {lowerThreshold}")
        )
    if len(high_lines) > 0:
        legend_handles.append(
            Line2D([], [], color="red", lw=1.5, alpha=0.9, label=f"{attributeName} > {upperThreshold}")
        )
    if legend_handles:
        ax.legend(handles=legend_handles, loc="upper right")

    # Saving Figure
    print("Saving visualization...")
    plt.tight_layout()
    plt.savefig(
        f"{outputPath}{outputName}.svg", dpi=300, bbox_inches="tight", format="svg"
    )
    print(f"Completed Figure for {attributeName}!")





def main(GraphPath, Graph_File, attributeName, attributeToGraph, lowerThreshold, upperThreshold, filter, outputPath, outputName):
    G = loadgraph(GraphPath, Graph_File)
    edges = categorizingEdges(G, attributeToGraph, lowerThreshold, upperThreshold, filter)
    generateImage(G, edges, attributeName, lowerThreshold, upperThreshold, outputPath, outputName)

if __name__ == '__main__':
    # For Usage Stress
    main(
        '/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis/',
        "boston_only_usage.graphml",
        "Usage Stress",
        'usage_stress',
        1,
        1000,
        True,
        '/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis/PresentedToClient/',
        "boston_only_heatmap_UsageStressLog"
    )
    main(
        '/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis/',
        "boston_only_usage.graphml",
        "Usage Stress",
        'usage_stress',
        1,
        1000,
        False,
        '/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis/PresentedToClient/',
        "boston_only_heatmap_UsageStressLogUnfiltered"
    )
    # For Potential Improvement 
    main(
        '/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis/',
        "boston_only_usage.graphml",
        "Potential Improvement",
        'potential_Dbenefit',
        100,
        50000,
        True,
        '/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis/PresentedToClient/',
        "boston_only_heatmap_PotentialImprovementLog"
    )
    main(
        '/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis/',
        "boston_only_usage.graphml",
        "Potential Improvement",
        'potential_Dbenefit',
        100,
        50000,
        False,
        '/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis/PresentedToClient/',
        "boston_only_heatmap_PotentialImprovementLogUnfiltered"
    )
    # For Demand 
    main(
        '/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis/',
        "boston_only_usage.graphml",
        "Usage",
        'path_count',
        1,
        500,
        False,
        '/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis/PresentedToClient/',
        "boston_only_heatmap_UsageLog"
    )