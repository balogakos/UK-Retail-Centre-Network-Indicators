## Helper Functions for UK Retail Centre Street-Network Indicators

from dataclasses import dataclass
import math
import numpy as np
import pandas as pd
import shapely
from shapely import STRtree
from shapely.ops import polygonize
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
import igraph as ig


# 1. Highway Class Definitions & Parameters -------------------------------

WALK_CLASSES = {
    'residential', 'unclassified', 'living_street', 'tertiary', 'tertiary_link',
    'secondary', 'secondary_link', 'primary', 'primary_link', 'trunk', 'trunk_link',
    'service', 'footway', 'pedestrian', 'path', 'steps'
}

CARFREE_CLASSES = {'footway', 'pedestrian', 'path', 'steps'}

DRIVE_CLASSES = {
    'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link',
    'secondary', 'secondary_link', 'tertiary', 'tertiary_link', 'residential',
    'unclassified', 'living_street'
}

ARTERIAL_CLASSES = {
    'motorway', 'motorway_link', 'trunk', 'trunk_link',
    'primary', 'primary_link', 'secondary', 'secondary_link'
}

STREET_GRID_EXCLUDED_TIERS = {
    'Small Local Centre',
    'Small Retail Park',
    'Large Retail Park',
    'Small Shopping Centre',
    'Large Shopping Centre'
}

UNIVERSAL_INDICATORS = [
    'walk_reach_400',
    'drive_reach_400',
    'arterial_share',
    'service_share',
    'carfree_share',
    'walk_median_edge_len_m',
    'walk_meshedness',
    'walk_sightline_continuity',
    'flow_concentration'
]

STREET_GRID_INDICATORS = [
    'walk_block_median_area_m2',
    'orientation_entropy'
]

ALL_INDICATORS = UNIVERSAL_INDICATORS + STREET_GRID_INDICATORS


@dataclass(frozen=True)
class NetworkParams:
    buffer_m: float = 100.0
    tol_m: float = 10.0
    sidewalk_mode: str = 'remove'
    context_m: float = 400.0
    reach_m: float = 400.0


# 2. Modal Filtering & Geometric Sidewalk Detection -----------------------

def _isin(series, values):
    return series.isin(values).to_numpy()


def get_walk_mask(df):
    fc = df['fclass']
    m = _isin(fc, WALK_CLASSES)
    m &= ~_isin(df['access'], ['private', 'no'])
    m &= ~_isin(df['foot'], ['no'])
    m &= ~((fc == 'service') & (df['service'] == 'driveway')).to_numpy()
    return m


def get_drive_mask(df):
    m = _isin(df['fclass'], DRIVE_CLASSES)
    m &= ~_isin(df['access'], ['private', 'no'])
    m &= ~_isin(df['motor_vehicle'], ['no'])
    return m


def get_service_mask(df):
    fc = df['fclass']
    m = (fc == 'service').to_numpy()
    m &= ~_isin(df['service'], ['driveway'])
    m &= ~_isin(df['access'], ['private', 'no'])
    m &= ~_isin(df['motor_vehicle'], ['no'])
    return m


def detect_parallel_sidewalks(df):
    """Identify footways mapped as parallel roadside pavements or crossings."""
    fc = df['fclass'].to_numpy()
    tagged = _isin(df['footway'], ['sidewalk', 'crossing', 'traffic_island']) & (fc == 'footway')
    cand = (fc == 'footway') & ~tagged
    road = _isin(df['fclass'], DRIVE_CLASSES | {'service'})
    if cand.sum() == 0 or road.sum() == 0:
        return tagged

    geoms = df.geometry.to_numpy()
    tree = STRtree(geoms[road])
    lines = geoms[cand]
    lens = shapely.length(lines)
    n = np.maximum(3, (lens // 10).astype(int) + 1)
    idx = np.repeat(np.arange(len(lines)), n)
    start = np.repeat(np.cumsum(n) - n, n)
    pos = np.arange(n.sum()) - start
    frac = pos / (np.repeat(n, n) - 1)
    pts = shapely.line_interpolate_point(lines[idx], frac, normalized=True)
    near = tree.query_nearest(pts, max_distance=12.0, all_matches=False)
    hit = np.zeros(len(pts), dtype=float)
    hit[near[0]] = 1.0
    share = np.bincount(idx, weights=hit, minlength=len(lines)) / n
    sw = (share >= 0.8) & (lens >= 8.0)

    out = tagged.copy()
    out[np.where(cand)[0][sw]] = True
    return out


# 3. Planar Graph Construction & Junction Consolidation -------------------

def _explode_lines(geoms, clip_poly):
    if len(geoms) == 0:
        return np.array([], dtype=object)
    parts = shapely.get_parts(shapely.intersection(geoms, clip_poly))
    parts = parts[shapely.get_type_id(parts) == 1]
    return parts[shapely.length(parts) >= 1.0]


def build_consolidated_graph(geoms, grade_sep, clip_poly, tol_m):
    """Planarise ground-level ways, merge degree-2 chains, and consolidate junctions within tol_m."""
    geoms = np.asarray(geoms, dtype=object)
    grade_sep = np.asarray(grade_sep, dtype=bool)
    ground = _explode_lines(geoms[~grade_sep], clip_poly)
    gsep = _explode_lines(geoms[grade_sep], clip_poly)

    merged = None
    segs = []
    if len(ground):
        merged = shapely.line_merge(shapely.union_all(ground))
        g = shapely.get_parts(merged)
        segs.append(g[shapely.get_type_id(g) == 1])
    if len(gsep):
        segs.append(gsep)
    if not segs:
        return None

    segs = np.concatenate(segs)
    segs = segs[shapely.length(segs) >= 0.5]
    if len(segs) < 2:
        return None

    p0 = shapely.get_coordinates(shapely.get_point(segs, 0))
    p1 = shapely.get_coordinates(shapely.get_point(segs, -1))
    pts = np.empty((2 * len(segs), 2))
    pts[0::2], pts[1::2] = p0, p1
    pairs = cKDTree(pts).query_pairs(tol_m, output_type='ndarray')
    n = len(pts)
    if len(pairs):
        adj = coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(n, n))
        _, lab = connected_components(adj, directed=False)
    else:
        lab = np.arange(n)

    eu, ev = lab[0::2], lab[1::2]
    keep = eu != ev
    segs, eu, ev = segs[keep], eu[keep], ev[keep]
    if len(segs) < 2:
        return None

    elen = shapely.length(segs)
    df = pd.DataFrame({
        'a': np.minimum(eu, ev),
        'b': np.maximum(eu, ev),
        'len': elen,
        'i': np.arange(len(segs))
    })
    df = df.sort_values('len').drop_duplicates(['a', 'b'])
    idx = df['i'].to_numpy()
    segs, eu, ev, elen = segs[idx], eu[idx], ev[idx], df['len'].to_numpy()

    used, inv = np.unique(np.concatenate([eu, ev]), return_inverse=True)
    m = len(segs)
    eu, ev = inv[:m], inv[m:]
    n_nodes = len(used)
    cnt = np.bincount(lab, minlength=lab.max() + 1)[used]
    x = np.bincount(lab, weights=pts[:, 0], minlength=lab.max() + 1)[used] / cnt
    y = np.bincount(lab, weights=pts[:, 1], minlength=lab.max() + 1)[used] / cnt
    deg = np.bincount(np.concatenate([eu, ev]), minlength=n_nodes)
    csr = csr_matrix((np.maximum(elen, 0.5), (eu, ev)), shape=(n_nodes, n_nodes))

    return dict(
        N=n_nodes, xy=np.column_stack([x, y]), eu=eu, ev=ev,
        elen=elen, egeom=segs, deg=deg, csr=csr, merged=merged
    )


# 4. Network Indicator Calculations ---------------------------------------

def _gini(values):
    a = np.asarray(values, dtype=float)
    a = a[np.isfinite(a) & (a >= 0)]
    if len(a) < 5 or a.sum() == 0:
        return np.nan
    a = np.sort(a)
    n = len(a)
    return float(((2 * np.arange(1, n + 1) - n - 1) * a).sum() / (n * a.sum()))


def compute_ring_reach(g, poly, src_buf_m, limit_m):
    """Proportion of surrounding-ring street length reachable within limit_m network distance."""
    if g is None:
        return np.nan
    x, y = g['xy'][:, 0], g['xy'][:, 1]
    src = np.where(shapely.contains_xy(poly.buffer(src_buf_m), x, y))[0]
    if len(src) == 0:
        c = poly.centroid
        d = np.hypot(x - c.x, y - c.y)
        j = int(np.argmin(d))
        if shapely.distance(shapely.points(x[j], y[j]), poly) > 100.0:
            return np.nan
        src = np.array([j])

    dist = dijkstra(g['csr'], directed=False, indices=src, limit=limit_m, min_only=True)
    du, dv = dist[g['eu']], dist[g['ev']]
    ru = np.where(np.isfinite(du), np.maximum(0.0, limit_m - du), 0.0)
    rv = np.where(np.isfinite(dv), np.maximum(0.0, limit_m - dv), 0.0)
    reach = np.minimum(g['elen'], ru + rv)

    mid = shapely.line_interpolate_point(g['egeom'], 0.5, normalized=True)
    shapely.prepare(poly)
    ring = ~shapely.contains(poly, mid)
    tot = g['elen'][ring].sum()
    if tot < 200.0:
        return np.nan
    return float(reach[ring].sum() / tot)


def _endpoint_bearings(g, edges):
    geom = g['egeom'][edges]
    ln = g['elen'][edges]
    p0 = shapely.get_coordinates(shapely.get_point(geom, 0))
    p1 = shapely.get_coordinates(shapely.get_point(geom, -1))
    d = np.minimum(15.0, ln / 2.0)
    a = shapely.get_coordinates(shapely.line_interpolate_point(geom, d))
    b = shapely.get_coordinates(shapely.line_interpolate_point(geom, np.maximum(ln - 15.0, ln / 2.0)))
    bs = np.degrees(np.arctan2(a[:, 1] - p0[:, 1], a[:, 0] - p0[:, 0])) % 360.0
    be = np.degrees(np.arctan2(b[:, 1] - p1[:, 1], b[:, 0] - p1[:, 0])) % 360.0
    return bs, be


def compute_centre_indicators(poly, cand, classification=None, params=NetworkParams()):
    """Compute the 9 universal core indicators and 2 street-grid indicators for a retail centre."""
    ctx = poly.buffer(params.context_m)
    core = poly.buffer(params.buffer_m)
    res = {k: np.nan for k in ALL_INDICATORS}
    res.update(sidewalk_mapped_share=np.nan, n_walk_edges=0, n_drive_edges=0)

    if cand is None or len(cand) == 0:
        return res

    cand = cand.reset_index(drop=True)
    sw = detect_parallel_sidewalks(cand)
    fw = (cand['fclass'] == 'footway').to_numpy()
    fw_len = shapely.length(cand.geometry.to_numpy()[fw]).sum()
    if fw_len >= 100.0:
        res['sidewalk_mapped_share'] = float(shapely.length(cand.geometry.to_numpy()[sw]).sum() / fw_len)

    wm = get_walk_mask(cand)
    if params.sidewalk_mode == 'remove':
        wm &= ~sw
    # Street-structure mask excludes highway=service (car-park access lanes and loading rings)
    wm_street = wm & (cand['fclass'] != 'service').to_numpy()
    dm = get_drive_mask(cand)
    sm = get_service_mask(cand)

    geoms = cand.geometry.to_numpy()
    gs = cand['is_grade_sep'].to_numpy()

    # 1. Modal Composition Shares inside Core Readout Buffer
    clipped = shapely.length(shapely.intersection(geoms, core))
    fc = cand['fclass'].to_numpy()
    drive_len = clipped[dm].sum()
    if drive_len >= 50.0:
        res['arterial_share'] = float(clipped[dm & np.isin(fc, list(ARTERIAL_CLASSES))].sum() / drive_len)
        res['service_share'] = float(clipped[sm].sum() / (drive_len + clipped[sm].sum()))
    walk_len = clipped[wm].sum()
    if walk_len >= 50.0:
        res['carfree_share'] = float(clipped[wm & np.isin(fc, list(CARFREE_CLASSES))].sum() / walk_len)

    # 2. Build Consolidated Graphs (400 m Context)
    gw = build_consolidated_graph(geoms[wm], gs[wm], ctx, params.tol_m) if wm.sum() >= 2 else None
    gw_street = build_consolidated_graph(geoms[wm_street], gs[wm_street], ctx, params.tol_m) if wm_street.sum() >= 2 else None
    gd = build_consolidated_graph(geoms[dm], gs[dm], ctx, params.tol_m) if dm.sum() >= 2 else None

    res['n_walk_edges'] = 0 if gw is None else len(gw['elen'])
    res['n_drive_edges'] = 0 if gd is None else len(gd['elen'])

    # 3. External Ring Reach (400 m)
    res['walk_reach_400'] = compute_ring_reach(gw, poly, 30.0, params.reach_m)
    res['drive_reach_400'] = compute_ring_reach(gd, poly, 50.0, params.reach_m)

    # 4. Walk Graph Metrics (Grain, Flow Concentration, Sightline Continuity)
    shapely.prepare(core)
    if gw is not None:
        core_e = shapely.intersects(gw['egeom'], core)
        x, y = gw['xy'][:, 0], gw['xy'][:, 1]
        core_n = shapely.contains_xy(core, x, y)

        if core_e.sum() >= 3:
            res['walk_median_edge_len_m'] = float(np.median(gw['elen'][core_e]))

            if core_e.sum() >= 5:
                ig_g = ig.Graph(n=gw['N'], edges=list(zip(gw['eu'].tolist(), gw['ev'].tolist())))
                eb = np.array(ig_g.edge_betweenness(directed=False, cutoff=params.reach_m, weights=gw['elen'].tolist()))
                res['flow_concentration'] = _gini(eb[core_e])

        junc = core_n & (gw['deg'] >= 3)
        if junc.sum() >= 3 and core_e.sum() > 0:
            e_idx = np.where(core_e)[0]
            bs, be = _endpoint_bearings(gw, e_idx)
            inc = {}
            for k, e in enumerate(e_idx):
                inc.setdefault(gw['eu'][e], []).append(bs[k])
                inc.setdefault(gw['ev'][e], []).append(be[k])
            cont = []
            for nd in np.where(junc)[0]:
                b = inc.get(nd, [])
                if len(b) < 3:
                    continue
                b = np.array(b)
                diff = np.abs(b[:, None] - b[None, :]) % 360.0
                diff = np.minimum(diff, 360.0 - diff)
                cont.append(bool(np.any(np.triu(np.abs(180.0 - diff) <= 20.0, 1))))
            if len(cont) >= 3:
                res['walk_sightline_continuity'] = float(np.mean(cont))

    # 5. Car-Park-Cleaned Street Structure Metrics (Meshedness, Block Area, Orientation Entropy)
    if gw_street is not None:
        core_se = shapely.intersects(gw_street['egeom'], core)
        if core_se.sum() >= 3:
            e_idx = np.where(core_se)[0]
            nodes, inv = np.unique(np.concatenate([gw_street['eu'][e_idx], gw_street['ev'][e_idx]]), return_inverse=True)
            E, Nn = len(e_idx), len(nodes)
            if Nn >= 4:
                sub = coo_matrix((np.ones(E), (inv[:E], inv[E:])), shape=(Nn, Nn))
                C = connected_components(sub, directed=False)[0]
                res['walk_meshedness'] = float(max(0.0, (E - Nn + C) / (2 * Nn - 5)))

            # Street-Grid Set: compute only for eligible traditional street centres
            if classification not in STREET_GRID_EXCLUDED_TIERS:
                sx, sy = gw_street['xy'][:, 0], gw_street['xy'][:, 1]
                dx = sx[gw_street['ev'][e_idx]] - sx[gw_street['eu'][e_idx]]
                dy = sy[gw_street['ev'][e_idx]] - sy[gw_street['eu'][e_idx]]
                ang = np.degrees(np.arctan2(dy, dx)) % 360.0
                w = gw_street['elen'][e_idx]
                bins = np.zeros(36)
                for a_, w_ in ((ang, w), ((ang + 180.0) % 360.0, w)):
                    bins += np.bincount(((a_ + 5.0) % 360.0 // 10.0).astype(int), weights=w_, minlength=36)[:36]
                pr = bins[bins > 0] / bins.sum()
                res['orientation_entropy'] = float(-(pr * np.log(pr)).sum() / math.log(36)) if len(pr) > 1 else 0.0

        if classification not in STREET_GRID_EXCLUDED_TIERS and gw_street['merged'] is not None:
            polys = np.array(list(polygonize(gw_street['merged'])), dtype=object)
            if len(polys):
                area = shapely.area(polys)
                thick = 4.0 * area / np.maximum(shapely.length(polys), 1e-6)
                polys, area = polys[thick >= 20.0], area[thick >= 20.0]
                if len(polys):
                    inside = shapely.contains(core, shapely.point_on_surface(polys))
                    if inside.sum() >= 2:
                        res['walk_block_median_area_m2'] = float(np.median(area[inside]))

    return res
