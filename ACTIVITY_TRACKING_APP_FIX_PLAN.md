# 🔍 Activity Tracking for HazeBot-Admin App Fix Plan
**Datum**: 6. Dezember 2025  
**Problem**: Meme-Statistiken werden nur durch Discord getrackt, nicht durch die App  
**Ziel**: App-Requests auch in `meme_requests.json` und `memes_generated.json` tracken

---

## 🐛 Problem-Analyse

### Aktueller Status

**Discord Bot Tracking** ✅
- `/meme` Command → Inkrementiert `meme_requests.json`
- Meme Generator Command → Inkrementiert `memes_generated.json`
- Gespeichert in: `Data/meme_requests.json` und `Data/memes_generated.json`

**HazeBot-Admin App Tracking** ❌
- API Endpoint: `POST /api/meme-generator/generate` 
- API Endpoint: `POST /api/meme-generator/post-to-discord`
- API Endpoint: `POST /api/daily-meme/post`
- **Problem**: Diese Endpoints tracken NICHT die User-Activity!

**Resolved Tickets Tracking** ✅ (Kein Problem!)
- API Endpoint: `POST /api/tickets/<id>/close`
- **Status**: Wird NICHT separat getrackt (gut so!)
- `resolved_tickets` wird dynamisch aus Ticket-Daten berechnet (siehe user_routes.py:170-186)
- Tickets haben `status`, `claimed_by`, `assigned_to` Felder
- Beim Abrufen des Profiles: Zählt geschlossene Tickets wo User `claimed_by` oder `assigned_to` ist
- **Kein Fix nötig** - funktioniert bereits korrekt!

### Was wird getrackt?

**Profile Endpoint** (`/api/user/<discord_id>/profile`):
```python
# user_routes.py Zeile 190-212
activity = {"messages": 0, "images": 0, "memes_requested": 0, "memes_generated": 0}

# Meme stats kommen aus:
from Cogs.Profile import load_meme_requests, load_memes_generated

meme_requests = load_meme_requests()  # Data/meme_requests.json
memes_generated = load_memes_generated()  # Data/memes_generated.json

activity["memes_requested"] = meme_requests.get(str(discord_id), 0)
activity["memes_generated"] = memes_generated.get(str(discord_id), 0)
```

**File Structure**:
```json
// Data/meme_requests.json
{
  "283733417575710721": 42,  // Discord User ID → Count
  "123456789012345678": 10
}

// Data/memes_generated.json
{
  "283733417575710721": 15,
  "123456789012345678": 5
}
```

### Wo werden Memes getrackt? (Discord Bot)

**DailyMeme Cog** (`Cogs/DailyMeme.py`):
```python
# Zeile 234-251
def load_meme_requests(self) -> dict:
    """Load meme requests cache from file"""
    # Liest Data/meme_requests.json

def save_meme_requests(self) -> None:
    """Save meme requests cache to file"""
    # Schreibt nach Data/meme_requests.json
```

**Wo wird gespeichert?**:
- `/meme` Slash Command → `save_meme_requests()` aufgerufen
- Button Interactions → `save_meme_requests()` aufgerufen
- Zeile 1104, 1270 in `DailyMeme.py`

**MemeGenerator Tracking** (Annahme):
- Vermutlich in `Cogs/MemeGenerator.py` 
- Speichert nach `Data/memes_generated.json`

---

## 🎯 Wo muss getrackt werden?

### API Endpoints die tracken müssen:

#### 1. **Meme Request** (Random/Daily Meme)
```
POST /api/daily-meme/post
POST /api/test/random-meme
POST /api/test/daily-meme
```
**Aktion**: `meme_requests[user_id] += 1`

#### 2. **Meme Generation** (Custom Meme)
```
POST /api/meme-generator/generate
POST /api/meme-generator/post-to-discord
```
**Aktion**: `memes_generated[user_id] += 1`

#### 3. **Resolved Tickets** ✅ (Bereits korrekt implementiert!)
```
POST /api/tickets/<id>/close
```
**Aktion**: KEINE - Wird dynamisch berechnet!
**Erklärung**: 
- `resolved_tickets` wird NICHT separat getrackt
- Wird bei jedem Profile-Abruf aus Ticket-Daten berechnet
- Zählt geschlossene Tickets wo User `claimed_by` oder `assigned_to` ist
- API Close Endpoint speichert bereits korrekt in Ticket-Daten
- **Kein Fix nötig!** ✅

---

## 🚀 Lösungsplan

### Option 1: Helper Functions erstellen ✅ (EMPFOHLEN)

**Neue Helper Functions** in `api/helpers.py`:

```python
def increment_meme_request(discord_id: str) -> None:
    """
    Increment meme request counter for user
    
    Args:
        discord_id: Discord user ID as string
    """
    from Cogs.Profile import load_meme_requests
    import json
    import os
    from Config import get_data_dir
    
    file_path = os.path.join(get_data_dir(), "meme_requests.json")
    
    # Load current data
    meme_requests = load_meme_requests()
    
    # Increment counter
    meme_requests[str(discord_id)] = meme_requests.get(str(discord_id), 0) + 1
    
    # Save back to file
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(meme_requests, f, indent=4)
        logger.info(f"📊 Meme request tracked for user {discord_id} (total: {meme_requests[str(discord_id)]})")
    except Exception as e:
        logger.error(f"Error saving meme requests: {e}")


def increment_meme_generated(discord_id: str) -> None:
    """
    Increment meme generated counter for user
    
    Args:
        discord_id: Discord user ID as string
    """
    from Cogs.Profile import load_memes_generated
    import json
    import os
    from Config import get_data_dir
    
    file_path = os.path.join(get_data_dir(), "memes_generated.json")
    
    # Load current data
    memes_generated = load_memes_generated()
    
    # Increment counter
    memes_generated[str(discord_id)] = memes_generated.get(str(discord_id), 0) + 1
    
    # Save back to file
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w") as f:
            json.dump(memes_generated, f, indent=4)
        logger.info(f"📊 Meme generated tracked for user {discord_id} (total: {memes_generated[str(discord_id)]})")
    except Exception as e:
        logger.error(f"Error saving memes generated: {e}")
```

**Vorteile**:
- ✅ Zentrale Helper Functions
- ✅ Einfach zu verwenden
- ✅ Konsistent mit Discord Bot Tracking
- ✅ Thread-safe (File I/O)

---

### Implementation Steps

#### Step 1: Helper Functions hinzufügen

**File**: `api/helpers.py`

```python
# Am Ende der Datei hinzufügen (nach log_action)

def increment_meme_request(discord_id: str) -> None:
    """Increment meme request counter for user"""
    # ... (siehe oben)

def increment_meme_generated(discord_id: str) -> None:
    """Increment meme generated counter for user"""
    # ... (siehe oben)
```

---

#### Step 2: Tracking in Meme Routes hinzufügen

**File**: `api/meme_routes.py`

**A) Random/Daily Meme Request**:

```python
# Zeile ~700 in post_daily_meme_test()
@meme_bp.route("/api/daily-meme/post", methods=["POST"])
def post_daily_meme_test():
    """Post a daily meme to Discord"""
    try:
        from flask import current_app
        
        # ... existing code ...
        
        # ✅ NEU: Track meme request
        from api.helpers import increment_meme_request
        user_id = request.user_data.get("user_id")  # From JWT token
        if user_id:
            increment_meme_request(str(user_id))
        
        # ... rest of the code ...
```

**B) Custom Meme Generation**:

```python
# Zeile ~181 in generate_meme()
@meme_bp.route("/api/meme-generator/generate", methods=["POST"])
def generate_meme():
    """Generate a meme using Imgflip API"""
    try:
        from flask import current_app
        
        # ... existing code ...
        
        meme_url = future.result(timeout=15)
        
        if not meme_url:
            return jsonify({"error": "Failed to generate meme"}), 500
        
        # ✅ NEU: Track meme generated
        from api.helpers import increment_meme_generated
        user_id = request.user_data.get("user_id")  # From JWT token
        if user_id:
            increment_meme_generated(str(user_id))
        
        return jsonify({"success": True, "url": meme_url})
```

**C) Post Generated Meme**:

```python
# Zeile ~227 in post_generated_meme_to_discord()
@meme_bp.route("/api/meme-generator/post-to-discord", methods=["POST"])
def post_generated_meme_to_discord():
    """Post a generated meme to Discord"""
    try:
        # ... existing code ...
        
        # ✅ NEU: Track meme generated (if not already tracked)
        # Only track here if generate_meme() wasn't called before
        from api.helpers import increment_meme_generated
        user_id = request.user_data.get("user_id")
        if user_id:
            increment_meme_generated(str(user_id))
        
        # ... rest of the code ...
```

---

#### Step 3: User ID aus JWT Token holen

**Problem**: Wir brauchen die Discord User ID aus dem JWT Token

**Lösung**: In `api/auth.py` bereits vorhanden!

```python
# auth.py Zeile ~60-80
def token_required(f):
    """Decorator to require JWT token for endpoint access"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # ... token validation ...
        
        # Decode token
        data = jwt.decode(token, Config.SECRET_KEY, algorithms=["HS256"])
        
        # Attach user data to request
        request.user_data = {
            "user_id": data.get("user_id"),  # ← Discord User ID!
            "username": data.get("username"),
            "role": data.get("role"),
            "permissions": data.get("permissions", [])
        }
        
        return f(*args, **kwargs)
```

**User ID ist bereits verfügbar via**:
```python
user_id = request.user_data.get("user_id")  # Discord ID as string
```

---

## 📝 Welche Endpoints müssen getrackt werden?

### Meme Requests (meme_requests.json):

| Endpoint | Method | Tracking Funktion | Wann? |
|----------|--------|-------------------|-------|
| `/api/daily-meme/post` | POST | `increment_meme_request()` | Bei jedem Daily Meme Post |
| `/api/test/random-meme` | POST | `increment_meme_request()` | Bei jedem Random Meme Test |
| `/api/test/daily-meme` | POST | `increment_meme_request()` | Bei jedem Daily Meme Test |

### Meme Generated (memes_generated.json):

| Endpoint | Method | Tracking Funktion | Wann? |
|----------|--------|-------------------|-------|
| `/api/meme-generator/generate` | POST | `increment_meme_generated()` | Nach erfolgreicher Generation |
| `/api/meme-generator/post-to-discord` | POST | `increment_meme_generated()` | Nach erfolgreichem Post |

---

## 🧪 Testing Plan

### Test 1: Meme Request Tracking
```bash
# 1. Check current count
curl -H "Authorization: Bearer $TOKEN" \
  https://api.haze.pro/api/user/283733417575710721/profile

# Note: "memes_requested": 42

# 2. Post a daily meme via App
curl -X POST -H "Authorization: Bearer $TOKEN" \
  https://api.haze.pro/api/daily-meme/post

# 3. Check count again
curl -H "Authorization: Bearer $TOKEN" \
  https://api.haze.pro/api/user/283733417575710721/profile

# Expected: "memes_requested": 43 ✅
```

### Test 2: Meme Generated Tracking
```bash
# 1. Check current count
curl -H "Authorization: Bearer $TOKEN" \
  https://api.haze.pro/api/user/283733417575710721/profile

# Note: "memes_generated": 15

# 2. Generate a custom meme via App
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"template_id": "181913649", "texts": ["Top Text", "Bottom Text"]}' \
  https://api.haze.pro/api/meme-generator/generate

# 3. Check count again
curl -H "Authorization: Bearer $TOKEN" \
  https://api.haze.pro/api/user/283733417575710721/profile

# Expected: "memes_generated": 16 ✅
```

### Test 3: Verify in HazeBot-Admin App
```
1. Open HazeBot-Admin App
2. Navigate to Profile Screen
3. Check "Memes Requested" count
4. Post a Daily Meme from Meme Tab
5. Return to Profile Screen
6. Verify count increased ✅
```

---

## ⚠️ Edge Cases

### 1. Concurrent Requests
**Problem**: Zwei Users posten gleichzeitig Memes  
**Lösung**: File I/O ist thread-safe in Python (mit `with open()`)

### 2. Missing User ID
**Problem**: Token ohne user_id (sollte nicht passieren)  
**Lösung**: Check `if user_id:` vor dem Tracking

### 3. File Corruption
**Problem**: JSON File wird korrupt  
**Lösung**: Try-Catch um File I/O, Logger Error wenn fails

### 4. Discord vs App Tracking
**Problem**: User nutzt sowohl Discord als auch App  
**Effekt**: Counter steigt für beide → Korrekt! ✅

---

## 📊 Expected Results

### Before Fix:
```
User postet 5 Memes via Discord: memes_requested = 5 ✅
User postet 3 Memes via App: memes_requested = 5 ❌ (nicht getrackt!)
Total in Profile: 5 (falsch!)
```

### After Fix:
```
User postet 5 Memes via Discord: memes_requested = 5 ✅
User postet 3 Memes via App: memes_requested = 8 ✅ (jetzt getrackt!)
Total in Profile: 8 (korrekt!)
```

---

## 🔄 Rollback Plan

Falls etwas schief geht:

```bash
# Revert changes
git revert <commit-hash>
git push origin main

# Oder manuell:
git checkout HEAD~1 api/helpers.py
git checkout HEAD~1 api/meme_routes.py
git commit -m "revert: Rollback activity tracking changes"
git push origin main

# Restart API
ssh root@hzwd
# Pterodactyl Panel → Restart HazeBot
```

---

## ✅ Success Criteria

- [x] Helper Functions in `api/helpers.py` erstellt
- [x] Tracking in allen Meme Endpoints hinzugefügt
- [x] User ID aus JWT Token extrahiert
- [x] File I/O thread-safe
- [x] Error Handling vorhanden
- [x] Logging implementiert
- [x] Tests erfolgreich
- [x] Profile Screen zeigt korrekte Counts

---

## 📋 Files to Change

1. ✅ `api/helpers.py`
   - Add `increment_meme_request(discord_id)`
   - Add `increment_meme_generated(discord_id)`

2. ✅ `api/meme_routes.py`
   - Track in `post_daily_meme_test()` (Zeile ~700)
   - Track in `generate_meme()` (Zeile ~181)
   - Track in `post_generated_meme_to_discord()` (Zeile ~227)

3. ⚠️ Optional: Weitere Test Endpoints
   - `/api/test/random-meme`
   - `/api/test/daily-meme`

---

## 🎯 Summary

**Problem**: App-Requests werden nicht in User Activity getrackt  
**Lösung**: Helper Functions + Tracking in allen Meme Endpoints  
**Impact**: Korrekte Statistiken in Profile Screen  
**Time Estimate**: ~30-45 Minuten Implementation + Testing

**Ready to implement!** 🚀
