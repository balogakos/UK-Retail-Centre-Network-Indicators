"""Generate publication figures for walk_reach and drive_reach catchment indicators.

Outputs:
  - Output Data/Figures/profile_01_walk_reach.png
  - Output Data/Figures/profile_01_walk_reach_400.png
  - Output Data/Figures/profile_02_drive_reach.png
  - Output Data/Figures/profile_02_drive_reach_400.png
  - Updates Output Data/Indicator_Profile_Examples.csv
"""

from pathlib import Path
import re
import geopandas as gpd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection, PatchCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Polygon as MplPolygon
import numpy as np
import pandas as pd
import shapely
from shapely import STRtree

REPO_ROOT = Path(__file__).resolve().parents[1]
CENTRES_PATH = REPO_ROOT / 'Input Data' / 'retailcentre_bounds_uk.gpkg'
ROADS_DIR = REPO_ROOT / 'Input Data' / 'exemplar_roads'
WALK_PATH = REPO_ROOT / 'Input Data' / 'walk_catchments.gpkg'
DRIVE_PATH = REPO_ROOT / 'Input Data' / 'drive_catchments.gpkg'
CSV_PATH = REPO_ROOT / 'Output Data' / 'UK_Retail_Centre_Network_Indicators.csv'
FIG_DIR = REPO_ROOT / 'Output Data' / 'Figures'
EXAMPLES_CSV = REPO_ROOT / 'Output Data' / 'Indicator_Profile_Examples.csv'

PAGE_BG = '#0d1117'
TEXT_LIGHT = '#f0f6fc'
TEXT_MUTED = '#8b949e'
NEUTRAL_ROAD = '#2e353f'
FONT_FAMILY = 'Times New Roman'


def _clean_label_name(rc_name):
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


def _add_polygon_patches(ax, geom, facecolor, edgecolor, linewidth=1.2, alpha=0.4, zorder=3):
    patches = []
    for part in shapely.get_parts(geom):
        if shapely.get_type_id(part) == 3:
            coords = np.asarray(part.exterior.coords)
            patches.append(MplPolygon(coords, closed=True))
    if patches:
        pc = PatchCollection(
            patches,
            facecolor=facecolor,
            edgecolor=edgecolor,
            linewidth=linewidth,
            alpha=alpha,
            zorder=zorder
        )
        ax.add_collection(pc)


def plot_catchment_panel(ax, centre_row, catchment_geom, roads_gdf,
                         band_label, title_color, fill_col, edge_col,
                         centre_fill, centre_edge, is_drive=False):
    ax.set_facecolor(PAGE_BG)
    c_geom = centre_row['geometry']

    minx, miny, maxx, maxy = catchment_geom.bounds
    cx, cy = (minx + maxx) / 2.0, (miny + maxy) / 2.0
    span = max(maxx - minx, maxy - miny)
    radius = span * 0.54 + 20.0
    study_circle = shapely.Point(cx, cy).buffer(radius, quad_segs=48)

    # 1. Road networks
    if roads_gdf is not None and len(roads_gdf) > 0:
        cand_geoms = roads_gdf.geometry.to_numpy()
        clipped = shapely.intersection(cand_geoms, study_circle)
        valid_mask = ~shapely.is_empty(clipped)
        clipped = clipped[valid_mask]

        if len(clipped) > 0:
            inside_mask = shapely.intersects(clipped, catchment_geom)

            # Contextual roads outside catchment
            bg_segs = _lines_to_segments(clipped[~inside_mask])
            if bg_segs:
                ax.add_collection(LineCollection(bg_segs, colors=NEUTRAL_ROAD, linewidths=0.65, alpha=0.75, zorder=2, rasterized=True))

            # Reachable roads inside catchment
            reach_segs = _lines_to_segments(clipped[inside_mask])
            if reach_segs:
                lw = 1.35 if not is_drive else 1.45
                hi_col = '#22d3ee' if not is_drive else '#38bdf8'
                ax.add_collection(LineCollection(reach_segs, colors=hi_col, linewidths=lw, alpha=0.96, zorder=4, rasterized=True))

    # 2. Catchment polygon with translucent fill and crisp boundary
    _add_polygon_patches(ax, catchment_geom, facecolor=fill_col, edgecolor=edge_col,
                         linewidth=1.6, alpha=0.24, zorder=3)

    # 3. Retail centre footprint
    _add_polygon_patches(ax, c_geom, facecolor=centre_fill, edgecolor=centre_edge,
                         linewidth=1.3, alpha=0.90, zorder=5)

    pad = radius * 0.03
    ax.set_xlim(cx - radius - pad, cx + radius + pad)
    ax.set_ylim(cy - radius - pad, cy + radius + pad)
    ax.set_aspect('equal')
    ax.set_axis_off()

    val_str = f"{band_label} · {centre_row['val']:.2f} ({int(centre_row['time_min'])} min)"
    short_name = _clean_label_name(centre_row['RC_Name'])

    ax.text(
        0.5, 1.03,
        val_str,
        transform=ax.transAxes, ha='center', va='bottom',
        fontsize=11.5, weight='bold', family=FONT_FAMILY, color=title_color, clip_on=False
    )
    ax.text(
        0.5, -0.03,
        short_name,
        transform=ax.transAxes, ha='center', va='top',
        fontsize=11.5, weight='bold', family=FONT_FAMILY, color=TEXT_LIGHT, clip_on=False
    )


def generate_walk_figure(df, centres_gdf, walk_gdf):
    out_path = FIG_DIR / 'profile_01_walk_reach_catchment.png'

    exemplars = [
        ('Low', 6019, 'peel_walk.parquet'),
        ('Median', 754, 'stony_stratford_walk.parquet'),
        ('High', 54, 'bradford_walk.parquet')
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.6), dpi=220, facecolor=PAGE_BG)

    for ax, (band_label, rcid, road_file) in zip(axes, exemplars):
        c_row = centres_gdf[centres_gdf['RC_ID'] == rcid].iloc[0].to_dict()
        df_row = df[df['RC_ID'] == rcid].iloc[0]
        c_row['val'] = float(df_row['walk_reach'])
        c_row['time_min'] = float(df_row['walk_time_min'])
        c_row['RC_Name'] = df_row['RC_Name']
        c_row['geometry'] = centres_gdf[centres_gdf['RC_ID'] == rcid].geometry.iloc[0]

        w_geom = walk_gdf[walk_gdf['RC_ID'] == rcid].geometry.iloc[0]

        roads_path = ROADS_DIR / road_file
        roads_gdf = gpd.read_parquet(roads_path) if roads_path.exists() else None

        plot_catchment_panel(
            ax=ax,
            centre_row=c_row,
            catchment_geom=w_geom,
            roads_gdf=roads_gdf,
            band_label=band_label,
            title_color='#22d3ee',
            fill_col='#0284c7',
            edge_col='#22d3ee',
            centre_fill='#38bdf8',
            centre_edge='#ffffff',
            is_drive=False
        )

    handles = [
        Patch(facecolor='#38bdf8', edgecolor='#ffffff', alpha=0.90, label='Retail centre footprint'),
        Patch(facecolor='#0284c7', edgecolor='#22d3ee', alpha=0.35, label='Walkable network isochrone'),
        Line2D([0], [0], color='#22d3ee', lw=2.0, label='Reachable street network'),
        Line2D([0], [0], color=NEUTRAL_ROAD, lw=1.2, label='Contextual street network'),
    ]
    fig.legend(
        handles=handles,
        loc='lower center',
        ncol=len(handles),
        frameon=False,
        prop={'family': FONT_FAMILY, 'size': 10.5},
        labelcolor=TEXT_MUTED,
        bbox_to_anchor=(0.5, 0.01)
    )
    fig.suptitle(
        'Walkable Catchment Reach (Directness Ratio)',
        fontsize=20, fontweight='bold', family=FONT_FAMILY,
        color=TEXT_LIGHT, y=0.97
    )
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.13, top=0.82, wspace=0.06)

    fig.savefig(out_path, dpi=220, facecolor=PAGE_BG, bbox_inches='tight')
    fig.savefig(FIG_DIR / 'profile_01_walk_reach.png', dpi=220, facecolor=PAGE_BG, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved walk profile: {out_path}')


def generate_drive_figure(df, centres_gdf, drive_gdf):
    out_path = FIG_DIR / 'profile_02_drive_reach_catchment.png'

    exemplars = [
        ('Low', 6019, 'peel_drive.parquet'),
        ('Median', 183, 'derry_drive.parquet'),
        ('High', 139, 'bristol_drive.parquet')
    ]

    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.6), dpi=220, facecolor=PAGE_BG)

    for ax, (band_label, rcid, road_file) in zip(axes, exemplars):
        c_row = centres_gdf[centres_gdf['RC_ID'] == rcid].iloc[0].to_dict()
        df_row = df[df['RC_ID'] == rcid].iloc[0]
        c_row['val'] = float(df_row['drive_reach'])
        c_row['time_min'] = float(df_row['drive_time_min'])
        c_row['RC_Name'] = df_row['RC_Name']
        c_row['geometry'] = centres_gdf[centres_gdf['RC_ID'] == rcid].geometry.iloc[0]

        d_geom = drive_gdf[drive_gdf['RC_ID'] == rcid].geometry.iloc[0]

        roads_path = ROADS_DIR / road_file
        roads_gdf = gpd.read_parquet(roads_path) if roads_path.exists() else None

        plot_catchment_panel(
            ax=ax,
            centre_row=c_row,
            catchment_geom=d_geom,
            roads_gdf=roads_gdf,
            band_label=band_label,
            title_color='#38bdf8',
            fill_col='#1e3a8a',
            edge_col='#38bdf8',
            centre_fill='#fb7185',
            centre_edge='#ffffff',
            is_drive=True
        )

    handles = [
        Patch(facecolor='#fb7185', edgecolor='#ffffff', alpha=0.90, label='Retail centre footprint'),
        Patch(facecolor='#1e3a8a', edgecolor='#38bdf8', alpha=0.35, label='Drivable network isochrone'),
        Line2D([0], [0], color='#38bdf8', lw=2.0, label='Reachable road network'),
        Line2D([0], [0], color=NEUTRAL_ROAD, lw=1.2, label='Contextual road network'),
    ]
    fig.legend(
        handles=handles,
        loc='lower center',
        ncol=len(handles),
        frameon=False,
        prop={'family': FONT_FAMILY, 'size': 10.5},
        labelcolor=TEXT_MUTED,
        bbox_to_anchor=(0.5, 0.01)
    )
    fig.suptitle(
        'Motorised Road Catchment Reach (Directness Ratio)',
        fontsize=20, fontweight='bold', family=FONT_FAMILY,
        color=TEXT_LIGHT, y=0.97
    )
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.13, top=0.82, wspace=0.06)

    fig.savefig(out_path, dpi=220, facecolor=PAGE_BG, bbox_inches='tight')
    fig.savefig(FIG_DIR / 'profile_02_drive_reach.png', dpi=220, facecolor=PAGE_BG, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved drive profile: {out_path}')


def update_examples_csv(df):
    ex_df = pd.read_csv(EXAMPLES_CSV)

    new_rows = [
        {
            'indicator': 'walk_reach',
            'profile_band': 'Low',
            'RC_ID': 6019,
            'RC_Name': 'Peel Retail Park; Sunderland (North East; England)',
            'Classification': 'Small Retail Park',
            'Region_NM': 'North East',
            'Area_km2': 0.091,
            'value': float(df[df['RC_ID'] == 6019]['walk_reach'].iloc[0]),
            'formatted_value': f"{df[df['RC_ID'] == 6019]['walk_reach'].iloc[0]:.2f}",
            'figure_file': 'Output Data/Figures/profile_01_walk_reach_catchment.png'
        },
        {
            'indicator': 'walk_reach',
            'profile_band': 'Median',
            'RC_ID': 754,
            'RC_Name': 'High Street; Stony Stratford; Milton Keynes (South East; England)',
            'Classification': 'District Centre',
            'Region_NM': 'South East',
            'Area_km2': 0.108,
            'value': float(df[df['RC_ID'] == 754]['walk_reach'].iloc[0]),
            'formatted_value': f"{df[df['RC_ID'] == 754]['walk_reach'].iloc[0]:.2f}",
            'figure_file': 'Output Data/Figures/profile_01_walk_reach_catchment.png'
        },
        {
            'indicator': 'walk_reach',
            'profile_band': 'High',
            'RC_ID': 54,
            'RC_Name': 'Bradford; Bradford (Yorkshire and The Humber; England)',
            'Classification': 'Major Town Centre',
            'Region_NM': 'Yorkshire and The Humber',
            'Area_km2': 0.453,
            'value': float(df[df['RC_ID'] == 54]['walk_reach'].iloc[0]),
            'formatted_value': f"{df[df['RC_ID'] == 54]['walk_reach'].iloc[0]:.2f}",
            'figure_file': 'Output Data/Figures/profile_01_walk_reach_catchment.png'
        },
        {
            'indicator': 'drive_reach',
            'profile_band': 'Low',
            'RC_ID': 6019,
            'RC_Name': 'Peel Retail Park; Sunderland (North East; England)',
            'Classification': 'Small Retail Park',
            'Region_NM': 'North East',
            'Area_km2': 0.091,
            'value': float(df[df['RC_ID'] == 6019]['drive_reach'].iloc[0]),
            'formatted_value': f"{df[df['RC_ID'] == 6019]['drive_reach'].iloc[0]:.2f}",
            'figure_file': 'Output Data/Figures/profile_02_drive_reach_catchment.png'
        },
        {
            'indicator': 'drive_reach',
            'profile_band': 'Median',
            'RC_ID': 183,
            'RC_Name': 'Derry/Londonderry; Derry City and Strabane (Northern Ireland)',
            'Classification': 'Major Town Centre',
            'Region_NM': 'Northern Ireland',
            'Area_km2': 0.271,
            'value': float(df[df['RC_ID'] == 183]['drive_reach'].iloc[0]),
            'formatted_value': f"{df[df['RC_ID'] == 183]['drive_reach'].iloc[0]:.2f}",
            'figure_file': 'Output Data/Figures/profile_02_drive_reach_catchment.png'
        },
        {
            'indicator': 'drive_reach',
            'profile_band': 'High',
            'RC_ID': 139,
            'RC_Name': 'Old City (Bristol City Centre); City of Bristol (South West; England)',
            'Classification': 'Regional Centre',
            'Region_NM': 'South West',
            'Area_km2': 0.177,
            'value': float(df[df['RC_ID'] == 139]['drive_reach'].iloc[0]),
            'formatted_value': f"{df[df['RC_ID'] == 139]['drive_reach'].iloc[0]:.2f}",
            'figure_file': 'Output Data/Figures/profile_02_drive_reach_catchment.png'
        },
    ]

    remaining = ex_df[~ex_df['indicator'].isin(['walk_reach', 'drive_reach', 'walk_reach_400', 'drive_reach_400'])].to_dict('records')
    baseline_rows = ex_df[ex_df['indicator'].isin(['walk_reach_400', 'drive_reach_400'])].to_dict('records')

    updated = pd.DataFrame(new_rows + remaining + baseline_rows)
    updated.to_csv(EXAMPLES_CSV, index=False)
    print(f'Updated {EXAMPLES_CSV}')


def main():
    print('Loading datasets...')
    df = pd.read_csv(CSV_PATH)
    centres = gpd.read_file(CENTRES_PATH)[['RC_ID', 'RC_Name', 'Classification', 'geometry']].to_crs(27700)
    centres['RC_ID'] = centres['RC_ID'].astype(int)

    print('Loading walk catchments...')
    walk = gpd.read_file(WALK_PATH).to_crs(27700)
    walk['RC_ID'] = walk['RC_ID'].astype(int)

    print('Loading drive catchments...')
    drive = gpd.read_file(DRIVE_PATH).to_crs(27700)
    drive['RC_ID'] = drive['RC_ID'].astype(int)

    print('Generating walk catchment figure with road networks...')
    generate_walk_figure(df, centres, walk)

    print('Generating drive catchment figure with road networks...')
    generate_drive_figure(df, centres, drive)

    print('Updating examples lookup CSV...')
    update_examples_csv(df)
    print('All catchment figures and examples updated successfully!')


if __name__ == '__main__':
    main()
