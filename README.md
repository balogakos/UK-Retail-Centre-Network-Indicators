# UK-Retail-Centre-Network-Indicators
### Akos Balog

----

Welcome to the UK Retail Centre Street-Network Indicators repository. Here we provide open-access street-network morphology indicators, validation outputs, and reproducible Python code for the 9,623 UK retail centres delineated by the [Geographic Data Service (GeoDS)](https://geods.ac.uk).

## 1. Overview & Data Products

Indicators are developed for the UK release of the Geographic Data Service ([GeoDS](https://geods.ac.uk)) [Retail Centre Boundaries](https://data.geods.ac.uk/dataset/retail-centre-boundaries) dataset (`N = 9,623` retail centres in `EPSG:27700`) paired with multimodal street and footpath networks extracted from OpenStreetMap (`united-kingdom-latest.osm.pbf`).

To prevent confounding from OpenStreetMap pavement-mapping habits, polygon size, and off-street car-park loops, the indicators are constructed using a two-tier architecture following a 6-step validation framework (concept definition, operationalisation, parameter robustness, discriminant validity against polygon area and sidewalk mapping, convergent validity across retail hierarchy tiers, and exploratory outcome testing):

1. **Universal Core Set (9 Indicators — All 9,623 Retail Centres):**
   - **External Embeddedness:** `walk_reach_400`, `drive_reach_400`
   - **Car Dominance & Servicing:** `arterial_share`, `service_share`
   - **Pedestrian Priority:** `carfree_share`
   - **Street Grain & Redundancy:** `walk_median_edge_len_m`, `walk_meshedness`
   - **Legibility & Through-Movement:** `walk_sightline_continuity`, `flow_concentration`

2. **Street-Grid Set (2 Indicators — 1,521 Traditional Street Centres):**
   - **Block Scale & Grid Order:** `walk_block_median_area_m2`, `orientation_entropy`
   - *Scope note:* These two street-grid metrics are computed for traditional street-network centres (`Regional Centre`, `Major Town Centre`, `Town Centre`, `Market Town`, `District Centre`, and `Local Centre`; `N = 1,521`) and set to `NaN` for `Small Local Centres` (which lack sufficient edges to populate directional histograms or enclosed blocks) and out-of-town `Retail Parks` / `Shopping Centres`.

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
3. **Car-Park Loop Separation:** Off-street car-park circulation (`highway=service`) is measured explicitly via `service_share` and excluded prior to computing internal street-topology indicators (`walk_median_edge_len_m`, `walk_meshedness`, `walk_sightline_continuity`, `flow_concentration`, `walk_block_median_area_m2`, and `orientation_entropy`), preventing 20 m parking-bay aisles from masquerading as fine-grained urban streets or small street blocks.

![Visual QA of Sidewalk Removal and 10 m Junction Consolidation](Output%20Data/Figures/visual_qa_sidewalk_consolidation.png)

### 2.2 Validation Scorecard

| Indicator | Scope (`N`) | Missing (%) | Median (IQR) | $\rho_{\text{area}}$ (Street Centres) | Within-Tier $\|\rho_{\text{area}}\|$ | $\rho_{\text{sidewalk}}$ | Cliff's $\delta$ (Hierarchy) | Cliff's $\delta$ (Retail Park vs. High Street) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `walk_reach_400` | Universal (`9,623`) | 0.06% | 0.625 (0.543–0.693) | +0.170 | 0.152 | -0.122 | +0.487 | -0.720 |
| `drive_reach_400` | Universal (`9,623`) | 1.21% | 0.630 (0.538–0.709) | +0.201 | 0.184 | -0.046 | +0.280 | -0.591 |
| `arterial_share` | Universal (`9,623`) | 0.53% | 0.253 (0.058–0.370) | +0.125 | 0.088 | +0.112 | +0.149 | +0.444 |
| `service_share` | Universal (`9,623`) | 0.53% | 0.292 (0.185–0.412) | +0.086 | 0.199 | +0.047 | -0.145 | +0.689 |
| `carfree_share` | Universal (`9,623`) | 0.02% | 0.122 (0.056–0.204) | +0.162 | 0.068 | -0.044 | +0.677 | -0.419 |
| `walk_median_edge_len_m` | Universal (`9,623`) | 0.43% | 54.2 m (44.0–68.4) | -0.180 | 0.072 | -0.123 | -0.591 | +0.016 |
| `walk_meshedness` | Universal (`9,623`) | 0.43% | 0.063 (0.034–0.094) | +0.352 | 0.201 | +0.076 | +0.708 | -0.288 |
| `walk_sightline_continuity` | Universal (`9,623`) | 1.86% | 0.900 (0.833–0.960) | -0.057 | 0.111 | +0.052 | +0.004 | -0.119 |
| `flow_concentration` | Universal (`9,623`) | 0.88% | 0.431 (0.384–0.478) | +0.268 | 0.186 | +0.208 | +0.482 | +0.198 |
| `walk_block_median_area_m2` | Street-Grid (`1,521`) | 0.07% | 7,405 $\text{m}^2$ (4,993–11,213) | -0.075 | 0.076 | +0.001 | -0.449 | — |
| `orientation_entropy` | Street-Grid (`1,521`) | 0.00% | 0.917 (0.872–0.945) | +0.323 | 0.142 | -0.014 | +0.193 | — |

----

## 3. Indicator Reference & Representative Retail Centre Profiles

Below we document each of the 11 indicators, including its theoretical basis, mathematical construction, validation behaviour, and visual profiles of representative UK retail centres at the **Low (8th percentile)**, **Median (50th percentile)**, and **High (92nd percentile)** of the distribution.

---

### 3.1 `walk_reach_400` — Walkable Neighbourhood Embeddedness

- **Concept:** External pedestrian integration into the surrounding catchment ring ([Hillier 1996](https://discovery.ucl.ac.uk/id/eprint/3881/); [Sevtsuk & Mekonnen 2012](https://doi.org/10.3166/rig.22.287-305)).
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

- **Concept:** External vehicular integration into the surrounding 400 m road network ([Sevtsuk & Mekonnen 2012](https://doi.org/10.3166/rig.22.287-305)).
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

### 3.5 `carfree_share` — True Pedestrianised Street Share

- **Concept:** Dedicated car-free pedestrian space (pedestrianised high streets, precincts, arcades, and off-road footpaths) net of roadside pavements (Gehl 2010).
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

- **Concept:** Urban street grain and intersection frequency (Jacobs 1961; [Siksna 1997](https://doi.org/10.51347/jum.v1i1.4048)).
- **Construction:** Median length (in metres) of consolidated street edges (excluding off-street `highway=service` car-park lanes and parallel sidewalks) intersecting the 100 m core readout buffer.
- **Interpretation:** Lower values (`34–42 m`) indicate a fine-grained urban network with closely spaced street intersections and frequent turning opportunities; higher values (`> 60 m`) indicate coarse, long-block suburban road layouts (Cliff's $\delta = -0.591$ comparing Regional Centres to Small Local Centres; within-tier $|\rho_{\text{area}}| = 0.072$).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `walk_median_edge_len_m` |
|---|---:|---|---|---:|---:|
| **Low (8th pct — Fine Grain)** | 69 | Wakefield, Yorkshire and The Humber | Major Town Centre | 0.416 | **36.4 m** |
| **Median (50th pct)** | 200 | Lichfield, West Midlands | Major Town Centre | 0.139 | **47.3 m** |
| **High (92nd pct — Coarse Grain)** | 697 | Station Road, New Milton, New Forest | District Centre | 0.173 | **67.7 m** |

![Walkable Street Grain Profiles](Output%20Data/Figures/profile_06_walk_median_edge_len_m.png)

---

### 3.7 `walk_meshedness` — Street-Network Meshedness (Loop Redundancy)

- **Concept:** Planar cycle density and route redundancy ([Buhl et al. 2006](https://doi.org/10.1140/epjb/e2006-00085-1)).
- **Construction:** Evaluated on the consolidated street graph after removing off-street car-park aisles (`highway=service`) and parallel sidewalks:
  $$\alpha = \max\left(0,\; \frac{E - N + C}{2N - 5}\right)$$
  where $E$, $N$, and $C$ denote edges, nodes, and connected components within the 100 m core.
- **Interpretation:** Removing `highway=service` loops ensures that car-park rings do not inflate retail park scores. Traditional gridded Regional Centres exhibit high loop redundancy ($\delta = +0.708$ vs. Small Local Centres), whereas Retail Parks score lower than High Streets ($\delta = -0.288$).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `walk_meshedness` |
|---|---:|---|---|---:|---:|
| **Low (8th pct)** | 1465 | High Street, Dingwall, Highland | Local Centre | 0.102 | **0.052** |
| **Median (50th pct)** | 1326 | Main Street, Uddingston, South Lanarkshire | Local Centre | 0.092 | **0.096** |
| **High (92nd pct)** | 28 | Buchanan Street, Glasgow City Centre | Regional Centre | 0.347 | **0.144** |

![Street-Network Meshedness Profiles](Output%20Data/Figures/profile_07_walk_meshedness.png)

---

### 3.8 `walk_sightline_continuity` — Through-Junction Angular Continuity

- **Concept:** Visual legibility and axial street continuation across intersections ([Hillier & Iida 2005](https://doi.org/10.1007/11556114_30); [Porta et al. 2006b](https://doi.org/10.1016/j.physa.2005.12.063)).
- **Construction:** Proportion of street junctions of degree $k \ge 3$ within the 100 m core (on the car-park-cleaned street graph) that possess at least one pair of incident edges continuing straight through the junction within a $\le 20^\circ$ angular deflection.
- **Interpretation:** High scores (`> 0.94`) indicate linear high streets with uninterrupted axial continuity across cross-streets; lower scores (`< 0.83`) indicate medieval or Victorian layouts with frequent offset T-junctions and cranked intersections. Size-invariant ($\rho_{\text{area}} = -0.057$ across street centres).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `walk_sightline_continuity` |
|---|---:|---|---|---:|---:|
| **Low (8th pct)** | 159 | Walham Green, Hammersmith and Fulham | Town Centre | 0.210 | **0.80** |
| **Median (50th pct)** | 77 | Old Market Square, Nottingham City Centre | Regional Centre | 0.266 | **0.89** |
| **High (92nd pct)** | 889 | High Street, Thornton Heath, Croydon | District Centre | 0.114 | **0.96** |

![Through-Junction Sightline Continuity Profiles](Output%20Data/Figures/profile_08_walk_sightline_continuity.png)

---

### 3.9 `flow_concentration` — Through-Movement Hierarchy (Betweenness Gini)

- **Concept:** Concentration of shortest-path pedestrian movement onto a single spine versus dispersion across a multi-street grid ([Freeman 1977](https://doi.org/10.2307/3033543); [Porta et al. 2006a](https://doi.org/10.1068/b32045)).
- **Construction:** Gini coefficient of local shortest-path edge betweenness (400 m path cutoff on the 400 m context street graph, excluding `highway=service` car-park lanes) evaluated across street edges within the 100 m core.
- **Interpretation:** Lower values (`~0.38–0.41`) indicate compact multi-street centres where local movement distributes evenly across parallel lanes; higher values (`> 0.50`) indicate hierarchical centres where shortest paths funnel onto a primary corridor spine (Cliff's $\delta = +0.482$ across the retail hierarchy).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `flow_concentration` |
|---|---:|---|---|---:|---:|
| **Low (8th pct — Distributed Grid)** | 1118 | Willenhall, Walsall | Local Centre | 0.134 | **0.40** |
| **Median (50th pct)** | 750 | Piccadilly Basin, Manchester City Centre | Regional Centre | 0.121 | **0.46** |
| **High (92nd pct — Corridor Spine)** | 657 | The Mailbox, Birmingham City Centre | Regional Centre | 0.154 | **0.54** |

![Through-Movement Flow Concentration Profiles](Output%20Data/Figures/profile_09_flow_concentration.png)

---

### 3.10 `walk_block_median_area_m2` — Enclosed Urban Block Area *(Street-Grid Set)*

- **Concept:** Physical scale of enclosed urban street blocks ([Siksna 1997](https://doi.org/10.51347/jum.v1i1.4048); [Louf & Barthelemy 2014](https://doi.org/10.1098/rsif.2014.0924)).
- **Construction:** Computed for the 1,521 traditional street centres (`Regional`, `Major Town`, `Town`, `Market Town`, `District`, and `Local Centres`). Ground-level street segments (with `highway=service` car-park lanes and parallel sidewalks removed) are polygonised via `shapely.ops.polygonize`. Sliver traffic islands (thickness $4A/P < 20\text{ m}$) are filtered out, and the median area ($\text{m}^2$) of blocks whose interior point falls within the 100 m core is returned.
- **Interpretation:** Completely independent of centre polygon size ($\rho_{\text{area}} = -0.075$) and OSM sidewalk mapping ($\rho_{\text{sidewalk}} = +0.001$), with `0.07%` missingness across the 1,521 street centres. Fine-grained centres exhibit compact permeable blocks (`3,000–5,000` $\text{m}^2$; Cliff's $\delta = -0.449$ vs. District/Local Centres), whereas linear suburban corridors exhibit large elongated blocks (`> 14,000` $\text{m}^2$).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `walk_block_median_area_m2` |
|---|---:|---|---|---:|---:|
| **Low (8th pct — Fine Compact Blocks)** | 852 | Bolton Street, Ramsbottom, Bury | District Centre | 0.096 | **3,277 $\text{m}^2$** |
| **Median (50th pct)** | 842 | High Street, Blackheath, Sandwell | District Centre | 0.201 | **7,362 $\text{m}^2$** |
| **High (92nd pct — Large Coarse Blocks)** | 313 | Morningside Road, Churchhill, Edinburgh | District Centre | 0.123 | **16,750 $\text{m}^2$** |

![Enclosed Urban Block Area Profiles](Output%20Data/Figures/profile_10_walk_block_median_area_m2.png)

---

### 3.11 `orientation_entropy` — Street Bearing Orientation Entropy *(Street-Grid Set)*

- **Concept:** Geometric alignment of street bearings versus multi-directional irregularity ([Boeing 2019](https://doi.org/10.1007/s41109-019-0189-1)).
- **Construction:** Computed for the 1,521 traditional street centres on the car-park-cleaned street graph. Edge bearings (in both directions) are weighted by segment length into 36 compass bins of $10^\circ$, and Shannon entropy is normalised by $\ln(36) \in [0, 1]$.
- **Interpretation:** Low entropy (`< 0.83`) identifies orthogonal gridiron layouts aligned along two perpendicular axes (e.g. Victorian terraced grids along Stockport Road, Manchester); high entropy (`> 0.96`) identifies radial or multi-directional street patterns (e.g. Llanelli, Carmarthenshire). Restricting to the 1,521 street centres eliminates small-sample histogram bias (`0.00%` missing; within-tier $|\rho_{\text{area}}| = 0.142$).

| Band | `RC_ID` | Retail Centre | Classification | Area ($\text{km}^2$) | `orientation_entropy` |
|---|---:|---|---|---:|---:|
| **Low (8th pct — Orthogonal Grid)** | 934 | Stockport Road, Longsight, Manchester | District Centre | 0.121 | **0.815** |
| **Median (50th pct)** | 617 | Bridport, Dorset | Market Town | 0.137 | **0.928** |
| **High (92nd pct — Multi-Directional)** | 439 | Llanelli, Carmarthenshire | Market Town | 0.313 | **0.970** |

![Street Bearing Orientation Entropy Profiles](Output%20Data/Figures/profile_11_orientation_entropy.png)

----

## 4. References

- **Appleyard, D. (1981).** *Livable Streets*. University of California Press, Berkeley.
- **Boeing, G. (2019).** Urban spatial order: Street network orientation, configuration, and entropy. *Applied Network Science*, 4(1), 67. [https://doi.org/10.1007/s41109-019-0189-1](https://doi.org/10.1007/s41109-019-0189-1)
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
