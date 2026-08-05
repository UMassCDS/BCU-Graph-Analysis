"""
Street identity from edge attributes, for deciding whether two routes used the
"same street".

Route asymmetry only wants to blame the segments the reverse trip *could not*
reuse, so it has to ask "does this edge actually restrict the other direction?".
Graph-edge identity alone cannot answer that:

- A two-way street is two reciprocal edges, ``(u, v, k)`` and ``(v, u, k')``, and
  is never a restriction -- so ``unshared_edges`` drops every edge with a
  reciprocal outright.
- A divided road (dual carriageway) is mapped in OSM as two *separate* one-way
  ways on distinct nodes, split at different places, so the two directions of
  travel are different edges that share nothing topologically -- only their
  ``name`` and their geometry say they are one street. Left unpaired, each side
  looks like a one-way restriction. Once paired, it is dropped on the same
  existence test as a reciprocal: the road carries both directions, one per side.

``build_carriageway_pairs`` handles the second case by pairing one-way edges that
carry the opposite direction of the same named street, and ``unshared_edges``
applies all the identity rules to one trip's pair of routes.
"""

import geopandas as gpd
from osmnx.bearing import calculate_bearing
from shapely.geometry import LineString, Point

# How far apart two carriageways of the same road may run, in metres. Boston's
# widest divided roads (Commonwealth Avenue's streetcar reservation) need ~60 m;
# below that they stop pairing, and above it the pairing count flattens out.
CARRIAGEWAY_MAX_OFFSET_M = 60.0

# Minimum bearing difference (degrees) for two edges to count as carrying
# opposite directions of the same street. 180 is perfectly anti-parallel.
CARRIAGEWAY_MIN_BEARING_DIFF = 135.0

# Fraction of the shorter edge that must run alongside the other one. Without
# this, two ends of the same street meeting at an intersection would pair.
CARRIAGEWAY_MIN_OVERLAP_FRAC = 0.5


def _as_tuple(value):
    """OSM tags survive simplification as either a scalar or a list; yield both flat."""
    if value is None:
        return ()
    if isinstance(value, (list, tuple, set, frozenset)):
        return tuple(value)
    return (value,)


def edge_names(data):
    """
    Normalised street names on an edge, as a frozenset (empty when unnamed).

    A merged edge can carry several names (e.g. ``['Cambridge Street',
    'Washington Street']``), and any one of them is enough to identify the street.
    """
    names = set()
    for name in _as_tuple(data.get("name")):
        text = str(name).strip().lower()
        if text:
            names.add(text)
    return frozenset(names)


def edge_osmids(data):
    """
    Every OSM way id on an edge, as a frozenset of strings.

    Simplified edges carry a list of the ways they merged, so two edges sharing
    any id came (at least partly) from the same OSM way.
    """
    return frozenset(str(osmid) for osmid in _as_tuple(data.get("osmid")))


def _carriageway_candidates(G):
    """
    Named one-way edges, with the geometry and bearing needed to pair them up.

    Edges with a reciprocal edge are skipped: a two-way street already carries
    both directions, so it can't need a counterpart carriageway.

    Returns a list of (edge_key, names, geometry, bearing) tuples, where geometry
    is in WGS84.
    """
    coords = {n: (data["y"], data["x"]) for n, data in G.nodes(data=True)}
    candidates = []
    for u, v, k, data in G.edges(keys=True, data=True):
        if G.has_edge(v, u):
            continue
        names = edge_names(data)
        if not names:
            continue

        # osmnx only attaches a geometry where an edge is not a straight line
        # between its nodes, so fall back to that straight line.
        geometry = data.get("geometry")
        if geometry is None:
            geometry = LineString([(coords[u][1], coords[u][0]), (coords[v][1], coords[v][0])])

        (lat1, lon1), (lat2, lon2) = coords[u], coords[v]
        candidates.append(
            ((u, v, k), names, geometry, calculate_bearing(lat1, lon1, lat2, lon2))
        )
    return candidates


def _runs_alongside(short, long_, long_buffer, min_overlap_frac):
    """
    Whether the shorter of two lines runs *beside* the longer one, not into it.

    Two conditions, both as a fraction of the shorter line's own length:

    - How much of it lies within the longer line's offset buffer. This is the
      "are they close" test, and it is measured on the shorter line so the result
      is a true fraction. (Buffering the shorter line and measuring the longer one
      inside it does not work: a 10 m fragment's 60 m buffer is a 130 m blob that
      swallows an arbitrary length of the other line, so the ratio can exceed 1 and
      the test passes for anything nearby.)
    - How far apart its two endpoints land when projected onto the longer line.
      This is the "beside, not end-to-end" test. Consecutive blocks of one street
      that alternate one-way direction are collinear and anti-parallel and sit well
      inside each other's buffer, so proximity alone pairs them; but both of their
      endpoints project onto (nearly) the same station of the other block, because
      they extend past its end and clamp there. A carriageway running alongside
      instead spans roughly its own length. The same test rejects two arms of the
      same street meeting at a corner.

    Parameters:
    - short (LineString): the shorter of the two lines, in a projected CRS.
    - long_ (LineString): the longer line.
    - long_buffer (Polygon): ``long_`` buffered by the max offset.
    - min_overlap_frac (float): threshold both fractions must meet.

    Returns:
    - bool
    """
    if short.length <= 0:
        return False
    if short.intersection(long_buffer).length < min_overlap_frac * short.length:
        return False
    start = long_.project(Point(short.coords[0]))
    end = long_.project(Point(short.coords[-1]))
    return abs(end - start) >= min_overlap_frac * short.length


def build_carriageway_pairs(
    G,
    max_offset_m=CARRIAGEWAY_MAX_OFFSET_M,
    min_bearing_diff=CARRIAGEWAY_MIN_BEARING_DIFF,
    min_overlap_frac=CARRIAGEWAY_MIN_OVERLAP_FRAC,
):
    """
    Pair up the opposing carriageways of divided roads.

    Two named one-way edges are paired when they share a name, their bearings
    differ by at least ``min_bearing_diff`` (they carry opposite directions), and
    they run alongside each other -- within ``max_offset_m``, and side by side
    rather than end to end -- for at least ``min_overlap_frac`` of the shorter
    edge (see ``_runs_alongside``).

    The test is deliberately geometric rather than node-based. The two sides of a
    divided road are separate OSM ways on separate nodes, and they are rarely
    split at the same places -- a median crossover or slip lane can split one side
    into several segments while the other side stays whole -- so any rule that
    matches endpoints to endpoints misses those roads entirely. Matching on how
    the geometries run alongside each other handles mismatched splits: a short
    sub-segment still overlaps most of its own length against the long edge
    opposite it.

    Parameters:
    - G (nx.MultiDiGraph): graph with ``x``/``y`` node coordinates in WGS84.
    - max_offset_m (float): how far apart the two carriageways may run, in metres.
    - min_bearing_diff (float): min bearing difference, in degrees.
    - min_overlap_frac (float): share of the shorter edge that must run alongside
      the other one, both in proximity and in projected span.

    Returns:
    - dict: symmetric adjacency, ``(u, v, key) -> frozenset of (u, v, key)``.
      Edges with no counterpart are absent.
    """
    candidates = _carriageway_candidates(G)
    if not candidates:
        return {}

    # Project to metres so the offset and overlap thresholds are real distances.
    # Built by hand rather than with ox.graph_to_gdfs, which would materialise the
    # graph's several hundred OSM tag columns for every edge.
    gdf = gpd.GeoDataFrame(
        {"i": range(len(candidates))},
        geometry=[c[2] for c in candidates],
        crs="EPSG:4326",
    )
    gdf = gdf.to_crs(gdf.estimate_utm_crs())
    buffers = gdf.buffer(max_offset_m)
    geometries = gdf.geometry.tolist()

    # Spatial join gives the shortlist of edges close enough to be carriageways of
    # one road; the attribute and overlap tests below whittle it down.
    nearby = gpd.sjoin(
        gpd.GeoDataFrame({"i": gdf["i"]}, geometry=buffers, crs=gdf.crs),
        gpd.GeoDataFrame({"j": gdf["i"]}, geometry=gdf.geometry, crs=gdf.crs),
        how="inner",
        predicate="intersects",
    )

    pairs = {}
    for i, j in zip(nearby["i"].tolist(), nearby["j"].tolist()):
        if i >= j:  # each unordered pair once, and never an edge against itself
            continue
        if not (candidates[i][1] & candidates[j][1]):
            continue
        delta = abs((candidates[i][3] - candidates[j][3] + 180.0) % 360.0 - 180.0)
        if delta < min_bearing_diff:
            continue
        short, long_ = sorted((i, j), key=lambda n: geometries[n].length)
        if not _runs_alongside(
            geometries[short], geometries[long_], buffers.iloc[long_], min_overlap_frac
        ):
            continue
        pairs.setdefault(candidates[i][0], set()).add(candidates[j][0])
        pairs.setdefault(candidates[j][0], set()).add(candidates[i][0])

    return {edge: frozenset(counterparts) for edge, counterparts in pairs.items()}


def unshared_edges(G, cheap_edges, other_edges, counterparts=None):
    """
    The cheaper route's edges whose street the other direction's route did *not* use.

    An edge is treated as shared -- and so dropped -- when any of these hold:

    - It has a reciprocal edge ``(v, u, *)``. The street is already two-way, so it
      carries both directions of travel no matter which route used it; a
      contra-flow lane there would change nothing.
    - It has an opposing carriageway (see ``build_carriageway_pairs``). Same
      argument: the divided road carries both directions, one per side.
    - The other route used the same OSM way.

    The first two rules ask only whether the counterpart *exists*, not whether the
    other route used it. A reverse trip that skips an available counterpart is
    expressing a routing preference, not obeying a restriction, so blaming this
    segment for the trip's asymmetry would be a false positive -- and for divided
    roads it is the false positive that used to flood the ranking (VFW Parkway and
    friends), since OSM splits each carriageway at every intersection and each
    fragment then scored on its own.

    Parameters:
    - G (nx.MultiDiGraph): the graph both paths were routed on.
    - cheap_edges (list): (u, v, key) tuples on the cheaper route.
    - other_edges (list): (u, v, key) tuples on the more expensive route. Only their
      OSM way ids are consulted, since the other two rules are now properties of the
      cheaper route's own edges.
    - counterparts (dict): output of ``build_carriageway_pairs``, or None to skip
      the divided-road rule. Only membership is read, not the paired edges, so a
      plain set of edge keys works too.

    Returns:
    - list: the subset of ``cheap_edges``, in order, that carries the blame. Every
      edge in it is one-way and has no opposing carriageway.
    """
    counterparts = counterparts or {}
    other_osmids = set()
    for u, v, k in other_edges:
        other_osmids |= edge_osmids(G[u][v][k])

    unshared = []
    for u, v, k in cheap_edges:
        if G.has_edge(v, u):
            continue
        if (u, v, k) in counterparts:
            continue
        if other_osmids & edge_osmids(G[u][v][k]):
            continue
        unshared.append((u, v, k))
    return unshared
