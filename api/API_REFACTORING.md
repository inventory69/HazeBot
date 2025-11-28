# API Module Struktur

## Übersicht

Die Flask API wurde von einer monolithischen 6500-Zeilen Datei in eine modulare Blueprint-basierte Architektur aufgeteilt.

## Struktur

```
api/
├── app.py                      # Hauptdatei (<1000 Zeilen) - Flask Setup, Middleware, Blueprint Registration
├── helpers.py                   # Helper-Funktionen (Logging, Upvotes, Config)
├── auth.py                      # Auth Decorators & Middleware
├── auth_routes.py              # Login, OAuth, Token Management
├── routes/
│   ├── __init__.py
│   ├── admin_routes.py         # Admin Endpoints (Sessions, Cache, Logs)
│   ├── config_routes.py        # Configuration Management
│   ├── user_routes.py          # User Profile & Preferences
│   ├── meme_routes.py          # Meme Generator & Daily Meme
│   ├── rocket_league_routes.py # Rocket League Integration
│   ├── ticket_routes.py        # Ticket System
│   ├── hazehub_routes.py       # HazeHub Features
│   ├── cog_routes.py           # Cog Management
│   └── notification_routes.py  # Push Notifications
└── websocket_handlers.py       # WebSocket Events

```

## Vorteile

- ✅ **Wartbarkeit**: Jedes Modul hat eine klare Verantwortlichkeit
- ✅ **Lesbarkeit**: Kleinere, fokussierte Dateien (<1000 Zeilen)
- ✅ **Testbarkeit**: Einfacher zu testen und zu debuggen
- ✅ **Skalierbarkeit**: Neue Features können als separate Blueprints hinzugefügt werden
- ✅ **Code-Qualität**: Mit ruff geprüft und formatiert

## Migration

Alle Funktionen der ursprünglichen app.py bleiben vollständig erhalten. Die API-Endpunkte und Funktionalität sind identisch.

### Backup

Original-Datei gesichert als: `app.py.backup-20251128-172147`
