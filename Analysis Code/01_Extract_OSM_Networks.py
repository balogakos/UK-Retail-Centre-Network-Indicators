## Extracting OpenStreetMap Highway Networks for UK Retail Centres

import argparse
from pathlib import Path
import re
import subprocess
import tempfile
import geopandas as gpd
import pandas as pd
import shapely


# 1. Default Repository-Relative Paths & Tag Configuration ----------------

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PBF = REPO_ROOT / 'Input Data' / 'united-kingdom-latest.osm.pbf'
DEFAULT_CENTRES = REPO_ROOT / 'Input Data' / 'retailcentre_bounds_uk.gpkg'
DEFAULT_OUT_PARQUET = REPO_ROOT / 'Input Data' / 'uk_roads_400m.parquet'

KEEP_CLASSES = {
    'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link',
    'secondary', 'secondary_link', 'tertiary', 'tertiary_link', 'residential',
    'unclassified', 'living_street', 'service', 'pedestrian', 'footway', 'path', 'steps'
}

TAG_KEYS = (
    'footway', 'service', 'access', 'foot', 'motor_vehicle',
    'oneway', 'bridge', 'tunnel', 'layer'
)
TAG_RE = {k: re.compile(rf'"{k}"=>"([^"]*)"') for k in TAG_KEYS}


# 2. Extract Highway Ways & Filter to 400 m Context Buffers ---------------

def extract_tag(series, key):
    return series.str.extract(TAG_RE[key], expand=False).fillna('')


def main():
    parser = argparse.ArgumentParser(description='Extract OSM highway ways within 400 m of UK retail centres.')
    parser.add_argument('--pbf', type=Path, default=DEFAULT_PBF, help='Path to united-kingdom-latest.osm.pbf')
    parser.add_argument('--centres', type=Path, default=DEFAULT_CENTRES, help='Path to retailcentre_bounds_uk.gpkg')
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT_PARQUET, help='Output Parquet path')
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    tmp_pbf = Path(tempfile.gettempdir()) / 'uk_highways_filtered.osm.pbf'
    if not tmp_pbf.exists():
        subprocess.run(
            ['osmium', 'tags-filter', str(args.pbf), 'w/highway', '-o', str(tmp_pbf), '--overwrite'],
            check=True
        )

    centres = gpd.read_file(args.centres).to_crs(27700)
    mask_27700 = shapely.union_all(shapely.buffer(centres.geometry.to_numpy(), 450.0))
    mask_4326 = gpd.GeoSeries([mask_27700], crs=27700).to_crs(4326).iloc[0]

    gdf = gpd.read_file(
        tmp_pbf,
        layer='lines',
        mask=mask_4326,
        columns=['osm_id', 'highway', 'other_tags', 'geometry']
    )
    gdf = gdf[gdf['highway'].isin(KEEP_CLASSES)].copy()
    gdf = gdf.to_crs(27700)

    tree = shapely.STRtree(gdf.geometry.to_numpy())
    bufs = shapely.buffer(centres.geometry.to_numpy(), 420.0)
    keep_idx = pd.unique(tree.query(bufs, predicate='intersects')[1])
    gdf = gdf.iloc[keep_idx].reset_index(drop=True)

    # 3. Parse Ancillary OSM Tags (Sidewalks, Service Types, One-Way, Grade Separation)
    ot = gdf['other_tags'].fillna('')
    out = gpd.GeoDataFrame(
        {
            'osm_id': gdf['osm_id'].astype(str),
            'fclass': gdf['highway'].astype(str),
            'footway': extract_tag(ot, 'footway'),
            'service': extract_tag(ot, 'service'),
            'access': extract_tag(ot, 'access'),
            'foot': extract_tag(ot, 'foot'),
            'motor_vehicle': extract_tag(ot, 'motor_vehicle'),
            'oneway': extract_tag(ot, 'oneway'),
        },
        geometry=gdf.geometry,
        crs=27700
    )
    bridge = extract_tag(ot, 'bridge')
    tunnel = extract_tag(ot, 'tunnel')
    layer = extract_tag(ot, 'layer')
    out['is_grade_sep'] = (
        ~bridge.isin(['', 'no']) |
        ~tunnel.isin(['', 'no']) |
        ~layer.isin(['', '0'])
    )

    out.to_parquet(args.out, index=False)
    print(f'Saved {len(out):,} highway segments to {args.out}')


if __name__ == '__main__':
    main()
