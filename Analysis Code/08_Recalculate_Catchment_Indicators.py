## Recalculate Drive and Walk Catchment Indicators with Classification-Specific Times

import argparse
from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

REPO_ROOT = Path(__file__).resolve().parents[1]

# 1. Tier Catchment Time Configurations (in minutes) -----------------------
# Provided specification by retail centre hierarchy
CATCHMENT_CONFIG = {
    'Regional Centre':        {'drive_min': 20, 'walk_min': 15},
    'Large Shopping Centre':  {'drive_min': 20, 'walk_min': 15},
    'Major Town Centre':      {'drive_min': 15, 'walk_min': 15},
    'Large Retail Park':      {'drive_min': 15, 'walk_min': 10},
    'Small Shopping Centre':  {'drive_min': 15, 'walk_min': 10},
    'Town Centre':            {'drive_min': 10, 'walk_min': 15},
    'Small Retail Park':      {'drive_min': 10, 'walk_min': 10},
    'District Centre':        {'drive_min':  5, 'walk_min':  5},
    'Market Town':            {'drive_min':  5, 'walk_min':  5},
    'Local Centre':           {'drive_min':  5, 'walk_min':  5},
    'Small Local Centre':     {'drive_min':  5, 'walk_min':  5},
}

# 2. Recommended Speeds (km/h) -------------------------------------------
# Walking: UK Department for Transport (DfT) WebTAG standard = 4.8 km/h (80 m/min)
# Driving: Standard UK urban/conurbation retail gravity average = 30.0 km/h (500 m/min)
#          Congested town centre alternative = 24.0 km/h (400 m/min)
DEFAULT_WALK_SPEED_KMH = 4.8
DEFAULT_DRIVE_SPEED_KMH = 30.0


def get_catchment_distance(minutes: float, speed_kmh: float) -> float:
    """Convert travel time (minutes) and speed (km/h) into network distance (metres)."""
    return (speed_kmh * 1000.0 / 60.0) * minutes


def get_tier_distances(classification: str, walk_speed_kmh: float = DEFAULT_WALK_SPEED_KMH,
                       drive_speed_kmh: float = DEFAULT_DRIVE_SPEED_KMH) -> dict:
    """Return walk and drive limit distances (in metres) for a given retail classification."""
    config = CATCHMENT_CONFIG.get(classification, {'drive_min': 5, 'walk_min': 5})
    walk_m = get_catchment_distance(config['walk_min'], walk_speed_kmh)
    drive_m = get_catchment_distance(config['drive_min'], drive_speed_kmh)
    return {
        'walk_min': config['walk_min'],
        'drive_min': config['drive_min'],
        'walk_reach_m': walk_m,
        'drive_reach_m': drive_m,
    }


def compute_ring_reach(g, poly, src_buf_m: float, limit_m: float) -> float:
    """Compute reach ratio within an exterior buffer ring of radius `limit_m` metres.

    Numerator: Walkable/Drivable street length reachable within `limit_m` along the network.
    Denominator: Total street length located inside the exterior 0 to `limit_m` ring outside the centre.
    """
    if g is None or 'csr' not in g or g['csr'] is None:
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


def print_catchment_matrix():
    """Print the complete matrix of travel times, speeds, and resulting catchment distances."""
    print("=" * 105)
    print("UK RETAIL CENTRE CATCHMENT RECALCULATION MATRIX")
    print(f"Walking Speed: {DEFAULT_WALK_SPEED_KMH} km/h (DfT WebTAG standard, 80 m/min)")
    print(f"Driving Speed: {DEFAULT_DRIVE_SPEED_KMH} km/h (Standard UK urban average, 500 m/min)")
    print("=" * 105)
    header = f"{'Retail Centre Type':<26} | {'Walk Time':<10} | {'Walk Dist':<16} | {'Drive Time':<10} | {'Drive Dist (30km/h)':<20} | {'Drive Dist (24km/h)':<20}"
    print(header)
    print("-" * len(header))
    for tier, cfg in CATCHMENT_CONFIG.items():
        w_dist = get_catchment_distance(cfg['walk_min'], DEFAULT_WALK_SPEED_KMH)
        d_dist_30 = get_catchment_distance(cfg['drive_min'], 30.0)
        d_dist_24 = get_catchment_distance(cfg['drive_min'], 24.0)
        print(f"{tier:<26} | {cfg['walk_min']} mins    | {w_dist:,.0f} m ({w_dist/1000:.2f} km) | {cfg['drive_min']} mins   | {d_dist_30:,.0f} m ({d_dist_30/1000:.1f} km)    | {d_dist_24:,.0f} m ({d_dist_24/1000:.1f} km)")
    print("=" * 105)


if __name__ == '__main__':
    print_catchment_matrix()
