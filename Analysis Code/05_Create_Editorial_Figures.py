"""Create publication-ready figures for the UK retail-centre network data story.

Run from any directory with:
    python "Analysis Code/05_Create_Editorial_Figures.py"

Exports SVG, PDF, and 300-dpi PNG versions to Output Data/Editorial Figures/.
"""

from pathlib import Path
import sys
import warnings

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from shapely.geometry import box
from shapely.ops import polygonize


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Source Code"))

from Helper_Functions import (  # noqa: E402
    CARFREE_CLASSES,
    DRIVE_CLASSES,
    NetworkParams,
    build_consolidated_graph,
    detect_parallel_sidewalks,
    get_drive_mask,
    get_service_mask,
    get_walk_mask,
)


CSV_PATH = ROOT / "Output Data" / "UK_Retail_Centre_Network_Indicators.csv"
GPKG_PATH = ROOT / "Output Data" / "UK_Retail_Centre_Network_Indicators.gpkg"
ROADS_PATH = ROOT / "Input Data" / "uk_roads_400m.parquet"
OUT_DIR = ROOT / "Output Data" / "Editorial Figures"

BG = "#0d1117"
INK = "#f0f6fc"
MUTED = "#8b949e"
GRID = "#21262d"
BLUE = "#38bdf8"
BLUE_DARK = "#22d3ee"
ORANGE = "#fb923c"
TEAL = "#2dd4bf"
TEAL_DARK = "#14b8a6"
PALE = "#161b22"
BLOCK = "#fbbf24"

STREET_TYPES = {
    "Regional Centre", "Major Town Centre", "Town Centre", "Market Town",
    "District Centre", "Local Centre", "Small Local Centre",
}
PARK_TYPES = {"Small Retail Park", "Large Retail Park"}
SHOPPING_TYPES = {"Small Shopping Centre", "Large Shopping Centre"}
STREET_FCLASS = {
    "residential", "unclassified", "living_street", "tertiary", "tertiary_link",
    "secondary", "secondary_link", "primary", "primary_link", "trunk", "trunk_link",
    "motorway", "motorway_link",
}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10,
    "axes.titlesize": 12,
    "axes.labelsize": 10,
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "figure.facecolor": BG,
    "axes.facecolor": BG,
    "savefig.facecolor": BG,
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})


def load_inputs():
    indicators = pd.read_csv(CSV_PATH)
    centres = gpd.read_file(GPKG_PATH)
    roads = gpd.read_parquet(ROADS_PATH)
    if centres.crs is None or roads.crs is None or centres.crs != roads.crs:
        raise ValueError("Centre and road data must share a projected CRS.")
    return indicators, centres, roads


def find_centre(centres, phrase):
    found = centres[centres["RC_Name"].str.contains(phrase, case=False, regex=False, na=False)]
    if len(found) != 1:
        raise ValueError(f"Expected one centre matching {phrase!r}; found {len(found)}.")
    return found.iloc[0]


def local_roads(roads, centre, padding):
    region = centre.geometry.buffer(padding)
    ids = roads.sindex.query(region, predicate="intersects")
    subset = roads.iloc[np.unique(ids)].copy()
    return subset[subset.geometry.intersects(region)].copy()


def clean_walk_network(data):
    sidewalk = detect_parallel_sidewalks(data)
    walkable = get_walk_mask(data) & ~sidewalk
    return data.loc[walkable].copy()


def group_summary(data, column, groups):
    rows = []
    for label, types in groups:
        values = data.loc[data["Classification"].isin(types), column].dropna()
        rows.append({"label": label, "values": values, "median": values.median(), "n": len(values)})
    return rows


def add_heading(fig, title, deck):
    fig.text(0.5, 0.965, title, ha="center", va="top", fontsize=21, fontweight="bold")
    fig.text(0.5, 0.925, deck, ha="center", va="top", fontsize=10.5, color=MUTED)


def add_footer(fig, note):
    fig.text(0.035, 0.018, note, ha="left", va="bottom", fontsize=7.6, color=MUTED)


def save_figure(fig, stem):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for ext, extra in [("svg", {}), ("pdf", {}), ("png", {"dpi": 300})]:
        fig.savefig(OUT_DIR / f"{stem}.{ext}", bbox_inches="tight", **extra)
    plt.close(fig)


def style_chart(ax):
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(length=0, pad=5)
    ax.grid(axis="x", color=GRID, linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)


def plot_lines(ax, gdf, color, lw, zorder=2, alpha=1.0):
    if len(gdf):
        gdf.plot(ax=ax, color=color, linewidth=lw, zorder=zorder, alpha=alpha)


def set_map_extent(ax, centre, side_m):
    point = centre.geometry.representative_point()
    half = side_m / 2
    ax.set_xlim(point.x - half, point.x + half)
    ax.set_ylim(point.y - half, point.y + half)
    ax.set_aspect("equal")
    ax.set_axis_off()


def draw_scale(ax, length_m=250):
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    x = x0 + (x1 - x0) * 0.06
    y = y0 + (y1 - y0) * 0.075
    ax.plot([x, x + length_m], [y, y], color=INK, lw=1.6, solid_capstyle="butt", zorder=20)
    ax.plot([x, x], [y - 9, y + 9], color=INK, lw=1.1, zorder=20)
    ax.plot([x + length_m, x + length_m], [y - 9, y + 9], color=INK, lw=1.1, zorder=20)
    label = f"{length_m} m" if length_m < 1000 else f"{length_m / 1000:g} km"
    ax.text(x + length_m / 2, y + (y1 - y0) * 0.018, label,
            ha="center", va="bottom", fontsize=7.5, color=INK, zorder=20)


def draw_reach_map(ax, roads, centre, title, score, side_m):
    region = box(*(
        centre.geometry.representative_point().x - side_m / 2,
        centre.geometry.representative_point().y - side_m / 2,
        centre.geometry.representative_point().x + side_m / 2,
        centre.geometry.representative_point().y + side_m / 2,
    ))
    ids = roads.sindex.query(region, predicate="intersects")
    local = roads.iloc[np.unique(ids)].copy()
    local = clean_walk_network(local)
    dedicated = local[local["fclass"].isin(CARFREE_CLASSES)]
    streets = local[~local["fclass"].isin(CARFREE_CLASSES)]
    plot_lines(ax, streets, BLUE, 0.48, zorder=2, alpha=0.9)
    plot_lines(ax, dedicated, ORANGE, 0.65, zorder=3, alpha=0.95)
    gpd.GeoSeries([centre.geometry], crs=roads.crs).plot(
        ax=ax, facecolor=TEAL, edgecolor=TEAL_DARK, linewidth=0.85, alpha=0.25, zorder=5
    )
    set_map_extent(ax, centre, side_m)
    ax.set_title(title, loc="left", pad=8, fontsize=11, fontweight="bold", color=INK)
    ax.text(0.02, 0.94, f"Walkable reach  {score:.1%}", transform=ax.transAxes,
            ha="left", va="top", fontsize=9, color=INK,
            bbox={"boxstyle": "round,pad=0.35", "facecolor": PALE, "edgecolor": "#30363d", "alpha": 0.92})
    draw_scale(ax, 250)


def draw_service_map(ax, roads, centre, title, score, side_m):
    point = centre.geometry.representative_point()
    region = box(point.x - side_m / 2, point.y - side_m / 2,
                 point.x + side_m / 2, point.y + side_m / 2)
    ids = roads.sindex.query(region, predicate="intersects")
    local = roads.iloc[np.unique(ids)].copy()
    motor = local.loc[get_drive_mask(local)].copy()
    service = local.loc[get_service_mask(local)].copy()
    plot_lines(ax, motor, BLUE, 0.55, zorder=2, alpha=0.9)
    plot_lines(ax, service, ORANGE, 0.75, zorder=3, alpha=0.95)
    gpd.GeoSeries([centre.geometry], crs=roads.crs).plot(
        ax=ax, facecolor=TEAL, edgecolor=TEAL_DARK, linewidth=0.85, alpha=0.25, zorder=5
    )
    set_map_extent(ax, centre, side_m)
    ax.set_title(title, loc="left", pad=8, fontsize=11, fontweight="bold", color=INK)
    ax.text(0.02, 0.94, f"Service-road share  {score:.1%}", transform=ax.transAxes,
            ha="left", va="top", fontsize=9, color=INK,
            bbox={"boxstyle": "round,pad=0.35", "facecolor": PALE, "edgecolor": "#30363d", "alpha": 0.92})
    draw_scale(ax, 250)


def draw_block_map(ax, roads, centre, title, edge_m, block_m2, side_m):
    point = centre.geometry.representative_point()
    region = box(point.x - side_m / 2, point.y - side_m / 2,
                 point.x + side_m / 2, point.y + side_m / 2)
    ids = roads.sindex.query(region, predicate="intersects")
    local = roads.iloc[np.unique(ids)].copy()
    walk = clean_walk_network(local)
    walk = walk[walk["fclass"] != "service"].copy()
    graph = build_consolidated_graph(
        walk.geometry.to_numpy(), walk["is_grade_sep"].to_numpy(), region, 10.0
    )
    if graph is not None:
        faces = list(polygonize(graph["egeom"]))
        core = centre.geometry.buffer(100)
        faces = [f for f in faces if core.covers(f.representative_point()) and f.area >= 500]
        if faces:
            gpd.GeoSeries(faces, crs=roads.crs).plot(
                ax=ax, facecolor=BLOCK, edgecolor="#fde68a", linewidth=0.4, alpha=0.35, zorder=1
            )
        gpd.GeoSeries(graph["egeom"], crs=roads.crs).plot(
            ax=ax, color=BLUE_DARK, linewidth=0.6, zorder=3
        )
    gpd.GeoSeries([centre.geometry], crs=roads.crs).plot(
        ax=ax, facecolor="none", edgecolor=TEAL, linewidth=1.0, zorder=5
    )
    set_map_extent(ax, centre, side_m)
    ax.set_title(title, loc="left", pad=8, fontsize=11, fontweight="bold", color=INK)
    ax.text(0.02, 0.94, f"Median link  {edge_m:.1f} m   •   Median block  {block_m2:,.0f} m²",
            transform=ax.transAxes, ha="left", va="top", fontsize=8.2, color=INK,
            bbox={"boxstyle": "round,pad=0.35", "facecolor": PALE, "edgecolor": "#30363d", "alpha": 0.92})
    draw_scale(ax, 250)


def figure_reach(data, centres, roads):
    street = data[data["Classification"].isin(STREET_TYPES)]
    parks = data[data["Classification"].isin(PARK_TYPES)]
    fig = plt.figure(figsize=(13.2, 9.0), constrained_layout=False)
    add_heading(fig, "REACHING THE SURROUNDING STREET NETWORK",
                "Below 50% reach: 29.4% of retail parks, compared with 13.9% of street-based centres")

    ax = fig.add_axes([0.12, 0.66, 0.76, 0.20])
    vals = [street["walk_reach_400"].dropna().values, parks["walk_reach_400"].dropna().values]
    bp = ax.boxplot(vals, vert=False, positions=[1, 0], widths=0.48, patch_artist=True,
                    showfliers=False, medianprops={"color": INK, "linewidth": 1.7},
                    whiskerprops={"color": MUTED, "linewidth": 1.0},
                    capprops={"color": MUTED, "linewidth": 1.0})
    for patch, color in zip(bp["boxes"], [BLUE, ORANGE]):
        patch.set_facecolor(color)
        patch.set_alpha(0.80)
        patch.set_edgecolor(color)
    ax.axvline(0.5, color=MUTED, linestyle=(0, (3, 3)), linewidth=1.0, zorder=1)
    ax.set_yticks([0, 1], ["Retail parks", "Street-based centres"])
    ax.set_xlim(0, 1)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax.set_xlabel("Share of surrounding walkable street length reachable")
    ax.text(0.505, 1.62, "50% threshold", fontsize=8, color=MUTED, va="center")
    ax.text(0.995, 1.28, f"Median  {street.walk_reach_400.median():.1%}",
            ha="right", va="center", color=BLUE, fontsize=8.8)
    ax.text(0.995, 0.28, f"Median  {parks.walk_reach_400.median():.1%}",
            ha="right", va="center", color=ORANGE, fontsize=8.8)
    style_chart(ax)
    ax.grid(axis="y", visible=False)

    bradford = find_centre(centres, "Bradford; Bradford")
    peel = find_centre(centres, "Peel Retail Park; Sunderland")
    side = max(max(bradford.geometry.bounds[2] - bradford.geometry.bounds[0],
                   bradford.geometry.bounds[3] - bradford.geometry.bounds[1]),
               max(peel.geometry.bounds[2] - peel.geometry.bounds[0],
                   peel.geometry.bounds[3] - peel.geometry.bounds[1])) + 650
    ax1 = fig.add_axes([0.06, 0.10, 0.42, 0.48])
    ax2 = fig.add_axes([0.53, 0.10, 0.42, 0.48])
    draw_reach_map(ax1, roads, bradford, "Bradford · Major Town Centre", 0.780751, side)
    draw_reach_map(ax2, roads, peel, "Peel Retail Park · Sunderland", 0.459240, side)
    legend = [Line2D([0], [0], color=BLUE, lw=1.6, label="Walkable streets"),
              Line2D([0], [0], color=ORANGE, lw=1.6, label="Dedicated pedestrian ways"),
              Patch(facecolor=TEAL, edgecolor=TEAL_DARK, alpha=0.35, label="Retail-centre boundary")]
    fig.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.5, 0.055),
               ncol=3, frameon=False, fontsize=8.5, labelcolor=INK)
    add_footer(fig, "Source: GeoDS retail-centre boundaries; OpenStreetMap network extract, 5 Nov 2026. "
               "Street-based centres include all non-park and non-shopping-centre classifications. "
               "© OpenStreetMap contributors, ODbL 1.0.")
    save_figure(fig, "figure_01_walkable_reach")


def figure_service(data, centres, roads):
    street = data[data["Classification"].isin(STREET_TYPES)]
    parks = data[data["Classification"].isin(PARK_TYPES)]
    shares = [street["service_share"].dropna(), parks["service_share"].dropna()]
    threshold = [s.gt(.5).mean() for s in shares]
    medians = [s.median() for s in shares]
    fig = plt.figure(figsize=(13.2, 8.7))
    add_heading(fig, "SERVICE ROADS INSIDE THE CENTRE",
                "Share of mapped motorised road length classified as service ways")
    ax = fig.add_axes([0.16, 0.68, 0.68, 0.18])
    bars = ax.barh([1, 0], threshold[::-1], color=[ORANGE, BLUE], height=0.48, zorder=3)
    ax.set_yticks([0, 1], ["Street-based centres", "Retail parks"])
    ax.set_xlim(0, 0.65)
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax.set_xlabel("Centres where service ways exceed half of the mapped network")
    for i, bar in enumerate(bars):
        value = threshold[::-1][i]
        median = medians[::-1][i]
        ax.text(value + 0.012, bar.get_y() + bar.get_height()/2,
                f"{value:.1%}  ·  median share {median:.1%}", va="center", fontsize=9, color=INK)
    style_chart(ax)
    ax.grid(axis="y", visible=False)

    rushden = find_centre(centres, "Rushden Lakes Shopping Centre")
    london = find_centre(centres, "London Road; Southend-on-Sea")
    side = max(max(rushden.geometry.bounds[2] - rushden.geometry.bounds[0],
                   rushden.geometry.bounds[3] - rushden.geometry.bounds[1]),
               max(london.geometry.bounds[2] - london.geometry.bounds[0],
                   london.geometry.bounds[3] - london.geometry.bounds[1])) + 620
    ax1 = fig.add_axes([0.06, 0.12, 0.42, 0.49])
    ax2 = fig.add_axes([0.53, 0.12, 0.42, 0.49])
    draw_service_map(ax1, roads, rushden, "Rushden Lakes · Large Retail Park", 0.639681, side)
    draw_service_map(ax2, roads, london, "London Road · Southend-on-Sea", 0.306324, side)
    legend = [Line2D([0], [0], color=BLUE, lw=1.6, label="Public motorised roads"),
              Line2D([0], [0], color=ORANGE, lw=1.6, label="Mapped service ways"),
              Patch(facecolor=TEAL, edgecolor=TEAL_DARK, alpha=0.35, label="Retail-centre boundary")]
    fig.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.5, 0.065),
               ncol=3, frameon=False, fontsize=8.5, labelcolor=INK)
    add_footer(fig, "Service share is calculated by length within 100 m of the retail-centre boundary. "
               "Source: GeoDS; OpenStreetMap extract, 5 Nov 2026. © OpenStreetMap contributors, ODbL 1.0.")
    save_figure(fig, "figure_02_service_roads")


def figure_pedestrian_and_grain(data, centres, roads):
    fig = plt.figure(figsize=(13.2, 9.4))
    add_heading(fig, "PEDESTRIAN ROUTES AND STREET GRAIN",
                "Pedestrian-way share and the spacing of links between street-network junctions")

    groups = [
        ("Regional Centre", {"Regional Centre"}),
        ("Major Town Centre", {"Major Town Centre"}),
        ("Town Centre", {"Town Centre"}),
        ("Market Town", {"Market Town"}),
        ("District Centre", {"District Centre"}),
        ("Local Centre", {"Local Centre"}),
        ("Small Local Centre", {"Small Local Centre"}),
        ("Retail Parks", PARK_TYPES),
    ]
    ax1 = fig.add_axes([0.08, 0.64, 0.40, 0.22])
    rows = group_summary(data, "carfree_share", groups)
    rows = list(reversed(rows))
    vals = np.array([r["median"] for r in rows])
    labels = [r["label"] for r in rows]
    colors = [ORANGE if label == "Retail Parks" else BLUE for label in labels]
    ax1.barh(np.arange(len(rows)), vals, color=colors, alpha=0.86, height=0.62, zorder=3)
    ax1.set_yticks(np.arange(len(rows)), labels, fontsize=8.2)
    ax1.set_xlim(0, 0.38)
    ax1.xaxis.set_major_formatter(mtick.PercentFormatter(1.0))
    ax1.set_xlabel("Median dedicated pedestrian-way share")
    for i, val in enumerate(vals):
        ax1.text(val + 0.006, i, f"{val:.1%}", va="center", fontsize=8.1, color=INK)
    style_chart(ax1)
    ax1.grid(axis="y", visible=False)

    ax2 = fig.add_axes([0.56, 0.67, 0.37, 0.19])
    grain_groups = [
        ("Regional Centres", {"Regional Centre"}),
        ("Street-based centres", STREET_TYPES),
        ("Retail parks", PARK_TYPES),
    ]
    grain = group_summary(data, "walk_median_edge_len_m", grain_groups)
    grain = list(reversed(grain))
    gv = np.array([r["median"] for r in grain])
    gl = [r["label"] for r in grain]
    gc = [ORANGE if label == "Retail parks" else BLUE for label in gl]
    ax2.barh(np.arange(len(grain)), gv, color=gc, alpha=0.86, height=0.55, zorder=3)
    ax2.set_yticks(np.arange(len(grain)), gl, fontsize=8.5)
    ax2.set_xlim(0, 70)
    ax2.set_xlabel("Median street-link length (metres)")
    for i, val in enumerate(gv):
        ax2.text(val + 1.0, i, f"{val:.1f} m", va="center", fontsize=8.2, color=INK)
    style_chart(ax2)
    ax2.grid(axis="y", visible=False)

    bristol = find_centre(centres, "Old City (Bristol City Centre)")
    leytonstone = centres.loc[
        centres["RC_Name"].eq("Leytonstone; Waltham Forest (London; England)")
    ].iloc[0]
    side = 1500
    ax3 = fig.add_axes([0.06, 0.11, 0.42, 0.45])
    ax4 = fig.add_axes([0.53, 0.11, 0.42, 0.45])
    draw_block_map(ax3, roads, bristol, "Bristol Old City · Regional Centre",
                   32.399814, 5079.331958, side)
    draw_block_map(ax4, roads, leytonstone, "Leytonstone · Town Centre",
                   41.230492, 16008.813279, side)
    legend = [Line2D([0], [0], color=BLUE_DARK, lw=1.4, label="Consolidated walkable street network"),
              Patch(facecolor=BLOCK, edgecolor="#fde68a", alpha=0.5, label="Illustrative enclosed blocks"),
              Patch(facecolor="none", edgecolor=TEAL, linewidth=1.0, label="Retail-centre boundary")]
    fig.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.5, 0.064),
               ncol=3, frameon=False, fontsize=8.3, labelcolor=INK)
    add_footer(fig, "Pedestrian-way share includes mapped footways, paths, steps and pedestrian streets after sidewalk filtering. "
               "Block map is illustrative; block-area scores are calculated for traditional street centres only. "
               "Source: GeoDS; OpenStreetMap extract, 5 Nov 2026. © OpenStreetMap contributors, ODbL 1.0.")
    save_figure(fig, "figure_03_pedestrian_routes_and_grain")


def main():
    if not ROADS_PATH.exists():
        raise FileNotFoundError(f"Missing road data: {ROADS_PATH}")
    data, centres, roads = load_inputs()
    figure_reach(data, centres, roads)
    figure_service(data, centres, roads)
    figure_pedestrian_and_grain(data, centres, roads)
    print(f"Figures written to: {OUT_DIR}")


if __name__ == "__main__":
    main()
