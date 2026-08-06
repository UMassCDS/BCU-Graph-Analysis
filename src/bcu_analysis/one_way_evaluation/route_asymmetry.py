"""
Route-asymmetry (contra-flow) analysis.

For every origin-destination (OD) pair we route both the forward trip (O->D) and
the reverse trip (D->O) on the directed LTS cost graph, and measure how asymmetric
the two costs are. On a two-way street the two routes are ~symmetric; where a
one-way restriction forces the reverse trip onto a long detour, the reverse cost is
much larger. That asymmetry is accumulated onto the *cheaper* route, so summing
across all trips highlights the corridors where a contra-flow bike lane would most
improve accessibility.

The asymmetry of a single trip is measured as a ratio::

    ratio = max(cost_fwd, cost_rev) / min(cost_fwd, cost_rev)

and each trip contributes ``ratio - ASYMMETRY_BASELINE`` to its cheaper-path
segments, so a perfectly symmetric trip (ratio == 1) contributes nothing and the
score reflects asymmetry rather than raw traffic volume.

Blame is restricted to the segments the *other* direction's route could not reuse.
Two-way segments are dropped outright -- they carry both directions already, so a
contra-flow lane there would change nothing -- as are one-way segments whose
street the more expensive route did use anyway. "Same street" is decided from edge
attributes rather than graph topology (see street_identity.py), which is what lets
the two carriageways of a divided road count as one street even though they are
disjoint one-way edges. Every cheaper-path segment still counts towards
``trip_count``; only the unshared one-way ones accumulate ``asymmetry`` and
``blame_count``.
"""

import multiprocessing
import time

import geopandas as gpd
import networkx as nx
import osmnx as ox
import pandas as pd
from shapely.geometry import LineString

from bcu_analysis.one_way_evaluation.street_identity import (
    build_carriageway_pairs,
    unshared_edges,
)

# Score columns read back from the CSV. max_lts and length come from the CSV rather
# than the graph so the join can't collide on a duplicate column name.
_SCORE_COLUMNS = [
    "u",
    "v",
    "key",
    "asymmetry",
    "asymmetry_norm",
    "trip_count",
    "blame_count",
    "max_lts",
    "length",
]

# OSM tags carried through to the edge GeoDataFrame. Deliberately short: the graph
# holds several hundred tag columns and materialising all of them (as
# ox.graph_to_gdfs does) exhausts memory on a graph this size.
_EDGE_TAGS = ("name", "highway", "oneway", "osmid")

# A trip contributes (ratio - ASYMMETRY_BASELINE) to its cheaper-path segments.
# With the baseline at 1.0 a perfectly symmetric trip (ratio == 1) contributes 0,
# so the accumulated score measures asymmetry, not traffic volume. Set to 0.0 to
# accumulate the raw ratio instead.
ASYMMETRY_BASELINE = 1.0

# How often to print routing progress (in OD pairs).
PROGRESS_EVERY = 500


def load_cost_graph(path):
    """
    Load the simplified LTS cost graph.

    ``cost`` is a custom edge attribute, so it must be coerced to float on load or
    osmnx returns it as a string (see graph_builder/assign_cost.py).
    """
    return ox.load_graphml(path, edge_dtypes={"cost": float})


def route_cost(G, orig, dest):
    """
    Shortest-path cost and node path from ``orig`` to ``dest`` on edge ``cost``.

    Returns (cost, node_path), or (None, None) if either node is missing from the
    graph or no path exists.
    """
    try:
        cost, node_path = nx.single_source_dijkstra(G, orig, dest, weight="cost")
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None, None
    return cost, node_path


def path_edge_keys(G, node_path):
    """
    Convert a node path into (u, v, key) edge tuples.

    For each hop the min-cost parallel edge is chosen so the accumulated segments
    match the edges Dijkstra actually traversed.
    """
    edges = []
    for u, v in zip(node_path[:-1], node_path[1:]):
        parallel = G[u][v]
        key = min(parallel, key=lambda k: parallel[k].get("cost", float("inf")))
        edges.append((u, v, key))
    return edges


def score_pair(G, origin, dest, baseline=ASYMMETRY_BASELINE, counterparts=None):
    """
    Route ``origin``<->``dest`` both ways and return the cheaper route's segments
    and their asymmetry contribution.

    Returns (cheap_edges, blamed_edges, score), where cheap_edges is every
    (u, v, key) tuple on the cheaper route and blamed_edges is the one-way subset
    whose street the more expensive route did not also use (see
    ``street_identity.unshared_edges``). Returns ``None`` if the pair is
    unreachable in either direction (or a zero-cost route makes the ratio
    undefined).

    ``counterparts`` is the divided-road pairing from
    ``street_identity.build_carriageway_pairs``; without it the two carriageways of
    a divided road are treated as separate streets.
    """
    cost_fwd, path_fwd = route_cost(G, origin, dest)
    cost_rev, path_rev = route_cost(G, dest, origin)
    if cost_fwd is None or cost_rev is None or min(cost_fwd, cost_rev) <= 0:
        return None

    ratio = max(cost_fwd, cost_rev) / min(cost_fwd, cost_rev)
    score = ratio - baseline
    if cost_fwd <= cost_rev:
        cheaper_path, other_path = path_fwd, path_rev
    else:
        cheaper_path, other_path = path_rev, path_fwd

    cheap_edges = path_edge_keys(G, cheaper_path)
    other_edges = path_edge_keys(G, other_path)
    blamed = unshared_edges(G, cheap_edges, other_edges, counterparts)
    return cheap_edges, blamed, score


# Set in each worker (via fork inheritance) so routing can read the shared graph
# without pickling it across the process boundary.
_WORKER_GRAPH = None
_WORKER_BASELINE = ASYMMETRY_BASELINE
_WORKER_COUNTERPARTS = None


def _route_pair_worker(pair):
    """Worker entry point: score one (origin, dest) pair using the shared graph."""
    origin, dest = pair
    return score_pair(_WORKER_GRAPH, origin, dest, _WORKER_BASELINE, _WORKER_COUNTERPARTS)


def _route_pairs(G, pairs, baseline, workers, counterparts=None):
    """
    Yield ``score_pair`` results for every pair, in parallel when ``workers > 1``.

    Parallelism uses a forking process pool: the graph is loaded once in the parent
    and inherited copy-on-write by the workers (routing only reads it), so the
    197 MB graph is never pickled across processes.
    """
    if not workers or workers <= 1:
        for origin, dest in pairs:
            yield score_pair(G, origin, dest, baseline, counterparts)
        return

    global _WORKER_GRAPH, _WORKER_BASELINE, _WORKER_COUNTERPARTS
    _WORKER_GRAPH = G
    _WORKER_BASELINE = baseline
    _WORKER_COUNTERPARTS = counterparts
    chunksize = max(1, len(pairs) // (workers * 8))
    ctx = multiprocessing.get_context("fork")
    try:
        with ctx.Pool(processes=workers) as pool:
            yield from pool.imap_unordered(_route_pair_worker, pairs, chunksize=chunksize)
    finally:
        _WORKER_GRAPH = None
        _WORKER_COUNTERPARTS = None


def accumulate_asymmetry(G, od_df, baseline=ASYMMETRY_BASELINE, workers=1):
    """
    Accumulate per-trip route asymmetry onto the segments of the cheaper route.

    Only the cheaper route's *unshared* segments are blamed: two-way segments, and
    segments whose street the more expensive route also used, carry both directions
    of travel already. ``trip_count`` still counts every cheaper-route traversal, so
    shared segments end up with trips but no asymmetry.

    Parameters:
    - G (nx.MultiDiGraph): the directed LTS cost graph (mutated in place).
    - od_df (pd.DataFrame): OD pairs with columns origin_node, destination_node.
      Duplicate pairs (across categories) are routed only once; the ``count``
      column, if present, is ignored.
    - baseline (float): subtracted from each trip's ratio before accumulation.
    - workers (int): number of routing processes. 1 = serial; >1 forks a process
      pool that shares the graph copy-on-write. Accumulation stays in the parent,
      so results are identical regardless of worker count.

    Returns:
    - nx.MultiDiGraph: G with per-edge ``asymmetry`` (float), ``trip_count`` (int),
      ``blame_count`` (int), and ``asymmetry_norm`` (float in [0, 1]) attributes.
    """
    for _, _, data in G.edges(data=True):
        data["asymmetry"] = 0.0
        data["trip_count"] = 0
        data["blame_count"] = 0

    pair_start = time.perf_counter()
    counterparts = build_carriageway_pairs(G)
    print(
        f"Paired opposing carriageways for {len(counterparts)} one-way edges "
        f"in {time.perf_counter() - pair_start:.1f}s",
        flush=True,
    )

    pairs = od_df[["origin_node", "destination_node"]].drop_duplicates()
    pairs = pairs[pairs["origin_node"] != pairs["destination_node"]]
    pairs = list(pairs.itertuples(index=False, name=None))

    total = len(pairs)
    print(f"Routing {total} unique OD pairs (both directions) on {workers} worker(s)...", flush=True)

    processed = 0
    skipped = 0
    start = time.perf_counter()
    for i, result in enumerate(_route_pairs(G, pairs, baseline, workers, counterparts), start=1):
        if result is None:
            skipped += 1
        else:
            cheap_edges, blamed_edges, score = result
            for u, v, k in cheap_edges:
                G[u][v][k]["trip_count"] += 1
            for u, v, k in blamed_edges:
                edge = G[u][v][k]
                edge["asymmetry"] += score
                edge["blame_count"] += 1
            processed += 1

        if i % PROGRESS_EVERY == 0 or i == total:
            elapsed = time.perf_counter() - start
            rate = i / elapsed if elapsed else 0.0
            eta = (total - i) / rate if rate else 0.0
            print(f"  {i}/{total} pairs ({rate:.1f}/s) | {elapsed:.1f}s elapsed | ETA {eta:.0f}s", flush=True)

    _normalize_asymmetry(G)

    elapsed = time.perf_counter() - start
    print(
        f"Route asymmetry: {processed} pairs scored, {skipped} skipped (unreachable) in {elapsed:.1f}s",
        flush=True,
    )
    return G


def _normalize_asymmetry(G):
    """Add an ``asymmetry_norm`` in [0, 1] (min-max) for map coloring."""
    scores = [data.get("asymmetry", 0.0) for _, _, data in G.edges(data=True)]
    hi = max(scores) if scores else 0.0
    for _, _, data in G.edges(data=True):
        data["asymmetry_norm"] = (data.get("asymmetry", 0.0) / hi) if hi > 0 else 0.0


def asymmetry_edges_df(G):
    """
    Return a lean per-edge DataFrame of asymmetry scores keyed by (u, v, key).

    No geometry is included — join back to the graph on (u, v, key) to recover
    edge geometry for plotting. Columns: u, v, key, asymmetry, asymmetry_norm,
    trip_count, blame_count, max_lts, length.
    """
    rows = [
        {
            "u": u,
            "v": v,
            "key": k,
            "asymmetry": data.get("asymmetry", 0.0),
            "asymmetry_norm": data.get("asymmetry_norm", 0.0),
            "trip_count": data.get("trip_count", 0),
            "blame_count": data.get("blame_count", 0),
            "max_lts": data.get("max_lts", ""),
            "length": data.get("length", ""),
        }
        for u, v, k, data in G.edges(keys=True, data=True)
    ]
    return pd.DataFrame(rows)


def load_edges_with_asymmetry(graph_path, csv_path):
    """
    Load the cost graph as an edge GeoDataFrame joined to per-edge asymmetry scores.

    ``asymmetry_edges_df`` writes scores without geometry, so anything that maps or
    ranks them has to join back to the graph; this is that join, shared by
    plot_route_asymmetry.py and top_asymmetric_segments.py.

    The GeoDataFrame is assembled by hand rather than with ``ox.graph_to_gdfs``, which
    materialises every OSM tag column in the graph (several hundred) and exhausts
    memory at this scale. Only the tags in ``_EDGE_TAGS`` are carried through.

    Parameters:
    - graph_path (str): the graph the scores were computed on -- the (u, v, key)
      tuples in the CSV only mean anything against that same graph.
    - csv_path (str): per-edge scores written by ``run_route_asymmetry.py``.

    Returns:
    - gpd.GeoDataFrame: indexed by (u, v, key), projected to the local UTM zone so
      distances and aspect ratio are in metres. Edges absent from the CSV score 0.0.
    """
    print(f"Loading cost graph from {graph_path}")
    G = load_cost_graph(graph_path)

    print(f"Building edge GeoDataFrame for {G.number_of_edges()} edges...")
    coords = {node: (data["x"], data["y"]) for node, data in G.nodes(data=True)}
    columns = {key: [] for key in ("u", "v", "key", *_EDGE_TAGS)}
    geometries = []
    for u, v, k, data in G.edges(keys=True, data=True):
        columns["u"].append(u)
        columns["v"].append(v)
        columns["key"].append(k)
        for tag in _EDGE_TAGS:
            columns[tag].append(data.get(tag))

        # osmnx only attaches a geometry where an edge is not a straight line between
        # its nodes, so fall back to that straight line.
        geometry = data.get("geometry")
        if geometry is None:
            geometry = LineString([coords[u], coords[v]])
        geometries.append(geometry)

    edges = gpd.GeoDataFrame(columns, geometry=geometries, crs="EPSG:4326")
    edges = edges.set_index(["u", "v", "key"])

    print(f"Loading asymmetry scores from {csv_path}")
    scores = pd.read_csv(csv_path, usecols=_SCORE_COLUMNS).set_index(["u", "v", "key"])

    edges = edges.join(scores)
    for column in ("asymmetry", "asymmetry_norm"):
        edges[column] = edges[column].fillna(0.0)
    for column in ("trip_count", "blame_count"):
        edges[column] = edges[column].fillna(0).astype(int)

    # Project to metres so the plotted aspect ratio is real distance, not degrees.
    return edges.to_crs(edges.estimate_utm_crs())
