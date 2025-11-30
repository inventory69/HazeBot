# HazeBot mit API Integration

## 🚀 Start mit API

Um den Bot **mit** API-Integration zu starten (für die Admin-App Test-Funktionen):

```bash
python start_with_api.py
```

Dies startet:
- Den Discord Bot
- Die Flask API auf Port 5070
- Verbindet beide, sodass die API auf Bot-Funktionen zugreifen kann

## 📱 Admin App Test-Funktionen

Die Admin App hat jetzt einen **Test**-Tab mit folgenden Funktionen:

### Get Random Meme
- Holt ein zufälliges Meme von konfigurierten Quellen (Reddit/Lemmy)
- Zeigt URL, Titel, Source, Subreddit, Author und Score
- NSFW-Inhalte werden gefiltert

### Test Daily Meme
- Postet ein Daily Meme in den konfigurierten Kanal
- Verwendet die tatsächliche `daily_meme_task` Funktion
- Pingt optional die konfigurierte Rolle

## ⚙️ Konfiguration

Die Test-Endpoints verwenden die gleiche Konfiguration wie der Bot:
- `MEME_CHANNEL_ID` - Kanal für Daily Meme Posts
- `MEME_ROLE_ID` - Rolle die gepingt werden soll
- Subreddit/Lemmy-Listen aus der Config

## 🔧 Troubleshooting

### "Bot instance not available"
- Stelle sicher, dass du `start_with_api.py` verwendest, nicht `Main.py`
- Der Bot muss laufen, damit die API darauf zugreifen kann

### "DailyMeme cog not loaded"
- Prüfe ob das DailyMeme Cog geladen ist: `!listcogs`
- Falls disabled: Aktiviere es mit dem CogManager

### Timeout-Fehler
- Meme-Fetch kann länger dauern bei langsamer API
- Timeout ist auf 15 Sekunden für Random Meme, 30 für Daily Meme gesetzt

## 🔐 Authentifizierung

Die Test-Endpoints benötigen ein gültiges JWT-Token:
1. Login über die Admin App
2. Token wird automatisch für alle API-Calls verwendet

## 📝 Hinweise

- **Random Meme** testet nur das Fetching, postet nichts
- **Daily Meme** postet tatsächlich in den Discord-Kanal!
- Verwende Test-Modus für Experimente, Production-Modus für Live-Server
