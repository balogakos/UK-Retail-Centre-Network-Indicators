"""Calculate road network shares inside walking catchments for all UK retail centres.

Outputs:
  - Updates Output Data/UK_Retail_Centre_Network_Indicators.csv
  - Updates Output Data/UK_Retail_Centre_Network_Indicators.gpkg
"""

from pathlib import Path
import time
import geopandas as gpd
import numpy as np
import osmium
import pandas as pd
import pyogrio
import pyproj
import shapely

REPO_ROOT = Path(__file__).resolve().parents[1]
PBF_PATH = REPO_ROOT / 'Input Data' / 'united-kingdom-latest.osm.pbf'
WALK_PATH = REPO_ROOT / 'Input Data' / 'walk_catchments.gpkg'
CSV_PATH = REPO_ROOT / 'Output Data' / 'UK_Retail_Centre_Network_Indicators.csv'
GPKG_PATH = REPO_ROOT / 'Output Data' / 'UK_Retail_Centre_Network_Indicators.gpkg'

DRIVE_CLASSES = {
    'motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link',
    'secondary', 'secondary_link', 'tertiary', 'tertiary_link', 'residential',
    'unclassified', 'living_street'
}
ARTERIAL_CLASSES = {
    'motorway', 'motorway_link', 'trunk', 'trunk_link',
    'primary', 'primary_link', 'secondary', 'secondary_link'
}
WALK_CLASSES = {
    'residential', 'unclassified', 'living_street', 'tertiary', 'tertiary_link',
    'secondary', 'secondary_link', 'primary', 'primary_link', 'trunk', 'trunk_link',
    'service', 'footway', 'pedestrian', 'path', 'steps'
}
CARFREE_CLASSES = {'footway', 'pedestrian', 'path', 'steps'}
SIDEWALK_VALS = {'sidewalk', 'crossing', 'traffic_island'}
PRIVATE_VALS = {'private', 'no'}

KEEP_CLASSES = DRIVE_CLASSES | WALK_CLASSES | {'service'}


def main():
    print('=' * 80)
    print('CALCULATING ROAD NETWORK SHARES INSIDE WALKING CATCHMENTS')
    print('=' * 80)
    t0 = time.time()

    print('Loading walk catchments...')
    walk_27700 = gpd.read_file(WALK_PATH).to_crs(27700)
    walk_4326 = walk_27700.to_crs(4326)
    n_centres = len(walk_27700)
    print(f'Loaded {n_centres:,} catchments in {time.time() - t0:.2f}s')

    rc_ids = walk_27700['RC_ID'].astype(int).to_numpy()
    walk_geoms_27700 = walk_27700.geometry.to_numpy()
    shapely.prepare(walk_geoms_27700)

    print('Building spatial index on catchment envelopes...')
    tree_4326_env = shapely.STRtree(walk_4326.geometry.envelope.to_numpy())

    wkbfab = osmium.geom.WKBFactory()
    transformer = pyproj.Transformer.from_crs(4326, 27700, always_xy=True)

    drivable_m = np.zeros(n_centres, dtype=np.float64)
    arterial_m = np.zeros(n_centres, dtype=np.float64)
    service_m = np.zeros(n_centres, dtype=np.float64)
    walkable_m = np.zeros(n_centres, dtype=np.float64)
    carfree_m = np.zeros(n_centres, dtype=np.float64)

    class CatchmentRoadStreamHandler(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.count = 0
            self.matched_ways = 0
            self.t_start = time.time()

        def way(self, w):
            hw = w.tags.get('highway')
            if not hw or hw not in KEEP_CLASSES:
                return
            self.count += 1

            if self.count % 250000 == 0:
                elapsed = time.time() - self.t_start
                rate = self.count / max(1.0, elapsed)
                print(f'Processed {self.count:,} highway ways ({elapsed:.1f}s, {rate:.0f} ways/sec, matched {self.matched_ways:,} ways)...', flush=True)

            try:
                wkb = wkbfab.create_linestring(w)
            except Exception:
                return

            geom_4326 = shapely.from_wkb(wkb)
            cand_indices = tree_4326_env.query(geom_4326)
            if len(cand_indices) == 0:
                return

            access = w.tags.get('access', '')
            foot = w.tags.get('foot', '')
            motor = w.tags.get('motor_vehicle', '')
            service_tag = w.tags.get('service', '')
            footway_tag = w.tags.get('footway', '')

            is_private = access in PRIVATE_VALS

            is_drive = (hw in DRIVE_CLASSES) and not is_private and (motor not in PRIVATE_VALS)
            is_arterial = is_drive and (hw in ARTERIAL_CLASSES)
            is_service = (hw == 'service') and not is_private and (service_tag != 'driveway') and (motor not in PRIVATE_VALS)

            is_walk = (hw in WALK_CLASSES) and not is_private and (foot not in PRIVATE_VALS) and not (hw == 'service' and service_tag == 'driveway')
            is_sidewalk = (footway_tag in SIDEWALK_VALS) and (hw == 'footway')
            if is_sidewalk:
                is_walk = False

            is_carfree = is_walk and (hw in CARFREE_CLASSES) and not is_sidewalk

            if not (is_drive or is_arterial or is_service or is_walk or is_carfree):
                return

            coords = shapely.get_coordinates(geom_4326)
            x, y = transformer.transform(coords[:, 0], coords[:, 1])
            geom_27700 = shapely.linestrings(np.column_stack([x, y]))

            matched = False
            for c_idx in cand_indices:
                c_poly = walk_geoms_27700[c_idx]
                if shapely.intersects(geom_27700, c_poly):
                    clipped = shapely.intersection(geom_27700, c_poly)
                    len_m = shapely.length(clipped)
                    if len_m > 0:
                        matched = True
                        if is_drive:
                            drivable_m[c_idx] += len_m
                        if is_arterial:
                            arterial_m[c_idx] += len_m
                        if is_service:
                            service_m[c_idx] += len_m
                        if is_walk:
                            walkable_m[c_idx] += len_m
                        if is_carfree:
                            carfree_m[c_idx] += len_m

            if matched:
                self.matched_ways += 1

    print('Scanning UK OpenStreetMap PBF extract with Pyosmium...')
    handler = CatchmentRoadStreamHandler()
    t_scan = time.time()
    handler.apply_file(str(PBF_PATH), locations=True)
    scan_duration = time.time() - t_scan
    print(f'Finished PBF scan: processed {handler.count:,} ways in {scan_duration:.1f}s ({handler.count/scan_duration:.0f} ways/sec)')
    print(f'Total matched ways across all catchments: {handler.matched_ways:,}')

    print('Computing catchment indicator ratios...')
    d_valid = drivable_m >= 50.0
    arterial_share = np.full(n_centres, np.nan)
    arterial_share[d_valid] = np.round(arterial_m[d_valid] / drivable_m[d_valid], 4)

    ds_valid = (drivable_m + service_m) >= 50.0
    service_share = np.full(n_centres, np.nan)
    service_share[ds_valid] = np.round(service_m[ds_valid] / (drivable_m[ds_valid] + service_m[ds_valid]), 4)

    w_valid = walkable_m >= 50.0
    carfree_share = np.full(n_centres, np.nan)
    carfree_share[w_valid] = np.round(carfree_m[w_valid] / walkable_m[w_valid], 4)

    res_df = pd.DataFrame({
        'RC_ID': rc_ids,
        'catchment_arterial_share': arterial_share,
        'catchment_service_share': service_share,
        'catchment_carfree_share': carfree_share,
        'catchment_walkable_km': np.round(walkable_m / 1000.0, 2),
        'catchment_drivable_km': np.round(drivable_m / 1000.0, 2),
    })

    print(f'Updating CSV dataset: {CSV_PATH}')
    existing_df = pd.read_csv(CSV_PATH)
    for col in ['catchment_arterial_share', 'catchment_service_share', 'catchment_carfree_share', 'catchment_walkable_km', 'catchment_drivable_km']:
        if col in existing_df.columns:
            existing_df = existing_df.drop(columns=[col])

    updated_df = existing_df.merge(res_df, on='RC_ID', how='left')
    updated_df.to_csv(CSV_PATH, index=False)
    print(f'Saved updated CSV table ({len(updated_df):,} rows, {len(updated_df.columns)} columns)')

    if GPKG_PATH.exists():
        print(f'Updating GeoPackage: {GPKG_PATH}')
        gpkg_gdf = gpd.read_file(GPKG_PATH)
        for col in ['catchment_arterial_share', 'catchment_service_share', 'catchment_carfree_share', 'catchment_walkable_km', 'catchment_drivable_km']:
            if col in gpkg_gdf.columns:
                gpkg_gdf = gpkg_gdf.drop(columns=[col])
        updated_gpkg = gpkg_gdf.merge(res_df, on='RC_ID', how='left')
        pyogrio.write_dataframe(updated_gpkg, GPKG_PATH, layer='UK_Retail_Centre_Network_Indicators', layer_options={'OVERWRITE': 'YES'})
        print(f'Saved updated GeoPackage ({len(updated_gpkg):,} features)')

    print('=' * 80)
    print('CATCHMENT ROAD SHARES RECALCULATION COMPLETE')
    print('=' * 80)
    print('Summary Statistics across 9,623 UK Retail Centres:')
    print(updated_df[['catchment_arterial_share', 'catchment_service_share', 'catchment_carfree_share', 'catchment_walkable_km', 'catchment_drivable_km']].describe().T[['count', 'mean', 'std', 'min', '50%', 'max']])


if __name__ == '__main__':
    main()
