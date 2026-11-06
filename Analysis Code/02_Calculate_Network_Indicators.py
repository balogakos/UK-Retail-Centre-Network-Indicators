## Calculating Street-Network Indicators for UK Retail Centres

from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path
import sys
import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely import STRtree
from shapely.ops import polygonize
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
import math

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source Code'))
from Helper_Functions import (
    ALL_INDICATORS,
    STREET_GRID_EXCLUDED_TIERS,
    UNIVERSAL_INDICATORS,
    STREET_GRID_INDICATORS,
    NetworkParams,
    build_consolidated_graph,
    compute_centre_indicators,
    detect_parallel_sidewalks,
    get_walk_mask,
)


# 1. Input & Output Paths -------------------------------------------------

CENTRES_PATH = Path('/Users/akosbalog/Downloads/retailcentre_bounds_uk.gpkg')
ROADS_PARQUET = Path('outputs/v2/uk_roads_400m.parquet')
BASELINE_CACHE = Path('outputs/v2/indicators_baseline.csv')
OUT_DIR = Path('Output Data')
OUT_CSV = OUT_DIR / 'UK_Retail_Centre_Network_Indicators.csv'
OUT_GPKG = OUT_DIR / 'UK_Retail_Centre_Network_Indicators.gpkg'

_ROADS = None
_RTREE = None


# 2. Worker Initialisation & Street-Structure Calculation -----------------

def _init_worker():
    global _ROADS, _RTREE
    _ROADS = gpd.read_parquet(ROADS_PARQUET)
    _RTREE = STRtree(_ROADS.geometry.to_numpy())


def _compute_street_structure_row(args):
    rc_id, poly_wkb, classification, params = args
    poly = shapely.from_wkb(poly_wkb)
    ctx = poly.buffer(params.context_m)
    core = poly.buffer(params.buffer_m)
    idx = _RTREE.query(ctx, predicate='intersects')
    if len(idx) == 0:
        return rc_id, np.nan, np.nan, np.nan

    cand = _ROADS.iloc[idx].reset_index(drop=True)
    sw = detect_parallel_sidewalks(cand)
    wm_street = get_walk_mask(cand) & ~sw & (cand['fclass'] != 'service').to_numpy()
    if wm_street.sum() < 2:
        return rc_id, np.nan, np.nan, np.nan

    geoms = cand.geometry.to_numpy()[wm_street]
    gs = cand['is_grade_sep'].to_numpy()[wm_street]
    gw_street = build_consolidated_graph(geoms, gs, ctx, params.tol_m)
    if gw_street is None:
        return rc_id, np.nan, np.nan, np.nan

    shapely.prepare(core)
    core_se = shapely.intersects(gw_street['egeom'], core)
    meshedness = np.nan
    orient_ent = np.nan
    block_area = np.nan

    if core_se.sum() >= 3:
        e_idx = np.where(core_se)[0]
        nodes, inv = np.unique(
            np.concatenate([gw_street['eu'][e_idx], gw_street['ev'][e_idx]]),
            return_inverse=True
        )
        E, Nn = len(e_idx), len(nodes)
        if Nn >= 4:
            sub = coo_matrix((np.ones(E), (inv[:E], inv[E:])), shape=(Nn, Nn))
            C = connected_components(sub, directed=False)[0]
            meshedness = float(max(0.0, (E - Nn + C) / (2 * Nn - 5)))

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
            orient_ent = float(-(pr * np.log(pr)).sum() / math.log(36)) if len(pr) > 1 else 0.0

    if classification not in STREET_GRID_EXCLUDED_TIERS and gw_street['merged'] is not None:
        polys = np.array(list(polygonize(gw_street['merged'])), dtype=object)
        if len(polys):
            area = shapely.area(polys)
            thick = 4.0 * area / np.maximum(shapely.length(polys), 1e-6)
            polys, area = polys[thick >= 20.0], area[thick >= 20.0]
            if len(polys):
                inside = shapely.contains(core, shapely.point_on_surface(polys))
                if inside.sum() >= 2:
                    block_area = float(np.median(area[inside]))

    return rc_id, meshedness, block_area, orient_ent


# 3. Assemble & Export Final Indicator Dataset ----------------------------

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    centres = gpd.read_file(CENTRES_PATH).to_crs(27700)
    params = NetworkParams()

    tasks = [
        (row.RC_ID, shapely.to_wkb(row.geometry), row.Classification, params)
        for row in centres.itertuples()
    ]

    n_workers = min(8, os.cpu_count() or 4)
    with ProcessPoolExecutor(max_workers=n_workers, initializer=_init_worker) as pool:
        results = list(pool.map(_compute_street_structure_row, tasks, chunksize=64))

    street_df = pd.DataFrame(
        results,
        columns=['RC_ID', 'walk_meshedness', 'walk_block_median_area_m2', 'orientation_entropy']
    )

    base = pd.read_csv(BASELINE_CACHE)
    base = base.drop(columns=['walk_meshedness', 'walk_block_median_area_m2', 'orientation_entropy'])
    merged = base.merge(street_df, on='RC_ID', how='left')

    meta_cols = [
        'RC_ID', 'RC_Name', 'Classification', 'Country', 'Region_NM',
        'Area_km2', 'Retail_N', 'sidewalk_mapped_share'
    ]
    ordered_cols = [c for c in meta_cols + UNIVERSAL_INDICATORS + STREET_GRID_INDICATORS if c in merged.columns]
    final_df = merged[ordered_cols].copy()

    # Save CSV lookup table
    final_df.to_csv(OUT_CSV, index=False)
    print(f'Saved CSV lookup table: {OUT_CSV} ({len(final_df):,} centres)')

    # Save GeoPackage
    gdf = centres[['RC_ID', 'geometry']].merge(final_df, on='RC_ID', how='left')
    if OUT_GPKG.exists():
        OUT_GPKG.unlink()
    gdf.to_file(OUT_GPKG, layer='uk_retail_centre_network_indicators', driver='GPKG')
    print(f'Saved GeoPackage: {OUT_GPKG}')


if __name__ == '__main__':
    main()
