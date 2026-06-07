"""
Train Random Forest for effluent non-compliance prediction.

Target   : non_compliant = 1  if DBO5 > 50 mg/L  OR  NH4+ > 35 mg/L
Features : ADH, OD, NH4+, Toxicidad, pH, Temperatura, Caudal
Output   : model_compliance.pkl  +  model_metadata.json
"""
import sys, os, json, csv

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

FEATURES = [
    'adh_ugTTF_gVSS_h',
    'od_mgl',
    'nh4_mgl',
    'toxicity_pct',
    'ph',
    'temperatura_c',
    'caudal_m3h',
]

DATASET_PATH = os.path.join(os.path.dirname(__file__), '..', 'dataset_biomeat.csv')
MODEL_PATH   = os.path.join(os.path.dirname(__file__), 'model_compliance.pkl')
META_PATH    = os.path.join(os.path.dirname(__file__), 'model_metadata.json')

# ── Load ──────────────────────────────────────────────────────────────────────
print(f"Cargando dataset: {DATASET_PATH}")
X, y = [], []
with open(DATASET_PATH, newline='', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        X.append([float(row[feat]) for feat in FEATURES])
        dbo_ok = int(row['decreto_674_dbo_compliant'])
        nh4_ok = int(row['decreto_674_nh4_compliant'])
        y.append(0 if (dbo_ok and nh4_ok) else 1)   # 1 = no cumple

n_total = len(y)
n_pos   = sum(y)
n_neg   = n_total - n_pos
print(f"\nDataset: {n_total} observaciones")
print(f"  Cumple     (0): {n_neg:5d}  ({n_neg/n_total*100:.1f}%)")
print(f"  No cumple  (1): {n_pos:5d}  ({n_pos/n_total*100:.1f}%)")

# ── Split 80/20 estratificado ─────────────────────────────────────────────────
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, recall_score, precision_score,
                              f1_score, confusion_matrix)

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)
print(f"\nEntrenamiento: {len(X_train)} | Prueba: {len(X_test)}")

# ── Entrenar ──────────────────────────────────────────────────────────────────
print("\nEntrenando Random Forest (100 árboles, class_weight='balanced')...")
rf = RandomForestClassifier(
    n_estimators=100,
    min_samples_split=4,
    class_weight='balanced',
    random_state=42,
    n_jobs=-1,
)
rf.fit(X_train, y_train)
print("  Listo.")

# ── Evaluar ───────────────────────────────────────────────────────────────────
y_pred = rf.predict(X_test)
acc    = accuracy_score(y_test, y_pred)
rec    = recall_score(y_test, y_pred)
prec   = precision_score(y_test, y_pred)
f1     = f1_score(y_test, y_pred)
cm     = confusion_matrix(y_test, y_pred)

print("\n" + "═"*52)
print("  EVALUACION DEL MODELO")
print("═"*52)
print(f"  Accuracy  : {acc*100:5.1f}%")
print(f"  Recall    : {rec*100:5.1f}%   <- metrica clave")
print(f"  Precision : {prec*100:5.1f}%")
print(f"  F1-Score  : {f1*100:5.1f}%")

print("\n  Matriz de Confusion:")
print(f"  {'':20s}  Pred:Cumple  Pred:NoC")
print(f"  Real: Cumple       TN={cm[0][0]:5d}    FP={cm[0][1]:4d}")
print(f"  Real: No cumple    FN={cm[1][0]:5d}    TP={cm[1][1]:4d}")
print(f"\n  FN={cm[1][0]}: incumplimientos reales NO detectados (costo alto)")
print(f"  FP={cm[0][1]}: falsas alarmas (costo bajo: precaucion innecesaria)")

# ── Importancia de variables ──────────────────────────────────────────────────
feat_imp = sorted(
    zip(FEATURES, rf.feature_importances_),
    key=lambda x: x[1], reverse=True
)
print("\n  Importancia de Variables:")
for feat, imp in feat_imp:
    bar = chr(9608) * int(imp * 40)
    print(f"  {feat:25s} {imp:.4f}  {bar}")

# ── Por que el Recall es la metrica clave ─────────────────────────────────────
print("\n" + "═"*52)
print("  POR QUE EL RECALL ES LA METRICA CLAVE")
print("═"*52)
print("""
  Los costos de error son asimetricos en monitoreo ambiental:

  Falso Negativo (FN): la IA NO detecta un incumplimiento real.
    -> La planta opera sin correccion.
    -> Consecuencia: supera DBO5 <= 50 mg/L (Decreto 674/89).
    -> Impacto: multa, clausura temporal, dano ambiental irreversible.

  Falso Positivo (FP): la IA alerta pero el efluente si cumple.
    -> El operador toma precauciones innecesarias.
    -> Impacto: pequeno costo operativo (aireacion extra, carga reducida).

  Recall = TP / (TP + FN)
  Un Recall alto (>90%) garantiza que casi ningun evento de riesgo
  pase sin deteccion. Es preferible tener alguna alarma extra (FP)
  que perder un incumplimiento real (FN).
""")

# ── Guardar modelo ────────────────────────────────────────────────────────────
import joblib

joblib.dump(rf, MODEL_PATH)
print(f"Modelo guardado  : {MODEL_PATH}")

meta = {
    'features': FEATURES,
    'feature_importances': {f: round(float(v), 6) for f, v in feat_imp},
    'feature_importances_sorted': [
        {'key': f, 'importance': round(float(v), 6), 'importance_pct': round(float(v)*100, 1)}
        for f, v in feat_imp
    ],
    'metrics': {
        'accuracy':  round(float(acc),  4),
        'recall':    round(float(rec),  4),
        'precision': round(float(prec), 4),
        'f1':        round(float(f1),   4),
    },
    'confusion_matrix': cm.tolist(),
    'n_train': len(X_train),
    'n_test':  len(X_test),
    'n_estimators': 100,
    'target': 'non_compliant (DBO5>50 OR NH4+>35)',
}
with open(META_PATH, 'w', encoding='utf-8') as f:
    json.dump(meta, f, indent=2, ensure_ascii=False)
print(f"Metadata guardada: {META_PATH}")
