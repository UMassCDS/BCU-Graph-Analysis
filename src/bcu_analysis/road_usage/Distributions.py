import networkx as nx
import pandas as pd

def distributions(graphPath, graphFile, graphName, outputPath, path_count, distance, max_lts, cost, usage_stress, potential_Dbenefit):
    graph_path = graphPath
    graph_file = graphFile
    graph_name = graphName
    output_path = outputPath
    print("Loading graph...")
    G = nx.read_graphml(f"{graph_path}{graph_file}")

    # Extract edge attributes into a list of dictionaries
    print("Extracting edge attributes...")
    edge_attributes = []
    for u, v, data in G.edges(data=True):
        edge_attributes.append({
            'osmid': data.get('osmid'), #Unique id for each edge
            'usage_stress': data.get('usage_stress'), #path_count*max_lts
            'potential_Dbenefit': data.get('potential_Dbenefit'), #path_count*(cost-distance)
            'path_count' : data.get('path_count'), #number of least-cost paths that cross through the edge
            'distance': data.get('length'), #The length/distance of an edge
            'max_lts': data.get('max_lts'), #The highest stress level present on the edge
            'cost' : data.get('cost') #sum(LTScoefficient*distance) for all smaller segments that make up an edge
        })

    #Convert to a Pandas DataFrame
    df = pd.DataFrame(edge_attributes)
    df.to_csv(f'{output_path}{graph_name}.csv', index=False)

    print(f"For {graph_file}...")
    if path_count:
        df['path_count'] = pd.to_numeric(df['path_count'], errors='coerce')
        df_path_count = df[df['path_count']!=0]
        print("=== USAGE SUMMARY STATISTICS ===")
        print(df_path_count['path_count'].describe())
        print("\n" + "="*40 + "\n")
    if distance:
        df['distance'] = pd.to_numeric(df['distance'], errors='coerce')
        df_distance = df[df['distance']!=0]
        print("=== DISTANCE SUMMARY STATISTICS ===")
        print(df_distance['distance'].describe())
        print("\n" + "="*40 + "\n")
    if max_lts:
        df['max_lts'] = pd.to_numeric(df['max_lts'], errors='coerce')
        df_max_lts = df[df['max_lts']!=0]
        print("=== MAX LTS STATISTICS ===")
        print(df_max_lts['max_lts'].describe())
        print("\n" + "="*40 + "\n")
    if cost:
        df['cost'] = pd.to_numeric(df['cost'], errors='coerce')
        df_cost = df[df['cost']!=0]
        print("=== COST SUMMARY STATISTICS ===")
        print(df_cost['cost'].describe())
        print("\n" + "="*40 + "\n")
    if usage_stress:
        df['usage_stress'] = pd.to_numeric(df['usage_stress'], errors='coerce')
        df_usage_stress = df[df['usage_stress']!=0]
        print("=== USAGE STRESS SUMMARY STATISTICS ===")
        print(df_usage_stress['usage_stress'].describe())
        print("\n" + "="*40 + "\n")
    if potential_Dbenefit:
        df['potential_Dbenefit'] = pd.to_numeric(df['potential_Dbenefit'], errors='coerce')
        df_potential = df[df['potential_Dbenefit']!=0]
        print("=== POTENTIAL DBENFIT SUMMARY STATISTICS ===")
        print(df_potential['potential_Dbenefit'].describe())

def main(graphPath, graphFile, graphName, outputPath, path_count=True, distance=True, max_lts=True, cost=True, usage_stress=True, potential_Dbenefit=True):
    distributions(graphPath, graphFile, graphName, outputPath, path_count, distance, max_lts, cost, usage_stress, potential_Dbenefit)

if __name__ == '__main__':
    main("/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis/",
         "boston_only_usage.graphml", 
         "boston_only_usage", 
         "/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis/CostAnalysis/"
        )
    #main("/work/pi_plunkett_umass_edu/bcu/data/processed/osm/", 
    #     "boston_only_cost.graphml", 
    #     "boston_only_cost",
    #     "/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis/CostAnalysis/",
    #     False, True, False, True, False, False
    #    )
    #main("/work/pi_plunkett_umass_edu/bcu/data/processed/osm/", 
    #     "boston_only_cost_simplified.graphml", 
    #     "boston_only_cost_simplified",
    #     "/work/pi_plunkett_umass_edu/bcu/data/processed/road_usage_analysis/CostAnalysis/",
    #     False, True, True, True, False, False)