## Calculating Street-Network Indicators for UK Retail Centres

import argparse
from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path
import sys
import geopandas as gpd
import pandas as pd
import shapely
from shapely import STRtree

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / 'Source Code'))
from Helper_Functions import (
    ALL_INDICATORS,
    STREET_GRID_INDICATORS,
    UNIVERSAL_INDICATORS,
    NetworkParams,
    compute_centre_indicators,
)


# 1. Default Repository-Relative Input & Output Paths ---------------------

DEFAULT_CENTRES = REPO_ROOT / 'Input Data' / 'retailcentre_bounds_uk.gpkg'
DEFAULT_ROADS = REPO_ROOT / 'Input Data' / 'uk_roads_400m.parquet'
OUT_DIR = REPO_ROOT / 'Output Data'
DEFAULT_OUT_CSV = OUT_DIR / 'UK_Retail_Centre_Network_Indicators.csv'
DEFAULT_OUT_GPKG = OUT_DIR / 'UK_Retail_Centre_Network_Indicators.gpkg'

_ROADS = None
_RTREE = None


# 2. Worker Initialisation & Full Indicator Calculation -------------------

def _init_worker(roads_path):
    global _ROADS, _RTREE
    _ROADS = gpd.read_parquet(roads_path)
    _RTREE = STRtree(_ROADS.geometry.to_numpy())


def _compute_centre_row(args):
    rc_id, poly_wkb, classification, params = args
    poly = shapely.from_wkb(poly_wkb)
    ctx = poly.buffer(params.context_m)
    idx = _RTREE.query(ctx, predicate='intersects')
    cand = _ROADS.iloc[idx].reset_index(drop=True) if len(idx) > 0 else None
    res = compute_centre_indicators(poly, cand, classification=classification, params=params)
    res['RC_ID'] = rc_id
    return res


# 3. Assemble & Export Final Indicator Dataset ----------------------------

def main():
    parser = argparse.ArgumentParser(description='Calculate all 11 UK retail centre street-network indicators from scratch.')
    parser.add_argument('--centres', type=Path, default=DEFAULT_CENTRES, help='Path to retailcentre_bounds_uk.gpkg')
    parser.add_argument('--roads', type=Path, default=DEFAULT_ROADS, help='Path to uk_roads_400m.parquet')
    parser.add_argument('--out-csv', type=Path, default=DEFAULT_OUT_CSV, help='Output CSV path')
    parser.add_argument('--out-gpkg', type=Path, default=DEFAULT_OUT_GPKG, help='Output GeoPackage path')
    parser.add_argument('--workers', type=int, default=min(8, os.cpu_count() or 4), help='Parallel worker processes')
    args = parser.parse_args()

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    centres = gpd.read_file(args.centres).to_crs(27700)
    centres['Area_km2'] = shapely.area(centres.geometry.to_numpy()) / 1e6
    if 'Retail_N' not in centres.columns:
        for alt in ('N_Units', 'n_units', 'retail_n', 'Units_N'):
            if alt in centres.columns:
                centres['Retail_N'] = centres[alt]
                break

    params = NetworkParams()
    tasks = [
        (row.RC_ID, shapely.to_wkb(row.geometry), row.Classification, params)
        for row in centres.itertuples()
    ]

    with ProcessPoolExecutor(
        max_workers=args.workers,
        initializer=_init_worker,
        initargs=(str(args.roads),)
    ) as pool:
        results = list(pool.map(_compute_centre_row, tasks, chunksize=64))

    ind_df = pd.DataFrame(results)
    meta_cols = [
        c for c in ('RC_ID', 'RC_Name', 'Classification', 'Country', 'Region_NM', 'Area_km2', 'Retail_N')
        if c in centres.columns
    ]
    merged = pd.DataFrame(centres[meta_cols]).merge(ind_df, on='RC_ID', how='left')

    ordered_cols = meta_cols + ['sidewalk_mapped_share'] + UNIVERSAL_INDICATORS + STREET_GRID_INDICATORS
    ordered_cols = [c for c in ordered_cols if c in merged.columns]
    final_df = merged[ordered_cols].copy()

    final_df.to_csv(args.out_csv, index=False)
    print(f'Saved CSV lookup table: {args.out_csv} ({len(final_df):,} centres)')

    gdf = centres[['RC_ID', 'geometry']].merge(final_df, on='RC_ID', how='left')
    if args.out_gpkg.exists():
        args.out_gpkg.unlink()
    gdf.to_file(args.out_gpkg, layer='uk_retail_centre_network_indicators', driver='GPKG')
    print(f'Saved GeoPackage: {args.out_gpkg}')


if __name__ == '__main__':
    main()
