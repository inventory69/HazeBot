"""
Flask API for HazeBot Configuration
Provides REST endpoints to read and update bot configuration
"""

import os
import json
import sys
from pathlib import Path
from flask import Flask, jsonify, request
from flask_cors import CORS
import jwt
from datetime import datetime, timedelta
from functools import wraps

# Add parent directory to path to import Config
sys.path.insert(0, str(Path(__file__).parent.parent))
import Config

app = Flask(__name__)
CORS(app)  # Enable CORS for Flutter web

# Secret key for JWT (should be in environment variable in production)
app.config['SECRET_KEY'] = os.getenv('API_SECRET_KEY', 'dev-secret-key-change-in-production')

# Simple authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Token is invalid'}), 401
        except Exception:
            # Don't expose internal error details to avoid information leakage
            return jsonify({'error': 'Token validation failed'}), 401
        
        return f(*args, **kwargs)
    
    return decorated


@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'timestamp': datetime.now().isoformat()})


@app.route('/api/auth/login', methods=['POST'])
def login():
    """Simple authentication endpoint"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    # Simple check (in production, use proper authentication)
    admin_user = os.getenv('API_ADMIN_USER', 'admin')
    admin_pass = os.getenv('API_ADMIN_PASS', 'changeme')
    
    if username == admin_user and password == admin_pass:
        token = jwt.encode({
            'user': username,
            'exp': datetime.utcnow() + timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({'token': token})
    
    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/api/config', methods=['GET'])
@token_required
def get_config():
    """Get all bot configuration"""
    config_data = {
        # General Settings
        'general': {
            'bot_name': Config.BotName,
            'command_prefix': Config.CommandPrefix,
            'presence_update_interval': Config.PresenceUpdateInterval,
            'message_cooldown': Config.MessageCooldown,
            'fuzzy_matching_threshold': Config.FuzzyMatchingThreshold,
            'prod_mode': Config.PROD_MODE,
        },
        # Logging Configuration
        'logging': {
            'log_level': Config.LogLevel,
            'cog_log_levels': Config.COG_LOG_LEVELS,
        },
        # Discord IDs
        'discord_ids': {
            'guild_id': Config.GUILD_ID,
            'admin_role_id': Config.ADMIN_ROLE_ID,
            'moderator_role_id': Config.MODERATOR_ROLE_ID,
            'normal_role_id': Config.NORMAL_ROLE_ID,
            'member_role_id': Config.MEMBER_ROLE_ID,
            'changelog_role_id': Config.CHANGELOG_ROLE_ID,
            'meme_role_id': Config.MEME_ROLE_ID,
            'interest_role_ids': Config.INTEREST_ROLE_IDS,
            'interest_roles': Config.INTEREST_ROLES,
        },
        # Channels
        'channels': {
            'log_channel_id': Config.LOG_CHANNEL_ID,
            'changelog_channel_id': Config.CHANGELOG_CHANNEL_ID,
            'todo_channel_id': Config.TODO_CHANNEL_ID,
            'rl_channel_id': Config.RL_CHANNEL_ID,
            'meme_channel_id': Config.MEME_CHANNEL_ID,
            'server_guide_channel_id': Config.SERVER_GUIDE_CHANNEL_ID,
            'welcome_rules_channel_id': Config.WELCOME_RULES_CHANNEL_ID,
            'welcome_public_channel_id': Config.WELCOME_PUBLIC_CHANNEL_ID,
            'transcript_channel_id': Config.TRANSCRIPT_CHANNEL_ID,
            'tickets_category_id': Config.TICKETS_CATEGORY_ID,
        },
        # Rocket League
        'rocket_league': {
            'rank_check_interval_hours': Config.RL_RANK_CHECK_INTERVAL_HOURS,
            'rank_cache_ttl_seconds': Config.RL_RANK_CACHE_TTL_SECONDS,
        },
        # Meme Configuration
        'meme': {
            'default_subreddits': Config.DEFAULT_MEME_SUBREDDITS,
            'default_lemmy': Config.DEFAULT_MEME_LEMMY,
            'meme_sources': Config.MEME_SOURCES,
            'templates_cache_duration': Config.MEME_TEMPLATES_CACHE_DURATION,
        },
        # Welcome System
        'welcome': {
            'rules_text': Config.RULES_TEXT,
            'welcome_messages': Config.WELCOME_MESSAGES,
        },
        # Server Guide
        'server_guide': Config.SERVER_GUIDE_CONFIG,
        # Role Display Names
        'role_names': Config.ROLE_NAMES,
    }
    
    return jsonify(config_data)


@app.route('/api/config/general', methods=['GET', 'PUT'])
@token_required
def config_general():
    """Get or update general configuration"""
    if request.method == 'GET':
        return jsonify({
            'bot_name': Config.BotName,
            'command_prefix': Config.CommandPrefix,
            'presence_update_interval': Config.PresenceUpdateInterval,
            'message_cooldown': Config.MessageCooldown,
            'fuzzy_matching_threshold': Config.FuzzyMatchingThreshold,
        })
    
    if request.method == 'PUT':
        data = request.get_json()
        
        # Update configuration (in memory)
        if 'bot_name' in data:
            Config.BotName = data['bot_name']
        if 'command_prefix' in data:
            Config.CommandPrefix = data['command_prefix']
        if 'presence_update_interval' in data:
            Config.PresenceUpdateInterval = int(data['presence_update_interval'])
        if 'message_cooldown' in data:
            Config.MessageCooldown = int(data['message_cooldown'])
        if 'fuzzy_matching_threshold' in data:
            Config.FuzzyMatchingThreshold = float(data['fuzzy_matching_threshold'])
        
        # Save to file
        save_config_to_file()
        
        return jsonify({'success': True, 'message': 'Configuration updated'})


@app.route('/api/config/channels', methods=['GET', 'PUT'])
@token_required
def config_channels():
    """Get or update channel configuration"""
    if request.method == 'GET':
        return jsonify({
            'log_channel_id': Config.LOG_CHANNEL_ID,
            'changelog_channel_id': Config.CHANGELOG_CHANNEL_ID,
            'todo_channel_id': Config.TODO_CHANNEL_ID,
            'rl_channel_id': Config.RL_CHANNEL_ID,
            'meme_channel_id': Config.MEME_CHANNEL_ID,
            'server_guide_channel_id': Config.SERVER_GUIDE_CHANNEL_ID,
            'welcome_rules_channel_id': Config.WELCOME_RULES_CHANNEL_ID,
            'welcome_public_channel_id': Config.WELCOME_PUBLIC_CHANNEL_ID,
            'transcript_channel_id': Config.TRANSCRIPT_CHANNEL_ID,
            'tickets_category_id': Config.TICKETS_CATEGORY_ID,
        })
    
    if request.method == 'PUT':
        data = request.get_json()
        
        # Validate and update channel IDs
        for key, value in data.items():
            key_upper = key.upper()
            if key_upper in Config.CURRENT_IDS:
                try:
                    # Validate Discord snowflake (should be a positive integer)
                    channel_id = int(value)
                    if channel_id <= 0:
                        return jsonify({'error': f'Invalid channel ID for {key}: must be positive'}), 400
                    
                    Config.CURRENT_IDS[key_upper] = channel_id
                    setattr(Config, key_upper, channel_id)
                except (ValueError, TypeError):
                    return jsonify({'error': f'Invalid channel ID for {key}: must be an integer'}), 400
        
        # Save to file
        save_config_to_file()
        
        return jsonify({'success': True, 'message': 'Channel configuration updated'})


@app.route('/api/config/roles', methods=['GET', 'PUT'])
@token_required
def config_roles():
    """Get or update role configuration"""
    if request.method == 'GET':
        return jsonify({
            'admin_role_id': Config.ADMIN_ROLE_ID,
            'moderator_role_id': Config.MODERATOR_ROLE_ID,
            'normal_role_id': Config.NORMAL_ROLE_ID,
            'member_role_id': Config.MEMBER_ROLE_ID,
            'changelog_role_id': Config.CHANGELOG_ROLE_ID,
            'meme_role_id': Config.MEME_ROLE_ID,
            'interest_role_ids': Config.INTEREST_ROLE_IDS,
            'interest_roles': Config.INTEREST_ROLES,
        })
    
    if request.method == 'PUT':
        data = request.get_json()
        
        # Validate and update role IDs
        for key, value in data.items():
            key_upper = key.upper()
            if key_upper in Config.CURRENT_IDS:
                try:
                    # Handle lists (like interest_role_ids) and dicts (like interest_roles)
                    if isinstance(value, list):
                        # Validate each ID in the list
                        validated_list = []
                        for item in value:
                            item_int = int(item)
                            if item_int <= 0:
                                return jsonify({'error': f'Invalid role ID in {key}: must be positive'}), 400
                            validated_list.append(item_int)
                        Config.CURRENT_IDS[key_upper] = validated_list
                        setattr(Config, key_upper, validated_list)
                    elif isinstance(value, dict):
                        # Validate each ID in the dict
                        validated_dict = {}
                        for k, v in value.items():
                            v_int = int(v)
                            if v_int <= 0:
                                return jsonify({'error': f'Invalid role ID for {k} in {key}: must be positive'}), 400
                            validated_dict[k] = v_int
                        Config.CURRENT_IDS[key_upper] = validated_dict
                        setattr(Config, key_upper, validated_dict)
                    else:
                        # Single role ID
                        role_id = int(value)
                        if role_id <= 0:
                            return jsonify({'error': f'Invalid role ID for {key}: must be positive'}), 400
                        Config.CURRENT_IDS[key_upper] = role_id
                        setattr(Config, key_upper, role_id)
                except (ValueError, TypeError):
                    return jsonify({'error': f'Invalid role ID for {key}: must be integer(s)'}), 400
        
        # Save to file
        save_config_to_file()
        
        return jsonify({'success': True, 'message': 'Role configuration updated'})


@app.route('/api/config/meme', methods=['GET', 'PUT'])
@token_required
def config_meme():
    """Get or update meme configuration"""
    if request.method == 'GET':
        return jsonify({
            'default_subreddits': Config.DEFAULT_MEME_SUBREDDITS,
            'default_lemmy': Config.DEFAULT_MEME_LEMMY,
            'meme_sources': Config.MEME_SOURCES,
            'templates_cache_duration': Config.MEME_TEMPLATES_CACHE_DURATION,
        })
    
    if request.method == 'PUT':
        data = request.get_json()
        
        if 'default_subreddits' in data:
            Config.DEFAULT_MEME_SUBREDDITS = data['default_subreddits']
        if 'default_lemmy' in data:
            Config.DEFAULT_MEME_LEMMY = data['default_lemmy']
        if 'meme_sources' in data:
            Config.MEME_SOURCES = data['meme_sources']
        if 'templates_cache_duration' in data:
            Config.MEME_TEMPLATES_CACHE_DURATION = int(data['templates_cache_duration'])
        
        # Save to file
        save_config_to_file()
        
        return jsonify({'success': True, 'message': 'Meme configuration updated'})


@app.route('/api/config/rocket_league', methods=['GET', 'PUT'])
@token_required
def config_rocket_league():
    """Get or update Rocket League configuration"""
    if request.method == 'GET':
        return jsonify({
            'rank_check_interval_hours': Config.RL_RANK_CHECK_INTERVAL_HOURS,
            'rank_cache_ttl_seconds': Config.RL_RANK_CACHE_TTL_SECONDS,
        })
    
    if request.method == 'PUT':
        data = request.get_json()
        
        if 'rank_check_interval_hours' in data:
            Config.RL_RANK_CHECK_INTERVAL_HOURS = int(data['rank_check_interval_hours'])
        if 'rank_cache_ttl_seconds' in data:
            Config.RL_RANK_CACHE_TTL_SECONDS = int(data['rank_cache_ttl_seconds'])
        
        # Save to file
        save_config_to_file()
        
        return jsonify({'success': True, 'message': 'Rocket League configuration updated'})


@app.route('/api/config/welcome', methods=['GET', 'PUT'])
@token_required
def config_welcome():
    """Get or update welcome system configuration"""
    if request.method == 'GET':
        return jsonify({
            'rules_text': Config.RULES_TEXT,
            'welcome_messages': Config.WELCOME_MESSAGES,
        })
    
    if request.method == 'PUT':
        data = request.get_json()
        
        if 'rules_text' in data:
            Config.RULES_TEXT = data['rules_text']
        if 'welcome_messages' in data:
            Config.WELCOME_MESSAGES = data['welcome_messages']
        
        # Save to file
        save_config_to_file()
        
        return jsonify({'success': True, 'message': 'Welcome configuration updated'})


@app.route('/api/config/server_guide', methods=['GET', 'PUT'])
@token_required
def config_server_guide():
    """Get or update server guide configuration"""
    if request.method == 'GET':
        return jsonify(Config.SERVER_GUIDE_CONFIG)
    
    if request.method == 'PUT':
        data = request.get_json()
        Config.SERVER_GUIDE_CONFIG = data
        
        # Save to file
        save_config_to_file()
        
        return jsonify({'success': True, 'message': 'Server guide configuration updated'})


def save_config_to_file():
    """Save current configuration to a JSON file for persistence"""
    config_file = Path(__file__).parent.parent / 'Data' / 'api_config_overrides.json'
    config_file.parent.mkdir(exist_ok=True)
    
    config_data = {
        'general': {
            'bot_name': Config.BotName,
            'command_prefix': Config.CommandPrefix,
            'presence_update_interval': Config.PresenceUpdateInterval,
            'message_cooldown': Config.MessageCooldown,
            'fuzzy_matching_threshold': Config.FuzzyMatchingThreshold,
        },
        'channels': {
            'log_channel_id': Config.LOG_CHANNEL_ID,
            'changelog_channel_id': Config.CHANGELOG_CHANNEL_ID,
            'todo_channel_id': Config.TODO_CHANNEL_ID,
            'rl_channel_id': Config.RL_CHANNEL_ID,
            'meme_channel_id': Config.MEME_CHANNEL_ID,
            'server_guide_channel_id': Config.SERVER_GUIDE_CHANNEL_ID,
            'welcome_rules_channel_id': Config.WELCOME_RULES_CHANNEL_ID,
            'welcome_public_channel_id': Config.WELCOME_PUBLIC_CHANNEL_ID,
            'transcript_channel_id': Config.TRANSCRIPT_CHANNEL_ID,
            'tickets_category_id': Config.TICKETS_CATEGORY_ID,
        },
        'roles': {
            'admin_role_id': Config.ADMIN_ROLE_ID,
            'moderator_role_id': Config.MODERATOR_ROLE_ID,
            'normal_role_id': Config.NORMAL_ROLE_ID,
            'member_role_id': Config.MEMBER_ROLE_ID,
            'changelog_role_id': Config.CHANGELOG_ROLE_ID,
            'meme_role_id': Config.MEME_ROLE_ID,
            'interest_role_ids': Config.INTEREST_ROLE_IDS,
            'interest_roles': Config.INTEREST_ROLES,
        },
        'meme': {
            'default_subreddits': Config.DEFAULT_MEME_SUBREDDITS,
            'default_lemmy': Config.DEFAULT_MEME_LEMMY,
            'meme_sources': Config.MEME_SOURCES,
            'templates_cache_duration': Config.MEME_TEMPLATES_CACHE_DURATION,
        },
        'rocket_league': {
            'rank_check_interval_hours': Config.RL_RANK_CHECK_INTERVAL_HOURS,
            'rank_cache_ttl_seconds': Config.RL_RANK_CACHE_TTL_SECONDS,
        },
        'welcome': {
            'rules_text': Config.RULES_TEXT,
            'welcome_messages': Config.WELCOME_MESSAGES,
        },
        'server_guide': Config.SERVER_GUIDE_CONFIG,
    }
    
    with open(config_file, 'w') as f:
        json.dump(config_data, f, indent=2)


def load_config_from_file():
    """Load configuration overrides from JSON file"""
    config_file = Path(__file__).parent.parent / 'Data' / 'api_config_overrides.json'
    
    if not config_file.exists():
        return
    
    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        # Apply general settings
        if 'general' in config_data:
            for key, value in config_data['general'].items():
                setattr(Config, key.upper() if not key.isupper() else key, value)
        
        # Apply channel settings
        if 'channels' in config_data:
            for key, value in config_data['channels'].items():
                setattr(Config, key.upper(), value)
                Config.CURRENT_IDS[key.upper()] = value
        
        # Apply role settings
        if 'roles' in config_data:
            for key, value in config_data['roles'].items():
                setattr(Config, key.upper(), value)
                Config.CURRENT_IDS[key.upper()] = value
        
        # Apply meme settings
        if 'meme' in config_data:
            for key, value in config_data['meme'].items():
                setattr(Config, key.upper() if not key.isupper() else key, value)
        
        # Apply Rocket League settings
        if 'rocket_league' in config_data:
            for key, value in config_data['rocket_league'].items():
                setattr(Config, key.upper() if not key.isupper() else key, value)
        
        # Apply welcome settings
        if 'welcome' in config_data:
            for key, value in config_data['welcome'].items():
                setattr(Config, key.upper(), value)
        
        # Apply server guide settings
        if 'server_guide' in config_data:
            Config.SERVER_GUIDE_CONFIG = config_data['server_guide']
            
    except Exception as e:
        print(f"Error loading config from file: {e}")


if __name__ == '__main__':
    # Load any saved configuration on startup
    load_config_from_file()
    
    # Get port from environment or use default
    port = int(os.getenv('API_PORT', 5000))
    
    # Check if we're in debug mode (only for development)
    debug_mode = os.getenv('API_DEBUG', 'false').lower() == 'true'
    
    if debug_mode:
        print("WARNING: Running in DEBUG mode. This should NEVER be used in production!")
    
    print(f"Starting HazeBot Configuration API on port {port}")
    print(f"API Documentation: http://localhost:{port}/api/health")
    
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
