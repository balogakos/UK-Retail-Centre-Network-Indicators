# UK-Retail-Centre-Network-Indicators


This repository contains street-network morphology indicators, validation tables, and Python scripts for the 9,623 UK retail centres delineated by the [Geographic Data Service (GeoDS)](https://geods.ac.uk).

## 1. Overview and Data Products

The indicators are built for the UK release of the Geographic Data Service ([GeoDS](https://geods.ac.uk)) [Retail Centre Boundaries](https://data.geods.ac.uk/dataset/retail-centre-boundaries) dataset (`N = 9,623` retail centres in British National Grid, `EPSG:27700`, included in [`Input Data/retailcentre_bounds_uk.gpkg`](Input%20Data/retailcentre_bounds_uk.gpkg)), paired with street and footpath networks extracted from OpenStreetMap (`united-kingdom-latest.osm.pbf`).

Because raw OpenStreetMap street graphs are sensitive to local pavement-mapping habits, polygon size, split junctions, and off-street car-park circulation, the indicators are split into two groups:

1. **Universal Core Set (9 Indicators for all 9,623 Retail Centres):**
   - **External Network Embeddedness:** `walk_reach_400`, `drive_reach_400`
   - **Car Dominance and Servicing:** `arterial_share`, `service_share`
   - **Dedicated Pedestrian Ways:** `carfree_share`
   - **Street Grain and Loop Structure:** `walk_median_edge_len_m`, `walk_meshedness`
   - **Axial Legibility and Movement Hierarchy:** `walk_sightline_continuity`, `flow_concentration`

2. **Street-Grid Set (2 Indicators for 1,521 Traditional Street Centres):**
   - **Block Scale and Grid Alignment:** `walk_block_median_area_m2`, `orientation_entropy`
   - These two metrics are calculated for traditional street-network centres (`Regional Centre`, `Major Town Centre`, `Town Centre`, `Market Town`, `District Centre`, and `Local Centre`; `N = 1,521`). They are left as `NaN` for `Small Local Centres`, which generally consist of a single linear shopping parade with too few streets to form enclosed urban blocks or directional histograms, as well as out-of-town `Retail Parks` and `Shopping Centres`.

![UK Retail Centre Street-Network Morphologies](Output%20Data/Figures/uk_retail_centre_indicator_popouts.png)

### 1.1 Data Downloads

All output datasets and validation tables are stored in the `Output Data/` directory:

- **Geopackage (Polygons and Indicators):** [UK_Retail_Centre_Network_Indicators.gpkg](Output%20Data/UK_Retail_Centre_Network_Indicators.gpkg)
- **Lookup Table (CSV):** [UK_Retail_Centre_Network_Indicators.csv](Output%20Data/UK_Retail_Centre_Network_Indicators.csv)
- **Validation Scorecard (CSV):** [Validation_Scorecard.csv](Output%20Data/Validation_Scorecard.csv)
- **Parameter Perturbation Robustness Table (CSV):** [Validation_Robustness.csv](Output%20Data/Validation_Robustness.csv)
- **Representative Centre Examples (CSV):** [Indicator_Profile_Examples.csv](Output%20Data/Indicator_Profile_Examples.csv)

### 1.2 Pipeline Structure

All scripts use repository-relative paths and compute the dataset from scratch:

- [`Source Code/Helper_Functions.py`](Source%20Code/Helper_Functions.py): Graph construction, parallel sidewalk detection, topology-aware junction consolidation, and indicator calculation functions.
- [`Analysis Code/01_Extract_OSM_Networks.py`](Analysis%20Code/01_Extract_OSM_Networks.py): Extracts highway ways within 400 m of [`Input Data/retailcentre_bounds_uk.gpkg`](Input%20Data/retailcentre_bounds_uk.gpkg) from `Input Data/united-kingdom-latest.osm.pbf` into `Input Data/uk_roads_400m.parquet`, preserving `footway`, `service`, `access`, `foot`, `motor_vehicle`, `oneway`, `bridge`, `tunnel`, and `layer` tags.
- [`Analysis Code/02_Calculate_Network_Indicators.py`](Analysis%20Code/02_Calculate_Network_Indicators.py): Computes all 11 indicators and `sidewalk_mapped_share` directly from the retail centre boundaries and extracted road network.
- [`Analysis Code/03_Validate_Network_Indicators.py`](Analysis%20Code/03_Validate_Network_Indicators.py): Generates [`Validation_Scorecard.csv`](Output%20Data/Validation_Scorecard.csv) and the stratified perturbation sensitivity table [`Validation_Robustness.csv`](Output%20Data/Validation_Robustness.csv).
- [`Analysis Code/04_Generate_Indicator_Profiles.py`](Analysis%20Code/04_Generate_Indicator_Profiles.py): Produces the national overview figure [`uk_retail_centre_indicator_popouts.png`](Output%20Data/Figures/uk_retail_centre_indicator_popouts.png), the methodological construction figure [`visual_qa_sidewalk_consolidation.png`](Output%20Data/Figures/visual_qa_sidewalk_consolidation.png), the 11 distribution profile figures [`profile_01_*.png` to `profile_11_*.png`](Output%20Data/Figures/), and [`Indicator_Profile_Examples.csv`](Output%20Data/Indicator_Profile_Examples.csv).
- [`Analysis Code/05_Create_Editorial_Figures.py`](Analysis%20Code/05_Create_Editorial_Figures.py): Exports high-resolution dark-mode publication figures for the GeoDS retail centre morphology data story.
- [`Analysis Code/06_Export_Explorer_Data.py`](Analysis%20Code/06_Export_Explorer_Data.py): Compiles optimized, lightweight JSON structures for the interactive web map, radar charts, and comparative benchmarks.
- [`Analysis Code/07_Fill_Data_in_Brief_Template.py`](Analysis%20Code/07_Fill_Data_in_Brief_Template.py): Automatically populates the Elsevier Data in Brief manuscript template with complete data specifications, value bullets, and methodology.

### 1.3 Interactive Web Map and Dual Comparator

An open-source, client-side web application is included in [`explorer/`](explorer/) for exploring and comparing all 9,623 UK retail centres:

- **Interactive National Map:** Powered by Leaflet and CartoDB Dark Matter tiles, rendering all 9,623 retail centres with dynamic metric choropleth coloring and classification filtering.
- **Instant Search Autocomplete:** Real-time search across all UK centre names and IDs with immediate map zoom and boundary polygon highlighting.
- **11-Axis Morphology Radar Diagrams:** Normalized percentile radar charts comparing any selected centre against its hierarchical tier median, regional median, and national benchmarks.
- **Side-by-Side Dual Comparator:** Pin any primary centre and comparator centre (or launch curated exemplar pairs such as *Bradford vs. Peel Retail Park* or *Bristol Old City vs. Leytonstone*) with overlaid dual radar charts and indicator delta metrics.

To run the explorer locally:
```bash
python -m http.server 8000 --directory explorer
# Then open http://localhost:8000 in your browser
```

To deploy on GitHub Pages, select the repository's GitHub Pages settings and choose the deployment branch and directory (or copy `explorer/` into `docs/`).

----

## 2. Methodological Controls and Validation

### 2.1 Graph Cleaning and Consolidation

Directly converting OpenStreetMap ways into a planar graph creates three recurring distortions in retail centres. First, in cities where contributors map roadside pavements as separate `highway=footway` geometries, uncleaned graphs treat every pavement crossing as an extra street intersection and count roadside pavements as pedestrianised streets. Second, dual carriageways and complex intersections split single street junctions into clusters of nearby nodes, while naive Euclidean node clustering can falsely merge unconnected parallel streets. Third, off-street car-park circulation (`highway=service`) creates dense loops of 20 m parking aisles that mimic fine-grained historic street blocks.

Our graph construction pipeline addresses these three issues in sequence:

1. **Bearing-Aligned Parallel Sidewalk Filter (`detect_parallel_sidewalks`):** Removes ways explicitly tagged as `footway=sidewalk`, `crossing`, or `traffic_island`, along with untagged `highway=footway` segments ($\ge 8\text{ m}$) where at least 75% of sampled points (spaced every $10\text{ m}$) lie within $12\text{ m}$ of a motorised road and align within $25^\circ \pmod{180^\circ}$ of that road's tangent bearing. Requiring both proximity and parallel alignment retains genuine footpaths that cut across or diverge from roads.
2. **Car-Park and Service Separation (`gw_street`):** Off-street car-park aisles and loading bays (`highway=service`) are measured through `service_share` and removed before building the street-topology graph used for `walk_median_edge_len_m`, `walk_meshedness`, `walk_sightline_continuity`, `flow_concentration`, `walk_block_median_area_m2`, and `orientation_entropy`.
3. **Topology-Aware 10 m Junction Consolidation (`build_consolidated_graph`):** Ground-level ways are planarised at intersections while preserving grade-separated bridges and tunnels, and coincident endpoints within $0.5\text{ m}$ are snapped to form the initial planar graph $G_0$. Following [Boeing (2025)](https://doi.org/10.1111/tgis.70037), nodes within a $10\text{ m}$ Euclidean radius are merged only if they are topologically connected in $G_0$ within a short network path ($\le 25\text{ m}$) or within a $1.5\text{ m}$ endpoint snap tolerance, do not collapse a connecting street edge longer than $25\text{ m}$ into a self-loop, and remain within $10\text{ m}$ of their cluster seed so clusters cannot chain transitively across parallel streets.

![Step-by-Step Street-Network Graph Construction](Output%20Data/Figures/visual_qa_sidewalk_consolidation.png)

### 2.2 Validation Scorecard

| Indicator | Scope (`N`) | Missing (%) | Median (IQR) | $\rho_{\text{area}}$ (Street Centres) | Within-Tier $\|\rho_{\text{area}}\|$ | $\rho_{\text{sidewalk}}$ | $\varepsilon^2_{\text{region}}$ | Cliff's $\delta$ (Hierarchy) | Cliff's $\delta$ (Retail Park vs. High Street) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `walk_reach_400` | Universal (`9,623`) | 0.06% | 0.628 (0.545 to 0.696) | +0.135 | 0.139 | -0.156 | 0.027 | +0.351 | -0.687 |
| `drive_reach_400` | Universal (`9,623`) | 1.21% | 0.627 (0.536 to 0.707) | +0.195 | 0.180 | -0.040 | 0.007 | +0.260 | -0.590 |
| `arterial_share` | Universal (`9,623`) | 0.53% | 0.253 (0.058 to 0.370) | +0.125 | 0.088 | +0.099 | 0.013 | +0.149 | +0.444 |
| `service_share` | Universal (`9,623`) | 0.53% | 0.292 (0.185 to 0.412) | +0.086 | 0.199 | +0.013 | 0.049 | -0.145 | +0.689 |
| `carfree_share` | Universal (`9,623`) | 0.02% | 0.144 (0.074 to 0.229) | +0.165 | 0.066 | +0.025 | 0.026 | +0.668 | -0.345 |
| `walk_median_edge_len_m` | Universal (`9,623`) | 0.39% | 50.1 m (40.3 to 63.9) | -0.187 | 0.062 | -0.127 | 0.010 | -0.632 | +0.036 |
| `walk_meshedness` | Universal (`9,623`) | 0.39% | 0.065 (0.036 to 0.094) | +0.320 | 0.189 | +0.006 | 0.027 | +0.548 | -0.303 |
| `walk_sightline_continuity` | Universal (`9,623`) | 1.73% | 0.897 (0.833 to 0.952) | -0.072 | 0.113 | +0.033 | 0.036 | -0.014 | -0.132 |
| `flow_concentration` | Universal (`9,623`) | 0.77% | 0.442 (0.392 to 0.494) | +0.261 | 0.194 | +0.257 | 0.010 | +0.563 | +0.188 |
| `walk_block_median_area_m2` | Street-Grid (`1,521`) | 0.07% | 6,910 $\text{m}^2$ (4,696 to 10,338) | -0.073 | 0.081 | +0.026 | 0.070 | -0.418 | n/a |
| `orientation_entropy` | Street-Grid (`1,521`) | 0.00% | 0.920 (0.877 to 0.948) | +0.311 | 0.134 | -0.045 | 0.047 | +0.191 | n/a |

*Note: $\varepsilon^2_{\text{region}} = (H - k + 1)/(n - k)$ reports the non-parametric Kruskal-Wallis epsilon-squared effect size across UK regions.*

### 2.3 Parameter Perturbation Robustness (`Validation_Robustness.csv`)

We test rank stability using Spearman correlations ($\rho$) on a stratified random sample of $n = 525$ UK retail centres across all 10 retail classifications in [03_Validate_Network_Indicators.py](Analysis%20Code/03_Validate_Network_Indicators.py), varying the core readout buffer (`50 m` and `150 m` vs. `100 m` baseline), the junction consolidation tolerance (`5 m` and `15 m` vs. `10 m` baseline), and sidewalk retention (`keep_sidewalks`):

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

Several validation patterns and scope boundaries should be kept in mind when using the dataset:

- **Scope of validation:** The scorecard and perturbation checks evaluate completeness, ordinal rank stability across buffer and consolidation choices, independence from polygon area and sidewalk mapping, and contrasts across official retail centre classifications. Note that while exterior-ring and compositional indicators have high rank stability ($\min \rho \ge 0.932$), internal topological and block indicators (`walk_meshedness` at $\min \rho = 0.841$, `walk_block_median_area_m2` at $\min \rho = 0.849$, and `walk_sightline_continuity` at $\min \rho = 0.859$) show moderate sensitivity to the core readout buffer radius (`50 m` vs. `100 m`). Furthermore, these checks support using the variables as **descriptive street-network morphology indicators**; they do not evaluate agreement against external behavioural or economic outcomes such as pedestrian footfall, retail sales, vacancy rates, or observed shopper trajectories.
- **Moderate area association in `walk_meshedness` and `orientation_entropy`:** Across traditional street centres, `walk_meshedness` ($\rho_{\text{area}} = +0.320$, within-tier $|\rho_{\text{area}}| = 0.189$) and `orientation_entropy` ($\rho_{\text{area}} = +0.311$, within-tier $|\rho_{\text{area}}| = 0.134$) retain moderate positive correlations with polygon area because larger town and city centres naturally span more street blocks and directional alignments than compact local centres; models of retail performance should control for hierarchy tier or log-area when using these two metrics.
- **Residual sidewalk-mapping association in `flow_concentration`:** While `flow_concentration` has near-zero regional variance ($\varepsilon^2_{\text{region}} = 0.010$), it carries the largest residual correlation with `sidewalk_mapped_share` ($\rho_{\text{sidewalk}} = +0.257$), reflecting the fact that dense urban centres with more detailed OSM footway mapping also tend to have stronger hierarchical corridor spines.
- **Descriptive role of `walk_sightline_continuity`:** `walk_sightline_continuity` is independent of centre size ($\rho_{\text{area}} = -0.072$), but shows virtually no contrast across the retail hierarchy ($\delta = -0.014$) and should be treated as a descriptive measure of axial street alignment rather than a typology classifier.

----

## 3. Indicator Descriptions and Retail Centre Profiles

The sections below set out the conceptual background, calculation, and practical meaning of each indicator, paired with maps of representative UK retail centres at the **Low (8th percentile)**, **Median (50th percentile)**, and **High (92nd percentile)** of the national distribution.

---

### 3.1 Walkable Neighbourhood Reach (`walk_reach_400`)

Walkable neighbourhood reach measures how well a retail centre is connected on foot to its surrounding residential and mixed-use catchment. Drawing on the concept of metric reach and network accessibility ([Hillier 1996](https://discovery.ucl.ac.uk/id/eprint/3881/); [Sevtsuk & Mekonnen 2012](https://doi.org/10.3166/rig.22.287-305)), we run a multi-source Dijkstra shortest-path search outward from all walkable nodes within 30 m of the retail centre boundary. To prevent the indicator from scaling mechanically with the internal size of the retail centre, the denominator is restricted strictly to the exterior 0 to 400 m ring outside the polygon. The indicator reports the share of walkable street length in that exterior ring that can be reached within a 400 m walk from the centre perimeter.

Across the UK, the median score is `0.63` (interquartile range `0.55` to `0.70`), and the metric is almost invariant to buffer and consolidation perturbations ($\min \rho = 0.994$). For retail centres, high values (`0.75` to `0.85`, such as Bradford at `0.78`) identify high streets and town centres that are stitched into surrounding residential streets across their entire perimeter, enabling short walk-in shopping trips from all directions. Low values (`< 0.50`, such as Peel Retail Park in Sunderland at `0.46`) identify isolated retail enclaves cut off from neighbouring streets by railway lines, rivers, or fenced arterial perimeters, resulting in a strong separation between Retail Parks and High Streets (Cliff's $\delta = -0.687$).

![Walkable Neighbourhood Reach Profiles](Output%20Data/Figures/profile_01_walk_reach_400.png)

---

### 3.2 Motorised Road-Network Embeddedness (`drive_reach_400`)

Motorised road-network embeddedness applies the same exterior-ring accessibility formulation ([Sevtsuk & Mekonnen 2012](https://doi.org/10.3166/rig.22.287-305)) to the consolidated public motorised road network (`DRIVE_CLASSES` consolidated at 10 m). Starting from all drivable road nodes within 50 m of the retail centre boundary, a multi-source Dijkstra search measures the proportion of public road length in the exterior 0 to 400 m catchment ring reachable within 400 m along the road graph. Because planar junction consolidation merges undirected road centrelines without modelling turn prohibitions or one-way restrictions, this indicator should be read as structural road-network embeddedness rather than legal turn-by-turn driving reach.

The national median is `0.63` (IQR `0.54` to `0.71`), with high rank stability across geometric perturbations ($\min \rho = 0.998$). For a retail centre, a high score (such as Tooting Graveney in London at `0.79`) indicates a centre embedded in a continuous urban street grid where buses, deliveries, and local traffic can approach along dozens of intersecting streets. A low score (such as Rushden Lakes Shopping Centre at `0.45`) reflects an out-of-town development connected to the surrounding highway network through a single roundabout or slip road, where most roads in the surrounding 400 m ring cannot be reached without a long detour (Cliff's $\delta = -0.590$ comparing Retail Parks with High Streets).

![Motorised Road-Network Embeddedness Profiles](Output%20Data/Figures/profile_02_drive_reach_400.png)

---

### 3.3 Arterial Traffic Share (`arterial_share`)

Arterial traffic share captures the extent to which a retail centre's road network is dominated by high-capacity through-traffic corridors rather than local streets, building on work on traffic severance and street hierarchy (Appleyard 1981; [Marshall 2005](https://doi.org/10.4324/9780203589397)). It is calculated within the 100 m core readout buffer as the length of public roads classified in OpenStreetMap as `motorway`, `trunk`, `primary`, or `secondary` (including their link roads), divided by total public drivable road length in the same buffer.

Across all 9,623 centres, the median arterial share is `0.25` (IQR `0.06` to `0.37`). In retail terms, low values (`< 0.10`, such as Coventry Road in Sparkbrook, Birmingham at `0.07`) occur where shopping parades sit within quiet residential or tertiary streets with calmer crossing conditions. High values (`> 0.50`, such as Parc Pemberton in Carmarthenshire at `0.57`) indicate retail parks straddling dual carriageways or high streets bisected by major A-roads (Cliff's $\delta = +0.444$ between Retail Parks and High Streets), where heavy vehicle flows create barrier effects between opposite sides of the centre.

![Arterial Traffic Share Profiles](Output%20Data/Figures/profile_03_arterial_share.png)

---

### 3.4 Service and Car-Park Access Share (`service_share`)

Service and car-park access share measures the proportion of a centre's motorised road network devoted to off-street parking circulation, loading bays, and internal access roads ([Marshall 2005](https://doi.org/10.4324/9780203589397)). Within the 100 m core buffer, it divides the total length of public and permissive `highway=service` ways (excluding private residential `service=driveway` segments) by the combined length of public drivable roads and service ways.

The UK median is `0.29` (IQR `0.19` to `0.41`), and the indicator is nearly orthogonal to both centre area ($\rho_{\text{area}} = +0.086$) and sidewalk mapping ($\rho_{\text{sidewalk}} = +0.013$). For retail analysis, `service_share` is the strongest single discriminator between car-park-led retail formats and traditional high streets (Cliff's $\delta = +0.689$). Traditional high streets such as London Road in Southend-on-Sea (`0.18`) rely on public street frontage with minimal off-street service roads, whereas out-of-town retail parks and designer outlets such as Cheshire Oaks (`0.61`) are structured around large surface car parks where internal parking loops account for the majority of the vehicle network.

![Service and Car-Park Share Profiles](Output%20Data/Figures/profile_04_service_share.png)

---

### 3.5 Dedicated Pedestrian-Way Share (`carfree_share`)

Dedicated pedestrian-way share quantifies how much of a retail centre's walkable network is reserved for pedestrians away from motor traffic (Gehl 2010). After applying our bearing-aligned sidewalk filter to remove roadside pavements and crossings, we sum the length of `pedestrian`, `footway`, `path`, and `steps` ways inside the 100 m core buffer and divide by the total non-sidewalk walkable network length. Because the numerator includes traffic-free footpaths, shopping arcades, and off-road cut-throughs alongside formal `highway=pedestrian` streets, the variable reflects overall dedicated pedestrian-way provision rather than solely pedestrianised high-street frontage.

Removing parallel sidewalks eliminates regional OSM pavement-mapping bias ($\rho_{\text{sidewalk}} = +0.025$, $\varepsilon^2_{\text{region}} = 0.026$) and reveals a strong gradient across the retail hierarchy (Cliff's $\delta = +0.668$ between Regional Centres and Small Local Centres). Centres with high scores (such as Thetford at `0.34`, or major regional shopping cores) offer dedicated traffic-free precincts and pedestrian priority zones that support lingering and comparison shopping, whereas low-scoring centres (`< 0.08`) confine pedestrians almost entirely to footpaths alongside vehicle roads.

![Dedicated Pedestrian-Way Share Profiles](Output%20Data/Figures/profile_05_carfree_share.png)

---

### 3.6 Walkable Street Grain (`walk_median_edge_len_m`)

Walkable street grain measures the typical distance between street intersections within a retail centre, grounded in classic urban morphology research on short blocks and intersection spacing (Jacobs 1961; [Siksna 1997](https://doi.org/10.51347/jum.v1i1.4048)). It is computed on the consolidated public street graph (with both parallel sidewalks and off-street `highway=service` car-park lanes removed) as the median length in metres of street edges intersecting the 100 m core buffer.

Across the UK, the median street link length is `50.1 m` (IQR `40.3 m` to `63.9 m`), with almost no within-tier area bias ($|\rho_{\text{area}}| = 0.062$). Notice that lower values represent a finer urban grain: historic cores and regional centres such as the Old City in Bristol (`32.4 m`) feature closely spaced intersections every 30 to 35 m, giving shoppers frequent corners, visual variety, and multiple ways to circulate between frontages (Cliff's $\delta = -0.632$ comparing Regional Centres to Small Local Centres). Higher values (`> 60 m`, such as South Norwood in Croydon at `63.9 m`) indicate long, uninterrupted street corridors where cross-streets are widely spaced and pedestrian movement is channelled along a single linear axis.

![Walkable Street Grain Profiles](Output%20Data/Figures/profile_06_walk_median_edge_len_m.png)

---

### 3.7 Street-Network Meshedness (`walk_meshedness`)

Street-network meshedness measures the density of closed street loops relative to the maximum possible number of loops in a planar graph of the same size ([Buhl et al. 2006](https://doi.org/10.1140/epjb/e2006-00085-1)). On the consolidated core street graph (with parallel sidewalks and off-street car-park loops excluded), it is calculated as:

$$\alpha = \max\left(0,\; \frac{E - N + C}{2N - 5}\right)$$

where $E$ is the number of street edges, $N$ is the number of nodes, and $C$ is the number of connected components within the 100 m core buffer.

Excluding `highway=service` ways is essential here: without that filter, the rows of parking bays in an out-of-town retail park form dozens of small topological cycles that artificially outscore historic town centres. Once car parks and sidewalks are removed ($\rho_{\text{sidewalk}} = +0.006$), `walk_meshedness` cleanly separates multi-street town and regional centres (Cliff's $\delta = +0.548$, such as Morley in Leeds at `0.141`) from dendritic retail parks ($\delta = -0.303$) and linear market streets (such as Honiton at `0.051`). For retail centres, higher meshedness means shoppers can circulate in continuous loops past multiple shopfronts without having to backtrack along the same pavement.

![Street-Network Meshedness Profiles](Output%20Data/Figures/profile_07_walk_meshedness.png)

---

### 3.8 Axial Sightline Continuity (`walk_sightline_continuity`)

Axial sightline continuity captures how frequently streets continue straight through intersections rather than terminating at T-junctions or deflecting sharply, drawing on axial line continuity in space syntax and dual street-graph analysis ([Hillier & Iida 2005](https://doi.org/10.1007/11556114_30); [Porta et al. 2006b](https://doi.org/10.1016/j.physa.2005.12.063)). For every street junction of degree $k \ge 3$ on the consolidated core street network, we compute the exterior deflection angles between all pairs of incident street segments. The indicator reports the proportion of junctions that have at least one pair of incident streets continuing straight through within a $20^\circ$ angular tolerance.

The national median is `0.90` (IQR `0.83` to `0.95`), and the metric is independent of both centre area ($\rho_{\text{area}} = -0.072$) and sidewalk mapping ($\rho_{\text{sidewalk}} = +0.033$). Because both linear local shopping parades and planned gridiron town centres feature straight main streets crossed by side roads, `walk_sightline_continuity` shows virtually no difference across the retail hierarchy ($\delta = -0.014$). Rather than ranking centre size or tier, it serves as a descriptive indicator of visual legibility: high scores (`0.95` in Whitley Bay) reflect planned grids and straight coastal or Victorian parades with long uninterrupted views, whereas lower scores (`0.80` in Kenton, Brent) identify more fragmented layouts where side streets meet at offset T-junctions.

![Through-Junction Sightline Continuity Profiles](Output%20Data/Figures/profile_08_walk_sightline_continuity.png)

---

### 3.9 Through-Movement Flow Concentration (`flow_concentration`)

Through-movement flow concentration measures whether local pedestrian shortest paths are channelled onto a single dominant high-street spine or spread evenly across a multi-street network ([Freeman 1977](https://doi.org/10.2307/3033543); [Brandes 2001](https://doi.org/10.1080/0022250X.2001.9990249); [Porta et al. 2006a](https://doi.org/10.1068/b32045)). Using `compute_distance_limited_edge_betweenness` on the 400 m street graph (excluding off-street `highway=service` ways), we compute exact shortest-path distances from every node up to a `400.0 m` metric distance limit via `scipy.sparse.csgraph.dijkstra`, and then run weighted, cutoff-aware Brandes ([2001](https://doi.org/10.1080/0022250X.2001.9990249), [2008](https://doi.org/10.1016/j.socnet.2007.11.001)) forward path counting ($\sigma$) and backward dependency accumulation across all equal-shortest predecessors (within a $10^{-7}\text{ m}$ tie tolerance). We then compute the Gini coefficient of those edge betweenness scores across street segments inside the 100 m core buffer.

Across UK retail centres, the median Gini concentration is `0.44` (IQR `0.39` to `0.49`), rising substantially toward the top of the retail hierarchy (Cliff's $\delta = +0.563$). For retail centres, lower values (`0.41` in Arnold, Gedling) indicate compact, balanced town centres where movement is shared across several parallel shopping streets. Higher values (`0.57` around St James Quarter in Edinburgh) identify centres where local pedestrian trajectories funnel disproportionately onto a primary arterial or pedestrianised spine, creating a sharp hierarchy between prime pitch frontage and quieter secondary backstreets.

![Through-Movement Flow Concentration Profiles](Output%20Data/Figures/profile_09_flow_concentration.png)

---

### 3.10 Enclosed Urban Block Area (`walk_block_median_area_m2`)

Enclosed urban block area measures the physical scale of the street blocks that make up a retail centre's urban fabric ([Siksna 1997](https://doi.org/10.51347/jum.v1i1.4048); [Louf & Barthelemy 2014](https://doi.org/10.1098/rsif.2014.0924)). It is calculated for the 1,521 traditional street centres (`Regional`, `Major Town`, `Town`, `Market Town`, `District`, and `Local Centres`). Ground-level street segments (after removing parallel sidewalks and off-street car-park lanes) are polygonised into enclosed faces via `shapely.ops.polygonize`. Narrow traffic islands and splitter medians with shape thickness $4A/P < 20\text{ m}$ are removed, and the indicator returns the median area in square metres of enclosed street blocks whose representative point lies within the 100 m core buffer.

The indicator has `0.07%` missingness across the 1,521 street centres and is invariant to both total retail centre area ($\rho_{\text{area}} = -0.073$) and sidewalk mapping ($\rho_{\text{sidewalk}} = +0.026$). Historic regional cores such as Kirkgate Market and Vicar Lane in Leeds (`3,026` $\text{m}^2$) are composed of tight, permeable urban blocks (`3,000` to `5,000` $\text{m}^2$) that create high corner density and dense shopfront perimeters (Cliff's $\delta = -0.418$ comparing Regional/Major Town Centres to District/Local Centres). Conversely, outer urban and suburban corridors such as Leytonstone in London (`16,009` $\text{m}^2$) are bounded by large, elongated street blocks that restrict cross-movement between parallel streets.

![Enclosed Urban Block Area Profiles](Output%20Data/Figures/profile_10_walk_block_median_area_m2.png)

---

### 3.11 Street Bearing Orientation Entropy (`orientation_entropy`)

Street bearing orientation entropy measures the directional order of a retail centre's street layout, distinguishing orthogonal grids from irregular or multi-directional street networks ([Boeing 2019](https://doi.org/10.1007/s41109-019-0189-1)). Calculated across the 1,521 traditional street centres on the car-park-cleaned street graph within the 100 m core buffer, every street segment's compass bearing (along with its reciprocal $180^\circ$ bearing) is weighted by segment length into 36 directional bins of $10^\circ$. We then compute the Shannon entropy of the resulting compass histogram, normalised by $\ln(36)$ so values lie on $[0, 1]$.

Across traditional street centres, the median entropy is `0.920` (IQR `0.877` to `0.948`) with `0.00%` missingness. Low entropy values (`0.818` in New Malden, Kingston upon Thames) identify planned gridiron retail centres where the high street and residential cross-streets align along two perpendicular axes. High entropy values (`0.972` around King Street in Aberdeen) identify organically grown historic cores or radial junctions where streets converge at multiple angles, shaping how easily visitors orient themselves and navigate across the centre.

![Street Bearing Orientation Entropy Profiles](Output%20Data/Figures/profile_11_orientation_entropy.png)

----

## 4. Data Provenance, Attribution, and Licensing

- **OpenStreetMap Extract Version and Provenance:** Street and footpath geometries (`2,646,803` highway segments within 400 m of UK retail centres in `Input Data/uk_roads_400m.parquet`) were extracted from the Geofabrik United Kingdom OpenStreetMap PBF extract (`united-kingdom-latest.osm.pbf`, size `2,281,092,125` bytes, timestamp `2026-11-05T16:12:58Z`, SHA-256 header/stat fingerprint `d07046874ca657c9`, recorded in [`Input Data/uk_roads_400m.provenance.json`](Input%20Data/uk_roads_400m.provenance.json)).
- **OpenStreetMap Attribution and Licence:** Street network data is copyright **© OpenStreetMap contributors** ([https://www.openstreetmap.org/copyright](https://www.openstreetmap.org/copyright)) and is licensed under the [Open Data Commons Open Database License (ODbL 1.0)](https://opendatacommons.org/licenses/odbl/1-0/). Any derivative datasets, maps, or publications using the extracted highway data or derived network indicators must credit `© OpenStreetMap contributors` and comply with ODbL 1.0 terms.
- **Retail Centre Boundaries Attribution:** UK retail centre boundaries and hierarchical classifications (`N = 9,623` polygons in `Input Data/retailcentre_bounds_uk.gpkg`) are provided by the [Geographic Data Service (GeoDS)](https://geods.ac.uk) [Retail Centre Boundaries](https://data.geods.ac.uk/dataset/retail-centre-boundaries) dataset.
- **Administrative Boundary Basemap Attribution:** Local Authority District boundaries in `Input Data/uk_basemap_boundaries.gpkg` contain public sector information licensed under the UK Open Government Licence v3.0 (Office for National Statistics / OS OpenData).

----

## 5. References

- **Appleyard, D. (1981).** *Livable Streets*. University of California Press, Berkeley.
- **Boeing, G. (2019).** Urban spatial order: Street network orientation, configuration, and entropy. *Applied Network Science*, 4(1), 67. [https://doi.org/10.1007/s41109-019-0189-1](https://doi.org/10.1007/s41109-019-0189-1)
- **Boeing, G. (2025).** Topological graph simplification Solutions to the street intersection miscount problem. *Transactions in GIS*, 29(1), e70037. [https://doi.org/10.1111/tgis.70037](https://doi.org/10.1111/tgis.70037)
- **Brandes, U. (2001).** A faster algorithm for betweenness centrality. *Journal of Mathematical Sociology*, 25(2), 163-177. [https://doi.org/10.1080/0022250X.2001.9990249](https://doi.org/10.1080/0022250X.2001.9990249)
- **Brandes, U. (2008).** On variants of shortest-path betweenness centrality and their generic computation. *Social Networks*, 30(2), 136-145. [https://doi.org/10.1016/j.socnet.2007.11.001](https://doi.org/10.1016/j.socnet.2007.11.001)
- **Buhl, J., Gautrais, J., Reeves, N., Solé, R. V., Valverde, S., Kuntz, P., & Theraulaz, G. (2006).** Topological patterns in street networks of self-organized urban settlements. *The European Physical Journal B*, 49(4), 513-522. [https://doi.org/10.1140/epjb/e2006-00085-1](https://doi.org/10.1140/epjb/e2006-00085-1)
- **Freeman, L. C. (1977).** A set of measures of centrality based on betweenness. *Sociometry*, 40(1), 35-41. [https://doi.org/10.2307/3033543](https://doi.org/10.2307/3033543)
- **Gehl, J. (2010).** *Cities for People*. Island Press, Washington, DC.
- **Hillier, B. (1996).** *Space is the Machine: A Configurational Theory of Architecture*. Cambridge University Press, Cambridge. [https://discovery.ucl.ac.uk/id/eprint/3881/](https://discovery.ucl.ac.uk/id/eprint/3881/)
- **Hillier, B., & Iida, S. (2005).** Network and psychological effects in urban movement. In A. G. Cohn & D. M. Mark (Eds.), *Spatial Information Theory (COSIT 2005)*, Lecture Notes in Computer Science, vol. 3693 (pp. 475-490). Springer. [https://doi.org/10.1007/11556114_30](https://doi.org/10.1007/11556114_30)
- **Jacobs, J. (1961).** *The Death and Life of Great American Cities*. Random House, New York.
- **Louf, R., & Barthelemy, M. (2014).** A typology of street patterns. *Journal of the Royal Society Interface*, 11(101), 20140924. [https://doi.org/10.1098/rsif.2014.0924](https://doi.org/10.1098/rsif.2014.0924)
- **Marshall, S. (2005).** *Streets and Patterns*. Routledge, London. [https://doi.org/10.4324/9780203589397](https://doi.org/10.4324/9780203589397)
- **Porta, S., Crucitti, P., & Latora, V. (2006a).** The network analysis of urban streets: A primal approach. *Environment and Planning B: Planning and Design*, 33(5), 705-725. [https://doi.org/10.1068/b32045](https://doi.org/10.1068/b32045)
- **Porta, S., Crucitti, P., & Latora, V. (2006b).** The network analysis of urban streets: A dual approach. *Physica A: Statistical Mechanics and its Applications*, 369(2), 853-866. [https://doi.org/10.1016/j.physa.2005.12.063](https://doi.org/10.1016/j.physa.2005.12.063)
- **Sevtsuk, A., & Mekonnen, M. (2012).** Urban network analysis: A new toolbox for ArcGIS. *Revue Internationale de Géomatique*, 22(2), 287-305. [https://doi.org/10.3166/rig.22.287-305](https://doi.org/10.3166/rig.22.287-305)
- **Siksna, A. (1997).** The effects of block size and form in North American and Australian city centres. *Urban Morphology*, 1(1), 19-33. [https://doi.org/10.51347/jum.v1i1.4048](https://doi.org/10.51347/jum.v1i1.4048)

