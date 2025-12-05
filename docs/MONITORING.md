# 📊 Monitoring Documentation

Die vollständige Monitoring-Dokumentation wurde ausgelagert nach:

```
/home/liq/gitProjects/hazebot-monitoring-docs/
```

## 🚀 Quick Start

**Neu hier?** Starte mit dem Master Guide:
```
/home/liq/gitProjects/hazebot-monitoring-docs/MASTER_GUIDE.md
```

Oder öffne die README:
```
/home/liq/gitProjects/hazebot-monitoring-docs/README.md
```

---

## 📚 Was ist enthalten?

### Uptime Kuma Setup
- Vollständige Setup-Anleitung (10 Monitore)
- Quick Reference Card
- Deployment Checklist
- Architektur Diagramme
- Monitor Konfigurationen (JSON)

### Discord Integration
- Channel Setup Anleitung
- 5-Minuten Quick Start
- Visual Flow Diagramme
- Incident Response Workflow

### Deployment
- Maintenance Mode Script: `scripts/deploy_with_maintenance.sh`
- Token Generator: `scripts/generate_monitoring_token.sh`

---

## ⚡ Schnellstart

### 1. API vorbereiten
```bash
pip install psutil
export API_MONITORING_SECRET="$(openssl rand -hex 32)"
docker-compose restart hazebot-api
./scripts/generate_monitoring_token.sh
```

### 2. Uptime Kuma einrichten
Siehe: `/home/liq/gitProjects/hazebot-monitoring-docs/UPTIME_KUMA_SETUP.md`

### 3. Discord Channel setup
Siehe: `/home/liq/gitProjects/hazebot-monitoring-docs/DISCORD_MONITORING_QUICKSTART.md`

---

## 🔧 Deployment mit Maintenance Mode

Vor jedem Push auf `main`:

```bash
# Option 1: Mit Script (empfohlen)
./scripts/deploy_with_maintenance.sh

# Option 2: Manuell
# 1. Uptime Kuma: Pause ALL Monitors (5 min)
# 2. git push origin main
# 3. Warte auf Pterodactyl Restart
# 4. Uptime Kuma: Resume ALL Monitors
```

**Warum?** Verhindert False Downtime Alerts während des Service Restarts!

---

## 📋 API Endpoints

Neue Monitoring Endpoints:

| Endpoint | Auth | Beschreibung |
|----------|------|--------------|
| `GET /api/health` | ❌ No | Basic Health Check |
| `GET /api/health?detailed=true` | ❌ No | System Metrics (Memory, CPU, Disk, Cache) |
| `POST /api/auth/monitoring-token` | 🔐 Secret | Generiert 90-Tage JWT Token |

---

## 🔐 Environment Variables

Neue Environment Variables:

```bash
# Erforderlich für Token-Generierung
API_MONITORING_SECRET="..."  # openssl rand -hex 32

# Optional
API_VERSION="1.0.0"          # Wird in Health Check angezeigt
ENVIRONMENT="production"      # Wird in Health Check angezeigt
```

---

## 📖 Vollständige Dokumentation

Alle Details findest du hier:
```
/home/liq/gitProjects/hazebot-monitoring-docs/
├── MASTER_GUIDE.md                        (START HIER - Schritt-für-Schritt)
├── README.md                              (Übersicht)
├── UPTIME_KUMA_SETUP.md                   (400+ Zeilen)
├── UPTIME_KUMA_QUICKREF.md                (Quick Reference)
├── DEPLOYMENT_UPTIME_KUMA.md              (Deployment Guide)
├── UPTIME_KUMA_ARCHITECTURE.txt           (Diagramme)
├── uptime_kuma_monitors.json              (Monitor Configs)
├── DISCORD_MONITORING_CHANNEL_SETUP.md    (500+ Zeilen)
├── DISCORD_MONITORING_QUICKSTART.md       (5 Minuten)
├── DISCORD_MONITORING_FLOW.txt            (Visual Flows)
└── MONITORING_OVERVIEW.md                 (Gesamt-Übersicht)
```

---

## 🆘 Troubleshooting

**Health Check schlägt fehl:**
```bash
curl https://api.haze.pro/api/health?detailed=true | jq
docker-compose logs -f hazebot-api
```

**Token generieren:**
```bash
./scripts/generate_monitoring_token.sh
```

**Vollständiges Troubleshooting:**
Siehe Master Guide in `/home/liq/gitProjects/hazebot-monitoring-docs/`

---

**Version:** 1.0.0 | **Erstellt:** 5. Dezember 2025
