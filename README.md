# Biovant — Plataforma de Inteligencia Biológica Predictiva

Sistema de monitoreo inteligente para plantas de tratamiento de efluentes en la industria frigorífica. Combina sensores biológicos en tiempo real, microscopía digital automatizada, y un modelo predictivo (Random Forest) para anticipar incumplimientos regulatorios antes de que ocurran.

---

## Propuesta de valor

Las plantas de tratamiento de efluentes frigoríficos enfrentan multas, clausuras y daño ambiental cuando la biomasa colapsa sin aviso. Biovant detecta las señales tempranas del deterioro biológico y predice el riesgo de incumplimiento regulatorio con 24–48 horas de anticipación, permitiendo intervenciones preventivas en lugar de correctivas.

**Diferenciadores:**
- **EcoSentinel™** — análisis de comunidad microbiana via microscopía digital (Madoni Sludge Biotic Index, 1994)
- **Vibrio Sentinel™** — ensayo de toxicidad por bioluminiscencia *V. fischeri* (ISO 11348 / Microtox-equivalente)
- **BHI (Biomass Health Index)** — índice unificado 0–100 que integra actividad deshidrogenasa, OD, amonio y toxicidad
- **Cumplimiento normativo multi-marco** — Decreto 674/89, Res. ADA PBA, límites internos y exportación UE/Halal
- **Patrones históricos por planta** — el modelo aprende de los eventos críticos de cada instalación específica

---

## Tecnologías

| Capa | Stack |
|---|---|
| Frontend | React 18 (CDN, sin build step), Babel Standalone, SVG charts custom |
| Backend | FastAPI, Uvicorn, Python 3.11 |
| ML | scikit-learn — Random Forest (100 árboles, class_weight='balanced', Recall ≥ 90%) |
| Datos | pandas, joblib |
| Deploy Frontend | GitHub Pages |
| Deploy Backend | Render |

---

## Correr localmente

### Requisitos
- Python 3.9+
- pip

### Backend

```bash
cd backend
pip install -r requirements.txt
python train_model.py        # entrena el modelo (genera model_compliance.pkl)
uvicorn main:app --reload    # inicia en http://localhost:8000
```

### Frontend

Abrir directamente en el navegador:

```
frontend/index.html
```

O acceder vía el backend (que sirve el frontend en `GET /`):

```
http://localhost:8000
```

> El frontend detecta automáticamente si está corriendo en local y usa `http://localhost:8000`. En producción usa la URL de Render.

---

## Despliegue

### Backend — Render

1. Crear una cuenta en [render.com](https://render.com)
2. **New Web Service** → conectar el repo `vsaintignan/biovant-yhat`
3. Render detecta `render.yaml` automáticamente y configura:
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Hacer deploy — la URL del servicio será: `https://biovant-yhat.onrender.com`

> **Nota:** el plan gratuito de Render puede tardar ~30 segundos en responder la primera request (cold start). Esto es normal.

### Frontend — GitHub Pages

1. Ir a **Settings → Pages** en el repo `vsaintignan/biovant-yhat`
2. **Source:** Deploy from a branch
3. **Branch:** `main` · **Folder:** `/frontend`
4. Guardar — GitHub Pages publicará en: `https://vsaintignan.github.io/biovant-yhat/`

---

## Links

| Recurso | URL |
|---|---|
| Frontend (GitHub Pages) | https://vsaintignan.github.io/biovant-yhat/ |
| Backend API (Render) | https://biovant-yhat.onrender.com |
| Documentación API (Swagger) | https://biovant-yhat.onrender.com/docs |

---

## Escenarios de demostración

El dashboard incluye tres escenarios predefinidos para evaluación:

| Escenario | BHI | Descripción |
|---|---|---|
| Operación Normal | ~89 | Biomasa estable, todos los indicadores en rango |
| Biomasa Bajo Estrés | ~55 | Señales tempranas de deterioro, flagelados elevados |
| Riesgo de Falla | ~22 | Filamentosas dominantes, Vibrio en alerta crítica |

---

## Normativa aplicada

- **Decreto 674/89** — DBO₅ ≤ 50 mg/L · NH₄⁺ ≤ 35 mg/L · SST ≤ 35 mg/L
- **Res. ADA PBA** — DBO₅ ≤ 45 mg/L · DQO ≤ 200 mg/L · pH 6.5–9.5
- **Madoni Sludge Biotic Index (1994)** — interpretación de comunidad microbiana
- **ISO 11348** — ensayo de inhibición de bioluminiscencia *Vibrio fischeri*
