import networkx as nx

def metricsGraph(inputPath, inputFile, outputPath, outputFile):

    # Load the directed graph
    print("Loading graph...")
    G = nx.read_graphml(f"{inputPath}{inputFile}")
    print(f"Graph type: {type(G)}")
    print(f"Nodes: {G.number_of_nodes()}")
    print(f"Edges: {G.number_of_edges()}")

    # Calculate attributes for each edge
    min_cutoff = 1 #Will not calculate metrics for edges with a path_count below this value

    print("Calculating metrics (Usage Stress and Potential Direct Benefit of Improvement...)")
    for u, v, data in G.edges(data=True):
        # Get existing attributes
        path_count = float(data.get("path_count", 0))
        cost = float(data.get("cost", 0))
        distance = float(data.get("length", 0))
        # Some max_lts values are an empty string (for those instances, assigning a value of 0)
        max_lts = data.get("max_lts",0)
        if max_lts:
            max_lts = float(max_lts)
        else:
            max_lts = 0

        # If a road is unbikeable, do not consider it
        if max_lts == 0:
            data["usage_stress"] = 0
            data["potential_Dbenefit"] = 0
            continue

        # Calculate usage_stress 
        if path_count >= min_cutoff:
            data["usage_stress"] = path_count * max_lts
        else:
            data["usage_stress"] = 0

        # Calculate potential_Dbenefit
        if path_count >= min_cutoff:
            if cost - distance < 0:
                data["potential_Dbenefit"] = 0
            else:
                data["potential_Dbenefit"] = path_count * (cost - distance)
        else:
            data["potential_Dbenefit"] = 0

    # Save the updated graph
    nx.write_graphml(G, f"{outputPath}{outputFile}")
    print(f"Saved updated graph to: {outputFile}")

if __name__ == '__main__':
    metricsGraph(
        "/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis/", 
        "boston_only_cost_with_pathCount.graphml",
        "/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis/",
        "boston_only_usage.graphml"
    )