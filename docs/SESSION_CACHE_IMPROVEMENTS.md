# Session & Cache Improvements - Implementation Summary

## Problem gelöst ✅

Das Session-Ablauf-Problem wurde durch mehrere Verbesserungen gelöst:

1. **Session Timeout erhöht**: 5 Minuten → 30 Minuten
2. **Token Expiry erhöht**: 24 Stunden → 7 Tage
3. **Automatischer Token Refresh**: Frontend refresht Token bei 401 Errors
4. **API Cache-System**: Reduziert unnötige API-Calls

## Backend Änderungen

### 1. Session Management (`api/app.py`)

**Session Timeout erhöht:**
```python
# Vorher: 300 Sekunden (5 Minuten)
if (current_time - last_seen).total_seconds() > 300:

# Nachher: 1800 Sekunden (30 Minuten)
if (current_time - last_seen).total_seconds() > 1800:
```

**Token Expiry erhöht:**
```python
# Legacy Login
"exp": datetime.utcnow() + timedelta(days=7),  # Vorher: hours=24

# Discord OAuth
"exp": datetime.utcnow() + timedelta(days=7),  # Vorher: hours=24
```

**Neuer Token-Refresh Endpoint:**
```python
@app.route("/api/auth/refresh", methods=["POST"])
@token_required
def refresh_token():
    """Refresh JWT token with new expiry date (keeps same session_id)"""
    new_token = jwt.encode({
        "user": request.username,
        "discord_id": request.discord_id,
        "exp": datetime.utcnow() + timedelta(days=7),
        "role": request.user_role,
        "permissions": request.user_permissions,
        "auth_type": "refreshed",
        "session_id": request.session_id,  # Keep same session
    }, app.config["SECRET_KEY"], algorithm="HS256")
    
    return jsonify({"token": new_token, ...})
```

### 2. Cache-System (`api/cache.py`)

**Neue Datei mit vollständigem Cache-System:**

```python
class APICache:
    """Simple in-memory cache with TTL support"""
    
    def get(self, key: str) -> Optional[Any]
    def set(self, key: str, value: Any, ttl: int = 300)
    def delete(self, key: str) -> bool
    def invalidate_pattern(self, pattern: str) -> int
    def clear(self) -> None
    def cleanup_expired(self) -> int
    def get_stats(self) -> dict
```

**Decorator für einfaches Caching:**
```python
@cached(ttl=60, key_prefix="hazehub")
def expensive_function():
    return expensive_operation()
```

**Cache angewendet auf:**
- `GET /api/hazehub/latest-memes` - TTL: 60 Sekunden
- `GET /api/hazehub/latest-rankups` - TTL: 60 Sekunden
- `GET /api/gaming/members` - TTL: 30 Sekunden

**Neue Cache-Admin-Endpoints:**
```python
GET /api/admin/cache/stats       # Cache-Statistiken
POST /api/admin/cache/clear      # Cache leeren
POST /api/admin/cache/invalidate # Spezifische Keys löschen
```

**Cache-Statistiken:**
```json
{
  "hits": 150,
  "misses": 50,
  "sets": 50,
  "invalidations": 5,
  "total_requests": 200,
  "hit_rate": 75.0,
  "cache_size": 10
}
```

## Frontend Änderungen

### 1. Token Refresh System (`lib/services/api_service.dart`)

**Neue Methoden:**

```dart
// Refresh token mit neuem Expiry
Future<Map<String, dynamic>?> refreshToken() async {
  final response = await http.post(
    Uri.parse('$baseUrl/auth/refresh'),
    headers: {'Authorization': 'Bearer $_token'},
  );
  
  if (response.statusCode == 200) {
    final data = jsonDecode(response.body);
    setToken(data['token']);
    return data;
  }
  return null;
}

// Request mit automatischem Retry bei 401
Future<http.Response> _requestWithRetry(
  Future<http.Response> Function() request, {
  int maxRetries = 1,
}) async {
  http.Response response = await request();

  if (response.statusCode == 401 && maxRetries > 0) {
    debugPrint('⚠️ Got 401, attempting token refresh...');
    
    final refreshResult = await refreshToken();
    
    if (refreshResult != null) {
      debugPrint('✅ Retrying request with new token...');
      return await _requestWithRetry(request, maxRetries: maxRetries - 1);
    }
  }

  return response;
}
```

**HTTP Helper-Methoden:**
```dart
Future<http.Response> _get(String url, {Map<String, String>? headers})
Future<http.Response> _post(String url, {Map<String, String>? headers, Object? body})
Future<http.Response> _put(String url, {Map<String, String>? headers, Object? body})
Future<http.Response> _delete(String url, {Map<String, String>? headers})
```

**Wichtigste Endpoints migriert:**
- `getConfig()` - Haupt-Config
- `getLatestMemes()` - HazeHub Memes
- `getLatestRankups()` - HazeHub Rank-Ups
- `getGamingMembers()` - Gaming Hub

## Cloudflare Tunnel Optimierung

### Neue Datei: `CLOUDFLARE_TUNNEL_CONFIG.md`

**Wichtigste Einstellungen:**

```yaml
originRequest:
  # Keep-Alive erhöht (verhindert Connection Drops)
  keepAliveConnections: 100  # Vorher: 10
  keepAliveTimeout: 90s      # Vorher: 30s
  
  # Timeouts erhöht für langsame Endpoints
  connectTimeout: 30s        # Discord API Calls
  tlsTimeout: 10s
```

**Caching Rules:**
- `/api/*` - NICHT cachen (Bypass)
- `/static/*` - 1 Monat cachen

**Performance:**
- Auto Minify: Aktiviert
- Brotli: Aktiviert
- Rocket Loader: DEAKTIVIERT (bricht Flutter Web)

## Vorher vs. Nachher

### Session-Stabilität

**Vorher:**
- ❌ Sessions laufen nach 5 Minuten Inaktivität ab
- ❌ Token läuft nach 24 Stunden ab
- ❌ Kein automatischer Refresh
- ❌ User wird häufig ausgeloggt

**Nachher:**
- ✅ Sessions bleiben 30 Minuten aktiv
- ✅ Token läuft nach 7 Tagen ab
- ✅ Automatischer Token-Refresh bei 401
- ✅ User bleibt dauerhaft eingeloggt

### API Performance

**Vorher:**
- ❌ Jeder Request geht zum Bot
- ❌ Langsame Response-Zeiten
- ❌ Hohe Server-Last
- ❌ Keine Invalidierung möglich

**Nachher:**
- ✅ Häufige Requests werden gecached
- ✅ Schnellere Response-Zeiten (60% Hit-Rate erwartet)
- ✅ Reduzierte Server-Last
- ✅ Admin kann Cache manuell invalidieren

### Netzwerk-Stabilität

**Vorher:**
- ❌ Kurze Cloudflare Keep-Alive (30s)
- ❌ Connection Drops bei Inaktivität
- ❌ Keine optimierten Timeouts

**Nachher:**
- ✅ Längere Keep-Alive (90s)
- ✅ Stabile Connections
- ✅ Optimierte Timeouts für Discord API

## Testing

### Backend Tests

```bash
# API starten
cd /home/liq/gitProjects/HazeBot
python start_with_api.py

# Cache-Stats abrufen (Admin only)
curl -H "Authorization: Bearer <token>" \
  http://localhost:5070/api/admin/cache/stats

# Token refreshen
curl -X POST -H "Authorization: Bearer <token>" \
  http://localhost:5070/api/auth/refresh
```

### Frontend Tests

```bash
# Flutter App starten
cd /home/liq/gitProjects/HazeBot-Admin
flutter run -d linux

# Oder Web Build
flutter build web --release --pwa-strategy=none
cd build/web
python3 spa_server.py
```

**Test-Schritte:**
1. ✅ Login durchführen (Discord OAuth)
2. ✅ 10 Minuten warten (keine Aktivität)
3. ✅ Navigation zu HazeHub → sollte ohne Re-Login funktionieren
4. ✅ Cache-Wirkung prüfen (schnellere Response-Zeiten)
5. ✅ 401 Error provozieren → automatischer Token-Refresh

## Migration für bestehende Deployments

### 1. Backend aktualisieren

```bash
cd /home/liq/gitProjects/HazeBot
git pull origin main

# API neu starten
# (systemd service oder manuell)
sudo systemctl restart hazebot
# ODER
python start_with_api.py
```

### 2. Frontend neu builden

```bash
cd /home/liq/gitProjects/HazeBot-Admin
flutter build web --release --pwa-strategy=none

# Neue Build-Dateien deployen
# z.B. zu Static Host oder eigener Server
```

### 3. Cloudflare Tunnel Config aktualisieren

```bash
# Backup der alten Config
cp ~/.cloudflared/config.yml ~/.cloudflared/config.yml.backup

# Neue Settings aus CLOUDFLARE_TUNNEL_CONFIG.md übernehmen
nano ~/.cloudflared/config.yml

# Tunnel neu starten
sudo systemctl restart cloudflared
```

### 4. Hard Refresh im Browser

Nach Deploy IMMER Hard Refresh machen:
- **Linux/Windows**: `Ctrl + Shift + R`
- **Mac**: `Cmd + Shift + R`

Oder Browser-Cache komplett leeren.

## Monitoring

### Cache Performance

```bash
# Cache-Stats abrufen
curl -H "Authorization: Bearer $TOKEN" \
  https://test-hazebot-admin.hzwd.xyz/api/admin/cache/stats

# Erwartete Hit-Rate: 50-70% (nach Warmup)
```

### Session Tracking

```bash
# Aktive Sessions anzeigen
curl -H "Authorization: Bearer $TOKEN" \
  https://test-hazebot-admin.hzwd.xyz/api/admin/active-sessions

# Sollte Sessions für 30 Minuten zeigen
```

### Cloudflare Logs

```bash
# Tunnel Logs live verfolgen
cloudflared tail YOUR_TUNNEL_ID

# Connection-Probleme suchen
cloudflared tail YOUR_TUNNEL_ID | grep -i "error\|timeout\|disconnect"
```

## Bekannte Einschränkungen

1. **Cache ist In-Memory**:
   - ❌ Geht bei Server-Restart verloren
   - ✅ Für Production: Redis verwenden (optional)

2. **Token-Refresh nur bei 401**:
   - ❌ Proaktiver Refresh nicht implementiert
   - ✅ Reicht für normale Nutzung (7-Tage-Expiry)

3. **Cache-Invalidierung manuell**:
   - ❌ Keine automatische Invalidierung bei Config-Änderungen
   - ✅ Admin kann manuell invalidieren

## Future Improvements

### Kurzfristig (Optional)

- [ ] Cache-Invalidierung bei Config-Updates automatisieren
- [ ] Proaktiver Token-Refresh (z.B. 1 Tag vor Ablauf)
- [ ] Weitere Endpoints cachen (Templates, Logs, etc.)

### Langfristig (Nice-to-Have)

- [ ] Redis für persistenten Cache (Production)
- [ ] WebSocket für Real-Time Updates (statt Polling)
- [ ] HTTP/2 Server Push für Static Files
- [ ] Service Worker für Offline-Support

## Support

Bei Problemen:

1. **Backend-Logs prüfen**:
   ```bash
   tail -f /home/liq/gitProjects/HazeBot/Logs/api_audit.log
   ```

2. **Frontend-Logs prüfen**:
   - Browser Console (F12)
   - Suche nach "Token", "401", "refresh"

3. **Cache-Stats prüfen**:
   - Admin Panel → Sessions → Cache Stats (TODO: UI hinzufügen)

4. **Cloudflare Logs prüfen**:
   ```bash
   cloudflared tail YOUR_TUNNEL_ID
   ```

---

**Implementiert**: 13. November 2025
**Version**: HazeBot API v2.0
**Status**: ✅ Ready for Testing
