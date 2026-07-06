import json
import os
from pathlib import Path
import requests
import pandas as pd
import osmnx as ox

useragent = {"User-Agent": "bcu-labs"}

dataFolder = "data"
queryFolder = "src/bcu_analysis/graph_builder/query"

overpass_url = "https://overpass.kumi.systems/api/interpreter"

OVERWRITE = False


def build_tag_query(region, key, value):
    global OVERWRITE
    filepath = Path(queryFolder) / (region + ".query")
    filepath.parent.mkdir(exist_ok=True)
    if filepath.exists():
        print(f"{region} query already exists")
    else:
        OVERWRITE = True
        with filepath.open(mode="w") as f:
            f.write("[timeout:1800][out:json];\n")
            f.write(f'area["{key}"="{value}"]->.search_area;\n')
            f.write(".search_area out body;\n")
            f.write("""
(
    way[highway][footway!=sidewalk][service!=parking_aisle](area.search_area);
    way[footway=sidewalk][bicycle][bicycle!=no][bicycle!=dismount](area.search_area);
);
out qt tags;
            """)
        print(f"{filepath} created")


def download_tags(region):
    """

    https://towardsdatascience.com/loading-data-from-openstreetmap-with-python-and-the-overpass-api-513882a27fd0
    """
    global OVERWRITE
    queryFilepath = os.path.join(queryFolder, f"{region}.query")
    dataFilepath = os.path.join(dataFolder, f"{region}_1.json")

    if os.path.exists(dataFilepath) and (OVERWRITE is False):
        print(f"OSM data already downloaded for {region}")
    else:
        OVERWRITE = True
        with open(queryFilepath, "r") as f:
            lines = f.readlines()
        overpass_query = "".join(lines)  # .replace('\n','').replace('  ','')

        print(f"Downloaing OSM map data for {region}...")
        response = requests.get(overpass_url, headers=useragent, params={"data": overpass_query}, timeout=60 * 5)
        response.raise_for_status()  # Raise error if status code not 200
        data = response.json()

        print(f"\tDownloaded OSM map data for {region}")

        with open(dataFilepath, "w") as f:
            json.dump(data, f)
            print(f"Saved {region} map data")


def extract_tags(region):
    """
    Extract OSM tags to use in download
    """
    global OVERWRITE
    # load the data
    wayTagsCSV = os.path.join(dataFolder, f"{region}_2_way_tags.csv")

    if os.path.exists(wayTagsCSV) and (OVERWRITE is False):
        way_tags_series = pd.read_csv(wayTagsCSV, index_col=0)["tag"]
        print(f"Read {wayTagsCSV}")
    else:
        OVERWRITE = True
        print(f"Finding way tags for {region}...")
        with open(os.path.join(dataFolder, f"{region}_1.json"), "r") as f:
            data = json.load(f)

        # make a dataframe of tags
        dfs = []

        for element in data["elements"]:
            if element["type"] != "way":
                continue
            df = pd.DataFrame.from_dict(element["tags"], orient="index")
            dfs.append(df)

        tags_df = pd.concat(dfs).reset_index()
        tags_df.columns = ["tag", "tagvalue"]

        # count all the unique tag and value combinations
        # tag_value_counts = tags_df.value_counts().reset_index()
        # count all the unique tags
        tag_counts = tags_df["tag"].value_counts().reset_index()

        # explore the tags that start with 'cycleway'
        print(f"Cycleway tags:\n{tag_counts[tag_counts['tag'].str.contains('cycleway')]}")

        way_tags_series = tag_counts["tag"]  # all unique tags from the OSM download
        way_tags_series.to_csv(wayTagsCSV)
        print(f"\t{wayTagsCSV} saved.")

    way_tags = list(way_tags_series)

    # add the above list to the global osmnx settings
    ox.settings.useful_tags_way += way_tags
    ox.settings.osm_xml_way_tags = way_tags
    print("Way tags added to osmnx settings.")


def download_graph(region):
    """
    Download data for a given region
    """
    global OVERWRITE
    # create a filter to download selected data
    # this filter is based on osmfilter = ox.downloader._get_osm_filter("bike")
    # keeping the footway and construction tags
    osmfilter = (
        '["highway"]["area"!~"yes"]["access"!~"private"]'
        '["highway"!~"abandoned|bus_guideway|corridor|elevator|escalator|motor|'
        'planned|platform|proposed|raceway|steps"]'
        '["service"!~"private"]'
        '["indoor"!~"yes"]'
        '["service"!="parking_aisle"]'
    )

    # check if data has already been downloaded; if not, download
    filepath = f"{dataFolder}/{region}_3.graphml"
    if os.path.exists(filepath) and (OVERWRITE is False):
        # load graph
        print(f"Loading saved graph for {region}")
        G = ox.load_graphml(filepath)
    else:
        OVERWRITE = True
        print(f"Downloading {region} data (this may take some time)...")
        G = ox.graph_from_place(
            f"{region}, Massachusetts",
            retain_all=True,
            truncate_by_edge=True,
            simplify=False,
            custom_filter=osmfilter,
        )
        print(f"Saving {region} graph")
        ox.save_graphml(G, filepath)

        # plot downloaded graph - this is slow for a large area
        # fig, ax = ox.plot_graph(G, node_size=0, edge_color="w", edge_linewidth=0.2)
        # ox.plot_graph(G, node_size=0, edge_color="w", edge_linewidth=0.2)

    # convert graph to node and edge GeoPandas GeoDataFrames
    gdf_nodes, gdf_edges = ox.graph_to_gdfs(G)

    print(f"{gdf_edges.shape=}")
    print(f"{gdf_nodes.shape=}")

    return gdf_nodes, gdf_edges


if __name__ == "__main__":
    city = ["Boston", "wikipedia", "en:Boston"]
    build_tag_query(*city)
    download_tags(city[0])
    extract_tags(city[0])
    download_graph(city[0])
