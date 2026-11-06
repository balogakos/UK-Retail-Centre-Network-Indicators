## Validation Scorecard & Diagnostic Summary for UK Retail Centre Network Indicators

from pathlib import Path
import sys
import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Source Code'))
from Helper_Functions import (
    ALL_INDICATORS,
    STREET_GRID_EXCLUDED_TIERS,
    STREET_GRID_INDICATORS,
    UNIVERSAL_INDICATORS,
)


# 1. Configuration & Helper Statistics ------------------------------------

IN_CSV = Path('Output Data/UK_Retail_Centre_Network_Indicators.csv')
OUT_SCORECARD = Path('Output Data/Validation_Scorecard.csv')

HIGH_STREET_TIERS = {
    'Regional Centre', 'Major Town Centre', 'Town Centre',
    'District Centre', 'Market Town', 'Local Centre'
}
RETAIL_PARK_TIERS = {'Small Retail Park', 'Large Retail Park'}


def cliffs_delta(x, y):
    x = pd.Series(x).dropna().to_numpy()
    y = pd.Series(y).dropna().to_numpy()
    if len(x) == 0 or len(y) == 0:
        return np.nan
    u, _ = mannwhitneyu(x, y, alternative='two-sided')
    return float(2.0 * u / (len(x) * len(y)) - 1.0)


# 2. Compute Discriminant & Convergent Validity Scorecard -----------------

def main():
    df = pd.read_csv(IN_CSV)
    df_street = df[~df['Classification'].isin(STREET_GRID_EXCLUDED_TIERS)].copy()

    reg = df[df['Classification'] == 'Regional Centre']
    slc = df[df['Classification'] == 'Small Local Centre']
    dist_loc = df[df['Classification'].isin({'District Centre', 'Local Centre'})]
    rp = df[df['Classification'].isin(RETAIL_PARK_TIERS)]
    hs = df[df['Classification'].isin(HIGH_STREET_TIERS)]

    rows = []
    for ind in ALL_INDICATORS:
        scope = 'Universal Core (N = 9,623)' if ind in UNIVERSAL_INDICATORS else 'Street-Grid Set (N = 1,521)'
        sub = df if ind in UNIVERSAL_INDICATORS else df_street
        valid = sub.dropna(subset=[ind])

        # Missingness within eligible scope
        missing_pct = 100.0 * (1.0 - len(valid) / len(sub))

        # Size correlation (overall eligible scope & within-tier mean |rho|)
        rho_area, _ = spearmanr(valid[ind], valid['Area_km2'])
        rho_area_non_slc, _ = spearmanr(
            df_street.dropna(subset=[ind])[ind],
            df_street.dropna(subset=[ind])['Area_km2']
        )
        wt = []
        for _, g in valid.groupby('Classification'):
            if len(g) >= 20:
                r, _ = spearmanr(g[ind], g['Area_km2'])
                if np.isfinite(r):
                    wt.append(abs(r))
        mean_abs_wt = float(np.mean(wt)) if wt else np.nan

        # Sidewalk mapping artefact correlation
        sw_valid = valid.dropna(subset=['sidewalk_mapped_share'])
        rho_sw, _ = spearmanr(sw_valid[ind], sw_valid['sidewalk_mapped_share'])

        # Face validity contrasts (Cliff's delta)
        d_reg_local = cliffs_delta(reg[ind], slc[ind]) if ind in UNIVERSAL_INDICATORS else cliffs_delta(reg[ind], dist_loc[ind])
        d_rp_hs = cliffs_delta(rp[ind], hs[ind]) if ind in UNIVERSAL_INDICATORS else np.nan

        rows.append({
            'indicator': ind,
            'tier_scope': scope,
            'eligible_N': len(sub),
            'valid_N': len(valid),
            'missing_pct': round(missing_pct, 2),
            'median': round(float(valid[ind].median()), 3),
            'iqr_25': round(float(valid[ind].quantile(0.25)), 3),
            'iqr_75': round(float(valid[ind].quantile(0.75)), 3),
            'rho_area_all_eligible': round(float(rho_area), 3),
            'rho_area_street_centres': round(float(rho_area_non_slc), 3),
            'within_tier_abs_rho_area': round(mean_abs_wt, 3),
            'rho_sidewalk_mapped': round(float(rho_sw), 3),
            'cliffs_delta_hierarchy': round(float(d_reg_local), 3) if np.isfinite(d_reg_local) else np.nan,
            'cliffs_delta_rp_vs_hs': round(float(d_rp_hs), 3) if np.isfinite(d_rp_hs) else np.nan,
        })

    scorecard = pd.DataFrame(rows)
    scorecard.to_csv(OUT_SCORECARD, index=False)
    print(scorecard.to_string(index=False))
    print(f'\nSaved {OUT_SCORECARD}')


if __name__ == '__main__':
    main()
