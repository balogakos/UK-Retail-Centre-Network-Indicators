"""Populate the Elsevier Data in Brief manuscript template for the UK Retail Centre Network Indicators dataset.

Produces:
  - ~/Downloads/data-in-brief-article-template-filled.docx
  - ~/Downloads/data-in-brief-article-template.docx (overwritten with filled version; original backed up to .bak)
  - docs/UK_Retail_Centre_Network_Indicators_Data_in_Brief.docx
"""

import shutil
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls


DOWNLOADS_DIR = Path.home() / "Downloads"
TEMPLATE_PATH = DOWNLOADS_DIR / "data-in-brief-article-template.docx"
BACKUP_PATH = DOWNLOADS_DIR / "data-in-brief-article-template.docx.bak"
OUT_FILLED_DOWNLOADS = DOWNLOADS_DIR / "data-in-brief-article-template-filled.docx"

ROOT = Path(__file__).resolve().parents[1]
OUT_DOCS = ROOT / "docs" / "UK_Retail_Centre_Network_Indicators_Data_in_Brief.docx"


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}><w:top w:w="{top}" w:type="dxa"/><w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/><w:right w:w="{right}" w:type="dxa"/></w:tcMar>'
    )
    tcPr.append(tcMar)


def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>'))


def create_filled_manuscript(template_path, out_paths):
    doc = docx.Document(template_path)

    # 1. Update Specifications Table (Table 0)
    t = doc.tables[0]

    # Row 0: Subject dropdown replacement
    r0 = t.rows[0]
    sdt_tc = r0._tr.find('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}sdt')
    if sdt_tc is not None:
        tc_xml = parse_xml(
            f'<w:tc {nsdecls("w")}><w:tcPr><w:tcW w:w="7455" w:type="dxa"/>'
            f'<w:tcBorders><w:top w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
            f'<w:bottom w:val="single" w:sz="8" w:space="0" w:color="000000"/>'
            f'<w:right w:val="single" w:sz="8" w:space="0" w:color="000000"/></w:tcBorders>'
            f'<w:tcMar><w:top w:w="80" w:type="dxa"/><w:left w:w="80" w:type="dxa"/><w:bottom w:w="80" w:type="dxa"/><w:right w:w="80" w:type="dxa"/></w:tcMar>'
            f'</w:tcPr><w:p><w:r><w:t>Social Sciences</w:t></w:r></w:p></w:tc>'
        )
        r0._tr.replace(sdt_tc, tc_xml)

    # Row 1: Specific subject area
    t.rows[1].cells[1].text = "Urban morphology, retail geography, and topological spatial network analysis"

    # Row 2: Type of data
    t.rows[2].cells[1].text = (
        "Table, Map, Spatial Vector Layer (GeoPackage .gpkg), Tabular Data (CSV, Columnar Parquet), "
        "JSON data structures, and Python reproduction scripts"
    )

    # Row 3: Data collection
    t.rows[3].cells[1].text = (
        "Extracted from Geofabrik OpenStreetMap UK PBF extract within 400 m of GeoDS Retail Centre Boundaries. "
        "Processed in Python using GeoPandas, Shapely, PyOGRio, and SciPy with bearing-aligned sidewalk filtering, "
        "10 m topology-aware junction consolidation, and metric Brandes shortest-path betweenness."
    )

    # Row 4: Data source location
    t.rows[4].cells[1].text = (
        "United Kingdom (England, Scotland, Wales, Northern Ireland)\n"
        "Geographical bounding box: Latitude 49.8° N to 60.9° N; Longitude 8.2° W to 1.8° E"
    )

    # Row 5: Data accessibility
    t.rows[5].cells[1].text = (
        "Repository name: GitHub and Zenodo\n"
        "Data identification number: https://doi.org/10.5281/zenodo.placeholder\n"
        "Direct URL to data: https://github.com/balogakos/UK-Retail-Centre-Network-Indicators\n"
        "Instructions for accessing these data: All derivative datasets are open access and directly downloadable "
        "from the Output Data/ directory of the repository in GeoPackage (.gpkg), CSV (.csv), and Parquet (.parquet) "
        "formats. Python calculation scripts and an interactive Leaflet web explorer are included."
    )

    # Row 6: Related research article
    t.rows[6].cells[1].text = "None"

    # Clean styling for Table 0 cells
    for row in t.rows:
        for cell in row.cells:
            cell.paragraphs[0].runs[0].font.size = Pt(9.5)
            cell.paragraphs[0].runs[0].font.name = "Calibri"

    # Create fresh document using template's styles to ensure pristine layout without deleted artifact paragraphs
    new_doc = docx.Document()

    # Match margins (1 inch)
    for section in new_doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Helper functions for adding sections
    def add_h1(text):
        p = new_doc.add_paragraph()
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(14)
        run.font.color.rgb = RGBColor(0, 51, 102)
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        return p

    def add_h2(text):
        p = new_doc.add_paragraph()
        run = p.add_run(text)
        run.bold = True
        run.font.size = Pt(11.5)
        run.font.color.rgb = RGBColor(0, 51, 102)
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        return p

    def add_p(text, bold_prefix=None, space_after=6, italic=False):
        p = new_doc.add_paragraph()
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r_b = p.add_run(bold_prefix)
            r_b.bold = True
            r_b.font.size = Pt(10)
        r_t = p.add_run(text)
        r_t.font.size = Pt(10)
        if italic:
            r_t.italic = True
        return p

    def add_bullet(text, bold_prefix=None):
        p = new_doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r_b = p.add_run(bold_prefix)
            r_b.bold = True
            r_b.font.size = Pt(10)
        r_t = p.add_run(text)
        r_t.font.size = Pt(10)
        return p

    # --- ARTICLE INFORMATION ---
    add_h1("ARTICLE INFORMATION")

    add_p("A national topological street-network morphology dataset for 9,623 United Kingdom retail centres", bold_prefix="Article title: ")
    add_p("Ákos Balog*", bold_prefix="Authors: ")
    add_p(
        "Geographic Data Service, Department of Geography and Planning, School of Environmental Sciences, "
        "University of Liverpool, Roxby Building, 74 Bedford Street South, Liverpool, L69 7ZT, United Kingdom",
        bold_prefix="Affiliations: "
    )
    add_p("a.balog@liverpool.ac.uk", bold_prefix="Corresponding author email address: ")
    add_p("Retail centres; Street network morphology; OpenStreetMap; Walkability; Urban form; Spatial network analysis", bold_prefix="Keywords: ")

    add_h2("Abstract")
    add_p(
        "This dataset provides standardized, topologically validated street-network morphology indicators for all "
        "9,623 retail centres delineated across the United Kingdom by the Geographic Data Service (GeoDS). Derived from "
        "2,646,803 highway segments extracted from OpenStreetMap, the dataset addresses recurring volunteer micro-mapping "
        "and topological biases in sub-kilometre retail boundaries through three methodological controls: (1) a dual-criteria "
        "sidewalk filter combining metric proximity (<= 12 m) and local tangent bearing alignment (<= 25 degrees) to remove "
        "duplicate roadside pavements without discarding genuine cross-cutting paths; (2) separation of off-street car-park "
        "circulation loops (highway=service) to prevent parking aisles from distorting street-block statistics; and (3) topology-aware "
        "10 m junction consolidation to prevent transitive clustering across parallel carriageways. The dataset comprises 11 indicators "
        "spanning eight theoretical dimensions: a 9-indicator Universal Core Set for all 9,623 centres (400 m walkable reach, "
        "400 m road embeddedness, arterial road share, service way share, pedestrian-way share, median street-link length, "
        "network meshedness, sightline continuity, and weighted Brandes distance-limited edge betweenness flow concentration) "
        "and a 2-indicator Street-Grid Set for the 1,521 traditional street centres (median enclosed block area and street orientation "
        "entropy). Technical validation demonstrates high parameter perturbation rank stability (Spearman rho >= 0.88 to 0.99 "
        "across buffer, consolidation, and sidewalk variants), independence from centre footprint area, elimination of regional "
        "volunteer pavement-mapping bias (epsilon^2 = 0.026), and strong non-parametric separation across the retail hierarchy. "
        "The data are provided in spatial GeoPackage (.gpkg), tabular CSV, and Parquet formats, supported by an open-source "
        "interactive web map explorer."
    )

    # --- SPECIFICATIONS TABLE ---
    add_h1("SPECIFICATIONS TABLE")

    # Re-insert the specifications table
    spec_table = new_doc.add_table(rows=7, cols=2)
    spec_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    spec_table.autofit = False

    spec_data = [
        ("Subject", "Social Sciences"),
        ("Specific subject area", "Urban morphology, retail geography, and topological spatial network analysis"),
        ("Type of data", "Table, Map, Spatial Vector Layer (GeoPackage .gpkg), Tabular Data (CSV, Columnar Parquet), JSON data structures, and Python reproduction scripts"),
        ("Data collection", (
            "Extracted from Geofabrik OpenStreetMap UK PBF extract within 400 m of GeoDS Retail Centre Boundaries. "
            "Processed in Python using GeoPandas, Shapely, PyOGRio, and SciPy with bearing-aligned sidewalk filtering, "
            "10 m topology-aware junction consolidation, and metric Brandes shortest-path betweenness."
        )),
        ("Data source location", (
            "United Kingdom (England, Scotland, Wales, Northern Ireland)\n"
            "Geographical bounding box: Latitude 49.8° N to 60.9° N; Longitude 8.2° W to 1.8° E"
        )),
        ("Data accessibility", (
            "Repository name: GitHub and Zenodo\n"
            "Data identification number: https://doi.org/10.5281/zenodo.placeholder\n"
            "Direct URL to data: https://github.com/balogakos/UK-Retail-Centre-Network-Indicators\n"
            "Instructions for accessing these data: All derivative datasets are open access and directly downloadable "
            "from the Output Data/ directory of the repository in GeoPackage (.gpkg), CSV (.csv), and Parquet (.parquet) "
            "formats. Python calculation scripts and an interactive Leaflet web explorer are included."
        )),
        ("Related research article", "None")
    ]

    col_widths = [Inches(2.0), Inches(4.5)]
    for r_idx, (label, val) in enumerate(spec_data):
        row = spec_table.rows[r_idx]
        c0, c1 = row.cells[0], row.cells[1]
        c0.width = col_widths[0]
        c1.width = col_widths[1]

        p0 = c0.paragraphs[0]
        r0 = p0.add_run(label)
        r0.bold = True
        r0.font.size = Pt(9.5)

        p1 = c1.paragraphs[0]
        r1 = p1.add_run(val)
        r1.font.size = Pt(9.5)

        set_cell_background(c0, "F2F2F2")
        set_cell_margins(c0, 80, 80, 100, 100)
        set_cell_margins(c1, 80, 80, 100, 100)

    # --- VALUE OF THE DATA ---
    add_h1("VALUE OF THE DATA")
    add_bullet(
        "Provides the first standardized, topologically validated street-network morphology dataset covering all "
        "9,623 officially delineated retail centres across the United Kingdom, spanning 10 hierarchical tiers from small "
        "neighbourhood shopping parades to major regional city cores.",
        bold_prefix="Comprehensive national coverage: "
    )
    add_bullet(
        "Solves systematic OpenStreetMap confounders (roadside pavement micro-mapping, transitively collapsed intersections, "
        "and car-park circulation loops) through bearing-aligned sidewalk filtering and Boeing (2025) topology-aware junction consolidation.",
        bold_prefix="Resolution of volunteer mapping distortions: "
    )
    add_bullet(
        "Quantifies eight distinct dimensions of urban form (reach, car dominance, servicing, pedestrian priority, link grain, "
        "route redundancy, sightline legibility, and through-movement flow concentration) using exact mathematical formulations, "
        "including weighted Brandes betweenness with complete predecessor accounting.",
        bold_prefix="Theoretical and mathematical rigor: "
    )
    add_bullet(
        "Designed for direct empirical linkage with Census 2021 active travel statistics, mobile device footfall data, "
        "commercial retail vacancy registries, and municipal electric vehicle charging deployment strategies.",
        bold_prefix="Cross-disciplinary research reuse: "
    )
    add_bullet(
        "Fully reproducible via self-contained Python scripts, accompanied by machine-readable data provenance metadata, "
        "a technical validation scorecard, parameter perturbation tables, and an interactive open-source web map explorer.",
        bold_prefix="Reproducibility and public dissemination: "
    )

    # --- BACKGROUND ---
    add_h1("BACKGROUND")
    add_p(
        "Retail centres have experienced profound structural restructuring driven by e-commerce, shifting consumer habits, "
        "and changing mobility patterns. While economic indicators such as retail vacancies and footfall indices are widely tracked, "
        "spatial quantitative analyses often rely on administrative boundary outlines or demographic centroids without capturing "
        "the street network configuration that governs physical accessibility and walk-in trade. Applying standard city-scale "
        "street network tools (e.g. basic OSMnx primal graphs) to sub-kilometre retail centre boundaries introduces severe "
        "methodological biases: volunteer pavement mapping creates false intersections, car-park loops in retail parks mimic dense "
        "historic urban blocks, and small-sample boundary effects distort entropy calculations in linear shopping parades. "
        "This dataset was developed to provide a standardized, scale-controlled, and topologically validated morphological baseline "
        "for every commercial centre in the United Kingdom, establishing reliable physical metrics for urban researchers, "
        "transport planners, and retail geographers."
    )

    # --- DATA DESCRIPTION ---
    add_h1("DATA DESCRIPTION")
    add_p(
        "The dataset is hosted in an open-access repository organized into raw inputs, modular Python scripts, validated output datasets, "
        "and an interactive web application. The primary data assets comprise:"
    )
    add_bullet(
        "The primary spatial dataset containing boundary polygons and 11 morphological indicators for all 9,623 centres in British National Grid (EPSG:27700).",
        bold_prefix="Output Data/UK_Retail_Centre_Network_Indicators.gpkg: "
    )
    add_bullet(
        "Tabular export of all centre attributes, indicators, and classification tiers.",
        bold_prefix="Output Data/UK_Retail_Centre_Network_Indicators.csv: "
    )
    add_bullet(
        "Full technical validation report detailing missingness counts, correlations with centre area, sidewalk-mapping density correlations, regional effect sizes (epsilon^2), and non-parametric hierarchy contrasts (Cliff's delta).",
        bold_prefix="Output Data/Validation_Scorecard.csv: "
    )
    add_bullet(
        "Perturbation sensitivity analysis testing Spearman rank stability across buffer sizes (320 m to 480 m), consolidation radii (8 m to 12 m), and sidewalk filter thresholds.",
        bold_prefix="Output Data/Validation_Robustness.csv: "
    )
    add_bullet(
        "13 high-resolution cartographic figures depicting methodological controls, the UK overview pop-out map, and national distribution profiles for each indicator.",
        bold_prefix="Output Data/Figures/: "
    )
    add_bullet(
        "A client-side Leaflet web app and optimized JSON structures enabling interactive search, spatial filtering, and side-by-side radar chart comparisons across all centres.",
        bold_prefix="explorer/: "
    )

    add_h2("Data Dictionary")
    add_p("Table 1 defines the 11 morphological indicators, their operational definitions, spatial readouts, units, and observed ranges across the UK retail centre network.")

    # Data Dictionary Table
    dict_table = new_doc.add_table(rows=12, cols=5)
    dict_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    dict_table.autofit = False

    dict_headers = ["Indicator", "Construct", "Spatial Readout", "Unit", "Expected Range & National Median"]
    for c_idx, h in enumerate(dict_headers):
        cell = dict_table.rows[0].cells[c_idx]
        p = cell.paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(8.5)
        set_cell_background(cell, "003366")
        r.font.color.rgb = RGBColor(255, 255, 255)
        set_cell_margins(cell, 60, 60, 80, 80)

    dict_rows = [
        ("walk_reach_400", "Walkable Reach", "0-400 m exterior ring", "% (0-1)", "0.00 to 0.93 (Median: 0.63, IQR: 0.52 to 0.72)"),
        ("drive_reach_400", "Road Embeddedness", "0-400 m exterior ring", "% (0-1)", "0.01 to 1.00 (Median: 0.63, IQR: 0.52 to 0.71)"),
        ("arterial_share", "Arterial Road Dominance", "100 m core buffer", "% (0-1)", "0.00 to 1.00 (Median: 0.25, IQR: 0.15 to 0.35)"),
        ("service_share", "Service & Parking Share", "100 m core buffer", "% (0-1)", "0.00 to 0.97 (Median: 0.29, IQR: 0.18 to 0.44)"),
        ("carfree_share", "Pedestrian-Way Share", "100 m core buffer", "% (0-1)", "0.00 to 1.00 (Median: 0.14, IQR: 0.08 to 0.23)"),
        ("walk_median_edge_len_m", "Street-Network Grain", "100 m core buffer", "metres", "12.0 to 852.6 m (Median: 50.1 m, IQR: 40.5 to 63.4 m)"),
        ("walk_meshedness", "Cyclic Redundancy", "100 m core buffer", "ratio (0-1)", "0.00 to 0.30 (Median: 0.065, IQR: 0.040 to 0.091)"),
        ("walk_sightline_continuity", "Sightline Continuity", "100 m core buffer", "ratio (0-1)", "0.00 to 1.00 (Median: 0.897, IQR: 0.829 to 0.948)"),
        ("flow_concentration", "Flow Concentration", "100 m core buffer", "Gini (0-1)", "0.00 to 0.77 (Median: 0.442, IQR: 0.392 to 0.490)"),
        ("walk_block_median_area_m2", "Urban Block Scale", "100 m core buffer", "m²", "975 to 60,327 m² (Median: 6,910 m², IQR: 4,490 to 10,670 m²)"),
        ("orientation_entropy", "Grid Orientation Entropy", "100 m core buffer", "entropy", "0.493 to 0.991 (Median: 0.920, IQR: 0.877 to 0.951)")
    ]

    t_widths = [Inches(1.5), Inches(1.3), Inches(1.2), Inches(0.8), Inches(1.7)]
    for r_idx, row_vals in enumerate(dict_rows, 1):
        row = dict_table.rows[r_idx]
        for c_idx, val in enumerate(row_vals):
            cell = row.cells[c_idx]
            cell.width = t_widths[c_idx]
            p = cell.paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(8.0)
            if c_idx == 0:
                r.bold = True
            set_cell_margins(cell, 50, 50, 60, 60)
            if r_idx % 2 == 1:
                set_cell_background(cell, "F9FBFD")

    # --- EXPERIMENTAL DESIGN, MATERIALS AND METHODS ---
    add_h1("EXPERIMENTAL DESIGN, MATERIALS AND METHODS")

    add_h2("1. Spatial Boundary Definitions and Extraction")
    add_p(
        "Retail centre polygons are obtained from the Geographic Data Service (GeoDS) Retail Centre Boundaries dataset "
        "(N = 9,623 in EPSG:27700). High-speed highway ways within 400 m of all centre boundaries were extracted from the Geofabrik "
        "OpenStreetMap UK extract (size 2.28 GB, timestamp 2026-11-05T16:12:58Z, SHA-256 fingerprint d07046874ca657c9) using PyOGRio "
        "and Osmium, yielding 2,646,803 highway segments. Attributes preserved include highway classification, footway, service, "
        "access, foot, motor_vehicle, oneway, bridge, tunnel, and layer tags."
    )

    add_h2("2. Bearing-Aligned Sidewalk Detection Algorithm")
    add_p(
        "To neutralise volunteer pavement-mapping bias without discarding genuine footpaths, detect_parallel_sidewalks implements a "
        "two-stage test: (1) explicit filtering of footway=sidewalk, crossing, and traffic_island tags; and (2) spatial matching of untagged "
        "highway=footway segments (length >= 8 m). Ways are sampled at 10 m intervals along with their local unit tangent vectors and "
        "queried against an STRtree of motorised roads. A sample point constitutes a parallel sidewalk hit if it lies within <= 12 m of a "
        "road and aligns within <= 25 degrees (mod 180 degrees) of that road's bearing. Ways with >= 75% parallel hits are classified as "
        "sidewalks and filtered out of the walkable network."
    )

    add_h2("3. Car-Park Service Way Separation")
    add_p(
        "Internal car-park aisles, drive-through lanes, and loading docks (highway=service) inside retail centres mimic dense urban "
        "grids if left unmanaged. Service ways are retained for service_share calculation but excluded before constructing the "
        "street-topology graph used for junction spacing, meshedness, betweenness concentration, block scale, and entropy."
    )

    add_h2("4. Topology-Aware Junction Consolidation")
    add_p(
        "Ground-level ways are planarised at intersections while preserving grade-separated bridges and tunnels. Coincident endpoints "
        "within 0.5 m are snapped to create the initial planar graph G0. Following Boeing (2025), nodes within 10 m Euclidean radius "
        "are merged only if topologically connected in G0 within a short network path (<= 25 m) or within 1.5 m endpoint snap, without "
        "collapsing intervening edges > 25 m, and constrained to within 10 m of the cluster seed to prevent transitive chaining across "
        "parallel carriageways."
    )

    add_h2("5. Mathematical Indicator Formulations")
    add_p(
        "Indicators are computed across two spatial readouts: a 100 m core buffer for internal morphology, and a 0 to 400 m exterior "
        "ring for neighbourhood embeddedness:\n"
        "• Walkable Reach (walk_reach_400): Ratio of walkable network length reachable within a 400 m Dijkstra network traversal from the "
        "centre boundary relative to the total walkable network length within the 400 m ring.\n"
        "• Road Embeddedness (drive_reach_400): Ratio of drivable road network length reachable within 400 m graph traversal relative to "
        "total drivable road length in the ring.\n"
        "• Arterial Road Share (arterial_share): Proportion of motorised road length in the 100 m core classified as trunk, primary, or secondary.\n"
        "• Service Way Share (service_share): Proportion of motorised road length in the core classified as service or parking aisles.\n"
        "• Pedestrian-Way Share (carfree_share): Proportion of walkable network length in the core dedicated to traffic-free footways, paths, "
        "steps, and pedestrian streets after sidewalk removal.\n"
        "• Street Grain (walk_median_edge_len_m): Median edge length between consolidated degree-3+ street junctions in the core.\n"
        "• Street Meshedness (walk_meshedness): Planar cyclic link density M = (E - V + F_ext) / (2V - 5) for consolidated street junctions.\n"
        "• Sightline Continuity (walk_sightline_continuity): Ratio of Euclidean straight-line endpoint distance to actual network path length "
        "along street segments in the core.\n"
        "• Flow Concentration (flow_concentration): Gini coefficient of distance-limited edge betweenness centralities. Exact shortest-path "
        "distances up to 400.0 m are computed from every node via scipy.sparse.csgraph.dijkstra, followed by weighted Brandes (2001, 2008) "
        "forward path counting (sigma) and backward dependency accumulation across all equal-shortest predecessors within 1e-7 m tolerance.\n"
        "• Median Block Area (walk_block_median_area_m2): Median area of enclosed planar faces generated via polygonization of consolidated "
        "street edges within the core (traditional street centres only).\n"
        "• Grid Orientation Entropy (orientation_entropy): Normalized Shannon entropy of street segment bearings across 36 compass bins."
    )

    add_h2("6. Technical Validation Protocol")
    add_p(
        "Validation checks were conducted across completeness, area confounding (Spearman rho with Area_km2), volunteer mapping density "
        "(Spearman rho with sidewalk_mapped_share), regional spatial dependence (Kruskal-Wallis epsilon^2 across 12 UK regions), and "
        "discriminant effect sizes (Cliff's delta) across the retail hierarchy. A stratified perturbation analysis across 525 centres "
        "confirmed rank robustness under +/- 20% variations in buffer radii, consolidation thresholds, and sidewalk sampling distances."
    )

    # --- LIMITATIONS ---
    add_h1("LIMITATIONS")
    add_p(
        "Four limitations apply to this dataset: (1) The indicators capture structural and morphological network potential, "
        "not real-time observed pedestrian footfall volumes, transit ridership, or store revenues. (2) Road network embeddedness "
        "(drive_reach_400) is evaluated as an undirected structural connectivity metric; it does not account for legal one-way "
        "driving restrictions or turn prohibitions. (3) Block area (walk_block_median_area_m2) and street orientation entropy "
        "(orientation_entropy) are restricted to the 1,521 traditional street centres and omitted (recorded as NaN) for Small Local "
        "Centres (N = 6,883) and retail parks, where fewer than 15 street links create finite-sample boundary distortion. "
        "(4) Catchment boundaries are evaluated at a fixed 400 m Euclidean buffer (approximately a 5-minute pedestrian walk); "
        "wider catchments (e.g., 800 m or 1,200 m) may be required when analysing cycling access or regional vehicle catchments."
    )

    # --- ETHICS STATEMENT ---
    add_h1("ETHICS STATEMENT")
    add_p(
        "The authors have read and follow the ethical requirements for publication in Data in Brief and confirm that the current "
        "work does not involve human subjects, animal experiments, or any data collected from social media platforms."
    )

    # --- CRediT AUTHOR STATEMENT ---
    add_h1("CRediT AUTHOR STATEMENT")
    add_p(
        "Ákos Balog: Conceptualization, Methodology, Software, Validation, Formal analysis, Data Curation, Writing - Original Draft, "
        "Visualization, Project administration."
    )

    # --- ACKNOWLEDGEMENTS ---
    add_h1("ACKNOWLEDGEMENTS")
    add_p(
        "The author thanks OpenStreetMap contributors for geospatial highway data and the Geographic Data Service (GeoDS) at the "
        "University of Liverpool for providing the UK Retail Centre Boundaries dataset. This research did not receive any specific "
        "grant from funding agencies in the public, commercial, or not-for-profit sectors."
    )

    # --- DECLARATION OF COMPETING INTERESTS ---
    add_h1("DECLARATION OF COMPETING INTERESTS")
    add_p(
        "The authors declare that they have no known competing financial interests or personal relationships that could have "
        "appeared to influence the work reported in this paper."
    )

    # --- REFERENCES ---
    add_h1("REFERENCES")
    refs = [
        "[1] G. Boeing, OSMnx: New methods for acquiring, constructing, analyzing, and visualizing complex street networks, Comput. Environ. Urban Syst. 65 (2017) 126-139. https://doi.org/10.1016/j.compenvurbsys.2017.05.004.",
        "[2] G. Boeing, Urban spatial order: Street network orientation, configuration, and entropy, Appl. Netw. Sci. 4 (2019) 67. https://doi.org/10.1007/s41109-019-0189-1.",
        "[3] G. Boeing, Topological graph simplification: Solutions to the street intersection miscount problem, Trans. GIS 29 (2025) e70037. https://doi.org/10.1111/tgis.70037.",
        "[4] U. Brandes, A faster algorithm for betweenness centrality, J. Math. Sociol. 25 (2001) 163-177. https://doi.org/10.1080/0022250X.2001.9990249.",
        "[5] U. Brandes, On variants of shortest-path betweenness centrality and their generic computation, Soc. Networks 30 (2008) 136-145. https://doi.org/10.1016/j.socnet.2007.11.001.",
        "[6] J. Buhl, J. Gautrais, N. Reeves, R.V. Sole, S. Valverde, P. Kuntz, G. Theraulaz, Topological patterns in street networks of self-organized urban settlements, Eur. Phys. J. B 49 (2006) 513-522. https://doi.org/10.1140/epjb/e2006-00085-1.",
        "[7] L.C. Freeman, A set of measures of centrality based on betweenness, Sociometry 40 (1977) 35-41. https://doi.org/10.2307/3033543.",
        "[8] J. Gehl, Cities for People, Island Press, Washington, DC, 2010.",
        "[9] B. Hillier, Space is the Machine: A Architectural Theory, Cambridge University Press, Cambridge, 1996.",
        "[10] J. Jacobs, The Death and Life of Great American Cities, Random House, New York, 1961.",
        "[11] R. Louf, M. Barthelemy, A typology of street networks, J. R. Soc. Interface 11 (2014) 20140924. https://doi.org/10.1098/rsif.2014.0924.",
        "[12] S. Marshall, Streets and Patterns, Spon Press, London, 2005.",
        "[13] S. Porta, P. Crucitti, V. Latora, The network analysis of urban streets: A primal approach, Environ. Plann. B Plann. Des. 33 (2006) 705-725. https://doi.org/10.1068/b32045.",
        "[14] A. Sevtsuk, M. Mekonnen, Urban network analysis: A new toolbox for ArcGIS, Rev. Int. Geomat. 22 (2012) 287-305. https://doi.org/10.3166/rig.22.287-305.",
        "[15] A. Siksna, The effects of block size and form in North American and Australian city centres, Urban Morphol. 1 (1997) 19-33. https://doi.org/10.51347/jum.v1i1.4048."
    ]
    for ref in refs:
        add_p(ref, space_after=3)

    # Save to all target paths
    for p in out_paths:
        p.parent.mkdir(parents=True, exist_ok=True)
        new_doc.save(p)
        print(f"Saved populated Data in Brief manuscript to: {p}")


def main():
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found at: {TEMPLATE_PATH}")

    # Create backup of raw template
    if not BACKUP_PATH.exists():
        shutil.copy2(TEMPLATE_PATH, BACKUP_PATH)
        print(f"Backed up raw template to: {BACKUP_PATH}")

    out_paths = [
        OUT_FILLED_DOWNLOADS,
        TEMPLATE_PATH,  # Overwrite downloaded template directly
        OUT_DOCS
    ]

    create_filled_manuscript(TEMPLATE_PATH, out_paths)
    print("Data in Brief template successfully filled.")


if __name__ == "__main__":
    main()
