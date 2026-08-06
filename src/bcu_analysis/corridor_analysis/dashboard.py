import streamlit as st
from pathlib import Path
from corridor_analysis import core_algorithms as core
from corridor_analysis import export_utils as export

st.set_page_config(page_title="Boston Cyclists Union - Network Islands", page_icon="🚲", layout="wide")

st.title("🚲 Low-Stress Network Islands & Missing Link Corridors")
st.markdown("This view isolates connected **LTS 1 & 2 safe zones**. Solid paths are algorithmically generated **Missing Link Corridors**.")

# Parameters
st.sidebar.header("Parameters")
min_island_size = st.sidebar.slider("Minimum Island Size (edges)", min_value=5, max_value=200, value=20, step=5)
max_islands = st.sidebar.slider("Top Islands to Display", min_value=2, max_value=30, value=15, step=1)
show_missing_links = st.sidebar.checkbox("Show Proposed Missing Links", value=True)
link_complexity = st.sidebar.slider("Corridor Bridging Depth", min_value=1, max_value=15, value=10, step=1)

DATA_DIR = Path("data") 
GRAPH_PATH = DATA_DIR / "boston_only_usage.graphml"

with st.spinner("Processing network topology and missing links..."):
    G = core.load_graph(GRAPH_PATH)
    
    G_safe, top_islands, node_to_island = core.process_islands(G, min_island_size, max_islands)
    proposed_corridors, missing_edges = core.compute_missing_links(G, top_islands, link_complexity)
    
    deck = export.build_pydeck_map(G, node_to_island, proposed_corridors, missing_edges, show_missing_links)

    if show_missing_links and proposed_corridors:
        st.sidebar.markdown("---")
        st.sidebar.header("Top Priority Links")
        for rank, corridor in enumerate(proposed_corridors[:3]):
            st.sidebar.metric(label=f"#{rank + 1} - {corridor['id']}", value=f"{corridor['score']:,.0f} pts")

    base_size, upgraded_size, percentage_increase = core.calculate_roi(G_safe, G, missing_edges)
    
    st.sidebar.markdown("---")
    st.sidebar.header("Infrastructure ROI")
    st.sidebar.metric(label="Safe Network Expansion (Nodes)", value=f"{upgraded_size:,}", delta=f"+{percentage_increase:.1f}% Increase")

    st.pydeck_chart(deck, use_container_width=True)