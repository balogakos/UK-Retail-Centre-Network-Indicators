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


# 2. Modal Filtering & Parallel Sidewalk Detection ------------------------

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


def detect_parallel_sidewalks(df, max_dist_m=12.0, max_angle_deg=25.0):
    """Identify tagged sidewalks/crossings and untagged footways running parallel to roads.

    For untagged `highway=footway` segments (>= 8 m), sample points every 10 m and match each
    point to the nearest motorised road within `max_dist_m` (12 m). A sample point counts as
    a parallel-sidewalk match only if the local tangent bearing of the footway aligns within
    `max_angle_deg` (<= 25 degrees modulo 180 degrees) of the matched road's tangent bearing.
    """
    fc = df['fclass'].to_numpy()
    tagged = _isin(df['footway'], ['sidewalk', 'crossing', 'traffic_island']) & (fc == 'footway')
    cand = (fc == 'footway') & ~tagged
    road = _isin(df['fclass'], DRIVE_CLASSES | {'service'})
    if cand.sum() == 0 or road.sum() == 0:
        return tagged

    geoms = df.geometry.to_numpy()
    road_geoms = geoms[road]
    road_lens = shapely.length(road_geoms)
    tree = STRtree(road_geoms)

    lines = geoms[cand]
    lens = shapely.length(lines)
    n = np.maximum(3, (lens // 10).astype(int) + 1)
    idx = np.repeat(np.arange(len(lines)), n)
    start = np.repeat(np.cumsum(n) - n, n)
    pos = np.arange(n.sum()) - start
    frac = pos / (np.repeat(n, n) - 1)

    lines_rep = lines[idx]
    pts = shapely.line_interpolate_point(lines_rep, frac, normalized=True)
    near = tree.query_nearest(pts, max_distance=max_dist_m, all_matches=False)
    hit = np.zeros(len(pts), dtype=float)
    if near.shape[1] > 0:
        q_idx, r_idx = near[0], near[1]
        # Local tangent bearing of the candidate footway at each sample point
        f0 = np.maximum(0.0, frac[q_idx] - 0.05)
        f1 = np.minimum(1.0, frac[q_idx] + 0.05)
        fp0 = shapely.get_coordinates(shapely.line_interpolate_point(lines_rep[q_idx], f0, normalized=True))
        fp1 = shapely.get_coordinates(shapely.line_interpolate_point(lines_rep[q_idx], f1, normalized=True))
        ang_f = np.degrees(np.arctan2(fp1[:, 1] - fp0[:, 1], fp1[:, 0] - fp0[:, 0])) % 180.0

        # Local tangent bearing of the nearest road at the projected point
        matched_roads = road_geoms[r_idx]
        matched_lens = road_lens[r_idx]
        s = shapely.line_locate_point(matched_roads, pts[q_idx])
        s0 = np.maximum(0.0, s - 2.0)
        s1 = np.minimum(matched_lens, s + 2.0)
        rp0 = shapely.get_coordinates(shapely.line_interpolate_point(matched_roads, s0))
        rp1 = shapely.get_coordinates(shapely.line_interpolate_point(matched_roads, s1))
        ang_r = np.degrees(np.arctan2(rp1[:, 1] - rp0[:, 1], rp1[:, 0] - rp0[:, 0])) % 180.0

        diff = np.abs(ang_f - ang_r) % 180.0
        diff = np.minimum(diff, 180.0 - diff)
        hit[q_idx[diff <= max_angle_deg]] = 1.0

    share = np.bincount(idx, weights=hit, minlength=len(lines)) / n
    sw = (share >= 0.75) & (lens >= 8.0)

    out = tagged.copy()
    out[np.where(cand)[0][sw]] = True
    return out


# 3. Planar Graph Construction & Topology-Aware Junction Consolidation ----

def _explode_lines(geoms, clip_poly):
    if len(geoms) == 0:
        return np.array([], dtype=object)
    parts = shapely.get_parts(shapely.intersection(geoms, clip_poly))
    parts = parts[shapely.get_type_id(parts) == 1]
    return parts[shapely.length(parts) >= 1.0]


def build_consolidated_graph(geoms, grade_sep, clip_poly, tol_m):
    """Build planarised street graph with topology-aware junction consolidation (Boeing 2025).

    1. Ground-level ways are planarised at intersections while preserving grade-separated ways.
    2. Coincident segment endpoints within 0.5 m are snapped to form the true planar graph G_0.
    3. Node pairs within Euclidean distance <= `tol_m` are consolidated only if they are
       topologically connected in G_0 within a short network path (<= 2.5 * `tol_m`) or within
       a 1.5 m endpoint snap tolerance, do not collapse a long connecting edge (> 2.5 * `tol_m`),
       and lie within `tol_m` of their cluster seed (preventing transitive chaining).
    """
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

    # Step 1: Exact planar node graph G_0 (snapping coincident endpoints <= 0.5 m)
    snap_pairs = cKDTree(pts).query_pairs(0.5, output_type='ndarray')
    n_pts = len(pts)
    if len(snap_pairs):
        adj0 = coo_matrix((np.ones(len(snap_pairs)), (snap_pairs[:, 0], snap_pairs[:, 1])), shape=(n_pts, n_pts))
        _, raw_lab = connected_components(adj0, directed=False)
    else:
        raw_lab = np.arange(n_pts)

    n_raw = int(raw_lab.max()) + 1
    rcnt = np.bincount(raw_lab, minlength=n_raw)
    rx = np.bincount(raw_lab, weights=pts[:, 0], minlength=n_raw) / rcnt
    ry = np.bincount(raw_lab, weights=pts[:, 1], minlength=n_raw) / rcnt
    rxy = np.column_stack([rx, ry])

    ru, rv = raw_lab[0::2], raw_lab[1::2]
    rlen = shapely.length(segs)

    # Step 2: Topology-aware consolidation within tol_m
    if tol_m > 0.5 and n_raw >= 2:
        cand_pairs = cKDTree(rxy).query_pairs(tol_m, output_type='ndarray')
        if len(cand_pairs):
            valid_e = ru != rv
            eu0 = np.minimum(ru[valid_e], rv[valid_e])
            ev0 = np.maximum(ru[valid_e], rv[valid_e])
            elen0 = np.maximum(rlen[valid_e], 0.1)

            edge_df0 = pd.DataFrame({'u': eu0, 'v': ev0, 'len': elen0})
            min_edges = edge_df0.groupby(['u', 'v'], as_index=False)['len'].min()
            max_edges = edge_df0.groupby(['u', 'v'], as_index=False)['len'].max()

            row = np.concatenate([min_edges['u'].to_numpy(), min_edges['v'].to_numpy()])
            col = np.concatenate([min_edges['v'].to_numpy(), min_edges['u'].to_numpy()])
            dat = np.concatenate([min_edges['len'].to_numpy(), min_edges['len'].to_numpy()])
            raw_csr = csr_matrix((dat, (row, col)), shape=(n_raw, n_raw))

            long_e = max_edges[max_edges['len'] > 2.5 * tol_m]
            long_pairs = set(zip(long_e['u'].tolist(), long_e['v'].tolist()))

            cand_nodes = np.unique(cand_pairs.ravel())
            dist_mat = dijkstra(raw_csr, directed=False, indices=cand_nodes, limit=2.5 * tol_m)
            node_to_row = np.full(n_raw, -1, dtype=int)
            node_to_row[cand_nodes] = np.arange(len(cand_nodes))

            pu = np.minimum(cand_pairs[:, 0], cand_pairs[:, 1])
            pv = np.maximum(cand_pairs[:, 0], cand_pairs[:, 1])
            euclid_d = np.hypot(rxy[pu, 0] - rxy[pv, 0], rxy[pu, 1] - rxy[pv, 1])
            net_d = dist_mat[node_to_row[pu], pv]
            no_long_direct = np.array([(int(a), int(b)) not in long_pairs for a, b in zip(pu, pv)], dtype=bool)
            topo_ok = ((net_d <= 2.5 * tol_m) | (euclid_d <= 1.5)) & no_long_direct
            good_pairs = cand_pairs[topo_ok]

            if len(good_pairs):
                rdeg = np.bincount(np.concatenate([ru[valid_e], rv[valid_e]]), minlength=n_raw)
                nbrs = [[] for _ in range(n_raw)]
                for a, b in good_pairs:
                    nbrs[int(a)].append(int(b))
                    nbrs[int(b)].append(int(a))
                order = np.argsort(-rdeg)
                cluster_id = np.full(n_raw, -1, dtype=int)
                cid = 0
                for u in order:
                    u = int(u)
                    if cluster_id[u] != -1:
                        continue
                    cluster_id[u] = cid
                    if nbrs[u]:
                        ux, uy = rxy[u, 0], rxy[u, 1]
                        for v in nbrs[u]:
                            if cluster_id[v] == -1 and math.hypot(rxy[v, 0] - ux, rxy[v, 1] - uy) <= tol_m:
                                cluster_id[v] = cid
                    cid += 1
                lab = cluster_id[raw_lab]
            else:
                lab = raw_lab
        else:
            lab = raw_lab
    else:
        lab = raw_lab

    eu, ev = lab[0::2], lab[1::2]
    keep = (eu != ev) & (rlen >= 0.5)
    segs, eu, ev, elen = segs[keep], eu[keep], ev[keep], rlen[keep]
    if len(segs) < 2:
        return None

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

    row = np.concatenate([eu, ev])
    col = np.concatenate([ev, eu])
    dat = np.concatenate([np.maximum(elen, 0.5), np.maximum(elen, 0.5)])
    csr = csr_matrix((dat, (row, col)), shape=(n_nodes, n_nodes))

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


def compute_distance_limited_edge_betweenness(g, limit_m=400.0):
    """Compute weighted Brandes shortest-path edge betweenness restricted strictly to paths <= `limit_m` metres.

    Uses `scipy.sparse.csgraph.dijkstra` with `limit=limit_m` (in metres) for exact shortest-path
    distances, then performs full Brandes (2001, 2008) forward path counting (`sigma`) and backward
    dependency accumulation (`dep`) across ALL equal-shortest-path predecessors (within 1e-7 m tolerance).
    """
    n_nodes = g['N']
    eu, ev, elen = g['eu'], g['ev'], g['elen']
    m = len(elen)
    if m == 0 or n_nodes < 2:
        return np.zeros(m, dtype=float)

    w_edge = np.maximum(elen, 0.5)
    adj = [[] for _ in range(n_nodes)]
    for k in range(m):
        u, v, w = int(eu[k]), int(ev[k]), float(w_edge[k])
        adj[u].append((v, w, k))
        adj[v].append((u, w, k))

    dist = dijkstra(g['csr'], directed=False, limit=limit_m, return_predecessors=False)
    eb = np.zeros(m, dtype=float)
    tol = 1e-7

    for s in range(n_nodes):
        d_s = dist[s]
        valid = np.where(np.isfinite(d_s))[0]
        if len(valid) <= 1:
            continue
        order = valid[np.argsort(d_s[valid], kind='mergesort')].tolist()
        d_list = d_s.tolist()
        sigma = [0.0] * n_nodes
        sigma[s] = 1.0
        preds = [[] for _ in range(n_nodes)]

        for u in order:
            su = sigma[u]
            if su == 0.0:
                continue
            du = d_list[u]
            for w, w_len, k in adj[u]:
                dw = d_list[w]
                if dw > du and abs((du + w_len) - dw) <= tol * max(1.0, dw):
                    sigma[w] += su
                    preds[w].append((u, k))

        dep = [0.0] * n_nodes
        for w in reversed(order):
            if w == s:
                continue
            sw = sigma[w]
            if sw > 0.0:
                coeff = (1.0 + dep[w]) / sw
                for u, k in preds[w]:
                    c = sigma[u] * coeff
                    dep[u] += c
                    eb[k] += c

    return eb * 0.5



def compute_ring_reach(g, poly, src_buf_m, limit_m):
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

    res['n_walk_edges'] = 0 if gw_street is None else len(gw_street['elen'])
    res['n_drive_edges'] = 0 if gd is None else len(gd['elen'])

    # 3. External Ring Reach (400 m)
    res['walk_reach_400'] = compute_ring_reach(gw, poly, 30.0, params.reach_m)
    res['drive_reach_400'] = compute_ring_reach(gd, poly, 50.0, params.reach_m)

    # 4. Car-Park-Cleaned Street Topology Metrics (Grain, Meshedness, Sightlines, Flow, Blocks, Entropy)
    shapely.prepare(core)
    if gw_street is not None:
        core_se = shapely.intersects(gw_street['egeom'], core)
        sx, sy = gw_street['xy'][:, 0], gw_street['xy'][:, 1]
        core_sn = shapely.contains_xy(core, sx, sy)

        if core_se.sum() >= 3:
            res['walk_median_edge_len_m'] = float(np.median(gw_street['elen'][core_se]))

            e_idx = np.where(core_se)[0]
            nodes, inv = np.unique(
                np.concatenate([gw_street['eu'][e_idx], gw_street['ev'][e_idx]]),
                return_inverse=True
            )
            E, Nn = len(e_idx), len(nodes)
            if Nn >= 4:
                sub = coo_matrix((np.ones(E), (inv[:E], inv[E:])), shape=(Nn, Nn))
                C = connected_components(sub, directed=False)[0]
                res['walk_meshedness'] = float(max(0.0, (E - Nn + C) / (2 * Nn - 5)))

            if core_se.sum() >= 5:
                eb = compute_distance_limited_edge_betweenness(gw_street, limit_m=params.reach_m)
                res['flow_concentration'] = _gini(eb[core_se])

            if classification not in STREET_GRID_EXCLUDED_TIERS:
                dx = sx[gw_street['ev'][e_idx]] - sx[gw_street['eu'][e_idx]]
                dy = sy[gw_street['ev'][e_idx]] - sy[gw_street['eu'][e_idx]]
                ang = np.degrees(np.arctan2(dy, dx)) % 360.0
                w = gw_street['elen'][e_idx]
                bins = np.zeros(36)
                for a_, w_ in ((ang, w), ((ang + 180.0) % 360.0, w)):
                    bins += np.bincount(((a_ + 5.0) % 360.0 // 10.0).astype(int), weights=w_, minlength=36)[:36]
                pr = bins[bins > 0] / bins.sum()
                res['orientation_entropy'] = float(-(pr * np.log(pr)).sum() / math.log(36)) if len(pr) > 1 else 0.0

        junc = core_sn & (gw_street['deg'] >= 3)
        if junc.sum() >= 3 and core_se.sum() > 0:
            e_idx = np.where(core_se)[0]
            bs, be = _endpoint_bearings(gw_street, e_idx)
            inc = {}
            for k, e in enumerate(e_idx):
                inc.setdefault(gw_street['eu'][e], []).append(bs[k])
                inc.setdefault(gw_street['ev'][e], []).append(be[k])
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
