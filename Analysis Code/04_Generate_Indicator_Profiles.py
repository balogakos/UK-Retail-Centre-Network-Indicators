## Generating Low / Median / High Retail Centre Visual Profiles for All 11 Indicators

from pathlib import Path
import sys
import geopandas as gpd
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon as MplPolygon
import numpy as np
import pandas as pd
from scipy.sparse.csgraph import dijkstra
import shapely
from shapely import STRtree
from shapely.ops import polygonize

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / 'Source Code'))
from Helper_Functions import (
    ARTERIAL_CLASSES,
    CARFREE_CLASSES,
    STREET_GRID_EXCLUDED_TIERS,
    NetworkParams,
    build_consolidated_graph,
    compute_distance_limited_edge_betweenness,
    detect_parallel_sidewalks,
    get_drive_mask,
    get_service_mask,
    get_walk_mask,
)


# 1. Repository-Relative Paths & Indicator Specifications -----------------

CENTRES_PATH = REPO_ROOT / 'Input Data' / 'retailcentre_bounds_uk.gpkg'
ROADS_PARQUET = REPO_ROOT / 'Input Data' / 'uk_roads_400m.parquet'
IN_CSV = REPO_ROOT / 'Output Data' / 'UK_Retail_Centre_Network_Indicators.csv'
FIG_DIR = REPO_ROOT / 'Output Data' / 'Figures'
EXAMPLES_CSV = REPO_ROOT / 'Output Data' / 'Indicator_Profile_Examples.csv'

INDICATOR_SPECS = [
    ('walk_reach_400', 'profile_01_walk_reach_400.png',
     'Walkable Neighbourhood Reach (walk_reach_400)', '{:.2f}', 'universal', 'ring_walk'),
    ('drive_reach_400', 'profile_02_drive_reach_400.png',
     'Motorised Road-Network Embeddedness (drive_reach_400)', '{:.2f}', 'universal', 'ring_drive'),
    ('arterial_share', 'profile_03_arterial_share.png',
     'Arterial Traffic Road Share (arterial_share)', '{:.2f}', 'universal', 'arterial'),
    ('service_share', 'profile_04_service_share.png',
     'Service & Car-Park Access Share (service_share)', '{:.2f}', 'universal', 'service'),
    ('carfree_share', 'profile_05_carfree_share.png',
     'Dedicated Pedestrian-Way Share (carfree_share)', '{:.2f}', 'universal', 'carfree'),
    ('walk_median_edge_len_m', 'profile_06_walk_median_edge_len_m.png',
     'Walkable Street Grain: Median Edge Length (walk_median_edge_len_m)', '{:.1f} m', 'street_grid', 'street_graph'),
    ('walk_meshedness', 'profile_07_walk_meshedness.png',
     'Street-Network Meshedness / Loop Ratio (walk_meshedness)', '{:.3f}', 'street_grid', 'street_graph'),
    ('walk_sightline_continuity', 'profile_08_walk_sightline_continuity.png',
     'Descriptive Axial Sightline Continuity (walk_sightline_continuity)', '{:.2f}', 'street_grid', 'street_graph'),
    ('flow_concentration', 'profile_09_flow_concentration.png',
     'Through-Movement Flow Concentration: 400 m Metric Betweenness Gini (flow_concentration)', '{:.2f}', 'street_grid', 'betweenness'),
    ('walk_block_median_area_m2', 'profile_10_walk_block_median_area_m2.png',
     'Enclosed Urban Block Area (walk_block_median_area_m2)', '{:,.0f} m²', 'street_grid', 'blocks'),
    ('orientation_entropy', 'profile_11_orientation_entropy.png',
     'Street Bearing Orientation Entropy (orientation_entropy)', '{:.3f}', 'street_grid', 'street_graph'),
]


# 2. Helper Functions for Selecting & Plotting Representative Centres -----

def _lines_to_segments(geoms):
    segs = []
    for g in geoms:
        if g is None or g.is_empty:
            continue
        for part in shapely.get_parts(g):
            if shapely.get_type_id(part) == 1:
                coords = shapely.get_coordinates(part)
                if len(coords) >= 2:
                    segs.append(coords)
    return segs


def _clean_label_name(rc_name):
    base = str(rc_name).split('(')[0].strip().rstrip(';')
    parts = [p.strip() for p in base.split(';') if p.strip()]
    if len(parts) >= 2 and parts[0].lower() == parts[1].lower():
        parts = parts[:1] + parts[2:]
    out = ', '.join(parts[:2])
    return out if len(out) <= 38 else parts[0][:38]


def pick_three_centres(df, col, filter_mode):
    sub = df.dropna(subset=[col]).copy()
    if filter_mode == 'street_grid':
        sub = sub[~sub['Classification'].isin(STREET_GRID_EXCLUDED_TIERS)]
        sub = sub[(sub['Area_km2'] >= 0.09) & (sub['Area_km2'] <= 0.75)]
    elif col == 'carfree_share':
        sub_all = sub[(sub['Classification'] != 'Small Local Centre') & (sub['Area_km2'] >= 0.06) & (sub['Area_km2'] <= 0.85)].sort_values(col).reset_index(drop=True)
        sub_st = sub[(~sub['Classification'].isin(STREET_GRID_EXCLUDED_TIERS)) & (sub['Area_km2'] >= 0.09) & (sub['Area_km2'] <= 0.75)].sort_values(col).reset_index(drop=True)
        return [
            ('Low (8th pct)', sub_all.iloc[int(len(sub_all) * 0.08)]),
            ('Median (50th pct)', sub_st.iloc[int(len(sub_st) * 0.50)]),
            ('High (92nd pct)', sub_st.iloc[int(len(sub_st) * 0.92)]),
        ]
    else:
        sub = sub[sub['Classification'] != 'Small Local Centre']
        sub = sub[(sub['Area_km2'] >= 0.06) & (sub['Area_km2'] <= 0.85)]

    sub = sub.sort_values(col).reset_index(drop=True)
    n = len(sub)
    q_indices = [int(n * 0.08), int(n * 0.50), int(n * 0.92)]
    labels = ['Low (8th pct)', 'Median (50th pct)', 'High (92nd pct)']
    return [(lbl, sub.iloc[idx]) for lbl, idx in zip(labels, q_indices)]


def plot_panel(ax, row, cand, params, highlight_mode):
    poly = row.geometry
    core = poly.buffer(params.buffer_m)
    ctx = poly.buffer(params.context_m)
    view_box = poly.buffer(220.0) if 'ring' not in highlight_mode else ctx

    sw = detect_parallel_sidewalks(cand)
    wm = get_walk_mask(cand) & ~sw
    wm_street = wm & (cand['fclass'] != 'service').to_numpy()
    dm = get_drive_mask(cand)
    sm = get_service_mask(cand)
    fc = cand['fclass'].to_numpy()

    geoms = cand.geometry.to_numpy()
    gs = cand['is_grade_sep'].to_numpy()

    bg_segs = _lines_to_segments(shapely.intersection(geoms[wm | dm], view_box))
    if bg_segs:
        ax.add_collection(LineCollection(bg_segs, colors='#e0e0e0', linewidths=0.7, zorder=1))

    if highlight_mode in ('ring_walk', 'ring_drive'):
        use_mask = wm if highlight_mode == 'ring_walk' else dm
        src_buf = 30.0 if highlight_mode == 'ring_walk' else 50.0
        g = build_consolidated_graph(geoms[use_mask], gs[use_mask], ctx, params.tol_m)
        if g is not None:
            x, y = g['xy'][:, 0], g['xy'][:, 1]
            src = np.where(shapely.contains_xy(poly.buffer(src_buf), x, y))[0]
            if len(src) > 0:
                dist = dijkstra(g['csr'], directed=False, indices=src, limit=params.reach_m, min_only=True)
                du, dv = dist[g['eu']], dist[g['ev']]
                reached = np.isfinite(du) | np.isfinite(dv)
                mid = shapely.line_interpolate_point(g['egeom'], 0.5, normalized=True)
                ring = ~shapely.contains(poly, mid)
                s_reach = _lines_to_segments(g['egeom'][ring & reached])
                s_unreach = _lines_to_segments(g['egeom'][ring & ~reached])
                s_core = _lines_to_segments(g['egeom'][~ring])
                if s_unreach:
                    ax.add_collection(LineCollection(s_unreach, colors='#de2d26', linewidths=1.25, zorder=2))
                if s_reach:
                    ax.add_collection(LineCollection(s_reach, colors='#1f78b4', linewidths=1.45, zorder=3))
                if s_core:
                    ax.add_collection(LineCollection(s_core, colors='#636363', linewidths=1.1, zorder=2))
    elif highlight_mode == 'arterial':
        art = dm & np.isin(fc, list(ARTERIAL_CLASSES))
        non_art = dm & ~art
        s1 = _lines_to_segments(shapely.intersection(geoms[non_art], core))
        s2 = _lines_to_segments(shapely.intersection(geoms[art], core))
        if s1:
            ax.add_collection(LineCollection(s1, colors='#6baed6', linewidths=1.2, zorder=2))
        if s2:
            ax.add_collection(LineCollection(s2, colors='#cb181d', linewidths=2.3, zorder=4))
    elif highlight_mode == 'service':
        s_drv = _lines_to_segments(shapely.intersection(geoms[dm], core))
        s_srv = _lines_to_segments(shapely.intersection(geoms[sm], core))
        if s_drv:
            ax.add_collection(LineCollection(s_drv, colors='#6baed6', linewidths=1.2, zorder=2))
        if s_srv:
            ax.add_collection(LineCollection(s_srv, colors='#d95f02', linewidths=2.0, zorder=4))
    elif highlight_mode == 'carfree':
        cf = wm & np.isin(fc, list(CARFREE_CLASSES))
        shared = wm_street & ~cf
        s_sh = _lines_to_segments(shapely.intersection(geoms[shared], core))
        s_cf = _lines_to_segments(shapely.intersection(geoms[cf], core))
        if s_sh:
            ax.add_collection(LineCollection(s_sh, colors='#6baed6', linewidths=1.2, zorder=2))
        if s_cf:
            ax.add_collection(LineCollection(s_cf, colors='#238b45', linewidths=2.2, zorder=4))
    elif highlight_mode == 'betweenness':
        gw = build_consolidated_graph(geoms[wm_street], gs[wm_street], ctx, params.tol_m)
        if gw is not None:
            core_e = shapely.intersects(gw['egeom'], core)
            if core_e.sum() >= 5:
                eb = compute_distance_limited_edge_betweenness(gw, limit_m=params.reach_m)
                eb_core = eb[core_e]
                geoms_core = shapely.intersection(gw['egeom'][core_e], core)
                q75 = np.quantile(eb_core, 0.75) if len(eb_core) else 0
                spine = eb_core >= max(q75, 1e-6)
                s_back = _lines_to_segments(geoms_core[~spine])
                s_spine = _lines_to_segments(geoms_core[spine])
                if s_back:
                    ax.add_collection(LineCollection(s_back, colors='#6baed6', linewidths=1.15, zorder=2))
                if s_spine:
                    ax.add_collection(LineCollection(s_spine, colors='#cb181d', linewidths=2.3, zorder=4))
    elif highlight_mode == 'blocks':
        gw_st = build_consolidated_graph(geoms[wm_street], gs[wm_street], ctx, params.tol_m)
        if gw_st is not None and gw_st['merged'] is not None:
            polys = np.array(list(polygonize(gw_st['merged'])), dtype=object)
            if len(polys):
                area = shapely.area(polys)
                thick = 4.0 * area / np.maximum(shapely.length(polys), 1e-6)
                polys = polys[thick >= 20.0]
                if len(polys):
                    inside = shapely.contains(core, shapely.point_on_surface(polys))
                    for bp in polys[inside]:
                        xy = np.asarray(bp.exterior.coords)
                        ax.add_patch(MplPolygon(xy, closed=True, facecolor='#fdd0a2', edgecolor='#d94801', lw=1.0, alpha=0.65, zorder=2))
            st_segs = _lines_to_segments(shapely.intersection(gw_st['egeom'], core))
            if st_segs:
                ax.add_collection(LineCollection(st_segs, colors='#08519c', linewidths=1.4, zorder=3))
    else:
        gw = build_consolidated_graph(geoms[wm_street], gs[wm_street], core, params.tol_m)
        if gw is not None:
            segs = _lines_to_segments(gw['egeom'])
            if segs:
                ax.add_collection(LineCollection(segs, colors='#08519c', linewidths=1.5, zorder=3))
            junc = gw['deg'] >= 3
            if junc.sum() > 0:
                ax.scatter(gw['xy'][junc, 0], gw['xy'][junc, 1], s=11, c='#d94801', zorder=4)

    for p in shapely.get_parts(poly):
        x, y = p.exterior.xy
        ax.plot(x, y, color='#111111', lw=1.5, zorder=5)
    for p in shapely.get_parts(core):
        x, y = p.exterior.xy
        ax.plot(x, y, color='#555555', lw=0.9, ls='--', zorder=5)

    bounds_geom = view_box if 'ring' in highlight_mode else core
    minx, miny, maxx, maxy = bounds_geom.bounds
    span = max(maxx - minx, maxy - miny) * 0.56 + 25.0
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    ax.set_xlim(cx - span, cx + span)
    ax.set_ylim(cy - span, cy + span)
    ax.set_aspect('equal')
    ax.set_xticks([])
    ax.set_yticks([])


def _legend_for_mode(highlight_mode):
    base = [
        Line2D([0], [0], color='#111111', lw=1.5, label='Retail centre boundary'),
        Line2D([0], [0], color='#555555', lw=0.9, ls='--', label='100 m core readout buffer'),
    ]
    if 'ring' in highlight_mode:
        base += [
            Line2D([0], [0], color='#1f78b4', lw=1.6, label='Reachable 400 m ring network'),
            Line2D([0], [0], color='#de2d26', lw=1.4, label='Unreachable ring network (>400 m / severed)'),
        ]
    elif highlight_mode == 'arterial':
        base += [
            Line2D([0], [0], color='#cb181d', lw=2.3, label='Arterial roads (motorway/trunk/primary/secondary)'),
            Line2D([0], [0], color='#6baed6', lw=1.3, label='Local drivable streets'),
        ]
    elif highlight_mode == 'service':
        base += [
            Line2D([0], [0], color='#d95f02', lw=2.0, label='Service & car-park access lanes (highway=service)'),
            Line2D([0], [0], color='#6baed6', lw=1.3, label='Public drivable streets'),
        ]
    elif highlight_mode == 'carfree':
        base += [
            Line2D([0], [0], color='#238b45', lw=2.2, label='Dedicated pedestrian ways (pedestrian/footway/path, sidewalks removed)'),
            Line2D([0], [0], color='#6baed6', lw=1.3, label='Shared streets'),
        ]
    elif highlight_mode == 'betweenness':
        base += [
            Line2D([0], [0], color='#cb181d', lw=2.3, label='Primary movement corridors (top 25% 400 m betweenness)'),
            Line2D([0], [0], color='#6baed6', lw=1.2, label='Secondary walkable streets'),
        ]
    elif highlight_mode == 'blocks':
        base += [
            Line2D([0], [0], color='#d94801', lw=1.2, marker='s', markerfacecolor='#fdd0a2', markersize=7, label='Enclosed urban street blocks (car-park lanes excluded)'),
            Line2D([0], [0], color='#08519c', lw=1.4, label='Consolidated street network'),
        ]
    else:
        base += [
            Line2D([0], [0], color='#08519c', lw=1.5, label='Consolidated street network (sidewalks & car parks removed)'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='#d94801', markersize=5, label='Street junction (degree >= 3)'),
        ]
    return base


# 3. Generate All 11 Indicator Profile Figures ----------------------------

def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(IN_CSV)
    centres = gpd.read_file(CENTRES_PATH)[['RC_ID', 'geometry']].to_crs(27700)
    gdf = centres.merge(df, on='RC_ID', how='left')

    roads = gpd.read_parquet(ROADS_PARQUET)
    rtree = STRtree(roads.geometry.to_numpy())
    params = NetworkParams()

    example_records = []

    for col, fname, title, fmt, filter_mode, highlight_mode in INDICATOR_SPECS:
        picks = pick_three_centres(gdf, col, filter_mode)
        fig, axes = plt.subplots(1, 3, figsize=(14.5, 5.3))

        for ax, (pct_label, row) in zip(axes, picks):
            ctx = row.geometry.buffer(params.context_m)
            idx = rtree.query(ctx, predicate='intersects')
            cand = roads.iloc[idx].reset_index(drop=True)
            plot_panel(ax, row, cand, params, highlight_mode)

            val_str = fmt.format(row[col])
            short_name = _clean_label_name(row['RC_Name'])
            ax.set_title(
                f"{pct_label}: {val_str}\n{short_name}\n[{row['Classification']} | {row['Area_km2']:.2f} km²]",
                fontsize=9.5, pad=6
            )

            example_records.append({
                'indicator': col,
                'profile_band': pct_label,
                'RC_ID': row['RC_ID'],
                'RC_Name': row['RC_Name'],
                'Classification': row['Classification'],
                'Region_NM': row['Region_NM'],
                'Area_km2': round(float(row['Area_km2']), 3),
                'value': float(row[col]),
                'formatted_value': val_str,
                'figure_file': f'Output Data/Figures/{fname}'
            })

        fig.legend(handles=_legend_for_mode(highlight_mode), loc='lower center', ncol=2, fontsize=8.5, frameon=True)
        fig.suptitle(title, fontsize=12, fontweight='bold', y=0.98)
        fig.tight_layout(rect=[0, 0.08, 1, 0.93])
        out_path = FIG_DIR / fname
        fig.savefig(out_path, dpi=180)
        plt.close(fig)
        print(f'Saved {out_path}')

    ex_df = pd.DataFrame(example_records)
    ex_df.to_csv(EXAMPLES_CSV, index=False)
    print(f'Saved example lookup table: {EXAMPLES_CSV}')


if __name__ == '__main__':
    main()
