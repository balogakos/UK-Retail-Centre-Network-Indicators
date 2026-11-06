## Validation Scorecard & Perturbation Robustness Analysis for UK Retail Centre Network Indicators

import argparse
from concurrent.futures import ProcessPoolExecutor
import os
from pathlib import Path
import sys
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import kruskal, mannwhitneyu, spearmanr
import shapely
from shapely import STRtree

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / 'Source Code'))
from Helper_Functions import (
    ALL_INDICATORS,
    STREET_GRID_EXCLUDED_TIERS,
    STREET_GRID_INDICATORS,
    UNIVERSAL_INDICATORS,
    NetworkParams,
    compute_centre_indicators,
)


# 1. Configuration & Helper Statistics ------------------------------------

DEFAULT_IN_CSV = REPO_ROOT / 'Output Data' / 'UK_Retail_Centre_Network_Indicators.csv'
DEFAULT_CENTRES = REPO_ROOT / 'Input Data' / 'retailcentre_bounds_uk.gpkg'
DEFAULT_ROADS = REPO_ROOT / 'Input Data' / 'uk_roads_400m.parquet'
DEFAULT_OUT_SCORECARD = REPO_ROOT / 'Output Data' / 'Validation_Scorecard.csv'
DEFAULT_OUT_ROBUSTNESS = REPO_ROOT / 'Output Data' / 'Validation_Robustness.csv'

HIGH_STREET_TIERS = {
    'Regional Centre', 'Major Town Centre', 'Town Centre',
    'District Centre', 'Market Town', 'Local Centre'
}
RETAIL_PARK_TIERS = {'Small Retail Park', 'Large Retail Park'}

_ROADS = None
_RTREE = None


def _init_worker(roads_path):
    global _ROADS, _RTREE
    _ROADS = gpd.read_parquet(roads_path)
    _RTREE = STRtree(_ROADS.geometry.to_numpy())


def _compute_perturbation_row(args):
    rc_id, poly_wkb, classification, params = args
    poly = shapely.from_wkb(poly_wkb)
    ctx = poly.buffer(params.context_m)
    idx = _RTREE.query(ctx, predicate='intersects')
    cand = _ROADS.iloc[idx].reset_index(drop=True) if len(idx) > 0 else None
    res = compute_centre_indicators(poly, cand, classification=classification, params=params)
    res['RC_ID'] = rc_id
    return res


def cliffs_delta(x, y):
    x = pd.Series(x).dropna().to_numpy()
    y = pd.Series(y).dropna().to_numpy()
    if len(x) == 0 or len(y) == 0:
        return np.nan
    u, _ = mannwhitneyu(x, y, alternative='two-sided')
    return float(2.0 * u / (len(x) * len(y)) - 1.0)


def regional_eta_squared(df, col):
    if 'Region_NM' not in df.columns:
        return np.nan
    sub = df[['Region_NM', col]].dropna()
    groups = [g[col].to_numpy() for _, g in sub.groupby('Region_NM') if len(g) >= 5]
    if len(groups) < 2:
        return np.nan
    h_stat, _ = kruskal(*groups)
    n = sum(len(g) for g in groups)
    k = len(groups)
    return float(max(0.0, (h_stat - k + 1.0) / (n - k)))


# 2. Compute Discriminant & Convergent Validity Scorecard -----------------

def compute_scorecard(df):
    df_street = df[~df['Classification'].isin(STREET_GRID_EXCLUDED_TIERS)].copy()

    reg = df[df['Classification'] == 'Regional Centre']
    slc = df[df['Classification'] == 'Small Local Centre']
    dist_loc = df[df['Classification'].isin({'District Centre', 'Local Centre'})]
    rp = df[df['Classification'].isin(RETAIL_PARK_TIERS)]
    hs = df[df['Classification'].isin(HIGH_STREET_TIERS)]

    rows = []
    for ind in ALL_INDICATORS:
        scope = 'Universal Core (N = 9,623)' if ind in UNIVERSAL_INDICATORS else 'Street-Grid Set (N = 1,521)'
        sub = df if ind in UNIVERSAL_INDICATORS else df_street
        valid = sub.dropna(subset=[ind])

        missing_pct = 100.0 * (1.0 - len(valid) / len(sub))

        rho_area, _ = spearmanr(valid[ind], valid['Area_km2'])
        rho_area_non_slc, _ = spearmanr(
            df_street.dropna(subset=[ind])[ind],
            df_street.dropna(subset=[ind])['Area_km2']
        )
        wt = []
        for _, g in valid.groupby('Classification'):
            if len(g) >= 20:
                r, _ = spearmanr(g[ind], g['Area_km2'])
                if np.isfinite(r):
                    wt.append(abs(r))
        mean_abs_wt = float(np.mean(wt)) if wt else np.nan

        sw_valid = valid.dropna(subset=['sidewalk_mapped_share'])
        rho_sw, _ = spearmanr(sw_valid[ind], sw_valid['sidewalk_mapped_share'])
        eta2_reg = regional_eta_squared(valid, ind)

        d_reg_local = cliffs_delta(reg[ind], slc[ind]) if ind in UNIVERSAL_INDICATORS else cliffs_delta(reg[ind], dist_loc[ind])
        d_rp_hs = cliffs_delta(rp[ind], hs[ind]) if ind in UNIVERSAL_INDICATORS else np.nan

        rows.append({
            'indicator': ind,
            'tier_scope': scope,
            'eligible_N': len(sub),
            'valid_N': len(valid),
            'missing_pct': round(missing_pct, 2),
            'median': round(float(valid[ind].median()), 3),
            'iqr_25': round(float(valid[ind].quantile(0.25)), 3),
            'iqr_75': round(float(valid[ind].quantile(0.75)), 3),
            'rho_area_all_eligible': round(float(rho_area), 3),
            'rho_area_street_centres': round(float(rho_area_non_slc), 3),
            'within_tier_abs_rho_area': round(mean_abs_wt, 3),
            'rho_sidewalk_mapped': round(float(rho_sw), 3),
            'eta2_region': round(float(eta2_reg), 3) if np.isfinite(eta2_reg) else np.nan,
            'cliffs_delta_hierarchy': round(float(d_reg_local), 3) if np.isfinite(d_reg_local) else np.nan,
            'cliffs_delta_rp_vs_hs': round(float(d_rp_hs), 3) if np.isfinite(d_rp_hs) else np.nan,
        })

    return pd.DataFrame(rows)


# 3. Reproducible Parameter-Perturbation Sensitivity Analysis -------------

def compute_robustness_table(df, centres_path, roads_path, sample_n=400, workers=8):
    centres = gpd.read_file(centres_path)[['RC_ID', 'Classification', 'geometry']].to_crs(27700)
    rng = np.random.default_rng(42)

    # Stratified sample across retail classifications (guaranteeing street-grid coverage)
    sampled_parts = []
    for cls, grp in centres.groupby('Classification'):
        take = min(len(grp), max(25, int(round(sample_n * len(grp) / len(centres)))))
        idx = rng.choice(grp.index.to_numpy(), size=take, replace=False)
        sampled_parts.append(centres.loc[idx])
    sample_gdf = pd.concat(sampled_parts, ignore_index=True)

    base_sub = df[df['RC_ID'].isin(sample_gdf['RC_ID'])].copy()
    variants = {
        'rho_buf50': NetworkParams(buffer_m=50.0, tol_m=10.0, sidewalk_mode='remove'),
        'rho_buf150': NetworkParams(buffer_m=150.0, tol_m=10.0, sidewalk_mode='remove'),
        'rho_tol5': NetworkParams(buffer_m=100.0, tol_m=5.0, sidewalk_mode='remove'),
        'rho_tol15': NetworkParams(buffer_m=100.0, tol_m=15.0, sidewalk_mode='remove'),
        'rho_keep_sidewalks': NetworkParams(buffer_m=100.0, tol_m=10.0, sidewalk_mode='keep'),
    }

    variant_dfs = {}
    with ProcessPoolExecutor(
        max_workers=workers,
        initializer=_init_worker,
        initargs=(str(roads_path),)
    ) as pool:
        for v_name, v_params in variants.items():
            tasks = [
                (row.RC_ID, shapely.to_wkb(row.geometry), row.Classification, v_params)
                for row in sample_gdf.itertuples()
            ]
            res = list(pool.map(_compute_perturbation_row, tasks, chunksize=32))
            variant_dfs[v_name] = pd.DataFrame(res)

    rob_rows = []
    for ind in ALL_INDICATORS:
        row_dict = {'indicator': ind, 'sample_N': len(sample_gdf)}
        rhos = []
        for v_name, v_df in variant_dfs.items():
            merged = base_sub[['RC_ID', 'Region_NM', ind]].merge(
                v_df[['RC_ID', ind]], on='RC_ID', suffixes=('_base', '_var')
            ).dropna()
            if len(merged) >= 15:
                r, _ = spearmanr(merged[f'{ind}_base'], merged[f'{ind}_var'])
                row_dict[v_name] = round(float(r), 3)
                if v_name != 'rho_keep_sidewalks':
                    rhos.append(float(r))
            else:
                row_dict[v_name] = np.nan

        row_dict['min_rho_geom_perturb'] = round(float(min(rhos)), 3) if rhos else np.nan
        rob_rows.append(row_dict)

    return pd.DataFrame(rob_rows)


def main():
    parser = argparse.ArgumentParser(description='Validate UK retail centre street-network indicators.')
    parser.add_argument('--in-csv', type=Path, default=DEFAULT_IN_CSV)
    parser.add_argument('--centres', type=Path, default=DEFAULT_CENTRES)
    parser.add_argument('--roads', type=Path, default=DEFAULT_ROADS)
    parser.add_argument('--out-scorecard', type=Path, default=DEFAULT_OUT_SCORECARD)
    parser.add_argument('--out-robustness', type=Path, default=DEFAULT_OUT_ROBUSTNESS)
    parser.add_argument('--skip-robustness', action='store_true', help='Skip parameter perturbation run')
    parser.add_argument('--workers', type=int, default=min(8, os.cpu_count() or 4))
    args = parser.parse_args()

    df = pd.read_csv(args.in_csv)
    scorecard = compute_scorecard(df)
    scorecard.to_csv(args.out_scorecard, index=False)
    print('=== Validation Scorecard ===')
    print(scorecard.to_string(index=False))
    print(f'\nSaved {args.out_scorecard}')

    if not args.skip_robustness and args.roads.exists() and args.centres.exists():
        rob_df = compute_robustness_table(
            df, args.centres, args.roads, sample_n=400, workers=args.workers
        )
        rob_df.to_csv(args.out_robustness, index=False)
        print('\n=== Parameter Perturbation Robustness (Stratified Sample) ===')
        print(rob_df.to_string(index=False))
        print(f'\nSaved {args.out_robustness}')


if __name__ == '__main__':
    main()
