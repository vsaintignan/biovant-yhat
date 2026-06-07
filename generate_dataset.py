"""
Synthetic dataset generator — Bio-Meat Intelligence
10,000 observations of frigorífico effluent treatment, scientifically plausible.

Literature basis:
  - Del Nery et al. (2016) Water Sci Technol: DBO5 treated 30–800 mg/L, DQO/DBO ≈ 1.5–2.5
  - Bustillo-Lecompte & Mehrvar (2015) J Environ Manage: NH4+ 15–180 mg/L raw
  - Blonskaja et al. (2003) Adv Environ Res: OD 0.2–8 mg/L in activated sludge
  - Margesin & Schinner (2005): ADH (TTF-reduction) 0.05–4.5 μg TTF/gVSS·h
  - APHA standard methods for toxicity (Microtox % inhibition)
  - Metcalf & Eddy (2014) WWTP Engineering: OD saturation vs temperature, pH optima
  - Tchobanoglous et al. (2003): caudal típico frigorífico 5–80 m³/h; HRT 6–24 h
  - Rajeshwari et al. (2000) Renew Sust Energ Rev: pH óptimo 6.8–7.5 para biomasa aeróbica
"""

import sys
import random
import math
import csv
import os

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

SEED = 42
random.seed(SEED)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def randn():
    """Standard normal via Box-Muller."""
    while True:
        u1 = random.random()
        u2 = random.random()
        if u1 > 0:
            break
    return math.sqrt(-2 * math.log(u1)) * math.cos(2 * math.pi * u2)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def sample_normal(mu, sigma, lo=None, hi=None):
    v = mu + sigma * randn()
    if lo is not None or hi is not None:
        v = clamp(v, lo if lo is not None else -1e9, hi if hi is not None else 1e9)
    return v


def od_sat_at_temp(temp_c):
    """
    OD saturation (mg/L) at given temperature (freshwater, ~1 atm).
    Linear approximation valid 5–35°C (Benson & Krause 1984):
      OD_sat ≈ 14.62 - 0.3898*T + 0.006969*T²  (simplified to linear here)
    """
    return clamp(14.62 - 0.3898 * temp_c + 0.006969 * temp_c ** 2, 4.0, 14.0)


# ---------------------------------------------------------------------------
# Operational state definitions  (healthy 55 %, stressed 30 %, critical 15 %)
# ---------------------------------------------------------------------------

STATES = {
    "healthy": {
        "weight": 0.55,
        # Effluent after full aerobic treatment — within design capacity
        "dbo5_mu": 35,   "dbo5_sigma": 10,  "dbo5_lo": 10,  "dbo5_hi": 80,
        "nh4_mu":  8,    "nh4_sigma":  4,   "nh4_lo":  1,   "nh4_hi": 25,
        "od_mu":   6.5,  "od_sigma":   1.0, "od_lo":   3.5, "od_hi": 9.0,
        "adh_mu":  2.8,  "adh_sigma":  0.5, "adh_lo":  1.2, "adh_hi": 4.5,
        "tox_mu":  8,    "tox_sigma":  4,   "tox_lo":  1,   "tox_hi": 25,
        "dqo_ratio_mu": 1.65, "dqo_ratio_sigma": 0.12,
        # pH: tight around optimum
        "ph_mu": 7.15, "ph_sigma": 0.15, "ph_lo": 6.6, "ph_hi": 7.8,
        # Caudal (m³/h): within design capacity (~18 m³/h nominal for medium plant)
        "caudal_mu": 18, "caudal_sigma": 4, "caudal_lo": 6,  "caudal_hi": 38,
    },
    "stressed": {
        "weight": 0.30,
        # Partial failure or organic overload event
        "dbo5_mu": 120,  "dbo5_sigma": 35,  "dbo5_lo": 45,  "dbo5_hi": 260,
        "nh4_mu":  55,   "nh4_sigma":  18,  "nh4_lo": 20,   "nh4_hi": 110,
        "od_mu":   2.8,  "od_sigma":   0.8, "od_lo":   0.8, "od_hi": 5.5,
        "adh_mu":  1.5,  "adh_sigma":  0.4, "adh_lo":  0.3, "adh_hi": 2.8,
        "tox_mu":  38,   "tox_sigma":  12,  "tox_lo": 15,   "tox_hi": 70,
        "dqo_ratio_mu": 1.95, "dqo_ratio_sigma": 0.18,
        # pH: drifting — high DBO fermentation acidifies; high NH4 alkalinizes
        "ph_mu": 6.85, "ph_sigma": 0.30, "ph_lo": 6.0, "ph_hi": 8.2,
        # Caudal: above design capacity (overload trigger)
        "caudal_mu": 32, "caudal_sigma": 8, "caudal_lo": 14, "caudal_hi": 60,
    },
    "critical": {
        "weight": 0.15,
        # Biological collapse or severe hydraulic/organic overload
        "dbo5_mu": 380,  "dbo5_sigma": 100, "dbo5_lo": 180, "dbo5_hi": 750,
        "nh4_mu":  130,  "nh4_sigma":  30,  "nh4_lo": 65,   "nh4_hi": 210,
        "od_mu":   0.9,  "od_sigma":   0.4, "od_lo":   0.1, "od_hi": 2.5,
        "adh_mu":  0.5,  "adh_sigma":  0.2, "adh_lo":  0.05,"adh_hi": 1.1,
        "tox_mu":  72,   "tox_sigma":  14,  "tox_lo": 40,   "tox_hi": 98,
        "dqo_ratio_mu": 2.30, "dqo_ratio_sigma": 0.22,
        # pH: acid crash (VFAs) or extreme alkalinity from NH4 accumulation
        "ph_mu": 6.2,  "ph_sigma": 0.55, "ph_lo": 5.2, "ph_hi": 9.0,
        # Caudal: severely overloaded (or near-zero during breakdown)
        "caudal_mu": 52, "caudal_sigma": 14, "caudal_lo": 20, "caudal_hi": 90,
    },
}


# ---------------------------------------------------------------------------
# Season & weekday modifiers
# ---------------------------------------------------------------------------

SEASONS = ["summer", "autumn", "winter", "spring"]
DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

# Ambient / effluent temperature base (°C) by season — Argentina temperate zone
SEASON_TEMP = {
    "summer": (29.0, 2.5),   # (mu, sigma)
    "autumn": (20.0, 2.0),
    "winter": (12.5, 2.0),
    "spring": (22.0, 2.5),
}

def season_nh4_modifier(season):
    # NH4 more soluble in cold water (Henry's law)
    return {"summer": 0.90, "autumn": 1.00, "winter": 1.15, "spring": 0.95}[season]

def weekday_load_modifier(day):
    # Mon–Fri full slaughter; Sat partial; Sun minimal
    return {"Mon": 1.05, "Tue": 1.10, "Wed": 1.10, "Thu": 1.05,
            "Fri": 1.00, "Sat": 0.70, "Sun": 0.40}[day]


# ---------------------------------------------------------------------------
# Inter-variable correlations
# ---------------------------------------------------------------------------

def apply_correlations(dbo5, nh4, od, adh, tox, ph, temp_c, caudal, state_name):
    """
    Physical/biological relationships applied as conditional adjustments:

    OD:
      - High DBO5 → aerobic bacteria consume O2 → OD drops
      - High NH4+ → nitrification O2 demand (~4.3 g O2/g NH4) → OD drops
      - High temperature → lower OD saturation ceiling

    pH:
      - High organic load (fermentation VFAs) → pH decreases
      - High NH4+ accumulation → slight alkalinity production → pH increases
      - High caudal (short HRT) → less time for pH buffering → wider swings

    ADH:
      - OD fraction (aerobic bacteria need O2)
      - pH inhibition (bell curve centered on 7.15, sharp outside 6.5–7.8)
      - Toxicity inhibition (up to 55%)
      - Temperature optimum: ~25–30°C; drops below 15°C and above 35°C
    """
    s = STATES[state_name]

    # --- OD: organic load O2 demand ---
    dbo_excess = max(0, dbo5 - 50) / 200
    od -= dbo_excess * 1.5

    # --- OD: nitrification O2 demand ---
    nh4_excess = max(0, nh4 - 10) / 150
    od -= nh4_excess * 2.0

    # --- OD: temperature caps saturation ---
    od_sat = od_sat_at_temp(temp_c)
    od = min(od, od_sat * 0.95)   # can't exceed ~95% saturation in practice

    # --- pH: organic acids from high DBO5 ---
    acid_shift = max(0, dbo5 - 80) / 400     # VFA acidification
    ph -= acid_shift * 0.8

    # --- pH: alkalinity from NH4 accumulation (ammonium ↔ ammonia buffering) ---
    alk_shift = max(0, nh4 - 30) / 300
    ph += alk_shift * 0.4

    # --- pH: high caudal → reduced buffering capacity ---
    design_caudal = s["caudal_mu"]
    caudal_excess = max(0, caudal - design_caudal) / design_caudal
    ph -= caudal_excess * 0.25 * (1 if ph < 7.0 else -1)   # amplifies deviation

    # --- ADH: fraction of OD ---
    od_clamped = clamp(od, s["od_lo"], s["od_hi"])
    od_fraction = (od_clamped - s["od_lo"]) / max(0.01, s["od_hi"] - s["od_lo"])
    adh *= (0.4 + 0.6 * od_fraction)

    # --- ADH: pH inhibition ---
    ph_deviation = abs(clamp(ph, 4.0, 10.0) - 7.15)
    ph_factor = 1.0 - clamp((ph_deviation - 0.5) * 0.35, 0, 0.70)
    adh *= ph_factor

    # --- ADH: temperature — Q10 factor relative to 25°C optimum ---
    temp_factor = math.exp(-0.5 * ((temp_c - 25.0) / 8.0) ** 2)   # Gaussian peak
    adh *= (0.5 + 0.5 * temp_factor)

    # --- ADH: toxicity inhibition ---
    adh *= (1.0 - 0.55 * (tox / 100.0))

    return dbo5, nh4, od, adh, tox, ph


# ---------------------------------------------------------------------------
# BHI (mirrors backend/main.py)
# ---------------------------------------------------------------------------

def compute_bhi(adh_pct, od_pct, nh4_pct, tox_pct):
    return 0.25 * (adh_pct + od_pct + (100 - nh4_pct) + (100 - tox_pct))


def normalize(value, lo, hi):
    return clamp((value - lo) / (hi - lo) * 100, 0, 100)


ADH_MAX = 4.5    # μg TTF/gVSS·h → 100%
OD_MAX  = 9.2    # mg/L at 20°C → 100%
NH4_MAX = 210    # mg/L → 100% (worst)


def get_label(bhi):
    if bhi >= 75:
        return "healthy"
    elif bhi >= 50:
        return "stressed"
    return "critical"


# ---------------------------------------------------------------------------
# Weighted sampler
# ---------------------------------------------------------------------------

_state_names   = list(STATES.keys())
_state_weights = [STATES[s]["weight"] for s in _state_names]

def weighted_choice():
    r = random.random()
    cumulative = 0.0
    for name, w in zip(_state_names, _state_weights):
        cumulative += w
        if r < cumulative:
            return name
    return _state_names[-1]


# ---------------------------------------------------------------------------
# Main generation loop
# ---------------------------------------------------------------------------

N      = 10_000
OUTPUT = os.path.join(os.path.dirname(__file__), "dataset_biomeat.csv")

FIELDNAMES = [
    "obs_id",
    "season",
    "day_of_week",
    "operational_state",
    "temperatura_c",
    "ph",
    "caudal_m3h",
    "dbo5_mgl",
    "dqo_mgl",
    "dqo_dbo_ratio",
    "nh4_mgl",
    "od_mgl",
    "adh_ugTTF_gVSS_h",
    "toxicity_pct",
    "adh_pct",
    "od_pct",
    "nh4_pct",
    "bhi",
    "bhi_label",
    "decreto_674_dbo_compliant",
    "decreto_674_nh4_compliant",
]

rows = []

for i in range(N):
    state_name = weighted_choice()
    s          = STATES[state_name]
    season     = SEASONS[i % 4]
    day        = DAYS_OF_WEEK[i % 7]

    load_mod    = weekday_load_modifier(day)
    nh4_sea_mod = season_nh4_modifier(season)

    # --- Temperature: season-based, state-independent ---
    t_mu, t_sigma = SEASON_TEMP[season]
    temp_c = sample_normal(t_mu, t_sigma, 5.0, 40.0)

    # --- Primary variables ---
    dbo5   = sample_normal(s["dbo5_mu"] * load_mod,                s["dbo5_sigma"],   s["dbo5_lo"],   s["dbo5_hi"])
    nh4    = sample_normal(s["nh4_mu"]  * nh4_sea_mod * load_mod,  s["nh4_sigma"],    s["nh4_lo"],    s["nh4_hi"])
    od     = sample_normal(s["od_mu"],   s["od_sigma"],  s["od_lo"],  s["od_hi"])
    adh    = sample_normal(s["adh_mu"],  s["adh_sigma"], s["adh_lo"], s["adh_hi"])
    tox    = sample_normal(s["tox_mu"],  s["tox_sigma"], s["tox_lo"], s["tox_hi"])
    ph     = sample_normal(s["ph_mu"],   s["ph_sigma"],  s["ph_lo"],  s["ph_hi"])
    caudal = sample_normal(s["caudal_mu"] * load_mod, s["caudal_sigma"], s["caudal_lo"], s["caudal_hi"])
    dqo_ratio = sample_normal(s["dqo_ratio_mu"], s["dqo_ratio_sigma"], 1.2, 3.5)

    # --- Apply inter-variable correlations ---
    dbo5, nh4, od, adh, tox, ph = apply_correlations(
        dbo5, nh4, od, adh, tox, ph, temp_c, caudal, state_name
    )

    # --- Re-clamp after adjustments ---
    dbo5   = clamp(dbo5,   5,    800)
    nh4    = clamp(nh4,    0.5,  220)
    od     = clamp(od,     0.05, 9.5)
    adh    = clamp(adh,    0.02, 5.0)
    tox    = clamp(tox,    0,    99)
    ph     = clamp(ph,     4.5,  9.5)
    caudal = clamp(caudal, 1,    100)

    dqo = dbo5 * dqo_ratio

    # --- BHI ---
    adh_pct = normalize(adh, 0, ADH_MAX)
    od_pct  = normalize(od,  0, OD_MAX)
    nh4_pct = normalize(nh4, 0, NH4_MAX)
    tox_pct = tox

    bhi       = round(compute_bhi(adh_pct, od_pct, nh4_pct, tox_pct), 2)
    bhi_label = get_label(bhi)

    rows.append({
        "obs_id":               i + 1,
        "season":               season,
        "day_of_week":          day,
        "operational_state":    state_name,
        "temperatura_c":        round(temp_c, 2),
        "ph":                   round(ph, 3),
        "caudal_m3h":           round(caudal, 2),
        "dbo5_mgl":             round(dbo5, 2),
        "dqo_mgl":              round(dqo, 2),
        "dqo_dbo_ratio":        round(dqo_ratio, 3),
        "nh4_mgl":              round(nh4, 2),
        "od_mgl":               round(od, 3),
        "adh_ugTTF_gVSS_h":     round(adh, 4),
        "toxicity_pct":         round(tox, 2),
        "adh_pct":              round(adh_pct, 2),
        "od_pct":               round(od_pct, 2),
        "nh4_pct":              round(nh4_pct, 2),
        "bhi":                  bhi,
        "bhi_label":            bhi_label,
        "decreto_674_dbo_compliant": 1 if dbo5 <= 50 else 0,
        "decreto_674_nh4_compliant": 1 if nh4 <= 35 else 0,
    })


# ---------------------------------------------------------------------------
# Write CSV
# ---------------------------------------------------------------------------

with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
    writer.writeheader()
    writer.writerows(rows)

print(f"Dataset written: {OUTPUT}")
print(f"Rows: {len(rows)}")
print()

for state in _state_names:
    sub    = [r for r in rows if r["operational_state"] == state]
    n_sub  = len(sub)
    mu_bhi  = sum(r["bhi"]         for r in sub) / n_sub
    mu_dbo  = sum(r["dbo5_mgl"]    for r in sub) / n_sub
    mu_ph   = sum(r["ph"]          for r in sub) / n_sub
    mu_temp = sum(r["temperatura_c"] for r in sub) / n_sub
    mu_caud = sum(r["caudal_m3h"]  for r in sub) / n_sub
    print(f"  {state:10s}  n={n_sub:5d}  BHI={mu_bhi:5.1f}  "
          f"DBO5={mu_dbo:6.1f}  pH={mu_ph:.2f}  "
          f"T={mu_temp:.1f}°C  Q={mu_caud:.1f} m³/h")

dbo_ok = sum(r["decreto_674_dbo_compliant"] for r in rows)
nh4_ok = sum(r["decreto_674_nh4_compliant"] for r in rows)
print(f"\nDecreto 674/89 compliance:")
print(f"  DBO5 ≤50 mg/L : {dbo_ok/N*100:.1f}% ({dbo_ok}/{N})")
print(f"  NH4+ ≤35 mg/L : {nh4_ok/N*100:.1f}% ({nh4_ok}/{N})")
