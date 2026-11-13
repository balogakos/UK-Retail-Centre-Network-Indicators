## Recalculate UK Retail Centre Network Indicators using Per-Centre Catchments

from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np
import shapely
import shutil
import time

REPO_ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = REPO_ROOT / 'Input Data'
OUTPUT_DIR = REPO_ROOT / 'Output Data'

CSV_PATH = OUTPUT_DIR / 'UK_Retail_Centre_Network_Indicators.csv'
GPKG_PATH = OUTPUT_DIR / 'UK_Retail_Centre_Network_Indicators.gpkg'

CENTRES_PATH = INPUT_DIR / 'retailcentre_bounds_uk.gpkg'
WALK_PATH = INPUT_DIR / 'walk_catchments.gpkg'
DRIVE_PATH = INPUT_DIR / 'drive_catchments.gpkg'

print("=" * 80)
print("RECALCULATING FIRST TWO INDICATORS WITH PER-CENTRE CATCHMENTS")
print("=" * 80)
t0 = time.time()

# 1. Back up existing outputs if backups don't exist
if CSV_PATH.exists() and not (OUTPUT_DIR / 'UK_Retail_Centre_Network_Indicators.baseline_400m.csv').exists():
    shutil.copy(CSV_PATH, OUTPUT_DIR / 'UK_Retail_Centre_Network_Indicators.baseline_400m.csv')
    print("Backed up original CSV to UK_Retail_Centre_Network_Indicators.baseline_400m.csv")

# 2. Load retail centre boundaries (EPSG:27700 British National Grid)
print("Loading retail centre boundaries...")
centres = gpd.read_file(CENTRES_PATH).to_crs(27700)
centres['RC_ID'] = centres['RC_ID'].astype(int)

# 3. Load walk and drive catchments (reproject to EPSG:27700)
print("Loading walk and drive catchment polygons...")
walk = gpd.read_file(WALK_PATH).to_crs(27700)
walk['RC_ID'] = walk['RC_ID'].astype(int)

drive = gpd.read_file(DRIVE_PATH).to_crs(27700)
drive['RC_ID'] = drive['RC_ID'].astype(int)

# Align to centres index
walk = walk.set_index('RC_ID').loc[centres['RC_ID']].reset_index()
drive = drive.set_index('RC_ID').loc[centres['RC_ID']].reset_index()

c_geoms = centres.geometry.to_numpy()
w_geoms = walk.geometry.to_numpy()
d_geoms = drive.geometry.to_numpy()

# 4. Calculate Catchment Areas
print("Computing physical catchment areas (km²)...")
w_area_km2 = shapely.area(w_geoms) / 1e6
d_area_km2 = shapely.area(d_geoms) / 1e6

# 5. Calculate Catchment Reach Directness / Efficiency Ratios
# Walking speed: 4.8 km/h (80 m/min, UK DfT standard)
# Driving speed: 30.0 km/h (500 m/min, UK urban average)
print("Computing reach directness ratios relative to theoretical buffers...")
w_mins = walk['threshold_minutes'].to_numpy()
d_mins = drive['threshold_minutes'].to_numpy()

w_dist_m = w_mins * (4.8 * 1000.0 / 60.0)
d_dist_m = d_mins * (30.0 * 1000.0 / 60.0)

# Exterior reachable area (excluding the retail centre interior)
w_ext_area = shapely.area(shapely.difference(w_geoms, c_geoms))
d_ext_area = shapely.area(shapely.difference(d_geoms, c_geoms))

# Theoretical circular Euclidean buffer outside the centre
w_buf = shapely.buffer(c_geoms, w_dist_m)
d_buf = shapely.buffer(c_geoms, d_dist_m)

w_buf_ext_area = shapely.area(shapely.difference(w_buf, c_geoms))
d_buf_ext_area = shapely.area(shapely.difference(d_buf, c_geoms))

# Reach ratio in [0, 1]
w_reach_ratio = np.clip(w_ext_area / np.maximum(w_buf_ext_area, 1.0), 0.0, 1.0)
d_reach_ratio = np.clip(d_ext_area / np.maximum(d_buf_ext_area, 1.0), 0.0, 1.0)

# 6. Merge with Existing Indicator Table
existing_df = pd.read_csv(CSV_PATH)
existing_df['RC_ID'] = existing_df['RC_ID'].astype(int)

# Create new catchment columns
catchment_data = pd.DataFrame({
    'RC_ID': centres['RC_ID'],
    'walk_time_min': w_mins,
    'walk_reach': w_reach_ratio,
    'walk_catchment_km2': w_area_km2,
    'drive_time_min': d_mins,
    'drive_reach': d_reach_ratio,
    'drive_catchment_km2': d_area_km2,
    'walk_h3_count': walk['catchment_h3_count'],
    'drive_h3_count': drive['catchment_h3_count'],
})

merged_df = existing_df.merge(catchment_data, on='RC_ID', how='left')

# Reorder columns with new walk_reach and drive_reach at the front of indicators:
meta_cols = ['RC_ID', 'RC_Name', 'Classification', 'Country', 'Region_NM', 'Area_km2', 'Retail_N', 'sidewalk_mapped_share']
new_indicators = ['walk_reach', 'drive_reach', 'walk_catchment_km2', 'drive_catchment_km2', 'walk_time_min', 'drive_time_min']
other_indicators = [
    'arterial_share', 'service_share', 'carfree_share',
    'walk_median_edge_len_m', 'walk_meshedness', 'walk_sightline_continuity',
    'flow_concentration', 'walk_block_median_area_m2', 'orientation_entropy'
]
baseline_cols = ['walk_reach_400', 'drive_reach_400', 'walk_h3_count', 'drive_h3_count']

final_cols = [c for c in (meta_cols + new_indicators + other_indicators + baseline_cols) if c in merged_df.columns]
final_df = merged_df[final_cols].copy()

# Save updated CSV
final_df.to_csv(CSV_PATH, index=False)
print(f"Saved updated CSV lookup table: {CSV_PATH} ({len(final_df):,} centres)")

# Save updated GeoPackage
print("Updating GeoPackage with new catchment indicators...")
gdf = centres[['RC_ID', 'geometry']].merge(final_df, on='RC_ID', how='left')
if GPKG_PATH.exists():
    GPKG_PATH.unlink()
gdf.to_file(GPKG_PATH, layer='uk_retail_centre_network_indicators', driver='GPKG')
print(f"Saved updated GeoPackage: {GPKG_PATH}")

print(f"\nCompleted in {time.time()-t0:.2f}s")
print("\nRecalculated Indicator Summary by Classification (Medians):")
summary = final_df.groupby('Classification')[['walk_time_min', 'walk_reach', 'walk_catchment_km2', 'drive_time_min', 'drive_reach', 'drive_catchment_km2']].median()
print(summary.to_string())
