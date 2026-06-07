from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pathlib import Path
import random
import json
from datetime import datetime, timedelta

try:
    import joblib
    _JOBLIB = True
except ImportError:
    _JOBLIB = False

app = FastAPI(title="Bio-Meat Intelligence API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

@app.get("/")
def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


# ── Scenario base parameters ──────────────────────────────────────────────────
SCENARIOS = {
    "healthy": {
        "name": "Operación Normal",
        "adh": 94, "do_sat": 91, "nh4_norm": 7, "tox_norm": 4,
        "description": "Biomasa en condiciones óptimas de actividad",
        "adh_phy": 2.8, "od_phy": 6.5, "nh4_phy": 8.0,
        "ph": 7.15, "temp": 22.0, "caudal": 18.0,
        "dbo5": 32.0, "dqo_ratio": 1.65,
    },
    "stressed": {
        "name": "Biomasa Bajo Estrés",
        "adh": 61, "do_sat": 54, "nh4_norm": 46, "tox_norm": 31,
        "description": "Señales tempranas de deterioro detectadas",
        "adh_phy": 1.5, "od_phy": 2.8, "nh4_phy": 55.0,
        "ph": 6.85, "temp": 22.0, "caudal": 32.0,
        "dbo5": 120.0, "dqo_ratio": 1.95,
    },
    "critical": {
        "name": "Riesgo de Falla",
        "adh": 37, "do_sat": 27, "nh4_norm": 76, "tox_norm": 66,
        "description": "Alto riesgo de incumplimiento regulatorio",
        "adh_phy": 0.45, "od_phy": 0.9, "nh4_phy": 130.0,
        "ph": 6.2, "temp": 22.0, "caudal": 52.0,
        "dbo5": 380.0, "dqo_ratio": 2.30,
    },
}

# ── EcoSentinel — microbial community state (Madoni SBI) ──────────────────────
ECOSENTINEL = {
    "healthy": {
        "score": 88,
        "ciliados":     {"pct": 58, "status": "normal",   "note": "Dominantes (adheridos + reptantes)"},
        "flagelados":   {"pct":  8, "status": "normal",   "note": "Nivel basal"},
        "amebas":       {"pct":  5, "status": "normal",   "note": "Normal"},
        "filamentosas": {"pct":  4, "status": "normal",   "note": "Sin riesgo de bulking"},
        "floculos":     "compactos y bien estructurados",
        "floculos_status": "normal",
        "interpretation": (
            "Comunidad madura y estable, compatible con buena sedimentación y adecuada capacidad depuradora. "
            "Predominio de ciliados adheridos indicadores de lodo maduro (Madoni SBI: clase IV–V)."
        ),
    },
    "stressed": {
        "score": 52,
        "ciliados":     {"pct": 28, "status": "warning",  "note": "En descenso"},
        "flagelados":   {"pct": 38, "status": "warning",  "note": "Elevado — perturbación"},
        "amebas":       {"pct": 18, "status": "warning",  "note": "Elevado — estrés orgánico"},
        "filamentosas": {"pct": 14, "status": "warning",  "note": "Riesgo inicial"},
        "floculos":     "dispersos con fragmentación visible",
        "floculos_status": "warning",
        "interpretation": (
            "Compatible con cambios recientes de carga o perturbaciones operativas. "
            "El incremento de flagelados y amebas indica deterioro de condiciones aeróbicas (Madoni SBI: clase II–III)."
        ),
    },
    "critical": {
        "score": 22,
        "ciliados":     {"pct":  7, "status": "critical", "note": "Casi ausentes"},
        "flagelados":   {"pct": 48, "status": "critical", "note": "Dominantes — crisis"},
        "amebas":       {"pct": 16, "status": "warning",  "note": "Elevado"},
        "filamentosas": {"pct": 30, "status": "critical", "note": "RIESGO DE BULKING"},
        "floculos":     "muy dispersos con predominio filamentoso",
        "floculos_status": "critical",
        "interpretation": (
            "Ecosistema alterado con riesgo de deterioro del tratamiento biológico y pérdida de eficiencia. "
            "Bacterias filamentosas dominantes con riesgo inminente de bulking (Madoni SBI: clase I)."
        ),
    },
}

# ── Vibrio Sentinel — bioluminescence toxicity assay ─────────────────────────
VIBRIO = {
    "healthy": {
        "luminescence_pct": 94, "inhibition_pct": 6,
        "status": "normal",
        "interpretation": (
            "Bioluminiscencia de Vibrio fischeri dentro de rangos normales. "
            "Sin evidencia de compuestos inhibitorios significativos en el efluente."
        ),
    },
    "stressed": {
        "luminescence_pct": 65, "inhibition_pct": 35,
        "status": "warning",
        "interpretation": (
            "Disminución del 35% en bioluminiscencia detectada. "
            "Posible ingreso de compuestos inhibitorios: ácidos grasos, metales traza o detergentes. "
            "Verificar fuentes de toxicidad en la línea de producción."
        ),
    },
    "critical": {
        "luminescence_pct": 32, "inhibition_pct": 68,
        "status": "critical",
        "interpretation": (
            "Disminución severa del 68% en bioluminiscencia. "
            "Alta carga de compuestos tóxicos confirmada por Vibrio fischeri. "
            "Activar protocolo de emergencia y notificar al responsable ambiental."
        ),
    },
}

# ── Sensor trend directions per scenario ─────────────────────────────────────
SENSOR_TRENDS = {
    "healthy":  {"adh":"stable","od":"stable","nh4":"stable","tox":"stable",
                 "ph":"stable","temp":"stable","dbo5":"stable","dqo":"stable","caudal":"stable"},
    "stressed": {"adh":"down","od":"down","nh4":"up","tox":"up",
                 "ph":"down","temp":"stable","dbo5":"up","dqo":"up","caudal":"up"},
    "critical": {"adh":"down","od":"down","nh4":"up","tox":"up",
                 "ph":"down","temp":"stable","dbo5":"up","dqo":"up","caudal":"up"},
}

# ── Recommendations (rich, referencing EcoSentinel and Vibrio) ────────────────
RECOMMENDATIONS = {
    "healthy": [
        {"priority": "info",
         "action": "Mantener aireación en parámetros actuales",
         "impact": "Eficiencia operativa óptima sostenida",
         "timeframe": "Continuo",
         "signal": "BHI"},
        {"priority": "info",
         "action": "EcoSentinel confirma comunidad estable — continuar monitoreo estándar",
         "impact": "Detección temprana de cambios en la comunidad microbiana",
         "timeframe": "Diario",
         "signal": "EcoSentinel"},
        {"priority": "low",
         "action": "Programar próxima calibración del sensor Vibrio Sentinel",
         "impact": "Garantiza precisión en la detección de compuestos inhibitorios",
         "timeframe": "En 3 días",
         "signal": "Vibrio"},
    ],
    "stressed": [
        {"priority": "high",
         "action": "Aumentar aireación 15–20% — EcoSentinel detecta flagelados elevados (38%) por OD bajo",
         "impact": "Recuperación de OD en 4–6 h; reduce flagelados libre-natantes",
         "timeframe": "Inmediato",
         "signal": "EcoSentinel + OD"},
        {"priority": "high",
         "action": "Monitorear NH₄⁺ cada 2 h — supera umbral regulatorio Decreto 674/89",
         "impact": "Seguimiento de tendencia crítica; prevención de incumplimiento normativo",
         "timeframe": "Próximas 12 h",
         "signal": "NH₄⁺ / Normativa"},
        {"priority": "high",
         "action": "Vibrio Sentinel reporta 35% inhibición — investigar fuente tóxica en línea de producción",
         "impact": "Identifica compuestos inhibitorios antes del colapso biológico",
         "timeframe": "Próximas 4 h",
         "signal": "Vibrio"},
        {"priority": "medium",
         "action": "Reducir carga orgánica 10% — flóculos dispersos confirman estrés estructural",
         "impact": "Estabiliza estructura de flóculo y reduce estrés metabólico",
         "timeframe": "Próximas 6 h",
         "signal": "EcoSentinel"},
        {"priority": "low",
         "action": "Verificar y ajustar pH del reactor (6.8–7.2)",
         "impact": "Condiciones óptimas para actividad deshidrogenasa",
         "timeframe": "Hoy",
         "signal": "pH"},
    ],
    "critical": [
        {"priority": "critical",
         "action": "REDUCIR carga orgánica 30–40% YA — EcoSentinel: 35% filamentosas, riesgo de bulking inminente",
         "impact": "Previene colapso biológico total y pérdida masiva de biomasa",
         "timeframe": "INMEDIATO",
         "signal": "EcoSentinel"},
        {"priority": "critical",
         "action": "Vibrio: inhibición 68% — activar pretratamiento de emergencia y aislar fuentes tóxicas",
         "impact": "Reduce toxicidad antes del colapso definitivo de la biomasa activa",
         "timeframe": "INMEDIATO",
         "signal": "Vibrio"},
        {"priority": "high",
         "action": "Elevar aireación al máximo — OD crítico (0.9 mg/L), ciliados en mínimo histórico (8%)",
         "impact": "Recuperación de OD; favorece supervivencia de ciliados beneficiosos",
         "timeframe": "Inmediato",
         "signal": "OD + EcoSentinel"},
        {"priority": "high",
         "action": "Notificar responsable ambiental — NH₄⁺ 130 mg/L supera límite Decreto 674/89 (35 mg/L)",
         "impact": "Gestión regulatoria preventiva; documentación de emergencia",
         "timeframe": "Próxima hora",
         "signal": "Normativa"},
        {"priority": "medium",
         "action": "Preparar evidencia regulatoria y plan de contingencia (Decreto 674/89)",
         "impact": "Reduce riesgo de sanción administrativa y clausura operativa",
         "timeframe": "Próximas 4 h",
         "signal": "Cumplimiento"},
    ],
}

# ── AI model loading ──────────────────────────────────────────────────────────
_MODEL_DIR  = Path(__file__).parent
_MODEL_PATH = _MODEL_DIR / "model_compliance.pkl"
_META_PATH  = _MODEL_DIR / "model_metadata.json"

rf_model   = None
model_meta = {}

if _JOBLIB and _MODEL_PATH.exists():
    try:
        rf_model = joblib.load(_MODEL_PATH)
        if _META_PATH.exists():
            with open(_META_PATH, encoding="utf-8") as _f:
                model_meta = json.load(_f)
    except Exception:
        rf_model = None


# ── Helpers ───────────────────────────────────────────────────────────────────
def calculate_bhi(adh, do_sat, nh4_norm, tox_norm):
    return 0.25 * (adh + do_sat + (100 - nh4_norm) + (100 - tox_norm))

def get_status(bhi):
    if bhi >= 75:  return "green"
    if bhi >= 50:  return "yellow"
    return "red"

def get_compliance_risk(bhi):
    base = 8 if bhi >= 75 else (42 if bhi >= 50 else 78)
    return round(min(98, max(2, base + random.uniform(-4, 4))), 1)

def jitter(value, spread=3.0):
    return round(min(100, max(0, value + random.uniform(-spread, spread))), 1)

def jitter_phys(value, spread, lo=0.0, hi=1e9):
    return round(min(hi, max(lo, value + random.uniform(-spread, spread))), 3)

def _jitter_ecosentinel(base_score, base_pcts):
    score = round(min(100, max(0, base_score + random.uniform(-3, 3))), 1)
    pcts = {k: round(min(100, max(0, v + random.uniform(-3, 3))), 1) for k, v in base_pcts.items()}
    return score, pcts

def get_vibrio_timing(frequency_hours: int = 4) -> dict:
    """Compute scheduling metadata for the Vibrio batch assay."""
    now = datetime.now()
    period_h = (now.hour // frequency_hours) * frequency_hours
    last = now.replace(hour=period_h, minute=15, second=0, microsecond=0)
    if last > now:
        last -= timedelta(hours=frequency_hours)
    elapsed_min = int((now - last).total_seconds() / 60)
    next_s = last + timedelta(hours=frequency_hours)
    until_min = max(0, int((next_s - now).total_seconds() / 60))
    period_pct = elapsed_min / (frequency_hours * 60)
    freshness = "vigente" if period_pct < 0.8 else ("pendiente" if period_pct <= 1.0 else "vencido")
    def fmt_min(m):
        return f"hace {m // 60}h {m % 60}min" if m >= 60 else f"hace {m} min"
    def fmt_until(m):
        return f"en {m // 60}h {m % 60}min" if m >= 60 else f"en {m} min"
    return {
        "sample_time":     last.strftime("%d/%m/%Y — %H:%M hs"),
        "sample_elapsed":  fmt_min(elapsed_min),
        "next_sample_time": next_s.strftime("%H:%M hs"),
        "next_sample_in":  fmt_until(until_min),
        "frequency":       f"cada {frequency_hours} horas",
        "freshness_status": freshness,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/api/scenarios")
def list_scenarios():
    return [{"id": k, "name": v["name"], "description": v["description"]}
            for k, v in SCENARIOS.items()]


@app.get("/api/current/{scenario}")
def get_current(scenario: str):
    if scenario not in SCENARIOS:
        scenario = "healthy"
    s   = SCENARIOS[scenario]
    ec  = ECOSENTINEL[scenario]
    vib = VIBRIO[scenario]
    tr  = SENSOR_TRENDS[scenario]

    # BHI sensor percentages
    adh    = jitter(s["adh"])
    do_sat = jitter(s["do_sat"])
    nh4    = jitter(s["nh4_norm"])
    tox    = jitter(s["tox_norm"])
    bhi    = round(calculate_bhi(adh, do_sat, nh4, tox), 1)
    status = get_status(bhi)
    risk   = get_compliance_risk(bhi)

    # Physical unit conversions
    do_mgl     = round(do_sat * 0.092, 2)
    nh4_mgl    = round(nh4 * 0.45, 2)
    adh_ugTTF  = round(adh * 0.052, 2)     # re-scaled to realistic range (μg TTF/gVSS·h)
    ph         = jitter_phys(s["ph"],   0.12, 4.5, 9.5)
    temp       = jitter_phys(s["temp"], 1.5,  5.0, 45.0)
    caudal     = jitter_phys(s["caudal"], 2.5, 1.0, 100.0)
    dbo5       = jitter_phys(s["dbo5"],   s["dbo5"] * 0.06, 5.0, 800.0)
    dqo        = round(dbo5 * jitter_phys(s["dqo_ratio"], 0.08, 1.2, 3.5), 1)

    # EcoSentinel with jitter
    eco_score, eco_pcts = _jitter_ecosentinel(
        ec["score"],
        {k: ec[k]["pct"] for k in ["ciliados","flagelados","amebas","filamentosas"]}
    )
    # Vibrio — batch measurement, value stable per scheduled period (no jitter)
    vib_lum  = vib["luminescence_pct"]
    vib_inh  = vib["inhibition_pct"]
    vib_timing = get_vibrio_timing(frequency_hours=4)

    return {
        "bhi": bhi, "status": status,
        "scenario": scenario, "scenario_name": s["name"],
        "compliance_risk": risk,
        "sensors": {
            # Percentage-based (for BHI components)
            "adh": adh, "do_sat": do_sat, "nh4": nh4, "toxicity": tox,
            # Physical units for display
            "adh_unit": adh_ugTTF, "adh_unit_label": "μg TTF/h",
            "do_mgl": do_mgl,
            "nh4_mgl": nh4_mgl,
            "ph": round(ph, 2),
            "temperatura": round(temp, 1),
            "dbo5_mgl": round(dbo5, 1),
            "dqo_mgl": dqo,
            "caudal_m3h": round(caudal, 1),
            # Trends
            "trends": tr,
        },
        "ecosentinel": {
            "score": eco_score,
            "ciliados":     {**ec["ciliados"],     "pct": eco_pcts["ciliados"]},
            "flagelados":   {**ec["flagelados"],   "pct": eco_pcts["flagelados"]},
            "amebas":       {**ec["amebas"],       "pct": eco_pcts["amebas"]},
            "filamentosas": {**ec["filamentosas"], "pct": eco_pcts["filamentosas"]},
            "floculos":        ec["floculos"],
            "floculos_status": ec["floculos_status"],
            "interpretation":  ec["interpretation"],
        },
        "vibrio": {
            "luminescence_pct": vib_lum,
            "inhibition_pct":   vib_inh,
            "status":           vib["status"],
            "interpretation":   vib["interpretation"],
            **vib_timing,
        },
        "recommendations": RECOMMENDATIONS[scenario],
        "timestamp": datetime.now().isoformat(),
    }


# ── AI feature metadata ───────────────────────────────────────────────────────
_FEAT_META = {
    "adh_ugTTF_gVSS_h": {"label":"ADH",         "unit":"μg TTF/h","good":"up",    "warn":1.5, "crit":0.8},
    "od_mgl":            {"label":"OD",           "unit":"mg/L",   "good":"up",    "warn":4.0, "crit":1.5},
    "nh4_mgl":           {"label":"NH₄⁺",         "unit":"mg/L",   "good":"down",  "warn":25.0,"crit":50.0},
    "toxicity_pct":      {"label":"Toxicidad",    "unit":"%",      "good":"down",  "warn":20.0,"crit":50.0},
    "ph":                {"label":"pH",           "unit":"",       "good":"range", "opt_lo":6.8,"opt_hi":7.5},
    "temperatura_c":     {"label":"Temperatura",  "unit":"°C",     "good":"range", "opt_lo":18.0,"opt_hi":32.0},
    "caudal_m3h":        {"label":"Caudal",       "unit":"m³/h",   "good":"down",  "warn":28.0,"crit":45.0},
}
_STATUS_LABELS = {
    "up":   {"normal":"✓ normal","warning":"↓ bajo",  "critical":"↓ crítico"},
    "down": {"normal":"✓ normal","warning":"↑ alto",  "critical":"↑ crítico"},
    "range":{"normal":"✓ normal","warning":"~ desvío","critical":"⚠ extremo"},
}

def _feature_status(key, value):
    meta = _FEAT_META[key]
    if meta["good"] == "up":
        if value >= meta["warn"]:  return "normal",  "ok"
        if value >= meta["crit"]:  return "warning", "down"
        return "critical", "down"
    if meta["good"] == "down":
        if value <= meta["warn"]:  return "normal",  "ok"
        if value <= meta["crit"]:  return "warning", "up"
        return "critical", "up"
    lo, hi = meta["opt_lo"], meta["opt_hi"]
    if lo <= value <= hi:                       return "normal",   "ok"
    if value < lo - 2 or value > hi + 3:        return "critical", ("down" if value < lo else "up")
    return "warning", ("down" if value < lo else "up")

def _build_drivers(values):
    fi = model_meta.get("feature_importances", {})
    drivers = []
    for key in _FEAT_META:
        v = values[key]
        meta = _FEAT_META[key]
        status, direction = _feature_status(key, v)
        imp = fi.get(key, 0.0)
        drivers.append({
            "key": key, "label": meta["label"], "value": round(v,2), "unit": meta["unit"],
            "status": status, "direction": direction,
            "direction_label": _STATUS_LABELS[meta["good"]][status],
            "importance": round(imp,4), "importance_pct": round(imp*100,1),
        })
    drivers.sort(key=lambda d: d["importance"], reverse=True)
    return drivers


@app.get("/api/ai/predict/{scenario}")
def ai_predict(scenario: str):
    if scenario not in SCENARIOS:
        scenario = "healthy"
    s = SCENARIOS[scenario]

    adh    = jitter_phys(s["adh_phy"], s["adh_phy"]*0.12, 0.02, 5.0)
    od     = jitter_phys(s["od_phy"],  0.35,               0.05, 9.5)
    nh4    = jitter_phys(s["nh4_phy"], s["nh4_phy"]*0.07,  0.5, 220.0)
    tox    = jitter_phys(s["tox_norm"],2.5,                 0.0,  99.0)
    ph     = jitter_phys(s["ph"],      0.12,                4.5,   9.5)
    temp   = jitter_phys(s["temp"],    2.5,                 5.0,  40.0)
    caudal = jitter_phys(s["caudal"],  3.0,                 1.0, 100.0)

    feat_values = {
        "adh_ugTTF_gVSS_h": adh, "od_mgl": od, "nh4_mgl": nh4,
        "toxicity_pct": tox, "ph": ph, "temperatura_c": temp, "caudal_m3h": caudal,
    }

    ai_ready = rf_model is not None
    if ai_ready:
        X = [[feat_values[k] for k in
              ["adh_ugTTF_gVSS_h","od_mgl","nh4_mgl","toxicity_pct","ph","temperatura_c","caudal_m3h"]]]
        proba = float(rf_model.predict_proba(X)[0][1])
        risk_pct = round(proba * 100)
        prediction = "non_compliant" if proba >= 0.5 else "compliant"
    else:
        fallback = {"healthy": 12, "stressed": 55, "critical": 88}
        risk_pct = fallback.get(scenario, 12) + int(random.uniform(-4, 4))
        proba = risk_pct / 100
        prediction = "non_compliant" if risk_pct >= 50 else "compliant"

    metrics = model_meta.get("metrics", {"accuracy": 0.0, "recall": 0.0})
    fi_sorted = model_meta.get("feature_importances_sorted", [])

    return {
        "ai_ready": ai_ready, "scenario": scenario,
        "risk_pct": risk_pct, "non_compliant_probability": round(proba, 4),
        "prediction": prediction,
        "feature_drivers": _build_drivers(feat_values),
        "feature_importances_sorted": fi_sorted,
        "model_metrics": metrics,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/history/{scenario}")
def get_history(scenario: str, hours: int = 24):
    if scenario not in SCENARIOS:
        scenario = "healthy"
    s   = SCENARIOS[scenario]
    ec  = ECOSENTINEL[scenario]
    vib = VIBRIO[scenario]
    now = datetime.now()
    data = []

    # Start-state baselines (healthy scenario values)
    ST = {"adh":94,"do":91,"nh4":7,"tox":4,"eco":88,
          "ph":7.15,"temp":22.0,"dbo5":32.0,"caudal":18.0,"vib_inh":6.0}

    for i in range(hours, 0, -1):
        t = now - timedelta(hours=i)
        progress = 1 - (i / hours)

        def interp_jit(start, end, spread, lo=None, hi=None):
            v = start + (end - start) * progress
            v = v + random.uniform(-spread, spread)
            if lo is not None: v = max(lo, v)
            if hi is not None: v = min(hi, v)
            return v

        if scenario == "healthy":
            adh    = jitter(s["adh"], 5)
            do_sat = jitter(s["do_sat"], 5)
            nh4    = jitter(s["nh4_norm"], 3)
            tox    = jitter(s["tox_norm"], 2)
            eco    = jitter(ec["score"], 4)
            ph_v   = jitter_phys(ST["ph"],     0.06, 4.5, 9.5)
            temp_v = jitter_phys(ST["temp"],   0.5,  5.0, 45.0)
            dbo5_v = jitter_phys(ST["dbo5"],   2.0,  5.0, 800.0)
            cau_v  = jitter_phys(ST["caudal"], 1.0,  1.0, 100.0)
            vib_v  = jitter_phys(ST["vib_inh"],1.0,  0.0, 100.0)
        else:
            adh    = jitter(interp_jit(ST["adh"],  s["adh"],       3), 0)
            do_sat = jitter(interp_jit(ST["do"],   s["do_sat"],    3), 0)
            nh4    = jitter(interp_jit(ST["nh4"],  s["nh4_norm"],  2), 0)
            tox    = jitter(interp_jit(ST["tox"],  s["tox_norm"],  2), 0)
            eco    = jitter(interp_jit(ST["eco"],  ec["score"],    3), 0)
            ph_v   = round(interp_jit(ST["ph"],    s["ph"],        0.06, 4.5, 9.5), 2)
            temp_v = round(interp_jit(ST["temp"],  s["temp"],      0.5,  5.0, 45.0), 1)
            dbo5_v = round(interp_jit(ST["dbo5"],  s["dbo5"],      s["dbo5"]*0.04, 5.0, 800.0), 1)
            cau_v  = round(interp_jit(ST["caudal"],s["caudal"],    1.5, 1.0, 100.0), 1)
            vib_v  = round(interp_jit(ST["vib_inh"],vib["inhibition_pct"], 1.5, 0.0, 100.0), 1)

        dqo_v  = round(dbo5_v * jitter_phys(s["dqo_ratio"], 0.06, 1.2, 3.5), 1)
        bhi = round(calculate_bhi(adh, do_sat, nh4, tox), 1)
        data.append({
            "time":              t.strftime("%H:%M"),
            "bhi":               bhi,
            "ecosentinel_score": round(min(100, max(0, eco)), 1),
            "adh":               adh,
            "do_sat":            do_sat,
            "nh4":               nh4,
            "toxicity":          tox,
            "compliance_risk":   get_compliance_risk(bhi),
            "vibrio_inhibition": vib_v,
            "ph":                ph_v,
            "temperatura":       temp_v,
            "dbo5":              dbo5_v,
            "dqo":               dqo_v,
            "caudal":            cau_v,
        })
    return data
