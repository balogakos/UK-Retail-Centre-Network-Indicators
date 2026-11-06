# UK-Retail-Centre-Network-Indicators
### Akos Balog

----

Welcome to the UK Retail Centre Street-Network Indicators repository. Here we provide open-access street-network morphology indicators, validation outputs, and self-contained Python code for the 9,623 UK retail centres delineated by the [Geographic Data Service (GeoDS)](https://geods.ac.uk).

## 1. Overview & Data Products

Indicators are developed for the UK release of the Geographic Data Service ([GeoDS](https://geods.ac.uk)) [Retail Centre Boundaries](https://data.geods.ac.uk/dataset/retail-centre-boundaries) dataset (`N = 9,623` retail centres in `EPSG:27700`, included in [`Input Data/retailcentre_bounds_uk.gpkg`](Input%20Data/retailcentre_bounds_uk.gpkg)) paired with multimodal street and footpath networks extracted from OpenStreetMap (`united-kingdom-latest.osm.pbf`).

To control for OpenStreetMap pavement-mapping habits, polygon size, false endpoint snapping, and off-street car-park loops, the indicators are organised into a two-tier architecture and evaluated across completeness, parameter perturbation robustness, discriminant validity (against centre area and sidewalk mapping), and convergent validity across retail hierarchy tiers and formats:

1. **Universal Core Set (9 Indicators — All 9,623 Retail Centres):**
   - **External Network Embeddedness:** `walk_reach_400`, `drive_reach_400`
   - **Car Dominance & Servicing:** `arterial_share`, `service_share`
   - **Dedicated Pedestrian Ways:** `carfree_share`
   - **Street Grain & Redundancy:** `walk_median_edge_len_m`, `walk_meshedness`
   - **Descriptive Legibility & Through-Movement:** `walk_sightline_continuity`, `flow_concentration`

2. **Street-Grid Set (2 Indicators — 1,521 Traditional Street Centres):**
   - **Block Scale & Grid Order:** `walk_block_median_area_m2`, `orientation_entropy`
   - *Scope note:* These two street-grid metrics are computed for traditional street-network centres (`Regional Centre`, `Major Town Centre`, `Town Centre`, `Market Town`, `District Centre`, and `Local Centre`; `N = 1,521`) and set to `NaN` for `Small Local Centres` (which lack sufficient edges to populate directional histograms or enclosed blocks) and out-of-town `Retail Parks` / `Shopping Centres`.

![UK Retail Centre Street-Network Morphologies](Output%20Data/Figures/uk_retail_centre_indicator_popouts.png)

### 1.1 Download the Indicators & Validation Tables

All released indicators and reproducible validation tables are located in the `Output Data/` directory:

- **Geopackage (Polygons + Indicators):** [UK_Retail_Centre_Network_Indicators.gpkg](Output%20Data/UK_Retail_Centre_Network_Indicators.gpkg)
- **Lookup Table (CSV):** [UK_Retail_Centre_Network_Indicators.csv](Output%20Data/UK_Retail_Centre_Network_Indicators.csv)
- **Validation Scorecard (CSV):** [Validation_Scorecard.csv](Output%20Data/Validation_Scorecard.csv)
- **Parameter Perturbation Robustness Table (CSV):** [Validation_Robustness.csv](Output%20Data/Validation_Robustness.csv)
- **Representative Centre Profiles (CSV):** [Indicator_Profile_Examples.csv](Output%20Data/Indicator_Profile_Examples.csv)

### 1.2 Reproducible Self-Contained Pipeline

All scripts use repository-relative paths and compute indicators from scratch without relying on pre-computed intermediate tables:

- [Core Graph & Indicator Library (`Source Code/Helper_Functions.py`)](Source%20Code/Helper_Functions.py)
- [1. Extracting OpenStreetMap Highway Networks (`Analysis Code/01_Extract_OSM_Networks.py`)](Analysis%20Code/01_Extract_OSM_Networks.py) — extracts highway ways within 400 m of [`Input Data/retailcentre_bounds_uk.gpkg`](Input%20Data/retailcentre_bounds_uk.gpkg) from `Input Data/united-kingdom-latest.osm.pbf` into `Input Data/uk_roads_400m.parquet` (preserving `footway`, `service`, `access`, `foot`, `motor_vehicle`, `oneway`, `bridge`, `tunnel`, and `layer` tags).
- [2. Calculating Street-Network Indicators (`Analysis Code/02_Calculate_Network_Indicators.py`)](Analysis%20Code/02_Calculate_Network_Indicators.py) — computes all 11 indicators and `sidewalk_mapped_share` directly from `Input Data/retailcentre_bounds_uk.gpkg` and `Input Data/uk_roads_400m.parquet`.
- [3. Validating Network Indicators (`Analysis Code/03_Validate_Network_Indicators.py`)](Analysis%20Code/03_Validate_Network_Indicators.py) — generates both [`Validation_Scorecard.csv`](Output%20Data/Validation_Scorecard.csv) and the stratified perturbation sensitivity table [`Validation_Robustness.csv`](Output%20Data/Validation_Robustness.csv).
- [4. Generating Representative Visual Profiles (`Analysis Code/04_Generate_Indicator_Profiles.py`)](Analysis%20Code/04_Generate_Indicator_Profiles.py) — renders the national overview map [`uk_retail_centre_indicator_popouts.png`](Output%20Data/Figures/uk_retail_centre_indicator_popouts.png), the 11 distribution profile maps [`Output Data/Figures/profile_01_*.png` to `profile_11_*.png`](Output%20Data/Figures/), and exports [`Indicator_Profile_Examples.csv`](Output%20Data/Indicator_Profile_Examples.csv).

----

## 2. Methodological Controls & Validation Summary

### 2.1 Controlling for Sidewalk Mapping, Topology-Aware Junction Consolidation, and Car-Park Loops

Raw OpenStreetMap street graphs introduce three systematic biases when applied to retail centres:

1. **Bearing-Aligned Parallel Sidewalk Detection (`detect_parallel_sidewalks`):** In cities where OSM contributors map roadside pavements as separate `highway=footway` ways, naive topological metrics count every pavement crossing as extra street junctions and treat roadside pavements as car-free streets. Our filter removes explicitly tagged pavements (`footway=sidewalk`, `crossing`, `traffic_island`) and untagged `footway` ways ($\ge 8\text{ m}$) where $\ge 75\%$ of sampled points (spaced every $10\text{ m}$) lie within $12\text{ m}$ of a motorised road **and** align within $\le 25^\circ \pmod{180^\circ}$ of the matched road's local tangent bearing. Checking both proximity and parallel bearing alignment prevents genuine perpendicular or diverging footpaths near roads from being discarded as sidewalks.
2. **Topology-Aware 10 m Junction Consolidation (`build_consolidated_graph`):** Ground-level ways are planarised at intersections (preserving grade-separated bridges and tunnels) and coincident endpoints ($\le 0.5\text{ m}$) are snapped to form the true planar graph $G_0$. Following [Boeing (2025)](https://doi.org/10.1111/tgis.70037), nearby nodes within a **10 m Euclidean tolerance** are consolidated only if they are **topologically connected in $G_0$ within a short network path ($\le 25\text{ m}$)** or within a $1.5\text{ m}$ endpoint snap tolerance, do not collapse a connecting street segment $> 25\text{ m}$ into a self-loop, and lie within $10\text{ m}$ of their cluster seed (preventing transitive chaining across parallel streets or carriageways).
3. **Car-Park Loop Separation (`gw_street`):** Off-street car-park circulation (`highway=service`) is measured explicitly via `service_share` and excluded prior to computing all six internal street-topology indicators (`walk_median_edge_len_m`, `walk_meshedness`, `walk_sightline_continuity`, `flow_concentration`, `walk_block_median_area_m2`, and `orientation_entropy`), preventing 20 m parking-bay aisles from masquerading as fine-grained urban streets or small street blocks.

![Visual QA of Sidewalk Removal and 10 m Junction Consolidation](Output%20Data/Figures/visual_qa_sidewalk_consolidation.png)

### 2.2 Discriminant & Convergent Validation Scorecard

| Indicator | Scope (`N`) | Missing (%) | Median (IQR) | $\rho_{\text{area}}$ (Street Centres) | Within-Tier $\|\rho_{\text{area}}\|$ | $\rho_{\text{sidewalk}}$ | $\eta^2_{\text{region}}$ | Cliff's $\delta$ (Hierarchy) | Cliff's $\delta$ (Retail Park vs. High Street) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `walk_reach_400` | Universal (`9,623`) | 0.06% | 0.628 (0.545–0.696) | +0.135 | 0.139 | -0.156 | 0.027 | +0.351 | -0.687 |
| `drive_reach_400` | Universal (`9,623`) | 1.21% | 0.627 (0.536–0.707) | +0.195 | 0.180 | -0.040 | 0.007 | +0.260 | -0.590 |
| `arterial_share` | Universal (`9,623`) | 0.53% | 0.253 (0.058–0.370) | +0.125 | 0.088 | +0.099 | 0.013 | +0.149 | +0.444 |
| `service_share` | Universal (`9,623`) | 0.53% | 0.292 (0.185–0.412) | +0.086 | 0.199 | +0.013 | 0.049 | -0.145 | +0.689 |
| `carfree_share` | Universal (`9,623`) | 0.02% | 0.144 (0.074–0.229) | +0.165 | 0.066 | +0.025 | 0.026 | +0.668 | -0.345 |
| `walk_median_edge_len_m` | Universal (`9,623`) | 0.39% | 50.1 m (40.3–63.9) | -0.187 | 0.062 | -0.127 | 0.010 | -0.632 | +0.036 |
| `walk_meshedness` | Universal (`9,623`) | 0.39% | 0.065 (0.036–0.094) | +0.320 | 0.189 | +0.006 | 0.027 | +0.548 | -0.303 |
| `walk_sightline_continuity` | Universal (`9,623`) | 1.73% | 0.897 (0.833–0.952) | -0.072 | 0.113 | +0.033 | 0.036 | -0.014 | -0.132 |
| `flow_concentration` | Universal (`9,623`) | 0.77% | 0.442 (0.392–0.494) | +0.261 | 0.194 | +0.257 | 0.010 | +0.563 | +0.188 |
| `walk_block_median_area_m2` | Street-Grid (`1,521`) | 0.07% | 6,910 $\text{m}^2$ (4,696–10,338) | -0.073 | 0.081 | +0.026 | 0.070 | -0.418 | — |
| `orientation_entropy` | Street-Grid (`1,521`) | 0.00% | 0.920 (0.877–0.948) | +0.311 | 0.134 | -0.045 | 0.047 | +0.191 | — |

### 2.3 Parameter Perturbation Robustness (`Validation_Robustness.csv`)

Evaluated on a stratified random sample of $n = 525$ UK retail centres across all 10 retail classifications by [03_Validate_Network_Indicators.py](Analysis%20Code/03_Validate_Network_Indicators.py), testing Spearman rank stability ($\rho$) against core readout buffer perturbations (`50 m` and `150 m` vs. `100 m` baseline), junction consolidation tolerances (`5 m` and `15 m` vs. `10 m` baseline), and sidewalk retention (`keep_sidewalks`):

| Indicator | Sample `N` | $\rho$ (`buf = 50 m`) | $\rho$ (`buf = 150 m`) | $\rho$ (`tol = 5 m`) | $\rho$ (`tol = 15 m`) | $\rho$ (`keep_sidewalks`) | $\min \rho$ (Geometric Perturbations) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `walk_reach_400` | 525 | 1.000 | 1.000 | 0.997 | 0.994 | 0.899 | **0.994** |
| `drive_reach_400` | 525 | 1.000 | 1.000 | 0.998 | 0.998 | 1.000 | **0.998** |
| `arterial_share` | 525 | 0.956 | 0.967 | 1.000 | 1.000 | 1.000 | **0.956** |
| `service_share` | 525 | 0.946 | 0.966 | 1.000 | 1.000 | 1.000 | **0.946** |
| `carfree_share` | 525 | 0.932 | 0.956 | 1.000 | 1.000 | 0.793 | **0.932** |
| `walk_median_edge_len_m` | 525 | 0.875 | 0.918 | 0.951 | 0.942 | 0.905 | **0.875** |
| `walk_meshedness` | 525 | 0.841 | 0.893 | 0.974 | 0.964 | 0.780 | **0.841** |
| `walk_sightline_continuity` | 525 | 0.859 | 0.876 | 0.892 | 0.878 | 0.919 | **0.859** |
| `flow_concentration` | 525 | 0.894 | 0.912 | 0.971 | 0.958 | 0.860 | **0.894** |
| `walk_block_median_area_m2` | 525 | 0.849 | 0.915 | 1.000 | 1.000 | 0.909 | **0.849** |
| `orientation_entropy` | 525 | 0.940 | 0.959 | 0.992 | 0.991 | 0.967 | **0.940** |

**Known Caveats & Interpretation Notes:**
- **Moderate area association in `walk_meshedness` and `orientation_entropy`:** Across traditional street centres, `walk_meshedness` ($\rho_{\text{area}} = +0.320$, within-tier $|\rho_{\text{area}}| = 0.189$) and `orientation_entropy` ($\rho_{\text{area}} = +0.311$, within-tier $|\rho_{\text{area}}| = 0.134$) retain moderate positive correlations with centre footprint size because larger multi-block regional/major town centres naturally encompass more closed street loops and compass orientations than smaller local centres. Researchers modelling retail outcomes should control for centre hierarchy tier or log-area when using these two metrics.
- **Residual sidewalk-mapping association in `flow_concentration`:** While `flow_concentration` has near-zero regional variance ($\eta^2_{\text{region}} = 0.010$), it exhibits the largest residual association with `sidewalk_mapped_share` ($\rho_{\text{sidewalk}} = +0.257$) because dense urban centres where OSM contributors map more footways also tend to possess more hierarchical multi-corridor street networks.
- **Descriptive role of `walk_sightline_continuity`:** `walk_sightline_continuity` is robust to parameter perturbations ($\min \rho = 0.859$) and independent of centre size ($\rho_{\text{area}} = -0.072$), but shows near-zero separation across the retail hierarchy ($\delta = -0.014$) and weak separation between Retail Parks and High Streets ($\delta = -0.132$) because straight through-junctions occur in both linear local shopping parades and major city centres. It should be interpreted as a descriptive measure of axial street alignment rather than a retail hierarchy discriminator.

----

## 3. Indicator Reference & Representative Retail Centre Profiles

Below we document each of the 11 indicators, including its theoretical basis, mathematical construction, validation behaviour, and visual profiles of representative UK retail centres at the **Low (8th percentile)**, **Median (50th percentile)**, and **High (92nd percentile)** of the distribution.

---

### 3.1 `walk_reach_400` — Walkable Neighbourhood Embeddedness

- **Concept:** External pedestrian integration into the surrounding catchment ring ([Hillier 1996](https://discovery.ucl.ac.uk/id/eprint/3881/); [Sevtsuk & Mekonnen 2012](https://doi.org/10.3166/rig.22.287-305)).
- **Construction:** Using multi-source Dijkstra shortest paths starting from all walkable nodes within 30 m of the retail centre polygon, `walk_reach_400` measures the proportion of walkable street length in the **exterior 0–400 m ring outside the centre boundary** that is reachable within a 400 m network walk. Restricting the denominator strictly to the exterior ring avoids mechanical dependence on the polygon's internal area.
- **Interpretation:** Values near `0.75–0.85` indicate a high street seamlessly stitched into surrounding residential streets. Values below `0.50` indicate an enclave severed from its surroundings by rivers, railways, or arterial barriers (Cliff's $\delta = -0.687$ comparing Retail Parks to High Streets; $\min \rho = 0.994$ across geometric perturbations).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `walk_reach_400` |
|---|---:|---|---|---:|---:|
| **Low (8th pct)** | 6019 | Peel Retail Park, Sunderland | Small Retail Park | 0.091 | **0.46** |
| **Median (50th pct)** | 754 | High Street, Stony Stratford, Milton Keynes | District Centre | 0.108 | **0.67** |
| **High (92nd pct)** | 54 | Bradford, Yorkshire and The Humber | Major Town Centre | 0.453 | **0.78** |

![Walkable Neighbourhood Reach Profiles](Output%20Data/Figures/profile_01_walk_reach_400.png)

---

### 3.2 `drive_reach_400` — Motorised Road-Network Embeddedness

- **Concept:** Topological integration of the retail centre into the surrounding 400 m motorised road network ([Sevtsuk & Mekonnen 2012](https://doi.org/10.3166/rig.22.287-305)).
- **Construction:** Identical exterior-ring formulation to `walk_reach_400`, evaluated on the consolidated undirected public motorised road graph (`DRIVE_CLASSES`, consolidated at 10 m). Note that because planar graph consolidation merges undirected road centerlines without enforcing turn restrictions or one-way flow legality, this metric measures structural road-network embeddedness rather than legal turn-by-turn driver routing.
- **Interpretation:** Captures how directly the surrounding road fabric connects into the retail centre across all perimeter approaches ($\min \rho = 0.998$ across geometric perturbations; Cliff's $\delta = -0.590$ between single-entry Retail Parks and multi-approach High Streets).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `drive_reach_400` |
|---|---:|---|---|---:|---:|
| **Low (8th pct)** | 1863 | Rushden Lakes Shopping Centre, North Northamptonshire | Large Retail Park | 0.284 | **0.45** |
| **Median (50th pct)** | 183 | Derry/Londonderry, Northern Ireland | Major Town Centre | 0.271 | **0.67** |
| **High (92nd pct)** | 59 | Tooting Graveney, Wandsworth, London | Town Centre | 0.483 | **0.79** |

![Motorised Road-Network Embeddedness Profiles](Output%20Data/Figures/profile_02_drive_reach_400.png)

---

### 3.3 `arterial_share` — Arterial Traffic Dominance & Severance

- **Concept:** Heavy-traffic road allocation and pedestrian severance (Appleyard 1981; [Marshall 2005](https://doi.org/10.4324/9780203589397)).
- **Construction:** Proportion of public drivable road length within the 100 m core readout buffer classified as `motorway`, `trunk`, `primary`, or `secondary` (including link roads).
- **Interpretation:** Differentiates neighbourhood shopping streets built along quiet local/tertiary streets (`< 0.10`) from centres straddling major trunk/A-road corridors or arterial junctions (`> 0.50`; Cliff's $\delta = +0.444$ for Retail Parks vs. High Streets).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `arterial_share` |
|---|---:|---|---|---:|---:|
| **Low (8th pct)** | 513 | Coventry Road, Sparkbrook, Birmingham | District Centre | 0.210 | **0.07** |
| **Median (50th pct)** | 646 | Galashiels, Scottish Borders | Town Centre | 0.230 | **0.30** |
| **High (92nd pct)** | 4809 | Parc Pemberton, Carmarthenshire | Small Retail Park | 0.155 | **0.57** |

![Arterial Traffic Share Profiles](Output%20Data/Figures/profile_03_arterial_share.png)

---

### 3.4 `service_share` — Car-Park & Servicing Circulation Share

- **Concept:** Dominance of off-street car-park aisles, loading bays, and internal retail-park access roads ([Marshall 2005](https://doi.org/10.4324/9780203589397)).
- **Construction:** Length of public/permissive `highway=service` ways (excluding `service=driveway`) divided by total motorised road length (`DRIVE_CLASSES + service`) within the 100 m core buffer.
- **Interpretation:** Provides strong discrimination between traditional street-frontage centres and car-park-led retail formats (Cliff's $\delta = +0.689$ between Retail Parks and High Streets; $\rho_{\text{area}} = +0.086$ across street centres).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `service_share` |
|---|---:|---|---|---:|---:|
| **Low (8th pct)** | 310 | London Road, Milton, Southend-on-Sea | District Centre | 0.177 | **0.18** |
| **Median (50th pct)** | 2255 | Bath Road Retail Park, Slough | Large Retail Park | 0.066 | **0.39** |
| **High (92nd pct)** | 755 | Cheshire Oaks Designer Outlet, Chester | Large Shopping Centre | 0.190 | **0.61** |

![Service and Car-Park Share Profiles](Output%20Data/Figures/profile_04_service_share.png)

---

### 3.5 `carfree_share` — Dedicated Pedestrian-Way Share

- **Concept:** Dedicated car-free pedestrian ways (pedestrianised high streets, precincts, arcades, and off-road footpaths/paths) net of parallel roadside pavements (Gehl 2010).
- **Construction:** Length of `pedestrian`, `footway`, `path`, and `steps` ways within the 100 m core **after stripping parallel roadside sidewalks and crossings**, divided by total non-sidewalk walkable network length. Because this numerator includes off-road `footway` and `path` links in addition to `highway=pedestrian` streets, it should be interpreted as dedicated pedestrian-way share rather than exclusively formal pedestrianised street frontage.
- **Interpretation:** Eliminates OSM sidewalk-mapping bias ($\rho_{\text{sidewalk}} = +0.025$, $\eta^2_{\text{region}} = 0.026$) while strongly separating pedestrian-priority centres from vehicle-dominated retail parks and roadside parades (Cliff's $\delta = +0.668$ across the hierarchy; $\delta = -0.345$ for Retail Parks vs. High Streets).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `carfree_share` |
|---|---:|---|---|---:|---:|
| **Low (8th pct)** | 3040 | Bideford Atlantic Village, Torridge | Large Shopping Centre | 0.128 | **0.06** |
| **Median (50th pct)** | 265 | Bexhill-on-Sea, Rother | Town Centre | 0.313 | **0.20** |
| **High (92nd pct)** | 1120 | Thetford, Breckland | Local Centre | 0.141 | **0.34** |

![Dedicated Pedestrian-Way Share Profiles](Output%20Data/Figures/profile_05_carfree_share.png)

---

### 3.6 `walk_median_edge_len_m` — Walkable Street Grain (Intersection Spacing)

- **Concept:** Urban street grain and intersection frequency (Jacobs 1961; [Siksna 1997](https://doi.org/10.51347/jum.v1i1.4048)).
- **Construction:** Median length (in metres) of consolidated street edges (excluding off-street `highway=service` car-park lanes and parallel sidewalks) intersecting the 100 m core readout buffer.
- **Interpretation:** Lower values (`30–38 m`) indicate a fine-grained urban network with closely spaced street intersections and frequent turning opportunities; higher values (`> 60 m`) indicate coarse, long-block suburban road layouts (Cliff's $\delta = -0.632$ comparing Regional Centres to Small Local Centres; within-tier $|\rho_{\text{area}}| = 0.062$).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `walk_median_edge_len_m` |
|---|---:|---|---|---:|---:|
| **Low (8th pct — Fine Grain)** | 139 | Old City, Bristol City Centre | Regional Centre | 0.177 | **32.4 m** |
| **Median (50th pct)** | 68 | Ealing, London | Major Town Centre | 0.458 | **42.9 m** |
| **High (92nd pct — Coarse Grain)** | 877 | High Street, South Norwood, Croydon | District Centre | 0.098 | **63.9 m** |

![Walkable Street Grain Profiles](Output%20Data/Figures/profile_06_walk_median_edge_len_m.png)

---

### 3.7 `walk_meshedness` — Street-Network Meshedness (Loop Redundancy)

- **Concept:** Planar cycle density and route redundancy ([Buhl et al. 2006](https://doi.org/10.1140/epjb/e2006-00085-1)).
- **Construction:** Evaluated on the consolidated street graph after removing off-street car-park aisles (`highway=service`) and parallel sidewalks:
  $$\alpha = \max\left(0,\; \frac{E - N + C}{2N - 5}\right)$$
  where $E$, $N$, and $C$ denote edges, nodes, and connected components within the 100 m core.
- **Interpretation:** Removing `highway=service` loops ensures that car-park rings do not inflate retail park scores ($\rho_{\text{sidewalk}} = +0.006$). Gridded Regional Centres exhibit higher loop redundancy ($\delta = +0.548$ vs. Small Local Centres), whereas Retail Parks score lower than High Streets ($\delta = -0.303$). Note that `walk_meshedness` retains a moderate correlation with centre area ($\rho_{\text{area}} = +0.320$ across street centres; $+0.189$ within tiers).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `walk_meshedness` |
|---|---:|---|---|---:|---:|
| **Low (8th pct)** | 698 | High Street, Honiton, East Devon | Market Town | 0.117 | **0.051** |
| **Median (50th pct)** | 1023 | Lutterworth, Harborough | Market Town | 0.125 | **0.094** |
| **High (92nd pct)** | 449 | Queen Street, Morley, Leeds | District Centre | 0.194 | **0.141** |

![Street-Network Meshedness Profiles](Output%20Data/Figures/profile_07_walk_meshedness.png)

---

### 3.8 `walk_sightline_continuity` — Descriptive Axial Sightline Continuity

- **Concept:** Visual legibility and axial street continuation across intersections ([Hillier & Iida 2005](https://doi.org/10.1007/11556114_30); [Porta et al. 2006b](https://doi.org/10.1016/j.physa.2005.12.063)).
- **Construction:** Proportion of street junctions of degree $k \ge 3$ within the 100 m core (on the car-park-cleaned street graph) that possess at least one pair of incident edges continuing straight through the junction within a $\le 20^\circ$ angular deflection.
- **Interpretation:** High scores (`> 0.94`) indicate linear high streets or grids with uninterrupted axial continuation across cross-streets; lower scores (`< 0.83`) indicate layouts with frequent offset T-junctions and cranked intersections. Size-invariant ($\rho_{\text{area}} = -0.072$) and independent of sidewalk mapping ($\rho_{\text{sidewalk}} = +0.033$), but exhibits near-zero separation across the retail hierarchy ($\delta = -0.014$) and should be used as a descriptive morphological metric rather than a hierarchy classifier.

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `walk_sightline_continuity` |
|---|---:|---|---|---:|---:|
| **Low (8th pct)** | 1394 | Kenton Road, Kenton, Brent | Local Centre | 0.120 | **0.80** |
| **Median (50th pct)** | 763 | Main Street, Bingley, Bradford | District Centre | 0.105 | **0.88** |
| **High (92nd pct)** | 273 | Whitley Bay, North Tyneside | Town Centre | 0.199 | **0.95** |

![Through-Junction Sightline Continuity Profiles](Output%20Data/Figures/profile_08_walk_sightline_continuity.png)

---

### 3.9 `flow_concentration` — Through-Movement Hierarchy (400 m Metric Betweenness Gini)

- **Concept:** Concentration of shortest-path pedestrian movement onto a primary corridor spine versus dispersion across a multi-street grid ([Freeman 1977](https://doi.org/10.2307/3033543); [Porta et al. 2006a](https://doi.org/10.1068/b32045)).
- **Construction:** Gini coefficient of explicitly distance-limited shortest-path edge betweenness (`compute_distance_limited_edge_betweenness`, evaluated via `scipy.sparse.csgraph.dijkstra` with a strict `limit = 400.0 m` metric distance cutoff on the 400 m context street graph, excluding `highway=service` car-park lanes) across street edges within the 100 m core.
- **Interpretation:** Lower values (`~0.38–0.42`) indicate compact multi-street centres where local movement distributes evenly across parallel streets; higher values (`> 0.52`) indicate hierarchical centres where shortest paths funnel onto a primary corridor spine (Cliff's $\delta = +0.563$ across the retail hierarchy; note residual correlation with OSM sidewalk mapping $\rho_{\text{sidewalk}} = +0.257$).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `flow_concentration` |
|---|---:|---|---|---:|---:|
| **Low (8th pct — Distributed Grid)** | 653 | Arnold, Gedling | Town Centre | 0.172 | **0.41** |
| **Median (50th pct)** | 107 | High Wycombe, Buckinghamshire | Major Town Centre | 0.402 | **0.48** |
| **High (92nd pct — Corridor Spine)** | 146 | St James Quarter, Edinburgh City Centre | Regional Centre | 0.235 | **0.57** |

![Through-Movement Flow Concentration Profiles](Output%20Data/Figures/profile_09_flow_concentration.png)

---

### 3.10 `walk_block_median_area_m2` — Enclosed Urban Block Area *(Street-Grid Set)*

- **Concept:** Physical scale of enclosed urban street blocks ([Siksna 1997](https://doi.org/10.51347/jum.v1i1.4048); [Louf & Barthelemy 2014](https://doi.org/10.1098/rsif.2014.0924)).
- **Construction:** Computed for the 1,521 traditional street centres (`Regional`, `Major Town`, `Town`, `Market Town`, `District`, and `Local Centres`). Ground-level street segments (with `highway=service` car-park lanes and parallel sidewalks removed) are polygonised via `shapely.ops.polygonize`. Sliver traffic islands (thickness $4A/P < 20\text{ m}$) are filtered out, and the median area ($\text{m}^2$) of blocks whose interior point falls within the 100 m core is returned.
- **Interpretation:** Independent of centre polygon size ($\rho_{\text{area}} = -0.073$) and OSM sidewalk mapping ($\rho_{\text{sidewalk}} = +0.026$), with `0.07%` missingness across the 1,521 street centres. Fine-grained regional cores exhibit compact permeable blocks (`3,000–5,000` $\text{m}^2$; Cliff's $\delta = -0.418$ vs. District/Local Centres), whereas linear suburban corridors exhibit large elongated blocks (`> 14,000` $\text{m}^2$).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `walk_block_median_area_m2` |
|---|---:|---|---|---:|---:|
| **Low (8th pct — Fine Compact Blocks)** | 60 | Kirkgate Market & Vicar Lane, Leeds City Centre | Regional Centre | 0.243 | **3,026 $\text{m}^2$** |
| **Median (50th pct)** | 870 | Warwick Road, Acocks Green, Birmingham | District Centre | 0.150 | **6,844 $\text{m}^2$** |
| **High (92nd pct — Large Coarse Blocks)** | 730 | Leytonstone, Waltham Forest, London | Town Centre | 0.162 | **16,009 $\text{m}^2$** |

![Enclosed Urban Block Area Profiles](Output%20Data/Figures/profile_10_walk_block_median_area_m2.png)

---

### 3.11 `orientation_entropy` — Street Bearing Orientation Entropy *(Street-Grid Set)*

- **Concept:** Geometric alignment of street bearings versus multi-directional irregularity ([Boeing 2019](https://doi.org/10.1007/s41109-019-0189-1)).
- **Construction:** Computed for the 1,521 traditional street centres on the car-park-cleaned street graph. Edge bearings (in both directions) are weighted by segment length into 36 compass bins of $10^\circ$, and Shannon entropy is normalised by $\ln(36) \in [0, 1]$.
- **Interpretation:** Low entropy (`< 0.83`) identifies orthogonal gridiron layouts aligned along two perpendicular axes (e.g. New Malden, London); high entropy (`> 0.96`) identifies radial or multi-directional street patterns (e.g. King Street, Aberdeen). Restricting to the 1,521 street centres avoids small-parade histogram bias (`0.00%` missing; within-tier $|\rho_{\text{area}}| = 0.134$; overall $\rho_{\text{area}} = +0.311$).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `orientation_entropy` |
|---|---:|---|---|---:|---:|
| **Low (8th pct — Orthogonal Grid)** | 570 | High Street, New Malden, Kingston upon Thames | District Centre | 0.130 | **0.818** |
| **Median (50th pct)** | 1060 | High Street, Potters Bar, Hertsmere | Local Centre | 0.146 | **0.930** |
| **High (92nd pct — Multi-Directional)** | 1030 | King Street, Aberdeen City Centre | Major Town Centre | 0.169 | **0.972** |

![Street Bearing Orientation Entropy Profiles](Output%20Data/Figures/profile_11_orientation_entropy.png)

----

## 4. References

- **Appleyard, D. (1981).** *Livable Streets*. University of California Press, Berkeley.
- **Boeing, G. (2019).** Urban spatial order: Street network orientation, configuration, and entropy. *Applied Network Science*, 4(1), 67. [https://doi.org/10.1007/s41109-019-0189-1](https://doi.org/10.1007/s41109-019-0189-1)
- **Boeing, G. (2025).** Topological graph simplification Solutions to the street intersection miscount problem. *Transactions in GIS*, 29(1), e70037. [https://doi.org/10.1111/tgis.70037](https://doi.org/10.1111/tgis.70037)
- **Buhl, J., Gautrais, J., Reeves, N., Solé, R. V., Valverde, S., Kuntz, P., & Theraulaz, G. (2006).** Topological patterns in street networks of self-organized urban settlements. *The European Physical Journal B*, 49(4), 513–522. [https://doi.org/10.1140/epjb/e2006-00085-1](https://doi.org/10.1140/epjb/e2006-00085-1)
- **Freeman, L. C. (1977).** A set of measures of centrality based on betweenness. *Sociometry*, 40(1), 35–41. [https://doi.org/10.2307/3033543](https://doi.org/10.2307/3033543)
- **Gehl, J. (2010).** *Cities for People*. Island Press, Washington, DC.
- **Hillier, B. (1996).** *Space is the Machine: A Configurational Theory of Architecture*. Cambridge University Press, Cambridge. [https://discovery.ucl.ac.uk/id/eprint/3881/](https://discovery.ucl.ac.uk/id/eprint/3881/)
- **Hillier, B., & Iida, S. (2005).** Network and psychological effects in urban movement. In A. G. Cohn & D. M. Mark (Eds.), *Spatial Information Theory (COSIT 2005)*, Lecture Notes in Computer Science, vol. 3693 (pp. 475–490). Springer. [https://doi.org/10.1007/11556114_30](https://doi.org/10.1007/11556114_30)
- **Jacobs, J. (1961).** *The Death and Life of Great American Cities*. Random House, New York.
- **Louf, R., & Barthelemy, M. (2014).** A typology of street patterns. *Journal of the Royal Society Interface*, 11(101), 20140924. [https://doi.org/10.1098/rsif.2014.0924](https://doi.org/10.1098/rsif.2014.0924)
- **Marshall, S. (2005).** *Streets and Patterns*. Routledge, London. [https://doi.org/10.4324/9780203589397](https://doi.org/10.4324/9780203589397)
- **Porta, S., Crucitti, P., & Latora, V. (2006a).** The network analysis of urban streets: A primal approach. *Environment and Planning B: Planning and Design*, 33(5), 705–725. [https://doi.org/10.1068/b32045](https://doi.org/10.1068/b32045)
- **Porta, S., Crucitti, P., & Latora, V. (2006b).** The network analysis of urban streets: A dual approach. *Physica A: Statistical Mechanics and its Applications*, 369(2), 853–866. [https://doi.org/10.1016/j.physa.2005.12.063](https://doi.org/10.1016/j.physa.2005.12.063)
- **Sevtsuk, A., & Mekonnen, M. (2012).** Urban network analysis: A new toolbox for ArcGIS. *Revue Internationale de Géomatique*, 22(2), 287–305. [https://doi.org/10.3166/rig.22.287-305](https://doi.org/10.3166/rig.22.287-305)
- **Siksna, A. (1997).** The effects of block size and form in North American and Australian city centres. *Urban Morphology*, 1(1), 19–33. [https://doi.org/10.51347/jum.v1i1.4048](https://doi.org/10.51347/jum.v1i1.4048)
