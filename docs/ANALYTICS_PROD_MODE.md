# Analytics PROD_MODE Configuration Summary

## ✅ Was bereits funktioniert

### Backend (api/app.py)
```python
# Zeile 48-49
analytics_file = Path(__file__).parent.parent / Config.DATA_DIR / "app_analytics.json"
analytics = analytics_module.AnalyticsAggregator(analytics_file)
```

Das Backend verwendet bereits `Config.DATA_DIR`, welches automatisch gesetzt wird:

**Config.py Zeile 37:**
```python
DATA_DIR = "Data" if PROD_MODE else "TestData"
```

**Verhalten:**
- ✅ `PROD_MODE=true` → schreibt nach `Data/app_analytics.json`
- ✅ `PROD_MODE=false` → schreibt nach `TestData/app_analytics.json`

---

## ✅ Was jetzt auch funktioniert

### Dashboard Server (view_analytics.py)
**Neu hinzugefügt:**
- Lädt `.env` Datei beim Start
- Liest `PROD_MODE` aus Environment
- Zeigt aktuellen Modus beim Start an:

```
📊 HazeBot Analytics Dashboard Server
============================================================
🔧 Mode: PRODUCTION
📂 Data Directory: Data/
✅ Server started on 0.0.0.0:8082
```

### Dashboard Frontend (analytics_dashboard.html)
**Neu hinzugefügt:**
- Versucht zuerst `Data/app_analytics.json` zu laden (Production)
- Fällt zurück auf `TestData/app_analytics.json` (Development)
- Zeigt Quelle im "Last Update" an: `(Source: Data/)`

**Auto-Detection:**
```javascript
// Versucht Data/ (Production) zuerst
try {
    const response = await fetch('../Data/app_analytics.json');
    if (response.ok) {
        data = await response.json();
        console.log('📊 Loaded from Data/ (PRODUCTION mode)');
    }
} catch (e) {
    // Fallback zu TestData/ (Development)
    const response = await fetch('../TestData/app_analytics.json');
    console.log('📊 Loaded from TestData/ (DEVELOPMENT mode)');
}
```

---

## 🔍 Wie es funktioniert

### Daten-Flow

```
.env Datei
  ↓
PROD_MODE=true
  ↓
Config.DATA_DIR = "Data"
  ↓
api/app.py → analytics_file = "Data/app_analytics.json"
  ↓
Analytics schreibt nach Data/app_analytics.json
  ↓
Dashboard lädt aus Data/app_analytics.json
```

### Dateien die PROD_MODE respektieren

| Datei | Was sie macht | Wie |
|-------|--------------|-----|
| `Config.py` | Setzt `DATA_DIR` basierend auf `PROD_MODE` | `DATA_DIR = "Data" if PROD_MODE else "TestData"` |
| `api/app.py` | Initialisiert Analytics mit korrektem Pfad | `analytics_file = Config.DATA_DIR / "app_analytics.json"` |
| `api/analytics.py` | Schreibt Analytics-Daten | Verwendet übergebenen `analytics_file` Path |
| `view_analytics.py` | Zeigt Modus beim Start an | Lädt `.env` und zeigt `DATA_DIR` |
| `analytics_dashboard.html` | Lädt Daten von korrektem Ort | Versucht `Data/` zuerst, dann `TestData/` |

---

## 📝 Alle Dateien die PROD_MODE respektieren

Aus `Config.py`:

```python
# Core
DATA_DIR = "Data" if PROD_MODE else "TestData"

# Files die DATA_DIR verwenden:
PERSISTENT_VIEWS_FILE = f"{DATA_DIR}/persistent_views.json"
ACTIVE_RULES_VIEWS_FILE = f"{DATA_DIR}/active_rules_views.json"
RL_ACCOUNTS_FILE = f"{DATA_DIR}/rl_accounts.json"
RL_CONGRATS_VIEWS_FILE = f"{DATA_DIR}/rl_congrats_views.json"
MEME_SUBREDDITS_FILE = f"{DATA_DIR}/meme_subreddits.json"
MEME_LEMMY_FILE = f"{DATA_DIR}/meme_lemmy_communities.json"
MEME_TEMPLATES_CACHE_FILE = f"{DATA_DIR}/meme_templates.json"
MOD_DATA_FILE = f"{DATA_DIR}/mod_data.json"
ACTIVITY_FILE = f"{DATA_DIR}/activity.json"

# Und jetzt auch:
app_analytics.json  # via api/app.py
```

---

## ✅ Testing

### Test 1: Produktions-Modus
```bash
# .env
PROD_MODE=true

# Server starten
cd /path/to/HazeBot
python3 analytics/view_analytics.py --host 0.0.0.0 --port 8082 --no-browser

# Erwartete Ausgabe:
# 🔧 Mode: PRODUCTION
# 📂 Data Directory: Data/
```

Dashboard öffnen → sollte `(Source: Data/)` zeigen

### Test 2: Development-Modus
```bash
# .env
PROD_MODE=false

# Server starten
python3 analytics/view_analytics.py --host 0.0.0.0 --port 8082 --no-browser

# Erwartete Ausgabe:
# 🔧 Mode: DEVELOPMENT
# 📂 Data Directory: TestData/
```

Dashboard öffnen → sollte `(Source: TestData/)` zeigen

---

## 🚀 Deployment

Auf deinem Production Server:

```bash
# 1. Sicherstellen dass PROD_MODE=true in .env
grep PROD_MODE .env
# Sollte zeigen: PROD_MODE=true

# 2. Analytics Server starten
python3 analytics/view_analytics.py --host 0.0.0.0 --port 8082 --no-browser

# 3. Überprüfen
# Sollte zeigen: "Mode: PRODUCTION" und "Data Directory: Data/"
```

Dashboard öffnen auf: `https://analytics-hazebot-admin.hzwd.xyz/`

---

## 📊 Console Output beim Start

**Production:**
```
============================================================
📊 HazeBot Analytics Dashboard Server
============================================================

🔧 Mode: PRODUCTION
📂 Data Directory: Data/
✅ Server started on 0.0.0.0:8082
🌐 Dashboard URL: http://0.0.0.0:8082/analytics/analytics_dashboard.html

Press Ctrl+C to stop the server
```

**Development:**
```
============================================================
📊 HazeBot Analytics Dashboard Server
============================================================

🔧 Mode: DEVELOPMENT
📂 Data Directory: TestData/
✅ Server started on localhost:8082
🌐 Dashboard URL: http://localhost:8082/analytics/analytics_dashboard.html

Press Ctrl+C to stop the server
```

---

## 🔒 Sicherheit

Das Analytics-Dashboard lädt Daten basierend auf dem Server-Status:
- ✅ Wenn `Data/app_analytics.json` existiert → verwendet Production-Daten
- ✅ Wenn nicht → fällt zurück auf `TestData/app_analytics.json`

**Wichtig:** Das Dashboard respektiert den Server-Status, nicht die Client-Umgebung!

