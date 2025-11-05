# HazeBot Configuration API

REST API for configuring the HazeBot Discord bot through a web interface.

## Features

- JWT-based authentication
- Full CRUD operations for all bot configuration
- CORS enabled for Flutter web interface
- Persistent configuration storage

## Installation

```bash
pip install -r api_requirements.txt
```

## Environment Variables

Add these to your `.env` file:

```env
# API Configuration
API_PORT=5000
API_SECRET_KEY=your-secret-key-here
API_ADMIN_USER=admin
API_ADMIN_PASS=your-secure-password
```

## Running the API

```bash
cd api
python app.py
```

The API will be available at `http://localhost:5000`

## API Endpoints

### Authentication

#### POST /api/auth/login
Login and receive JWT token.

**Request:**
```json
{
  "username": "admin",
  "password": "your-password"
}
```

**Response:**
```json
{
  "token": "eyJ..."
}
```

### Configuration Endpoints

All configuration endpoints require authentication. Include the token in the Authorization header:
```
Authorization: Bearer <token>
```

#### GET /api/health
Health check endpoint (no auth required)

#### GET /api/config
Get all bot configuration

#### GET/PUT /api/config/general
Get or update general bot settings:
- bot_name
- command_prefix
- presence_update_interval
- message_cooldown
- fuzzy_matching_threshold

#### GET/PUT /api/config/channels
Get or update channel IDs:
- log_channel_id
- changelog_channel_id
- todo_channel_id
- rl_channel_id
- meme_channel_id
- server_guide_channel_id
- welcome_rules_channel_id
- welcome_public_channel_id
- transcript_channel_id
- tickets_category_id

#### GET/PUT /api/config/roles
Get or update role IDs:
- admin_role_id
- moderator_role_id
- normal_role_id
- member_role_id
- changelog_role_id
- meme_role_id
- interest_role_ids
- interest_roles

#### GET/PUT /api/config/meme
Get or update meme system configuration:
- default_subreddits
- default_lemmy
- meme_sources
- templates_cache_duration

#### GET/PUT /api/config/rocket_league
Get or update Rocket League configuration:
- rank_check_interval_hours
- rank_cache_ttl_seconds

#### GET/PUT /api/config/welcome
Get or update welcome system configuration:
- rules_text
- welcome_messages

#### GET/PUT /api/config/server_guide
Get or update server guide configuration

## Example Usage

```python
import requests

# Login
response = requests.post('http://localhost:5000/api/auth/login', json={
    'username': 'admin',
    'password': 'your-password'
})
token = response.json()['token']

# Get configuration
headers = {'Authorization': f'Bearer {token}'}
config = requests.get('http://localhost:5000/api/config', headers=headers).json()

# Update general settings
requests.put('http://localhost:5000/api/config/general', 
    headers=headers,
    json={'bot_name': 'New Bot Name'}
)
```

## Security Notes

- Change default credentials in production
- Use HTTPS in production
- Store API_SECRET_KEY securely
- Implement rate limiting for production use
