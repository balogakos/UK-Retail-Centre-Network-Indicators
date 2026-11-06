# UK-Retail-Centre-Network-Indicators
### Akos Balog

----

Welcome to the UK Retail Centre Street-Network Indicators repository. Here we provide open-access street-network morphology indicators, validation outputs, and reproducible Python code for the 9,623 retail centres in the CDRC Retail Centre Boundaries data product.

## 1. Overview & Data Products

Indicators are developed for the UK release of the CDRC [Retail Centre Boundaries](https://data.cdrc.ac.uk/dataset/retail-centre-boundaries) dataset (`N = 9,623` retail centres in `EPSG:27700`) paired with multimodal street and footpath networks extracted from OpenStreetMap (`united-kingdom-latest.osm.pbf`).

To prevent confounding from OpenStreetMap pavement-mapping habits, polygon size, and off-street car-park loops, the indicators are constructed using a two-tier architecture following a 6-step validation framework (concept definition, operationalisation, parameter robustness, discriminant validity against polygon area and sidewalk mapping, convergent validity across retail hierarchy tiers, and exploratory outcome testing):

1. **Universal Core Set (9 Indicators — All 9,623 Retail Centres):**
   - **External Embeddedness:** `walk_reach_400`, `drive_reach_400`
   - **Car Dominance & Servicing:** `arterial_share`, `service_share`
   - **Pedestrian Priority:** `carfree_share`
   - **Street Grain & Redundancy:** `walk_median_edge_len_m`, `walk_meshedness`
   - **Legibility & Through-Movement:** `walk_sightline_continuity`, `flow_concentration`

2. **Street-Grid Set (2 Indicators — 1,521 Traditional Street Centres):**
   - **Block Scale & Grid Order:** `walk_block_median_area_m2`, `orientation_entropy`
   - *Scope note:* Consistent with [Ballantyne et al. (2022)](https://github.com/patrickballantyne/CDRC-Retail-Indicators), these two street-grid metrics are computed for traditional street-network centres (`Regional Centre`, `Major Town Centre`, `Town Centre`, `Market Town`, `District Centre`, and `Local Centre`; `N = 1,521`) and set to `NaN` for `Small Local Centres` (which lack sufficient edges to populate directional histograms or enclosed blocks) and out-of-town `Retail Parks` / `Shopping Centres`.

### 1.1 Download the Indicators

The released indicators and validation tables are available in the `Output Data/` directory:

- **Geopackage (Polygons + Indicators):** [UK_Retail_Centre_Network_Indicators.gpkg](Output%20Data/UK_Retail_Centre_Network_Indicators.gpkg)
- **Lookup Table (CSV):** [UK_Retail_Centre_Network_Indicators.csv](Output%20Data/UK_Retail_Centre_Network_Indicators.csv)
- **Validation Scorecard (CSV):** [Validation_Scorecard.csv](Output%20Data/Validation_Scorecard.csv)
- **Representative Centre Profiles (CSV):** [Indicator_Profile_Examples.csv](Output%20Data/Indicator_Profile_Examples.csv)

### 1.2 Code

Code is organised into `Source Code/` and `Analysis Code/`:

- [Core Graph & Indicator Library (`Source Code/Helper_Functions.py`)](Source%20Code/Helper_Functions.py)
- [1. Extracting OpenStreetMap Highway Networks (`Analysis Code/01_Extract_OSM_Networks.py`)](Analysis%20Code/01_Extract_OSM_Networks.py)
- [2. Calculating Street-Network Indicators (`Analysis Code/02_Calculate_Network_Indicators.py`)](Analysis%20Code/02_Calculate_Network_Indicators.py)
- [3. Validating Network Indicators (`Analysis Code/03_Validate_Network_Indicators.py`)](Analysis%20Code/03_Validate_Network_Indicators.py)
- [4. Generating Representative Visual Profiles (`Analysis Code/04_Generate_Indicator_Profiles.py`)](Analysis%20Code/04_Generate_Indicator_Profiles.py)

----

## 2. Methodological Controls & Validation Summary

### 2.1 Controlling for OSM Sidewalk Mapping, Junction Tolerance, and Car-Park Loops

Raw OpenStreetMap street graphs introduce three systematic biases when applied to retail centres:

1. **Sidewalk Mapping Artefacts:** In cities where OSM contributors map roadside pavements as separate parallel `highway=footway` ways, naive topological metrics count every pavement crossing as two extra street junctions and treat roadside pavements as car-free streets. Our pipeline identifies and removes tagged pavements (`footway=sidewalk`, `crossing`, `traffic_island`) and untagged `footway` ways running parallel ($\ge 80\%$ of sample points within $12\text{ m}$) to a motorised road before building the pedestrian street graph.
2. **Unified Consolidation Tolerance:** Both pedestrian and vehicular graphs are planarised on ground-level ways (preserving grade-separated bridges and tunnels) and consolidated at a uniform **10 m junction tolerance** within a 400 m context buffer, reading out core metrics on a 100 m buffer around the retail centre boundary.
3. **Car-Park Loop Separation:** Off-street car-park circulation (`highway=service`) is measured explicitly via `service_share` and excluded prior to computing street-loop redundancy (`walk_meshedness`), enclosed block area (`walk_block_median_area_m2`), and bearing entropy (`orientation_entropy`), preventing car-park aisles from registering as small urban street blocks.

![Visual QA of Sidewalk Removal and 10 m Junction Consolidation](Output%20Data/Figures/visual_qa_sidewalk_consolidation.png)

### 2.2 Validation Scorecard

| Indicator | Scope (`N`) | Missing (%) | Median (IQR) | $\rho_{\text{area}}$ (Street Centres) | Within-Tier $\|\rho_{\text{area}}\|$ | $\rho_{\text{sidewalk}}$ | Cliff's $\delta$ (Hierarchy) | Cliff's $\delta$ (Retail Park vs. High Street) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `walk_reach_400` | Universal (`9,623`) | 0.06% | 0.625 (0.543–0.693) | +0.170 | 0.152 | -0.122 | +0.487 | -0.720 |
| `drive_reach_400` | Universal (`9,623`) | 1.21% | 0.630 (0.538–0.709) | +0.201 | 0.184 | -0.046 | +0.280 | -0.591 |
| `arterial_share` | Universal (`9,623`) | 0.53% | 0.253 (0.058–0.370) | +0.125 | 0.088 | +0.112 | +0.149 | +0.444 |
| `service_share` | Universal (`9,623`) | 0.53% | 0.292 (0.185–0.412) | +0.086 | 0.199 | +0.047 | -0.145 | +0.689 |
| `carfree_share` | Universal (`9,623`) | 0.02% | 0.122 (0.056–0.204) | +0.162 | 0.068 | -0.044 | +0.677 | -0.419 |
| `walk_median_edge_len_m` | Universal (`9,623`) | 0.06% | 40.0 m (34.5–48.3) | -0.128 | 0.127 | -0.140 | -0.434 | -0.257 |
| `walk_meshedness` | Universal (`9,623`) | 0.43% | 0.063 (0.034–0.094) | +0.352 | 0.201 | +0.076 | +0.708 | -0.288 |
| `walk_sightline_continuity` | Universal (`9,623`) | 0.19% | 0.900 (0.851–0.944) | -0.038 | 0.097 | +0.040 | +0.046 | -0.155 |
| `flow_concentration` | Universal (`9,623`) | 0.09% | 0.464 (0.422–0.509) | +0.212 | 0.273 | +0.216 | +0.197 | +0.570 |
| `walk_block_median_area_m2` | Street-Grid (`1,521`) | 0.07% | 7,405 $\text{m}^2$ (4,993–11,213) | -0.075 | 0.076 | +0.001 | -0.449 | — |
| `orientation_entropy` | Street-Grid (`1,521`) | 0.00% | 0.917 (0.872–0.945) | +0.323 | 0.142 | -0.014 | +0.193 | — |

----

## 3. Indicator Reference & Representative Retail Centre Profiles

Below we document each of the 11 indicators, including its theoretical basis, mathematical construction, validation behaviour, and visual profiles of representative UK retail centres at the **Low (8th percentile)**, **Median (50th percentile)**, and **High (92nd percentile)** of the distribution.

---

### 3.1 `walk_reach_400` — Walkable Neighbourhood Embeddedness

- **Concept:** External pedestrian integration into the surrounding catchment ring ([Hillier 1996](https://discovery.ucl.ac.uk/id/eprint/3881/); [Sevtsuk & Mekonnen 2012](https://www.sciencedirect.com/science/article/pii/S016920461200059X)).
- **Construction:** Using multi-source Dijkstra shortest paths starting from all walkable nodes within 30 m of the retail centre polygon, `walk_reach_400` measures the proportion of walkable street length in the **exterior 0–400 m ring outside the centre boundary** that is reachable within a 400 m network walk. Restricting the denominator strictly to the exterior ring eliminates mechanical dependence on the polygon's internal area.
- **Interpretation:** Values near `0.75–0.85` indicate a high street seamlessly stitched into surrounding residential streets. Values below `0.50` indicate an enclave severed from its surroundings by rivers, railways, or arterial slip roads (Cliff's $\delta = -0.720$ comparing Retail Parks to High Streets).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `walk_reach_400` |
|---|---:|---|---|---:|---:|
| **Low (8th pct)** | 3843 | Sturry Road Retail Park, Canterbury | Large Retail Park | 0.158 | **0.46** |
| **Median (50th pct)** | 1460 | Attercliffe Road, Sheffield | Local Centre | 0.149 | **0.67** |
| **High (92nd pct)** | 737 | High Street, Fullwell Cross, Redbridge | District Centre | 0.117 | **0.78** |

![Walkable Neighbourhood Reach Profiles](Output%20Data/Figures/profile_01_walk_reach_400.png)

---

### 3.2 `drive_reach_400` — Vehicular Neighbourhood Embeddedness

- **Concept:** External vehicular integration into the surrounding 400 m road network.
- **Construction:** Identical exterior-ring formulation to `walk_reach_400`, evaluated on the consolidated public motorised road graph (`DRIVE_CLASSES`, consolidated at 10 m).
- **Interpretation:** Captures how directly the surrounding road fabric connects into the retail centre across all perimeter approaches ($\min \rho = 0.99$ across parameter perturbations; Cliff's $\delta = -0.591$ between single-entry Retail Parks and multi-approach High Streets).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `drive_reach_400` |
|---|---:|---|---|---:|---:|
| **Low (8th pct)** | 9256 | Chestnut Avenue Retail Park, Eastleigh | Small Retail Park | 0.103 | **0.45** |
| **Median (50th pct)** | 235 | Epsom, Epsom and Ewell | Town Centre | 0.217 | **0.67** |
| **High (92nd pct)** | 964 | High Street, Strood, Medway | District Centre | 0.169 | **0.79** |

![Vehicular Neighbourhood Reach Profiles](Output%20Data/Figures/profile_02_drive_reach_400.png)

---

### 3.3 `arterial_share` — Arterial Traffic Dominance & Severance

- **Concept:** Heavy-traffic road allocation and pedestrian severance ([Appleyard 1981](https://www.ucpress.edu/); [Marshall 2005](https://www.routledge.com/Streets-and-Patterns/Marshall/p/book/9780415317504)).
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

- **Concept:** Dominance of off-street car-park aisles, loading bays, and internal retail-park access roads.
- **Construction:** Length of public/permissive `highway=service` ways (excluding `service=driveway`) divided by total motorised road length (`DRIVE_CLASSES + service`) within the 100 m core buffer.
- **Interpretation:** Provides strong discrimination between traditional street-frontage centres and car-park-led retail formats (Cliff's $\delta = +0.689$ between Retail Parks and High Streets; $\rho_{\text{area}} = +0.086$ across street centres).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `service_share` |
|---|---:|---|---|---:|---:|
| **Low (8th pct)** | 310 | London Road, Milton, Southend-on-Sea | District Centre | 0.177 | **0.18** |
| **Median (50th pct)** | 2255 | Bath Road Retail Park, Slough | Large Retail Park | 0.066 | **0.39** |
| **High (92nd pct)** | 755 | Cheshire Oaks Designer Outlet, Chester | Large Shopping Centre | 0.190 | **0.61** |

![Service and Car-Park Share Profiles](Output%20Data/Figures/profile_04_service_share.png)

---

### 3.5 `carfree_share` — True Pedestrianised Street Share

- **Concept:** Dedicated car-free pedestrian space (pedestrianised high streets, precincts, arcades, and off-road footpaths) net of roadside pavements.
- **Construction:** Length of `pedestrian`, `footway`, `path`, and `steps` ways within the 100 m core **after stripping parallel roadside sidewalks and crossings**, divided by total non-sidewalk walkable network length.
- **Interpretation:** Eliminates regional OSM sidewalk-mapping bias ($\rho_{\text{sidewalk}} = -0.044$; regional $\eta^2$ reduced from `0.076` to `0.016`) while strongly separating pedestrianised Regional and Major Town Centres from local roadside parades (Cliff's $\delta = +0.677$).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `carfree_share` |
|---|---:|---|---|---:|---:|
| **Low (8th pct)** | 9332 | Barrbridge Leisure Park, North Lanarkshire | Small Retail Park | 0.109 | **0.04** |
| **Median (50th pct)** | 1225 | Turners Hill, Cheshunt, Broxbourne | Local Centre | 0.086 | **0.15** |
| **High (92nd pct)** | 143 | Southend-on-Sea | Major Town Centre | 0.238 | **0.30** |

![True Car-Free Street Share Profiles](Output%20Data/Figures/profile_05_carfree_share.png)

---

### 3.6 `walk_median_edge_len_m` — Walkable Street Grain (Intersection Spacing)

- **Concept:** Urban street grain and intersection frequency ([Jacobs 1961](https://www.penguinrandomhouse.com/books/86058/the-death-and-life-of-great-american-cities-by-jane-jacobs/); [Siksna 1997](https://www.tandfonline.com/doi/abs/10.1057/udi.1997.3)).
- **Construction:** Median length (in metres) of consolidated walkable street edges intersecting the 100 m core readout buffer.
- **Interpretation:** Lower values (`28–36 m`) indicate a fine-grained network with frequent turning opportunities and closely spaced intersections; higher values (`> 45 m`) indicate coarse, long-block road layouts (Cliff's $\delta = -0.434$ comparing Regional Centres to Small Local Centres).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `walk_median_edge_len_m` |
|---|---:|---|---|---:|---:|
| **Low (8th pct — Fine Grain)** | 8535 | Ely Leisure Village, East Cambridgeshire | Small Retail Park | 0.093 | **29.1 m** |
| **Median (50th pct)** | 32 | North Laine, Brighton and Hove | Regional Centre | 0.325 | **35.7 m** |
| **High (92nd pct — Coarse Grain)** | 9359 | Heaton Mills Retail Park, Manchester | Small Retail Park | 0.065 | **46.0 m** |

![Walkable Street Grain Profiles](Output%20Data/Figures/profile_06_walk_median_edge_len_m.png)

---

### 3.7 `walk_meshedness` — Street-Network Meshedness (Loop Redundancy)

- **Concept:** Planar cycle density and route redundancy ([Buhl et al. 2006](https://link.springer.com/article/10.1140/epjb/e2006-00085-1)).
- **Construction:** Evaluated on the consolidated street graph after removing off-street car-park aisles (`highway=service`) and parallel sidewalks:
  $$\alpha = \max\left(0,\; \frac{E - N + C}{2N - 5}\right)$$
  where $E$, $N$, and $C$ denote edges, nodes, and connected components within the 100 m core.
- **Interpretation:** Removing `highway=service` loops ensures that car-park rings do not inflate retail park scores. Traditional gridded Regional Centres exhibit high loop redundancy ($\delta = +0.708$ vs. Small Local Centres), whereas Retail Parks score lower than High Streets ($\delta = -0.288$).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `walk_meshedness` |
|---|---:|---|---|---:|---:|
| **Low (8th pct)** | 9569 | Toby Carvery, North Tyneside | Small Retail Park | 0.061 | **0.037** |
| **Median (50th pct)** | 6290 | Alvis Retail Park, Coventry | Small Retail Park | 0.105 | **0.088** |
| **High (92nd pct)** | 56 | George Street, Edinburgh City Centre | Regional Centre | 0.265 | **0.140** |

![Street-Network Meshedness Profiles](Output%20Data/Figures/profile_07_walk_meshedness.png)

---

### 3.8 `walk_sightline_continuity` — Through-Junction Angular Continuity

- **Concept:** Visual legibility and axial street continuation across intersections ([Hillier & Iida 2005](https://link.springer.com/chapter/10.1007/11556114_30); [Porta et al. 2006](https://journals.sagepub.com/doi/10.1068/b32045)).
- **Construction:** Proportion of junctions of degree $k \ge 3$ within the 100 m core that possess at least one pair of incident edges continuing straight through the junction within a $\le 20^\circ$ angular deflection.
- **Interpretation:** High scores (`> 0.92`) indicate continuous axial thoroughfares; lower scores (`< 0.82`) indicate fragmented layouts dominated by offset T-junctions and cranked turns. Size-invariant ($\rho_{\text{area}} = -0.038$ across street centres).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `walk_sightline_continuity` |
|---|---:|---|---|---:|---:|
| **Low (8th pct)** | 2842 | Springkerse Retail Park, Stirling | Large Retail Park | 0.292 | **0.81** |
| **Median (50th pct)** | 520 | Abingdon-on-Thames, Vale of White Horse | Town Centre | 0.109 | **0.89** |
| **High (92nd pct)** | 9258 | Churchill Way West Retail Park, Salisbury | Small Retail Park | 0.061 | **0.95** |

![Through-Junction Sightline Continuity Profiles](Output%20Data/Figures/profile_08_walk_sightline_continuity.png)

---

### 3.9 `flow_concentration` — Through-Movement Hierarchy (Betweenness Gini)

- **Concept:** Concentration of shortest-path pedestrian movement onto a single spine versus dispersion across a multi-street grid ([Porta et al. 2006](https://journals.sagepub.com/doi/10.1068/b32045)).
- **Construction:** Gini coefficient of local shortest-path edge betweenness (400 m path cutoff on the 400 m context graph) evaluated across walkable edges within the 100 m core.
- **Interpretation:** Lower values (`~0.42–0.45`) indicate balanced multi-street grids where movement distributes across parallel routes (e.g. Stockton-on-Tees); higher values (`> 0.55`) indicate dendritic or ribbon centres where all local movement funnels along a single main corridor.

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `flow_concentration` |
|---|---:|---|---|---:|---:|
| **Low (8th pct — Distributed Grid)** | 184 | Stockton-on-Tees | Major Town Centre | 0.320 | **0.44** |
| **Median (50th pct)** | 654 | Warminster, Wiltshire | Market Town | 0.085 | **0.50** |
| **High (92nd pct — Single Spine)** | 4381 | Strathkelvin Retail Park, East Dunbartonshire | Large Retail Park | 0.158 | **0.58** |

![Through-Movement Flow Concentration Profiles](Output%20Data/Figures/profile_09_flow_concentration.png)

---

### 3.10 `walk_block_median_area_m2` — Enclosed Urban Block Area *(Street-Grid Set)*

- **Concept:** Physical scale of enclosed urban blocks ([Siksna 1997](https://www.tandfonline.com/doi/abs/10.1057/udi.1997.3); [Porta et al. 2014](https://journals.sagepub.com/doi/10.1068/b130048p)).
- **Construction:** Computed for the 1,521 traditional street centres (`Regional`, `Major Town`, `Town`, `Market Town`, `District`, and `Local Centres`). Ground-level street segments (with `highway=service` car-park lanes and parallel sidewalks removed) are polygonised via `shapely.ops.polygonize`. Sliver traffic islands (thickness $4A/P < 20\text{ m}$) are filtered out, and the median area ($\text{m}^2$) of blocks whose interior point falls within the 100 m core is returned.
- **Interpretation:** Completely independent of centre polygon size ($\rho_{\text{area}} = -0.075$) and OSM sidewalk mapping ($\rho_{\text{sidewalk}} = +0.001$), with `0.07%` missingness across the 1,521 street centres. Historic and regional cores exhibit compact permeable blocks (`3,000–5,000` $\text{m}^2$; Cliff's $\delta = -0.449$ vs. District/Local Centres), whereas suburban local centres exhibit large superblocks (`> 14,000` $\text{m}^2$).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `walk_block_median_area_m2` |
|---|---:|---|---|---:|---:|
| **Low (8th pct — Fine Compact Blocks)** | 635 | Cambridge | Town Centre | 0.120 | **3,223 $\text{m}^2$** |
| **Median (50th pct)** | 724 | Main Street, Larne, Mid and East Antrim | District Centre | 0.268 | **7,330 $\text{m}^2$** |
| **High (92nd pct — Large Coarse Blocks)** | 1182 | High Street, Brownhills, Walsall | Local Centre | 0.147 | **16,789 $\text{m}^2$** |

![Enclosed Urban Block Area Profiles](Output%20Data/Figures/profile_10_walk_block_median_area_m2.png)

---

### 3.11 `orientation_entropy` — Street Bearing Orientation Entropy *(Street-Grid Set)*

- **Concept:** Geometric alignment of street bearings versus multi-directional irregularity ([Boeing 2019](https://link.springer.com/article/10.1007/s41109-019-0189-1)).
- **Construction:** Computed for the 1,521 traditional street centres on the car-park-cleaned street graph. Edge bearings (in both directions) are weighted by segment length into 36 compass bins of $10^\circ$, and Shannon entropy is normalised by $\ln(36) \in [0, 1]$.
- **Interpretation:** Low entropy (`< 0.83`) identifies orthogonal gridiron layouts aligned along two perpendicular axes (e.g. Victorian terraced grids along Stockport Road, Manchester); high entropy (`> 0.96`) identifies radial or multi-directional street patterns (e.g. Camberwell, London). Restricting to the 1,521 street centres eliminates small-sample histogram bias (`0.00%` missing; within-tier $|\rho_{\text{area}}| = 0.142$).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `orientation_entropy` |
|---|---:|---|---|---:|---:|
| **Low (8th pct — Orthogonal Grid)** | 934 | Stockport Road, Longsight, Manchester | District Centre | 0.121 | **0.815** |
| **Median (50th pct)** | 652 | Aberdare, Rhondda Cynon Taf | Market Town | 0.102 | **0.925** |
| **High (92nd pct — Multi-Directional)** | 519 | Camberwell, Southwark, London | District Centre | 0.156 | **0.970** |

![Street Bearing Orientation Entropy Profiles](Output%20Data/Figures/profile_11_orientation_entropy.png)
