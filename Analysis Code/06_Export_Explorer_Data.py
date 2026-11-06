"""Export optimized data structures for the UK Retail Centre Network Explorer web app.

Generates:
  - explorer/data/centres.json: compact index of all 9,623 centres with metrics and percentiles
  - explorer/data/boundaries.json: simplified polygon boundaries keyed by centre ID
  - explorer/data/benchmarks.json: national, hierarchical, and regional median baselines
  - explorer/data/exemplars.json: curated high-contrast comparator pairs
"""

import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
GPKG_PATH = ROOT / "Output Data" / "UK_Retail_Centre_Network_Indicators.gpkg"
OUT_DIR = ROOT / "explorer" / "data"

INDICATORS = [
    {
        "id": "walk_reach_400",
        "name": "Walkable Reach (400 m)",
        "short": "Walk Reach",
        "unit": "%",
        "fmt": ".1%",
        "higher_is": "better",
        "desc": "Share of surrounding street network reachable within a 400 m walk from the centre perimeter.",
    },
    {
        "id": "drive_reach_400",
        "name": "Road Embeddedness (400 m)",
        "short": "Road Reach",
        "unit": "%",
        "fmt": ".1%",
        "higher_is": "neutral",
        "desc": "Share of surrounding driveable street network topologically connected within 400 m.",
    },
    {
        "id": "arterial_share",
        "name": "Arterial Road Share",
        "short": "Arterial",
        "unit": "%",
        "fmt": ".1%",
        "higher_is": "lower",
        "desc": "Share of local roads classified as high-speed trunk, primary, or secondary highways.",
    },
    {
        "id": "service_share",
        "name": "Service & Parking Way Share",
        "short": "Service Share",
        "unit": "%",
        "fmt": ".1%",
        "higher_is": "lower",
        "desc": "Share of motorised network classified as service ways, car-park aisles, and loading bays.",
    },
    {
        "id": "carfree_share",
        "name": "Pedestrian-Way Share",
        "short": "Pedestrian Share",
        "unit": "%",
        "fmt": ".1%",
        "higher_is": "better",
        "desc": "Share of walkable network dedicated to traffic-free footways, pedestrian streets, and paths.",
    },
    {
        "id": "walk_median_edge_len_m",
        "name": "Median Link Length",
        "short": "Street Grain",
        "unit": "m",
        "fmt": ".1f m",
        "higher_is": "lower",
        "desc": "Median distance between street-network junctions. Shorter links indicate finer urban grain.",
    },
    {
        "id": "walk_meshedness",
        "name": "Street-Network Meshedness",
        "short": "Meshedness",
        "unit": "ratio",
        "fmt": ".3f",
        "higher_is": "better",
        "desc": "Cyclic link density. Higher values indicate multiple alternative routes and looped circuits.",
    },
    {
        "id": "walk_sightline_continuity",
        "name": "Sightline Continuity",
        "short": "Sightlines",
        "unit": "ratio",
        "fmt": ".3f",
        "higher_is": "neutral",
        "desc": "Geometric straightness of street segments. Higher values indicate long linear vistas.",
    },
    {
        "id": "flow_concentration",
        "name": "Flow Concentration (Betweenness)",
        "short": "Flow Concentration",
        "unit": "Gini",
        "fmt": ".3f",
        "higher_is": "neutral",
        "desc": "Gini concentration of 400 m shortest-path walk flows onto a dominant high-street spine.",
    },
    {
        "id": "walk_block_median_area_m2",
        "name": "Median Block Area",
        "short": "Block Area",
        "unit": "m²",
        "fmt": ",.0f m²",
        "higher_is": "lower",
        "desc": "Median area of enclosed urban blocks. Smaller blocks support walkable, permeable town cores.",
    },
    {
        "id": "orientation_entropy",
        "name": "Grid Orientation Entropy",
        "short": "Grid Order",
        "unit": "entropy",
        "fmt": ".3f",
        "higher_is": "neutral",
        "desc": "Directional entropy of street bearings. Lower values indicate strict orthogonal grids.",
    },
]

IND_KEYS = [ind["id"] for ind in INDICATORS]


def compute_percentiles(df, cols):
    """Compute 0-100 percentile rank for each column."""
    pct_df = pd.DataFrame(index=df.index)
    for col in cols:
        valid = df[col].dropna()
        if len(valid) == 0:
            pct_df[col] = np.nan
        else:
            pct_df[col] = df[col].rank(pct=True) * 100.0
    return pct_df


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Loading retail centre dataset...")
    gdf = gpd.read_file(GPKG_PATH)

    # Calculate WGS84 representative point coordinates
    print("Computing representative points and simplified boundaries in WGS84...")
    pt_wgs84 = gdf.geometry.representative_point().to_crs(4326)
    lons = pt_wgs84.x.round(5).tolist()
    lats = pt_wgs84.y.round(5).tolist()

    # Simplify polygon boundaries for fast interactive map display
    simp_wgs84 = gdf.geometry.simplify(10.0, preserve_topology=True).to_crs(4326)

    # Compute percentiles
    print("Computing national percentiles...")
    pct_df = compute_percentiles(gdf, IND_KEYS)

    # Compute benchmarks
    print("Computing hierarchical and regional benchmarks...")
    hierarchies = sorted(gdf["Classification"].dropna().unique().tolist())
    regions = sorted(gdf["Region_NM"].dropna().unique().tolist())

    hier_benchmarks = {}
    for h in hierarchies:
        sub = gdf[gdf["Classification"] == h]
        sub_pct = pct_df.loc[sub.index]
        hier_benchmarks[h] = {
            "n": int(len(sub)),
            "raw": {k: None if sub[k].dropna().empty else round(float(sub[k].median()), 4) for k in IND_KEYS},
            "pct": {k: None if sub_pct[k].dropna().empty else round(float(sub_pct[k].median()), 1) for k in IND_KEYS},
        }

    region_benchmarks = {}
    for r in regions:
        sub = gdf[gdf["Region_NM"] == r]
        sub_pct = pct_df.loc[sub.index]
        region_benchmarks[r] = {
            "n": int(len(sub)),
            "raw": {k: None if sub[k].dropna().empty else round(float(sub[k].median()), 4) for k in IND_KEYS},
            "pct": {k: None if sub_pct[k].dropna().empty else round(float(sub_pct[k].median()), 1) for k in IND_KEYS},
        }

    national_benchmark = {
        "n": int(len(gdf)),
        "raw": {k: None if gdf[k].dropna().empty else round(float(gdf[k].median()), 4) for k in IND_KEYS},
        "pct": {k: 50.0 for k in IND_KEYS},
    }

    benchmarks_data = {
        "indicators": INDICATORS,
        "national": national_benchmark,
        "hierarchy": hier_benchmarks,
        "region": region_benchmarks,
    }

    benchmarks_path = OUT_DIR / "benchmarks.json"
    with open(benchmarks_path, "w", encoding="utf-8") as f:
        json.dump(benchmarks_data, f, indent=2)
    print(f"Saved benchmarks to {benchmarks_path}")

    # Build compact centres list
    print("Building centres index...")
    centres_list = []
    boundaries_dict = {}

    for idx, row in gdf.iterrows():
        cid = int(idx)
        raw_vals = [None if pd.isna(row[k]) else round(float(row[k]), 4) for k in IND_KEYS]
        pct_vals = [None if pd.isna(pct_df.loc[idx, k]) else round(float(pct_df.loc[idx, k]), 1) for k in IND_KEYS]

        centre_obj = {
            "i": cid,
            "rc_id": str(row["RC_ID"]),
            "name": str(row["RC_Name"]),
            "cls": str(row["Classification"]),
            "reg": str(row["Region_NM"]),
            "area_km2": round(float(row["Area_km2"]), 3) if pd.notna(row["Area_km2"]) else None,
            "x": lons[cid],
            "y": lats[cid],
            "m": raw_vals,
            "p": pct_vals,
        }
        centres_list.append(centre_obj)

        # Polygon coordinates for boundary display
        geom = simp_wgs84.iloc[cid]
        if geom is not None and not geom.is_empty:
            if geom.geom_type == "Polygon":
                coords = [[round(x, 5), round(y, 5)] for x, y in geom.exterior.coords]
                boundaries_dict[cid] = [coords]
            elif geom.geom_type == "MultiPolygon":
                coords = [[[round(x, 5), round(y, 5)] for x, y in p.exterior.coords] for p in geom.geoms]
                boundaries_dict[cid] = coords

    centres_path = OUT_DIR / "centres.json"
    with open(centres_path, "w", encoding="utf-8") as f:
        json.dump(centres_list, f, separators=(",", ":"))
    print(f"Saved {len(centres_list):,} centres to {centres_path} ({centres_path.stat().st_size / 1e6:.2f} MB)")

    boundaries_path = OUT_DIR / "boundaries.json"
    with open(boundaries_path, "w", encoding="utf-8") as f:
        json.dump(boundaries_dict, f, separators=(",", ":"))
    print(f"Saved boundaries to {boundaries_path} ({boundaries_path.stat().st_size / 1e6:.2f} MB)")

    # Build curated exemplars
    print("Building curated exemplar pairs...")
    def find_idx(phrase):
        matches = gdf[gdf["RC_Name"].str.contains(phrase, case=False, regex=False, na=False)]
        if len(matches) == 0:
            print(f"Warning: No match for {phrase}")
            return None
        return int(matches.index[0])

    exemplar_pairs = [
        {
            "title": "Neighbourhood Walk-in Reach vs. Island Retail Park",
            "desc": "Bradford's permeable street network reaches 78% of surrounding neighbourhood streets on foot, compared with 46% for Peel Retail Park's highway-severed boundary.",
            "centre_a_idx": find_idx("Bradford; Bradford"),
            "centre_b_idx": find_idx("Peel Retail Park; Sunderland"),
        },
        {
            "title": "Historic Fine Grain & Tight Blocks vs. Linear Corridor",
            "desc": "Bristol Old City features tightly spaced 32 m street links and 5,079 m² blocks, whereas Leytonstone stretches across widely spaced 41 m links and 16,000 m² blocks.",
            "centre_a_idx": find_idx("Old City (Bristol City Centre)"),
            "centre_b_idx": find_idx("Leytonstone; Waltham Forest"),
        },
        {
            "title": "Car-Park Circulation Loops vs. Active High-Street Frontage",
            "desc": "Rushden Lakes devotes 64% of its internal road network to service and parking loops, while Southend London Road prioritises public street frontages (18% service).",
            "centre_a_idx": find_idx("Rushden Lakes"),
            "centre_b_idx": find_idx("London Road; Southend-on-Sea"),
        },
        {
            "title": "Pedestrian Precinct Priority vs. Regional Shopping Complex",
            "desc": "Thetford town centre dedicates 34% of its walkable network to traffic-free pedestrian zones, compared with Meadowhall's ring-road bounded regional complex.",
            "centre_a_idx": find_idx("Thetford; Breckland"),
            "centre_b_idx": find_idx("Meadowhall; Sheffield"),
        },
        {
            "title": "Continuous Looped Circuits vs. Dominant Single Spine",
            "desc": "Morley Queen Street boasts high network meshedness (0.141) allowing continuous shopping loops, while Edinburgh St James funnels pedestrian flow heavily onto a primary corridor.",
            "centre_a_idx": find_idx("Queen Street; Morley"),
            "centre_b_idx": find_idx("St James Quarter (Edinburgh City Centre)"),
        },
    ]

    exemplars_path = OUT_DIR / "exemplars.json"
    with open(exemplars_path, "w", encoding="utf-8") as f:
        json.dump(exemplar_pairs, f, indent=2)
    print(f"Saved exemplars to {exemplars_path}")
    print("Explorer data generation complete.")


if __name__ == "__main__":
    main()
