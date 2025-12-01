# GitHub Copilot Code Review Instructions - HazeBot

## Review Philosophy
- Only comment when you have HIGH CONFIDENCE (>80%) that an issue exists
- Be concise: one sentence per comment when possible
- Focus on actionable feedback, not observations
- When reviewing text, only comment on clarity issues if the text is genuinely confusing or could lead to errors. "Could be clearer" is not the same as "is confusing" - stay silent unless HIGH confidence it will cause problems

## Priority Areas (Review These)

### Security & Safety
- Command injection risks (shell commands, user input)
- Path traversal vulnerabilities
- Credential exposure or hardcoded secrets (Config.py should NEVER be committed)
- Missing input validation on external data (Discord messages, API requests)
- JWT token validation and expiration handling
- Missing `@token_required` decorator on API endpoints
- SQL injection risks (even with SQLite)
- Improper error handling that could leak sensitive info (Discord tokens, API keys)
- Environment variables not properly loaded from `.env`

### Correctness Issues
- Logic errors that could cause exceptions or incorrect behavior
- Race conditions in async Discord.py code
- Resource leaks (Discord connections, database connections, file handles)
- Incorrect error propagation (bare `except:` without logging)
- Discord.py async/await misuse (`asyncio.run_coroutine_threadsafe` for Flask threads)
- Missing `if mounted:` checks before `setState()` in async callbacks
- Bot not properly handling Discord reconnects or rate limits
- Missing checks for `bot.get_cog()` returning None
- API endpoints not checking if bot instance exists
- Timeout handling for long-running operations (>45s for APIServer reload)
- Platform parameter being None in Rocket League stats (must validate before `.lower()`)

### Architecture & Patterns
- Code that violates modular Blueprint architecture (should not add endpoints directly to app.py)
- Missing error handling in API endpoints (should return proper JSON error responses)
- Async/await misuse or blocking operations in Discord event loop
- API endpoints not using Dependency Injection pattern (should receive dependencies via `init_*()`)
- Direct imports of global variables instead of via dependency injection
- Code duplication between Bot Commands and API endpoints (should reuse Bot functions)
- Missing logging with proper COG_PREFIXES (should use `logger` not `print()`)
- New API endpoints not registered in correct Blueprint module
- Helper functions not in `helpers.py` (should use `helpers_module`)
- Decorators not passed via `decorator_module` namespace

## Project-Specific Context

### Backend (Python/Discord.py/Flask)
- **Technology**: Python 3.11+, discord.py 2.x, Flask, JWT Authentication
- **Architecture**: Modular Blueprint-based API (refactored from 6500 → 301 lines main app)
- **Core Files**:
  - `Main.py` - Discord Bot standalone
  - `start_with_api.py` - Bot with APIServer Cog (Port 5070)
  - `api/app.py` - Flask main app (Blueprint registration only)
  - `Config.py` - Bot configuration (NEVER commit, use `.env`)
  - `Cogs/` - Discord Bot commands (modulares Cog-System)
  - `api/*.py` - Blueprint-Module für API routes

- **Error Handling**: 
  - Always use try-except with proper logging
  - API endpoints return `jsonify({"error": "message"})` with HTTP status codes
  - Bot commands send error embeds to Discord
  
- **Async Patterns**: 
  - Bot uses `@commands.command()` and `@app_commands.command()`
  - API uses `asyncio.run_coroutine_threadsafe(coro, bot.loop)` to call Bot functions
  - Always add timeout (10s standard, 45s for APIServer reload)

- **Authentication**:
  - All API endpoints need `@token_required` decorator
  - Admin-only endpoints need `@require_permission("admin_panel")`
  - JWT tokens with session tracking in `active_sessions`
  
- **Logging**: 
  - Use `Utils.Logger` with COG_PREFIXES
  - NO `print()` statements in production code
  - API endpoints use `helpers_module.log_api_call()`

- **Config Management**:
  - Never edit Config.py directly
  - Use `ConfigLoader.save_config()` for persistent changes
  - API config endpoints use `helpers_module.get_config_field()` and `set_config_field()`

- **Blueprint Pattern** (Version 3.8):
  ```python
  # New Blueprint module: api/feature_routes.py
  def init_feature_routes(app, config, logger, decorator_module, helpers_module):
      bp = Blueprint('feature', __name__, url_prefix='/api/feature')
      token_required = decorator_module.token_required
      
      @bp.route('/endpoint', methods=['GET'])
      @token_required
      def get_endpoint():
          try:
              helpers_module.log_api_call("GET /api/feature/endpoint")
              # Implementation
              return jsonify({"success": True})
          except Exception as e:
              logger.error(f"Error: {e}")
              return jsonify({"error": str(e)}), 500
      
      app.register_blueprint(bp)
  ```

- **Cog Protection**:
  - CogManager: CANNOT be unloaded/reloaded (CRITICAL)
  - APIServer: CANNOT be unloaded (only reload), returns 403

### Code Quality
- **Linting**: Use `ruff check --fix .` and `ruff format .`
- **Type Hints**: Always use type hints in function signatures
- **No Code Duplication**: Reuse existing Bot functions, don't duplicate logic
- **No Bare Excepts**: Always catch specific exceptions or log generic ones

## CI Pipeline Context

**Important**: Reviews happen before tests run. Do not flag issues that automated checks will catch.

### What Our Checks Do

**Python checks** (currently manual, should be automated):
- `ruff check --fix .` - Linting and auto-fix
- `ruff format .` - Code formatting
- Manual testing with `python start_with_api.py`
- API endpoint testing via Postman or `test_api_endpoints.py`

**Key setup**:
- Uses virtual environment (`.venv`)
- Loads environment variables from `.env` (never committed)
- Config.py contains secrets (never committed)
- Firebase credentials in `firebase-credentials.json` (never committed)

**Testing strategy**:
- Test on `testrefactor` branch first
- Merge to `main` after verification
- Manual rollback via backup files if needed (e.g., `app.py.backup-YYYYMMDD-HHMMSS`)

## Skip These (Low Value)

Do not comment on:
- **Style/formatting** - ruff handles this
- **Missing dependencies** - requirements.txt handles this
- **Minor naming suggestions** - unless truly confusing
- **Suggestions to add comments** - for self-documenting code
- **Refactoring suggestions** - unless there's a clear bug or maintainability issue
- **Multiple issues in one comment** - choose the single most critical issue
- **Logging suggestions** - unless for errors or security events (we have enough logging)
- **Pedantic accuracy in text** - unless it would cause actual confusion or errors

## Response Format

When you identify an issue:
1. **State the problem** (1 sentence)
2. **Why it matters** (1 sentence, only if not obvious)
3. **Suggested fix** (code snippet or specific action)

Example:
```
This endpoint is missing @token_required decorator. Add it before the route decorator to require authentication.
```

## When to Stay Silent

If you're uncertain whether something is an issue, don't comment. False positives create noise and reduce trust in the review process.

## Project Standards (from AI_PROJECT_INSTRUCTIONS.md)

### Code-Wiederverwendung
- ALWAYS reuse existing Bot functions (e.g., `DailyMeme.fetch_reddit_meme()`)
- API endpoints should wrap Bot functions, not duplicate logic
- Use `asyncio.run_coroutine_threadsafe()` to call async Bot functions from Flask

### API Development (Modular Blueprint Architecture)
- **NEW Endpoints**: Add to appropriate Blueprint module (e.g., `meme_routes.py` for Meme features)
- **Blueprint Pattern**: Always use `init_*()` function with Dependency Injection
- **Dependencies**: Pass via `init_*()` parameters, NOT global imports
- **Decorators**: Pass via `decorator_module` namespace (token_required, require_permission)
- **Helpers**: Pass via `helpers_module` (log_api_call, get_config_field, etc.)
- **ALWAYS** secure API endpoints with `@token_required`
- **ALWAYS** add permission checks for Admin-Only features (`@require_permission`)
- **ALWAYS** handle errors in API calls (try/catch)
- **ALWAYS** track sessions in `@token_required` Decorator
- **Blueprint Registration**: Register in `app.py` following established pattern
- **Module Size**: Keep individual Blueprint files < 1000 lines (split if larger)

### Recent Bug Fixes to Remember
- **Rocket League Stats**: Always check if `platform` is not None before calling `.lower()` (Bug fixed 29.11.2025)
- **APIServer Reload**: Needs 45s timeout (operation takes ~27s)
- **Session Management**: Logout endpoint must remove session immediately
- **Token Refresh**: Uses proactive refresh with 5-min buffer

### Files to NEVER Commit
- `Config.py` - Contains Discord tokens and API keys
- `.env` - Contains environment variables
- `firebase-credentials.json` - Contains Firebase credentials
- `*.log` - Log files
- `__pycache__/` - Python cache
- `.venv/` or `venv/` - Virtual environment
