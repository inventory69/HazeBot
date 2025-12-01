# Cloudflare Tunnel Configuration für HazeBot API

## QUICK START - Dashboard Configuration

> **TL;DR**: Konfiguration läuft komplett über das Cloudflare Dashboard.
> Keine YAML-Dateien nötig! 🎉

### 🎯 Dein Setup:
- **API Backend (Flask)**:    `http://192.168.0.188:5070`  → `/api`
- **Frontend (Flutter Web)**: `http://192.168.0.188:8080`  → `*` (catch-all)
- **Domain**:                 `test-hazebot-admin.hzwd.xyz`

### ⚡ Schnell-Konfiguration (5 Minuten):
1. ✅ Prüfe Route-Reihenfolge: `/api` MUSS über `*` stehen
2. ✅ Optimiere Route 1 (`/api`): Keep-alive 90s, Connections 100
3. ✅ Optimiere Route 2 (`*`): Keep-alive 60s, Connections 50
4. ✅ Aktiviere "No TLS Verify" für beide Routes (LAN IP!)
5. ✅ Teste: `curl https://test-hazebot-admin.hzwd.xyz/api/health`

### 1. Services starten:
```bash
# Terminal 1: Flask API starten
cd /home/liq/gitProjects/HazeBot
python start_with_api.py
# → Läuft auf http://192.168.0.188:5070

# Terminal 2: Flutter Web Server starten
cd /home/liq/gitProjects/HazeBot-Admin/build/web
python3 spa_server.py
# → Läuft auf http://192.168.0.188:8080
```

### 2. Cloudflare Dashboard öffnen:
```
1. Gehe zu: https://one.dash.cloudflare.com/
2. Wähle dein Team/Account
3. Navigation: Networks → Tunnels
4. Klicke auf deinen Tunnel
5. Tab: "Public Hostname"
```

### 3. Bestehende Routes prüfen:

**Checkliste - Was du sehen solltest:**

✅ **Route 1 (API)**
- Position: OBEN (Nummer 1)
- Subdomain/Domain: `test-hazebot-admin.hzwd.xyz`
- Path: `/api`
- Service: `http://192.168.0.188:5070`
- Origin configurations: 0 (oder mehr nach Optimierung)

✅ **Route 2 (Frontend)**
- Position: UNTEN (Nummer 2)
- Subdomain/Domain: `test-hazebot-admin.hzwd.xyz`
- Path: `*`
- Service: `http://192.168.0.188:8080`
- Origin configurations: 0 (oder mehr nach Optimierung)

**KRITISCH**: Route 1 (`/api`) MUSS über Route 2 (`*`) stehen!

❌ **FALSCH** (wenn so, dann umordnen):
```
1. test-hazebot-admin.hzwd.xyz  *     http://192.168.0.188:8080
2. test-hazebot-admin.hzwd.xyz  /api  http://192.168.0.188:5070
```

✅ **RICHTIG**:
```
1. test-hazebot-admin.hzwd.xyz  /api  http://192.168.0.188:5070
2. test-hazebot-admin.hzwd.xyz  *     http://192.168.0.188:8080
```

### 4. Route-Reihenfolge ändern (falls nötig):
```
Wenn /api UNTER * steht:
1. Klicke auf die 6 Punkte (⋮⋮) links neben der Route
2. Ziehe /api nach OBEN (über *)
3. Klicke "Save"
```

### 5. Origin Configurations optimieren:

**Für Route 1 (`/api` → Flask Backend):**

1. Klicke bei Route 1 auf die drei Punkte `⋮` → "Edit"
2. Scrolle zu "Additional application settings" → Klick zum Aufklappen
3. Setze folgende Werte:

| Setting                  | Wert | Grund                                    |
|--------------------------|------|------------------------------------------|
| Connect timeout          | 30   | Discord API Calls können langsam sein    |
| TLS timeout              | 10   | Standard ist ok                          |
| TCP keep-alive time      | 90   | Verhindert Connection Drops (war 30s)    |
| Keep-alive connections   | 100  | Mehr parallele User (war 10)             |
| HTTP Host Header         | -    | Leer lassen (nicht nötig für LAN IP)     |
| ☑ No TLS Verify          | ✅   | MUSS aktiv sein (LAN IP hat kein Cert)  |
| ☐ HTTP2 Origin           | ❌   | Flask nutzt HTTP/1.1                     |
| ☐ Disable Chunked Enc.   | ❌   | Nicht nötig                              |

4. Klicke "Save hostname"

**Für Route 2 (`*` → Flutter Frontend):**

Wiederhole für Route 2 mit angepassten Werten:

| Setting                  | Wert | Grund                                    |
|--------------------------|------|------------------------------------------|
| Connect timeout          | 10   | Static Files laden schnell               |
| TCP keep-alive time      | 60   | Kürzer als API (Frontend cached)         |
| Keep-alive connections   | 50   | Weniger nötig (static files)             |
| ☑ No TLS Verify          | ✅   | MUSS aktiv sein (LAN IP hat kein Cert)  |

### 6. Testen:
```bash
# API Test (sollte von Flask kommen)
curl https://test-hazebot-admin.hzwd.xyz/api/health
# Erwartete Response: {"status":"ok","timestamp":"..."}

# Frontend Test (sollte HTML von Port 8080 kommen)
curl -I https://test-hazebot-admin.hzwd.xyz/
# Erwartete Response: HTTP/2 200 + Content-Type: text/html

# Im Browser (Hard Refresh!)
# Ctrl+Shift+R oder Cmd+Shift+R
```

### 7. Troubleshooting:

**Problem: API gibt 404 oder HTML statt JSON**
→ Route-Reihenfolge falsch! `/api` muss ÜBER `*` stehen

**Problem: 502 Bad Gateway**
→ Prüfe ob Services laufen:
```bash
curl http://192.168.0.188:5070/api/health  # Flask
curl http://192.168.0.188:8080/            # Frontend
```

**Problem: 504 Gateway Timeout**
→ Origin Configuration fehlt oder Timeouts zu kurz

**Problem: Connection Drops nach Inaktivität**
→ TCP Keep-Alive Werte erhöhen (siehe Schritt 5)

---

## Route-Logik (Verständnis):
```
Anfrage → test-hazebot-admin.hzwd.xyz/api/config
  ↓
  ├─ Prüfe Route 1: /api → MATCH! ✅
  └─ Weiterleitung: http://192.168.0.188:5070/api/config

Anfrage → test-hazebot-admin.hzwd.xyz/
  ↓
  ├─ Prüfe Route 1: /api → KEIN MATCH ❌
  ├─ Prüfe Route 2: *    → MATCH! ✅
  └─ Weiterleitung: http://192.168.0.188:8080/

Anfrage → test-hazebot-admin.hzwd.xyz/assets/logo.png
  ↓
  ├─ Prüfe Route 1: /api → KEIN MATCH ❌
  ├─ Prüfe Route 2: *    → MATCH! ✅
  └─ Weiterleitung: http://192.168.0.188:8080/assets/logo.png
```

**KRITISCH**: Route-Reihenfolge! `/api` MUSS vor `*` kommen!

---

## Dashboard Screenshots Guide

### Route-Liste sollte SO aussehen:
```
┌────────────────────────────────────────────────────────────────┐
│ Public Hostname                                                │
├────┬──────────────────┬──────┬─────────────────────────┬──────┤
│ #  │ Subdomain/Domain │ Path │ Service                 │ Edit │
├────┼──────────────────┼──────┼─────────────────────────┼──────┤
│ ⋮⋮ │ test-hazebot-    │ /api │ http://192.168.0.188:   │ ...  │
│ 1  │ admin.hzwd.xyz   │      │ 5070                    │      │
├────┼──────────────────┼──────┼─────────────────────────┼──────┤
│ ⋮⋮ │ test-hazebot-    │ *    │ http://192.168.0.188:   │ ...  │
│ 2  │ admin.hzwd.xyz   │      │ 8080                    │      │
└────┴──────────────────┴──────┴─────────────────────────┴──────┘
```

### Origin Configuration Dialog (beim Editieren):
```
┌─────────────────────────────────────────────────┐
│ Edit Public Hostname                            │
├─────────────────────────────────────────────────┤
│ Subdomain: test-hazebot-admin                   │
│ Domain: hzwd.xyz                                │
│                                                 │
│ Path: /api                                      │
│                                                 │
│ Type: HTTP                                      │
│ URL: http://192.168.0.188:5070                 │
│                                                 │
│ ▼ Additional application settings              │
│                                                 │
│   Connect timeout: [30] seconds                 │
│   TLS timeout: [10] seconds                     │
│   TCP keep-alive time: [90] seconds             │
│   Keep-alive connections: [100]                 │
│                                                 │
│   ☑ No TLS Verify                              │
│   ☐ HTTP2 Origin                               │
│   ☐ Disable Chunked Encoding                   │
│                                                 │
│   [ Cancel ]  [ Save hostname ]                 │
└─────────────────────────────────────────────────┘
```

### Wichtige Felder erklärt:

**Connect timeout** (30s)
→ Zeit zum Herstellen der Verbindung zu 192.168.0.188:5070
→ Wichtig für Discord API Calls (RocketLeague, Warframe)

**TCP keep-alive time** (90s)
→ Hält Connection aktiv auch bei Inaktivität
→ Verhindert Session-Drops nach 30 Sekunden

**Keep-alive connections** (100)
→ Max. parallel aktive Connections
→ Wichtig für mehrere gleichzeitige User

**No TLS Verify** ✅
→ MUSS aktiviert sein für LAN IPs (192.168.x.x)
→ Localhost/LAN hat kein TLS Zertifikat

---

## Alternative: YAML Config (für Fortgeschrittene)

Falls du später doch die YAML-Datei verwenden willst:

tunnel: YOUR_TUNNEL_ID
credentials-file: /path/to/credentials.json

ingress:
  # Route 1: HazeBot Admin API (Flask Backend)
  # Wichtig: /api/* muss VOR catch-all kommen
  - hostname: test-hazebot-admin.hzwd.xyz
    path: /api
    service: http://192.168.0.188:5070
    originRequest:
      # Wichtig: HTTP/2 für bessere Performance
      httpHostHeader: test-hazebot-admin.hzwd.xyz
      
      # Keep-Alive Settings (verhindert Connection Drops)
      keepAliveConnections: 100  # Max connections zum Origin
      keepAliveTimeout: 90s      # Timeout für idle connections (Standard: 30s)
      
      # No-Happy-Eyeballs deaktiviert IPv6 fallback (falls IPv6 Probleme verursacht)
      noHappyEyeballs: false
      
      # Timeout Settings (wichtig für lange API Calls)
      connectTimeout: 30s        # Zeit zum Verbinden zum Origin
      tlsTimeout: 10s            # TLS Handshake Timeout
      noTLSVerify: true          # TLS Cert Validation (für LAN IP: true)
      
      # WebSocket Support (falls später benötigt)
      # HazeBot nutzt aktuell nur HTTP, aber für zukünftige Erweiterungen
      disableChunkedEncoding: false
      
      # HTTP/2 Origin (falls Flask HTTP/2 nutzt - aktuell HTTP/1.1)
      http2Origin: false

  # Route 2: Flutter Web App (Static Files) - Catch-all
  - hostname: test-hazebot-admin.hzwd.xyz
    service: http://192.168.0.188:8080
    originRequest:
      httpHostHeader: test-hazebot-admin.hzwd.xyz
      noTLSVerify: true
      # Kürzere Timeouts für Static Files
      connectTimeout: 10s
      keepAliveConnections: 50
      keepAliveTimeout: 60s
    
  # Catch-all rule (muss immer am Ende stehen)
  - service: http_status:404


# WICHTIGE EINSTELLUNGEN FÜR SESSION-STABILITÄT
# ------------------------------------------------------------------

# 0. KRITISCH: Route-Reihenfolge beachten!
#    /api Route MUSS VOR catch-all (*) kommen
#    → Sonst gehen API-Requests zu Port 8080 statt 5070!
#    Richtige Reihenfolge:
#      1. /api → 192.168.0.188:5070
#      2. *    → 192.168.0.188:8080
#      3. catch-all 404

# 1. Keep-Alive erhöhen (verhindert Connection Drops)
#    keepAliveTimeout: 90s statt Standard 30s
#    → Sessions bleiben länger aktiv ohne Re-Auth

# 2. Connection Pooling erhöhen
#    keepAliveConnections: 100 statt Standard 10
#    → Mehr parallel aktive User ohne Connection Drops

# 3. Timeouts erhöhen für langsame Endpoints
#    connectTimeout: 30s für Discord API Calls (RocketLeague, Warframe)
#    → Verhindert 504 Gateway Timeouts

# 4. HTTP/2 aktivieren (optional)
#    http2Origin: true wenn Flask HTTP/2 nutzt
#    → Bessere Performance, weniger Latenz

# 5. TLS Verify deaktivieren für LAN IPs
#    noTLSVerify: true für http://192.168.0.188
#    → Localhost/LAN IPs haben kein TLS Cert


# CLOUDFLARE DASHBOARD EINSTELLUNGEN
# ------------------------------------------------------------------

# Gehe zu: https://dash.cloudflare.com → Your Domain → SSL/TLS

# 1. SSL/TLS Encryption Mode: "Full (strict)"
#    → Verschlüsselte Verbindung zwischen Cloudflare und Origin

# 2. Always Use HTTPS: Aktiviert
#    → Alle HTTP Requests werden zu HTTPS umgeleitet

# 3. Minimum TLS Version: TLS 1.2
#    → Sicherer als TLS 1.0/1.1

# 4. Opportunistic Encryption: Aktiviert
#    → Nutzt verschlüsselte Connections wo möglich

# 5. TLS 1.3: Aktiviert
#    → Modernster TLS Standard


# CLOUDFLARE CACHING RULES
# ------------------------------------------------------------------

# Page Rules für test-hazebot-admin.hzwd.xyz:

# 1. API Endpoints: NICHT cachen
#    URL: test-hazebot-admin.hzwd.xyz/api/*
#    Settings: 
#      - Cache Level: Bypass
#      - Browser Cache TTL: Respect Existing Headers
#    → API Responses werden NICHT gecached
#    → Wichtig: Diese Regel MUSS vor der Catch-All-Regel sein!

# 2. Flutter Web App: Moderat cachen
#    URL: test-hazebot-admin.hzwd.xyz/*
#    Settings:
#      - Cache Level: Standard
#      - Edge Cache TTL: 1 hour (HTML/JS/CSS)
#      - Browser Cache TTL: 1 hour
#    → Flutter-Dateien werden gecached, aber nicht zu lange
#    → Nach Flutter Build: Hard Refresh nötig (Ctrl+Shift+R)

# 3. Static Assets: Aggressiv cachen (falls vorhanden)
#    URL: test-hazebot-admin.hzwd.xyz/assets/*
#    Settings:
#      - Cache Level: Cache Everything
#      - Edge Cache TTL: 1 month
#      - Browser Cache TTL: 1 month
#    → Bilder, Fonts, etc. werden lange gecached


# PERFORMANCE OPTIMIERUNGEN
# ------------------------------------------------------------------

# Cloudflare Dashboard → Speed → Optimization:

# 1. Auto Minify: Aktiviert (HTML, CSS, JS)
#    → Kleinere Dateigrößen

# 2. Brotli: Aktiviert
#    → Bessere Kompression als gzip

# 3. Rocket Loader: DEAKTIVIERT
#    → Kann Flutter Web brechen

# 4. Mirage: DEAKTIVIERT
#    → Kann Image Loading brechen

# 5. Polish: DEAKTIVIERT
#    → Kann Meme Images verändern


# MONITORING & DEBUGGING
# ------------------------------------------------------------------

# Cloudflare Logs:
# cloudflared tail YOUR_TUNNEL_ID

# Local Backend Test (direkt ohne Tunnel):
# curl -I http://192.168.0.188:5070/api/health

# Local Frontend Test (direkt ohne Tunnel):
# curl -I http://192.168.0.188:8080/

# Tunnel Connection Test:
# curl -I https://test-hazebot-admin.hzwd.xyz/api/health

# WebSocket Test (falls später benötigt):
# wscat -c wss://test-hazebot-admin.hzwd.xyz/ws

# Performance Test:
# time curl https://test-hazebot-admin.hzwd.xyz/api/hazehub/latest-memes

# Route Testing:
# curl -v https://test-hazebot-admin.hzwd.xyz/api/config  # → 192.168.0.188:5070
# curl -v https://test-hazebot-admin.hzwd.xyz/           # → 192.168.0.188:8080


# TROUBLESHOOTING
# ------------------------------------------------------------------

# Problem: 502 Bad Gateway
# Lösung: Prüfe ob Backend läuft
#   curl http://192.168.0.188:5070/api/health  # Flask API
#   curl http://192.168.0.188:8080/            # Flutter Web

# Problem: API Requests gehen zu Port 8080 statt 5070
# Lösung: /api Route muss VOR catch-all (*) in ingress kommen!
#   Reihenfolge in config.yml: /api DANN *

# Problem: 504 Gateway Timeout
# Lösung: Erhöhe connectTimeout auf 60s für langsame Endpoints

# Problem: WebSocket Connection Failed
# Lösung: Aktiviere WebSocket Support in originRequest

# Problem: Session Expiry nach kurzer Zeit
# Lösung: Erhöhe keepAliveTimeout auf 180s (3 Minuten)
#   (Bereits implementiert: 90s)

# Problem: Too Many Connections
# Lösung: Erhöhe keepAliveConnections auf 200+
#   (Bereits implementiert: 100 für API, 50 für Static)

# Problem: LAN IP nicht erreichbar
# Lösung: Firewall auf 192.168.0.188 prüfen
#   sudo ufw allow from 192.168.0.0/24 to any port 5070
#   sudo ufw allow from 192.168.0.0/24 to any port 8080


# SICHERHEIT
# ------------------------------------------------------------------

# 1. IP Whitelist (optional):
#    → Cloudflare Access Rules für /api/admin/*

# 2. Rate Limiting:
#    → Cloudflare Rate Limiting Rules (z.B. 100 req/min pro IP)

# 3. WAF (Web Application Firewall):
#    → Cloudflare Managed Rules aktivieren

# 4. DDoS Protection:
#    → Automatisch durch Cloudflare
