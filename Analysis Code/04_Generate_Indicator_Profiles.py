## Generating UK Overview Pop-Out Map and Low / Median / High Visual Profiles for All 11 Indicators

from pathlib import Path
import sys
import textwrap
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Polygon as MplPolygon
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


# 1. Repository-Relative Paths & Cartographic Styling ---------------------

CENTRES_PATH = REPO_ROOT / 'Input Data' / 'retailcentre_bounds_uk.gpkg'
ROADS_PARQUET = REPO_ROOT / 'Input Data' / 'uk_roads_400m.parquet'
UK_BASEMAP_GPKG = REPO_ROOT / 'Input Data' / 'uk_basemap_boundaries.gpkg'
IN_CSV = REPO_ROOT / 'Output Data' / 'UK_Retail_Centre_Network_Indicators.csv'
FIG_DIR = REPO_ROOT / 'Output Data' / 'Figures'
OVERVIEW_FIG = FIG_DIR / 'uk_retail_centre_indicator_popouts.png'
EXAMPLES_CSV = REPO_ROOT / 'Output Data' / 'Indicator_Profile_Examples.csv'

PAGE_BG = '#fbfaf7'
OVERVIEW_BG = '#f6f3ec'
LAND_FILL = '#efeadd'
LAD_STROKE = '#ddd7c8'
NEUTRAL_ROAD = '#cbc9c2'
TEXT_DARK = '#1b1b1b'
FONT_FAMILY = 'Times New Roman'

# Coordinated palette: (fill_hex, highlight_hex, secondary_hex)
PALETTE = {
    'walk_reach_400':            ('#269989', '#0072B2', '#d95f02'),
    'drive_reach_400':           ('#6576B8', '#2b5c8f', '#c53a32'),
    'arterial_share':            ('#D55E00', '#B51F2E', '#7b92a8'),
    'service_share':             ('#CC79A7', '#A63C36', '#7b92a8'),
    'carfree_share':             ('#269989', '#0b775e', '#7b92a8'),
    'walk_median_edge_len_m':    ('#E69F00', '#7251A1', '#c8c7c1'),
    'walk_meshedness':           ('#66A061', '#2b6a4c', '#c8c7c1'),
    'walk_sightline_continuity': ('#5975a4', '#1d4e89', '#c8c7c1'),
    'flow_concentration':        ('#D55E00', '#b51f2e', '#7b92a8'),
    'walk_block_median_area_m2': ('#E69F00', '#b85d19', '#2b5c8f'),
    'orientation_entropy':       ('#8c6bb1', '#59408D', '#c8c7c1'),
}

INDICATOR_SPECS = [
    ('walk_reach_400', 'profile_01_walk_reach_400.png',
     'Walkable Neighbourhood Reach', '{:.2f}', 'universal', 'ring_walk', 'high'),
    ('drive_reach_400', 'profile_02_drive_reach_400.png',
     'Motorised Road-Network Embeddedness', '{:.2f}', 'universal', 'ring_drive', 'high'),
    ('arterial_share', 'profile_03_arterial_share.png',
     'Arterial Traffic Share', '{:.2f}', 'universal', 'arterial', 'high'),
    ('service_share', 'profile_04_service_share.png',
     'Service & Car-Park Access Share', '{:.2f}', 'universal', 'service', 'high'),
    ('carfree_share', 'profile_05_carfree_share.png',
     'Dedicated Pedestrian-Way Share', '{:.2f}', 'universal', 'carfree', 'high'),
    ('walk_median_edge_len_m', 'profile_06_walk_median_edge_len_m.png',
     'Walkable Street Grain', '{:.1f} m', 'street_grid', 'street_graph', 'low'),
    ('walk_meshedness', 'profile_07_walk_meshedness.png',
     'Street-Network Meshedness', '{:.3f}', 'street_grid', 'street_graph', 'high'),
    ('walk_sightline_continuity', 'profile_08_walk_sightline_continuity.png',
     'Axial Sightline Continuity', '{:.2f}', 'street_grid', 'street_graph', 'high'),
    ('flow_concentration', 'profile_09_flow_concentration.png',
     'Through-Movement Flow Concentration', '{:.2f}', 'street_grid', 'betweenness', 'high'),
    ('walk_block_median_area_m2', 'profile_10_walk_block_median_area_m2.png',
     'Enclosed Urban Block Area', '{:,.0f} m²', 'street_grid', 'blocks', 'low'),
    ('orientation_entropy', 'profile_11_orientation_entropy.png',
     'Street Bearing Orientation Entropy', '{:.3f}', 'street_grid', 'street_graph', 'high'),
]


# 2. Geometry & Plotting Helpers ------------------------------------------

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
    import re
    cleaned = re.sub(r'\([^)]*\)', '', str(rc_name))
    parts = [p.strip() for p in cleaned.split(';') if p.strip()]
    dedup = []
    for p in parts:
        p_clean = p.replace('City of ', '').replace(' City', '').strip()
        if not dedup or p_clean.lower() not in dedup[-1].lower():
            dedup.append(p_clean if len(dedup) >= 1 else p.replace(' & ', ' and '))
    out = ', '.join(dedup[:2])
    if len(out) > 34 and len(dedup) >= 2:
        short_first = dedup[0].split(' and ')[0].strip()
        out2 = f"{short_first}, {dedup[1]}"
        return out2 if len(out2) <= 34 else dedup[0][:34]
    return out[:34]


def _add_centre_fill(ax, geom, facecolor, alpha=0.38, zorder=2):
    for part in shapely.get_parts(geom):
        if shapely.get_type_id(part) == 3:
            ax.add_patch(
                MplPolygon(
                    np.asarray(part.exterior.coords),
                    closed=True,
                    facecolor=facecolor,
                    edgecolor='none',
                    alpha=alpha,
                    zorder=zorder
                )
            )


def pick_three_centres(df, col, filter_mode):
    sub = df.dropna(subset=[col]).copy()
    if filter_mode == 'street_grid':
        sub = sub[~sub['Classification'].isin(STREET_GRID_EXCLUDED_TIERS)]
        sub = sub[(sub['Area_km2'] >= 0.09) & (sub['Area_km2'] <= 0.75)]
    elif col == 'carfree_share':
        sub_all = sub[(sub['Classification'] != 'Small Local Centre') & (sub['Area_km2'] >= 0.06) & (sub['Area_km2'] <= 0.85)].sort_values(col).reset_index(drop=True)
        sub_st = sub[(~sub['Classification'].isin(STREET_GRID_EXCLUDED_TIERS)) & (sub['Area_km2'] >= 0.09) & (sub['Area_km2'] <= 0.75)].sort_values(col).reset_index(drop=True)
        return [
            ('Low', sub_all.iloc[int(len(sub_all) * 0.08)]),
            ('Median', sub_st.iloc[int(len(sub_st) * 0.50)]),
            ('High', sub_st.iloc[int(len(sub_st) * 0.92)]),
        ]
    else:
        sub = sub[sub['Classification'] != 'Small Local Centre']
        sub = sub[(sub['Area_km2'] >= 0.06) & (sub['Area_km2'] <= 0.85)]

    sub = sub.sort_values(col).reset_index(drop=True)
    n = len(sub)
    q_indices = [int(n * 0.08), int(n * 0.50), int(n * 0.92)]
    labels = ['Low', 'Median', 'High']
    return [(lbl, sub.iloc[idx]) for lbl, idx in zip(labels, q_indices)]


def plot_panel(ax, row, cand, params, col, highlight_mode):
    ax.set_facecolor(PAGE_BG)
    poly = row.geometry
    core = poly.buffer(params.buffer_m)
    ctx = poly.buffer(params.context_m)

    # Organic radial clip around the retail centre so no rectangular frame appears
    minx, miny, maxx, maxy = (ctx if 'ring' in highlight_mode else core).bounds
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    radius = max(maxx - minx, maxy - miny) * 0.54 + 20.0
    study_circle = shapely.Point(cx, cy).buffer(radius, quad_segs=48)

    fill_col, hi_col, sec_col = PALETTE[col]
    _add_centre_fill(ax, poly, fill_col, alpha=0.38, zorder=2)

    sw = detect_parallel_sidewalks(cand)
    wm = get_walk_mask(cand) & ~sw
    wm_street = wm & (cand['fclass'] != 'service').to_numpy()
    dm = get_drive_mask(cand)
    sm = get_service_mask(cand)
    fc = cand['fclass'].to_numpy()

    geoms = cand.geometry.to_numpy()
    gs = cand['is_grade_sep'].to_numpy()

    bg_segs = _lines_to_segments(shapely.intersection(geoms[wm | dm], study_circle))
    if bg_segs:
        ax.add_collection(LineCollection(bg_segs, colors=NEUTRAL_ROAD, linewidths=0.45, alpha=0.72, zorder=3, rasterized=True))

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
                e_clip = shapely.intersection(g['egeom'], study_circle)
                s_reach = _lines_to_segments(e_clip[ring & reached])
                s_unreach = _lines_to_segments(e_clip[ring & ~reached])
                s_core = _lines_to_segments(e_clip[~ring])
                if s_unreach:
                    ax.add_collection(LineCollection(s_unreach, colors=sec_col, linewidths=1.05, alpha=0.85, zorder=4, rasterized=True))
                if s_reach:
                    ax.add_collection(LineCollection(s_reach, colors=hi_col, linewidths=1.35, alpha=0.95, zorder=5, rasterized=True))
                if s_core:
                    ax.add_collection(LineCollection(s_core, colors='#555555', linewidths=0.95, alpha=0.80, zorder=4, rasterized=True))
    elif highlight_mode == 'arterial':
        art = dm & np.isin(fc, list(ARTERIAL_CLASSES))
        non_art = dm & ~art
        s1 = _lines_to_segments(shapely.intersection(geoms[non_art], study_circle))
        s2 = _lines_to_segments(shapely.intersection(geoms[art], study_circle))
        if s1:
            ax.add_collection(LineCollection(s1, colors=sec_col, linewidths=0.85, alpha=0.75, zorder=4, rasterized=True))
        if s2:
            ax.add_collection(LineCollection(s2, colors=hi_col, linewidths=2.0, alpha=0.95, zorder=6, rasterized=True))
    elif highlight_mode == 'service':
        s_drv = _lines_to_segments(shapely.intersection(geoms[dm], study_circle))
        s_srv = _lines_to_segments(shapely.intersection(geoms[sm], study_circle))
        if s_drv:
            ax.add_collection(LineCollection(s_drv, colors=sec_col, linewidths=0.85, alpha=0.75, zorder=4, rasterized=True))
        if s_srv:
            ax.add_collection(LineCollection(s_srv, colors=hi_col, linewidths=1.55, alpha=0.95, zorder=6, rasterized=True))
    elif highlight_mode == 'carfree':
        cf = wm & np.isin(fc, list(CARFREE_CLASSES))
        shared = wm_street & ~cf
        s_sh = _lines_to_segments(shapely.intersection(geoms[shared], study_circle))
        s_cf = _lines_to_segments(shapely.intersection(geoms[cf], study_circle))
        if s_sh:
            ax.add_collection(LineCollection(s_sh, colors=sec_col, linewidths=0.9, alpha=0.75, zorder=4, rasterized=True))
        if s_cf:
            ax.add_collection(LineCollection(s_cf, colors=hi_col, linewidths=1.85, alpha=0.95, zorder=6, rasterized=True))
    elif highlight_mode == 'betweenness':
        gw = build_consolidated_graph(geoms[wm_street], gs[wm_street], ctx, params.tol_m)
        if gw is not None:
            core_e = shapely.intersects(gw['egeom'], study_circle)
            if core_e.sum() >= 5:
                eb = compute_distance_limited_edge_betweenness(gw, limit_m=params.reach_m)
                eb_sub = eb[core_e]
                geoms_sub = shapely.intersection(gw['egeom'][core_e], study_circle)
                q75 = np.quantile(eb_sub, 0.75) if len(eb_sub) else 0
                spine = eb_sub >= max(q75, 1e-6)
                s_back = _lines_to_segments(geoms_sub[~spine])
                s_spine = _lines_to_segments(geoms_sub[spine])
                if s_back:
                    ax.add_collection(LineCollection(s_back, colors=sec_col, linewidths=0.9, alpha=0.78, zorder=4, rasterized=True))
                if s_spine:
                    ax.add_collection(LineCollection(s_spine, colors=hi_col, linewidths=2.0, alpha=0.95, zorder=6, rasterized=True))
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
                        ax.add_patch(MplPolygon(xy, closed=True, facecolor=fill_col, edgecolor=hi_col, lw=0.8, alpha=0.48, zorder=3))
            st_segs = _lines_to_segments(shapely.intersection(gw_st['egeom'], study_circle))
            if st_segs:
                ax.add_collection(LineCollection(st_segs, colors=sec_col, linewidths=1.15, alpha=0.9, zorder=5, rasterized=True))
    else:
        gw = build_consolidated_graph(geoms[wm_street], gs[wm_street], study_circle, params.tol_m)
        if gw is not None:
            segs = _lines_to_segments(gw['egeom'])
            if segs:
                ax.add_collection(LineCollection(segs, colors=hi_col, linewidths=1.35, alpha=0.92, zorder=5, rasterized=True))
            junc = gw['deg'] >= 3
            if junc.sum() > 0:
                ax.scatter(gw['xy'][junc, 0], gw['xy'][junc, 1], s=10, c='#1b1b1b', alpha=0.75, zorder=6)

    ax.set_xlim(cx - radius * 1.03, cx + radius * 1.03)
    ax.set_ylim(cy - radius * 1.03, cy + radius * 1.03)
    ax.set_aspect('equal', adjustable='box')
    ax.set_axis_off()


def _legend_for_mode(col, highlight_mode):
    fill_col, hi_col, sec_col = PALETTE[col]
    handles = [Patch(facecolor=fill_col, edgecolor='none', alpha=0.42, label='Retail centre footprint')]
    if 'ring' in highlight_mode:
        handles += [
            Line2D([0], [0], color=hi_col, lw=1.8, label='Reachable within 400 m'),
            Line2D([0], [0], color=sec_col, lw=1.4, label='Unreachable (> 400 m)'),
        ]
    elif highlight_mode == 'arterial':
        handles += [
            Line2D([0], [0], color=hi_col, lw=2.0, label='Arterial roads'),
            Line2D([0], [0], color=sec_col, lw=1.1, label='Local streets'),
        ]
    elif highlight_mode == 'service':
        handles += [
            Line2D([0], [0], color=hi_col, lw=1.8, label='Service & car-park lanes'),
            Line2D([0], [0], color=sec_col, lw=1.1, label='Public streets'),
        ]
    elif highlight_mode == 'carfree':
        handles += [
            Line2D([0], [0], color=hi_col, lw=1.9, label='Dedicated pedestrian ways'),
            Line2D([0], [0], color=sec_col, lw=1.1, label='Shared streets'),
        ]
    elif highlight_mode == 'betweenness':
        handles += [
            Line2D([0], [0], color=hi_col, lw=2.0, label='Primary movement corridors (top 25%)'),
            Line2D([0], [0], color=sec_col, lw=1.1, label='Secondary walkable streets'),
        ]
    elif highlight_mode == 'blocks':
        handles += [
            Patch(facecolor=fill_col, edgecolor=hi_col, alpha=0.5, label='Enclosed urban street blocks'),
            Line2D([0], [0], color=sec_col, lw=1.3, label='Consolidated street network'),
        ]
    else:
        handles += [
            Line2D([0], [0], color=hi_col, lw=1.5, label='Consolidated street network'),
            Line2D([0], [0], marker='o', color='none', markerfacecolor='#1b1b1b', markersize=5, label='Street junction (degree ≥ 3)'),
        ]
    return handles


# 3. Generate Flagship UK Pop-Out Overview Map ----------------------------

def generate_uk_overview_popout_map(gdf, roads, rtree, params, exemplars):
    fig = plt.figure(figsize=(22, 13.5), dpi=220, facecolor=PAGE_BG)
    fig.text(
        0.5, 0.968,
        'UK Retail Centre Street-Network Morphologies',
        ha='center', va='top', fontsize=26, weight='bold',
        family=FONT_FAMILY, color=TEXT_DARK
    )

    # Central UK basemap panel
    main_ax = fig.add_axes([0.305, 0.06, 0.39, 0.85], facecolor=OVERVIEW_BG, zorder=1)
    if UK_BASEMAP_GPKG.exists():
        uk_outline = gpd.read_file(UK_BASEMAP_GPKG, layer='uk_outline').to_crs(27700)
        uk_lads = gpd.read_file(UK_BASEMAP_GPKG, layer='uk_lads').to_crs(27700)
        land_patches = []
        for g in uk_outline.geometry:
            for p in shapely.get_parts(g):
                if shapely.get_type_id(p) == 3:
                    land_patches.append(MplPolygon(np.asarray(p.exterior.coords), closed=True))
        if land_patches:
            main_ax.add_collection(
                PatchCollection(land_patches, facecolor=LAND_FILL, edgecolor='#b8b1a3', linewidth=0.45, zorder=2, rasterized=True)
            )
        lad_segs = []
        for g in uk_lads.geometry.boundary:
            lad_segs.extend(_lines_to_segments([g]))
        if lad_segs:
            main_ax.add_collection(
                LineCollection(lad_segs, colors=LAD_STROKE, linewidths=0.25, alpha=0.65, zorder=3, rasterized=True)
            )

    # All 9,623 UK retail centres as subtle background points on the UK basemap
    pts = shapely.centroid(gdf.geometry.to_numpy())
    px = shapely.get_x(pts)
    py = shapely.get_y(pts)
    main_ax.scatter(px, py, s=1.8, c='#7c8896', alpha=0.38, linewidths=0, zorder=4, rasterized=True)

    # Highlight the 11 exemplar centres on the UK map
    for idx_num, item in enumerate(exemplars, 1):
        col, title, fmt, highlight_mode, row = item
        pt = row.geometry.centroid
        fill_col, hi_col, _ = PALETTE[col]
        main_ax.scatter([pt.x], [pt.y], s=58, facecolor=hi_col, edgecolor='white', linewidth=1.3, zorder=10)

    main_ax.set_xlim(-65000, 670000)
    main_ax.set_ylim(5000, 1225000)
    main_ax.set_aspect('equal', adjustable='box')
    main_ax.set_axis_off()

    # Arrange 6 pop-outs on the left (3 rows x 2 cols) and 5 pop-outs on the right (3 rows: 2, 2, 1 centered)
    left_positions = [
        (0.025, 0.655), (0.162, 0.655),
        (0.025, 0.365), (0.162, 0.365),
        (0.025, 0.075), (0.162, 0.075),
    ]
    right_positions = [
        (0.710, 0.655), (0.847, 0.655),
        (0.710, 0.365), (0.847, 0.365),
        (0.778, 0.075),
    ]
    all_positions = left_positions + right_positions
    panel_w, panel_h = 0.128, 0.215

    for (col, title, fmt, highlight_mode, row), (x0, y0) in zip(exemplars, all_positions):
        fill_col, hi_col, _ = PALETTE[col]
        ax = fig.add_axes([x0, y0, panel_w, panel_h], facecolor=PAGE_BG, zorder=5)
        ctx = row.geometry.buffer(params.context_m)
        idx = rtree.query(ctx, predicate='intersects')
        cand = roads.iloc[idx].reset_index(drop=True)
        plot_panel(ax, row, cand, params, col, highlight_mode)

        val_str = fmt.format(row[col])
        short_name = _clean_label_name(row['RC_Name'])
        ax.text(
            0.5, 1.04, title,
            transform=ax.transAxes, ha='center', va='bottom',
            fontsize=9.8, weight='bold', family=FONT_FAMILY, color=hi_col, clip_on=False
        )
        ax.text(
            0.5, -0.03,
            f"{textwrap.fill(short_name, width=22)}\n({val_str})",
            transform=ax.transAxes, ha='center', va='top',
            fontsize=9.0, weight='bold', family=FONT_FAMILY, color=TEXT_DARK, clip_on=False
        )

    fig.savefig(OVERVIEW_FIG, bbox_inches='tight', facecolor=PAGE_BG)
    plt.close(fig)
    print(f'Saved UK overview pop-out figure: {OVERVIEW_FIG}')


def generate_methodological_controls_figure(gdf, roads, rtree, params):
    """Render a 4-panel step-by-step construction of the methodological controls."""
    qa_fig_path = FIG_DIR / 'visual_qa_sidewalk_consolidation.png'
    row = gdf[gdf['RC_ID'] == 88].iloc[0]  # Milsom Street & Westgate Street, Bath
    poly = row.geometry
    core = poly.buffer(params.buffer_m)
    minx, miny, maxx, maxy = core.bounds
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    radius = max(maxx - minx, maxy - miny) * 0.54 + 15.0
    study_circle = shapely.Point(cx, cy).buffer(radius, quad_segs=48)

    idx = rtree.query(poly.buffer(params.context_m), predicate='intersects')
    cand = roads.iloc[idx].reset_index(drop=True)
    geoms = cand.geometry.to_numpy()
    gs = cand['is_grade_sep'].to_numpy()

    wm_raw = get_walk_mask(cand)
    sw = detect_parallel_sidewalks(cand)
    wm_nosw = wm_raw & ~sw
    srv_mask = wm_nosw & (cand['fclass'] == 'service').to_numpy()
    wm_street = wm_nosw & ~srv_mask

    g1 = build_consolidated_graph(geoms[wm_raw], gs[wm_raw], core, 0.5)
    g2 = build_consolidated_graph(geoms[wm_nosw], gs[wm_nosw], core, 0.5)
    g3 = build_consolidated_graph(geoms[wm_street], gs[wm_street], core, 0.5)
    g4 = build_consolidated_graph(geoms[wm_street], gs[wm_street], core, params.tol_m)

    fig, axes = plt.subplots(1, 4, figsize=(18.0, 5.8), dpi=220, facecolor=PAGE_BG)

    steps = [
        ('1 · Raw OpenStreetMap Network', '#5975a4', g1),
        ('2 · Parallel Sidewalk Filter', '#D55E00', g2),
        ('3 · Car-Park & Service Separation', '#A63C36', g3),
        ('4 · 10 m Junction Consolidation', '#1d4e89', g4),
    ]

    for step_idx, (ax, (step_title, title_col, g_step)) in enumerate(zip(axes, steps)):
        ax.set_facecolor(PAGE_BG)
        _add_centre_fill(ax, poly, '#269989', alpha=0.26, zorder=2)

        if step_idx == 0:
            s_raw = _lines_to_segments(shapely.intersection(geoms[wm_raw], study_circle))
            if s_raw:
                ax.add_collection(LineCollection(s_raw, colors='#5975a4', linewidths=0.95, alpha=0.88, zorder=4, rasterized=True))
            junc = g1['deg'] >= 3
            pts = g1['xy'][junc]
            in_c = shapely.contains_xy(study_circle, pts[:, 0], pts[:, 1])
            ax.scatter(pts[in_c, 0], pts[in_c, 1], s=7.5, c='#2b2b2b', alpha=0.85, zorder=6, edgecolors='none')

        elif step_idx == 1:
            s_keep = _lines_to_segments(shapely.intersection(geoms[wm_nosw], study_circle))
            s_sw = _lines_to_segments(shapely.intersection(geoms[wm_raw & sw], study_circle))
            if s_keep:
                ax.add_collection(LineCollection(s_keep, colors='#2b5c8f', linewidths=0.95, alpha=0.82, zorder=4, rasterized=True))
            if s_sw:
                ax.add_collection(LineCollection(s_sw, colors='#D55E00', linewidths=1.35, alpha=0.95, zorder=5, rasterized=True))
            junc = g2['deg'] >= 3
            pts = g2['xy'][junc]
            in_c = shapely.contains_xy(study_circle, pts[:, 0], pts[:, 1])
            ax.scatter(pts[in_c, 0], pts[in_c, 1], s=7.5, c='#2b2b2b', alpha=0.80, zorder=6, edgecolors='none')

        elif step_idx == 2:
            s_sw = _lines_to_segments(shapely.intersection(geoms[wm_raw & sw], study_circle))
            s_st = _lines_to_segments(shapely.intersection(geoms[wm_street], study_circle))
            s_srv = _lines_to_segments(shapely.intersection(geoms[srv_mask], study_circle))
            if s_sw:
                ax.add_collection(LineCollection(s_sw, colors=NEUTRAL_ROAD, linewidths=0.55, alpha=0.65, zorder=3, rasterized=True))
            if s_st:
                ax.add_collection(LineCollection(s_st, colors='#2b5c8f', linewidths=1.0, alpha=0.85, zorder=4, rasterized=True))
            if s_srv:
                ax.add_collection(LineCollection(s_srv, colors='#A63C36', linewidths=1.45, alpha=0.95, zorder=5, rasterized=True))
            junc = g3['deg'] >= 3
            pts = g3['xy'][junc]
            in_c = shapely.contains_xy(study_circle, pts[:, 0], pts[:, 1])
            ax.scatter(pts[in_c, 0], pts[in_c, 1], s=8.0, c='#2b2b2b', alpha=0.82, zorder=6, edgecolors='none')

        elif step_idx == 3:
            s_removed = _lines_to_segments(shapely.intersection(geoms[wm_raw & ~wm_street], study_circle))
            s_ctx_st = _lines_to_segments(shapely.intersection(geoms[wm_street], study_circle.difference(core)))
            if s_removed:
                ax.add_collection(LineCollection(s_removed, colors=NEUTRAL_ROAD, linewidths=0.5, alpha=0.55, zorder=3, rasterized=True))
            if s_ctx_st:
                ax.add_collection(LineCollection(s_ctx_st, colors='#8fa3b8', linewidths=0.80, alpha=0.70, zorder=3, rasterized=True))
            ground = geoms[wm_street & ~gs]
            clipped = shapely.intersection(ground, core)
            merged = shapely.line_merge(shapely.union_all(clipped))
            polys = np.array(list(polygonize(merged)), dtype=object)
            if len(polys):
                areas = shapely.area(polys)
                valid_blocks = polys[(areas >= 100.0) & (areas <= 100000.0)]
                patches = []
                for bp in valid_blocks:
                    for part in shapely.get_parts(bp):
                        if shapely.get_type_id(part) == 3:
                            patches.append(MplPolygon(np.asarray(part.exterior.coords), closed=True))
                if patches:
                    pc = PatchCollection(patches, facecolor='#E69F00', edgecolor='#b85d19', linewidth=0.55, alpha=0.42, zorder=4)
                    ax.add_collection(pc)
            e_clip = shapely.intersection(g4['egeom'], study_circle)
            s_cons = _lines_to_segments(e_clip)
            if s_cons:
                ax.add_collection(LineCollection(s_cons, colors='#1d4e89', linewidths=1.35, alpha=0.95, zorder=5, rasterized=True))
            junc = g4['deg'] >= 3
            pts = g4['xy'][junc]
            in_c = shapely.contains_xy(study_circle, pts[:, 0], pts[:, 1])
            ax.scatter(pts[in_c, 0], pts[in_c, 1], s=13.0, c='#1b1b1b', alpha=0.92, zorder=6, edgecolors='none')


        pad = radius * 0.04
        ax.set_xlim(cx - radius - pad, cx + radius + pad)
        ax.set_ylim(cy - radius - pad, cy + radius + pad)
        ax.set_aspect('equal')
        ax.set_axis_off()

        n_junc = int((g_step['deg'] >= 3).sum())
        n_edges = len(g_step['eu'])
        ax.text(
            0.5, 1.03,
            step_title,
            transform=ax.transAxes, ha='center', va='bottom',
            fontsize=11.5, weight='bold', family=FONT_FAMILY, color=title_col, clip_on=False
        )
        ax.text(
            0.5, -0.03,
            f"{n_junc:,} junctions · {n_edges:,} edges",
            transform=ax.transAxes, ha='center', va='top',
            fontsize=11.0, weight='bold', family=FONT_FAMILY, color=TEXT_DARK, clip_on=False
        )

    handles = [
        Patch(facecolor='#269989', edgecolor='none', alpha=0.35, label='Retail centre footprint (Bath City Centre)'),
        Line2D([0], [0], color='#D55E00', lw=2.0, label='Parallel sidewalks removed (≤12 m, ≤25°)'),
        Line2D([0], [0], color='#A63C36', lw=2.0, label='Service & car-park loops separated'),
        Line2D([0], [0], color='#1d4e89', lw=2.0, label='Consolidated street network (10 m)'),
        Line2D([0], [0], marker='o', color='none', markerfacecolor='#1b1b1b', markersize=5.5, label='True street junctions (deg ≥ 3)'),
        Patch(facecolor='#E69F00', edgecolor='#b85d19', alpha=0.45, label='Enclosed urban blocks'),
    ]
    fig.legend(
        handles=handles,
        loc='lower center',
        ncol=len(handles),
        frameon=False,
        prop={'family': FONT_FAMILY, 'size': 9.8},
        bbox_to_anchor=(0.5, 0.01)
    )
    fig.suptitle(
        'Step-by-Step Street-Network Graph Construction',
        fontsize=20, fontweight='bold', family=FONT_FAMILY,
        color=TEXT_DARK, y=0.97
    )
    fig.subplots_adjust(left=0.015, right=0.985, bottom=0.13, top=0.82, wspace=0.04)
    fig.savefig(qa_fig_path, dpi=220, facecolor=PAGE_BG, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved methodological controls figure: {qa_fig_path}')


# 4. Generate All 11 Indicator Profile Figures ----------------------------

def main():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(IN_CSV)
    centres = gpd.read_file(CENTRES_PATH)[['RC_ID', 'geometry']].to_crs(27700)
    gdf = centres.merge(df, on='RC_ID', how='left')

    roads = gpd.read_parquet(ROADS_PARQUET)
    rtree = STRtree(roads.geometry.to_numpy())
    params = NetworkParams()

    example_records = []
    overview_exemplars = []

    for col, fname, title, fmt, filter_mode, highlight_mode, exemplar_side in INDICATOR_SPECS:
        picks = pick_three_centres(gdf, col, filter_mode)
        exemplar_row = picks[0][1] if exemplar_side == 'low' else picks[2][1]
        overview_exemplars.append((col, title, fmt, highlight_mode, exemplar_row))

        fill_col, hi_col, _ = PALETTE[col]
        fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.6), dpi=220, facecolor=PAGE_BG)

        for ax, (band_label, row) in zip(axes, picks):
            ctx = row.geometry.buffer(params.context_m)
            idx = rtree.query(ctx, predicate='intersects')
            cand = roads.iloc[idx].reset_index(drop=True)
            plot_panel(ax, row, cand, params, col, highlight_mode)

            val_str = fmt.format(row[col])
            short_name = _clean_label_name(row['RC_Name'])

            ax.text(
                0.5, 1.03,
                f"{band_label} · {val_str}",
                transform=ax.transAxes, ha='center', va='bottom',
                fontsize=11.5, weight='bold', family=FONT_FAMILY, color=hi_col, clip_on=False
            )
            ax.text(
                0.5, -0.03,
                short_name,
                transform=ax.transAxes, ha='center', va='top',
                fontsize=11.5, weight='bold', family=FONT_FAMILY, color=TEXT_DARK, clip_on=False
            )

            example_records.append({
                'indicator': col,
                'profile_band': band_label,
                'RC_ID': row['RC_ID'],
                'RC_Name': row['RC_Name'],
                'Classification': row['Classification'],
                'Region_NM': row['Region_NM'],
                'Area_km2': round(float(row['Area_km2']), 3),
                'value': float(row[col]),
                'formatted_value': val_str,
                'figure_file': f'Output Data/Figures/{fname}'
            })

        handles = _legend_for_mode(col, highlight_mode)
        fig.legend(
            handles=handles,
            loc='lower center',
            ncol=len(handles),
            frameon=False,
            prop={'family': FONT_FAMILY, 'size': 10.5},
            bbox_to_anchor=(0.5, 0.01)
        )
        fig.suptitle(
            title,
            fontsize=20, fontweight='bold', family=FONT_FAMILY,
            color=TEXT_DARK, y=0.97
        )
        fig.subplots_adjust(left=0.02, right=0.98, bottom=0.13, top=0.82, wspace=0.06)
        out_path = FIG_DIR / fname
        fig.savefig(out_path, dpi=220, facecolor=PAGE_BG, bbox_inches='tight')
        plt.close(fig)
        print(f'Saved {out_path}')

    generate_uk_overview_popout_map(gdf, roads, rtree, params, overview_exemplars)
    generate_methodological_controls_figure(gdf, roads, rtree, params)

    ex_df = pd.DataFrame(example_records)
    ex_df.to_csv(EXAMPLES_CSV, index=False)
    print(f'Saved example lookup table: {EXAMPLES_CSV}')


if __name__ == '__main__':
    main()

