## Extracting OpenStreetMap Highway Networks for UK Retail Centres

from pathlib import Path
import re
import subprocess
import geopandas as gpd
import pandas as pd
import shapely


# 1. File Paths & Tag Configuration ---------------------------------------

PBF_PATH = Path('/Users/akosbalog/Downloads/united-kingdom-latest.osm.pbf')
CENTRES_PATH = Path('/Users/akosbalog/Downloads/retailcentre_bounds_uk.gpkg')
OUT_PARQUET = Path('outputs/v2/uk_roads_400m.parquet')
TMP_PBF = Path('/tmp/uk_highways_filtered.osm.pbf')

KEEP_CLASSES = {
    'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link',
    'secondary', 'secondary_link', 'tertiary', 'tertiary_link', 'residential',
    'unclassified', 'living_street', 'service', 'pedestrian', 'footway', 'path', 'steps'
}

TAG_KEYS = ('footway', 'service', 'access', 'foot', 'motor_vehicle', 'bridge', 'tunnel', 'layer')
TAG_RE = {k: re.compile(rf'"{k}"=>"([^"]*)"') for k in TAG_KEYS}


# 2. Extract Highway Ways & Filter to 400 m Context Buffers ---------------

def extract_tag(series, key):
    return series.str.extract(TAG_RE[key], expand=False).fillna('')


def main():
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    if not TMP_PBF.exists():
        subprocess.run(
            ['osmium', 'tags-filter', str(PBF_PATH), 'w/highway', '-o', str(TMP_PBF), '--overwrite'],
            check=True
        )

    centres = gpd.read_file(CENTRES_PATH).to_crs(27700)
    mask_27700 = shapely.union_all(shapely.buffer(centres.geometry.to_numpy(), 450.0))
    mask_4326 = gpd.GeoSeries([mask_27700], crs=27700).to_crs(4326).iloc[0]

    gdf = gpd.read_file(
        TMP_PBF,
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

    # 3. Parse Ancillary OSM Tags (Sidewalks, Service Types, Grade Separation)
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

    out.to_parquet(OUT_PARQUET, index=False)
    print(f'Saved {len(out):,} highway segments to {OUT_PARQUET}')


if __name__ == '__main__':
    main()
