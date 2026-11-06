## Extracting OpenStreetMap Highway Networks for UK Retail Centres

import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import geopandas as gpd
import pandas as pd
import pyogrio
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


# 2. Provenance Fingerprinting & Highway Extraction -----------------------

def extract_tag(series, key):
    return series.str.extract(TAG_RE[key], expand=False).fillna('')


def pbf_fingerprint(pbf_path: Path) -> dict:
    """Compute provenance metadata and a fast content fingerprint for the source OSM PBF."""
    st = pbf_path.stat()
    h = hashlib.sha256()
    with pbf_path.open('rb') as f:
        h.update(f.read(65536))
    h.update(f'{st.st_size}:{st.st_mtime_ns}'.encode('utf-8'))
    digest = h.hexdigest()[:16]
    mtime_utc = datetime.datetime.fromtimestamp(st.st_mtime, tz=datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    return {
        'source_pbf_filename': pbf_path.name,
        'source_pbf_size_bytes': st.st_size,
        'source_pbf_modified_utc': mtime_utc,
        'source_pbf_fingerprint': digest,
        'osm_extract_provider': 'Geofabrik GmbH (https://download.geofabrik.de/europe/united-kingdom.html)',
        'osm_licence': 'Open Data Commons Open Database License (ODbL 1.0)',
        'osm_attribution': 'Map data © OpenStreetMap contributors (https://www.openstreetmap.org/copyright)',
    }


def main():
    parser = argparse.ArgumentParser(description='Extract OSM highway ways within 400 m of UK retail centres.')
    parser.add_argument('--pbf', type=Path, default=DEFAULT_PBF, help='Path to united-kingdom-latest.osm.pbf')
    parser.add_argument('--centres', type=Path, default=DEFAULT_CENTRES, help='Path to retailcentre_bounds_uk.gpkg')
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT_PARQUET, help='Output Parquet path')
    args = parser.parse_args()

    if not args.pbf.exists():
        raise FileNotFoundError(f'Source PBF not found: {args.pbf}')

    prov = pbf_fingerprint(args.pbf)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    centres = gpd.read_file(args.centres).to_crs(27700)

    # Key any temporary osmium cache directly to the source PBF fingerprint so stale PBFs are never reused
    if shutil.which('osmium'):
        tmp_pbf = Path(tempfile.gettempdir()) / f"uk_highways_{prov['source_pbf_fingerprint']}.osm.pbf"
        if not tmp_pbf.exists():
            subprocess.run(
                ['osmium', 'tags-filter', str(args.pbf), 'w/highway', '-o', str(tmp_pbf), '--overwrite'],
                check=True
            )
        mask_27700 = shapely.union_all(shapely.buffer(centres.geometry.to_numpy(), 450.0))
        mask_4326 = gpd.GeoSeries([mask_27700], crs=27700).to_crs(4326).iloc[0]
        gdf = gpd.read_file(
            tmp_pbf,
            layer='lines',
            mask=mask_4326,
            columns=['osm_id', 'highway', 'other_tags', 'geometry']
        )
    else:
        os.environ['OGR_INTERLEAVED_READING'] = 'YES'
        gdf = pyogrio.read_dataframe(
            args.pbf,
            layer='lines',
            where='highway IS NOT NULL',
            columns=['osm_id', 'highway', 'other_tags'],
            use_arrow=True
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
    prov['extracted_segments_count'] = int(len(out))
    prov['crs'] = 'EPSG:27700'
    prov_path = args.out.with_suffix('.provenance.json')
    prov_path.write_text(json.dumps(prov, indent=2) + '\n', encoding='utf-8')
    print(f'Saved {len(out):,} highway segments to {args.out}')
    print(f'Saved provenance metadata to {prov_path}')


if __name__ == '__main__':
    main()
