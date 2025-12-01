# HazeBot Analytics Dashboard - Remote Access Guide

## Übersicht

Das Analytics Dashboard kann auf verschiedene Arten von extern zugänglich gemacht werden:

---

## Option 1: SSH Tunnel (Empfohlen - Sicherste Methode)

### Vorteile
- ✅ Komplett sicher (SSH-verschlüsselt)
- ✅ Keine Firewall-Änderungen nötig
- ✅ Keine öffentliche Exposition
- ✅ Keine nginx-Konfiguration nötig
- ✅ Sofort einsatzbereit

### Setup

1. **Auf dem Server starten:**
```bash
cd /path/to/HazeBot
python analytics/view_analytics.py --port 8082 --no-browser
```

2. **Von deinem lokalen PC aus SSH-Tunnel erstellen:**
```bash
# Linux/macOS
ssh -L 8082:localhost:8082 user@your-server.com

# Windows PowerShell
ssh -L 8082:localhost:8082 user@your-server.com
```

3. **Dashboard öffnen:**
```
http://localhost:8082/analytics/analytics_dashboard.html
```

### Automatisierung mit SSH Config

Füge zu `~/.ssh/config` hinzu:

```
Host hazebot-analytics
    HostName your-server.com
    User your-username
    LocalForward 8082 localhost:8082
    LocalForward 5070 localhost:5070  # Optional: API auch tunneln
```

Dann einfach:
```bash
ssh hazebot-analytics
# Öffne in anderem Terminal/Tab
open http://localhost:8082/analytics/analytics_dashboard.html
```

---

## Option 2: nginx Reverse Proxy (Wie Admin Panel)

### Vorteile
- ✅ Über öffentliche URL erreichbar
- ✅ SSL-verschlüsselt
- ✅ Basic Auth möglich
- ✅ Kein SSH-Tunnel nötig

### Nachteile
- ⚠️ Öffentlich exponiert (aber mit Auth absicherbar)
- ⚠️ nginx-Konfiguration erforderlich

### Setup

#### 1. Analytics Server als Systemd Service (dauerhaft)

Erstelle `/etc/systemd/system/hazebot-analytics.service`:

```ini
[Unit]
Description=HazeBot Analytics Dashboard
After=network.target

[Service]
Type=simple
User=hazebot
WorkingDirectory=/home/hazebot/HazeBot
ExecStart=/home/hazebot/HazeBot/.venv/bin/python analytics/view_analytics.py --host 127.0.0.1 --port 8082 --no-browser
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Service aktivieren:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable hazebot-analytics
sudo systemctl start hazebot-analytics
sudo systemctl status hazebot-analytics
```

#### 2. Basic Auth einrichten (Empfohlen!)

```bash
# htpasswd installieren
sudo apt install apache2-utils

# User erstellen (z.B. "admin")
sudo htpasswd -c /etc/nginx/.htpasswd admin

# Weitere User hinzufügen (ohne -c!)
sudo htpasswd /etc/nginx/.htpasswd another_user
```

#### 3. nginx-Konfiguration

**Variante A: Als Subdomain (analytics.hzwd.xyz)**

Erstelle `/etc/nginx/sites-available/hazebot-analytics.conf`:

```nginx
# Analytics Dashboard auf Subdomain
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    
    server_name analytics.hzwd.xyz;
    
    # SSL (Certbot managed)
    ssl_certificate /etc/letsencrypt/live/analytics.hzwd.xyz/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/analytics.hzwd.xyz/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
    
    # Logging
    access_log /var/log/nginx/analytics-access.log;
    error_log /var/log/nginx/analytics-error.log;
    
    # Basic Auth - WICHTIG für Sicherheit!
    auth_basic "HazeBot Analytics - Login Required";
    auth_basic_user_file /etc/nginx/.htpasswd;
    
    # Analytics Dashboard Proxy
    location / {
        proxy_pass http://127.0.0.1:8082;
        
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}

# HTTP Redirect
server {
    listen 80;
    listen [::]:80;
    
    server_name analytics.hzwd.xyz;
    
    # Allow Certbot
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        return 301 https://$server_name$request_uri;
    }
}
```

**Variante B: Als Pfad auf existierendem Server (test-hazebot-admin.hzwd.xyz/analytics)**

Füge zum bestehenden `hazebot-admin.conf` Server-Block hinzu:

```nginx
# Füge NACH location /socket.io/ und /api/ aber VOR location / hinzu:

# ==================================
# Analytics Dashboard
# ==================================
location /analytics/ {
    # Basic Auth
    auth_basic "HazeBot Analytics - Login Required";
    auth_basic_user_file /etc/nginx/.htpasswd;
    
    # Proxy zu Analytics Server
    proxy_pass http://127.0.0.1:8082/analytics/;
    
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
}
```

#### 4. nginx aktivieren & SSL

```bash
# Site aktivieren (Ubuntu/Debian)
sudo ln -s /etc/nginx/sites-available/hazebot-analytics.conf /etc/nginx/sites-enabled/

# Test
sudo nginx -t

# Reload
sudo systemctl reload nginx

# SSL Zertifikat holen (nur für neue Subdomain)
sudo certbot --nginx -d analytics.hzwd.xyz
```

#### 5. Zugriff testen

**Subdomain:**
```
https://analytics.hzwd.xyz
Username: admin
Password: <dein-passwort>
```

**Pfad:**
```
https://test-hazebot-admin.hzwd.xyz/analytics/
Username: admin
Password: <dein-passwort>
```

---

## Option 3: Cloudflare Tunnel (Zero Trust)

### Vorteile
- ✅ Kein Port-Forwarding nötig
- ✅ Zero Trust Security
- ✅ Kostenlos
- ✅ DDoS Protection

### Setup

1. **Cloudflared installieren:**
```bash
# Ubuntu/Debian
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o cloudflared.deb
sudo dpkg -i cloudflared.deb

# Login
cloudflared tunnel login
```

2. **Tunnel erstellen:**
```bash
cloudflared tunnel create hazebot-analytics
```

3. **Konfiguration:** `~/.cloudflared/config.yml`
```yaml
tunnel: <TUNNEL-ID>
credentials-file: /home/user/.cloudflared/<TUNNEL-ID>.json

ingress:
  - hostname: analytics.hzwd.xyz
    service: http://localhost:8082
  - service: http_status:404
```

4. **DNS Route erstellen:**
```bash
cloudflared tunnel route dns hazebot-analytics analytics.hzwd.xyz
```

5. **Tunnel starten:**
```bash
cloudflared tunnel run hazebot-analytics
```

6. **Als Service einrichten:**
```bash
sudo cloudflared service install
sudo systemctl enable cloudflared
sudo systemctl start cloudflared
```

---

## Option 4: Tailscale VPN (Privates Netzwerk)

### Vorteile
- ✅ Privates VPN zwischen deinen Geräten
- ✅ Kein öffentlicher Zugriff
- ✅ Einfaches Setup
- ✅ Kostenlos für privaten Gebrauch

### Setup

1. **Tailscale installieren (Server & lokaler PC):**
```bash
# Ubuntu/Debian
curl -fsSL https://tailscale.com/install.sh | sh

# Login
sudo tailscale up
```

2. **Analytics Server starten:**
```bash
python analytics/view_analytics.py --host 0.0.0.0 --port 8082 --no-browser
```

3. **Von lokalem PC zugreifen:**
```
# Tailscale IP des Servers finden
tailscale ip -4

# Dashboard öffnen
http://<server-tailscale-ip>:8082/analytics/analytics_dashboard.html
```

---

## Sicherheitsempfehlungen

### Für öffentlichen Zugriff (nginx):
- ✅ **IMMER** Basic Auth verwenden
- ✅ SSL/TLS (HTTPS) aktivieren
- ✅ Starke Passwörter (htpasswd mit bcrypt)
- ✅ IP Whitelist (optional):
```nginx
# Nur deine IP erlauben
allow 1.2.3.4;  # Deine Home-IP
deny all;
```

### Für alle Methoden:
- ✅ Firewall nur nötige Ports öffnen
- ✅ fail2ban für nginx (Brute-Force Schutz)
- ✅ Regelmäßige Updates
- ✅ Logs überwachen

---

## Vergleichstabelle

| Methode | Sicherheit | Setup-Aufwand | Zugriff | Kosten |
|---------|------------|---------------|---------|--------|
| **SSH Tunnel** | ⭐⭐⭐⭐⭐ | Sehr niedrig | Nur während SSH-Session | Kostenlos |
| **nginx + Auth** | ⭐⭐⭐⭐ | Mittel | Immer online | Kostenlos |
| **Cloudflare Tunnel** | ⭐⭐⭐⭐⭐ | Mittel | Immer online | Kostenlos |
| **Tailscale** | ⭐⭐⭐⭐⭐ | Niedrig | Privates Netzwerk | Kostenlos |

---

## Empfehlung für deinen Use Case

### Für gelegentlichen Zugriff:
➡️ **SSH Tunnel** (Option 1) - Schnell, sicher, keine Konfiguration

### Für regelmäßigen Zugriff:
➡️ **nginx + Basic Auth** (Option 2) - Immer verfügbar, in bestehendes Setup integrierbar

### Für maximale Sicherheit:
➡️ **Tailscale** (Option 4) - Privates Netzwerk, zero-config nach Setup

---

## Troubleshooting

### Analytics Server startet nicht
```bash
# Prüfen ob Port frei ist
sudo lsof -i :8082

# Service Status prüfen
sudo systemctl status hazebot-analytics

# Logs anschauen
sudo journalctl -u hazebot-analytics -f
```

### nginx 502 Bad Gateway
```bash
# Analytics Server läuft?
curl http://localhost:8082/analytics/analytics_dashboard.html

# nginx error log
sudo tail -f /var/log/nginx/analytics-error.log
```

### SSH Tunnel bricht ab
```bash
# Keep-alive aktivieren in ~/.ssh/config
Host *
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

### Basic Auth funktioniert nicht
```bash
# Passwort neu setzen
sudo htpasswd -c /etc/nginx/.htpasswd admin

# nginx config testen
sudo nginx -t

# Reload
sudo systemctl reload nginx
```

