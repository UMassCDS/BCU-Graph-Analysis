import osm_download
import assign_cost

# Cities combined into a single graph. Each entry is
# (place_name, area_key, area_value): place_name is geocoded by
# graph_from_place, while (area_key, area_value) selects the Overpass area
# used to gather the set of useful OSM way tags.
cities = [
    ('Boston, Massachusetts', 'wikipedia', 'en:Boston'),
    ('Cambridge, Massachusetts', 'wikipedia', 'en:Cambridge, Massachusetts'),
    ('Somerville, Massachusetts', 'wikipedia', 'en:Somerville, Massachusetts'),
    ('Brookline, Massachusetts', 'wikipedia', 'en:Brookline, Massachusetts'),
]

# Filename prefix for the combined region's output files.
region = 'greater_boston'


if __name__=="__main__":
    places = [name for name, _, _ in cities]
    osm_download.build_tag_query(region, cities)
    osm_download.download_tags(region)
    osm_download.extract_tags(region)
    gdfNodes, gdfEdges=osm_download.download_graph(region, places)
    assign_cost.lts_edges(region, gdfEdges)
    assign_cost.build_cost_graph(region)
    assign_cost.simplify_cost_graph(region)