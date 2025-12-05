# Analytics Tools

Advanced analytics system for HazeBot Admin Panel with SQLite database, partitioning, and real-time visualization.

## 📊 Dashboard

Interactive HTML dashboard with real-time analytics, session tracking, and feature usage insights.

**Quick Start:**
```bash
python view_analytics.py
```

Opens dashboard at `http://localhost:8089` with JWT authentication support.

### Features

#### Core Metrics
- **User Analytics** - Total users, active users (7d/30d), new users
- **Session Tracking** - Real-time active sessions, average duration, total actions
- **Platform Stats** - Web, Android, iOS breakdown with version tracking
- **Feature Usage** - Top endpoints, route popularity, API call statistics

#### Advanced Features
- **Active Sessions** - Real-time list with last activity timestamps
- **Session Details** - Individual session drill-down (actions, duration, platform)
- **Peak Hours Analysis** - 24h activity heatmap
- **User Growth Chart** - Daily/weekly trend visualization
- **Device Distribution** - Platform and version breakdown
- **Time Range Filters** - 7d/30d/90d/all time views
- **Auto-Refresh** - Optional 30s updates for live monitoring

#### Charts & Visualizations
- 📈 **User Growth** - Daily active users over time
- 📱 **Platform Distribution** - Web vs Mobile (Android/iOS)
- 🔥 **Top Features** - Most used endpoints and routes
- ⏰ **Peak Usage** - Hour-by-hour activity patterns
- 👥 **Active Sessions** - Real-time session list with details

### Usage

```bash
# Default (port 8089, JWT auth)
python view_analytics.py

# Custom port
python view_analytics.py --port 9000

# Custom host (for network access)
python view_analytics.py --host 0.0.0.0

# No auto-browser
python view_analytics.py --no-browser
```

### Access Control

The dashboard is protected by JWT authentication (admin/mod roles only). See `ANALYTICS_JWT_SETUP.md` for setup instructions.

## 📁 Files

### Dashboard & Server
- **`analytics_dashboard.html`** - Interactive dashboard with Chart.js
- **`view_analytics.py`** - Flask server with API endpoints
- **`login.html`** - JWT authentication login page

### Database & Data Processing
- **`json_to_sqlite.py`** - Migration tool (JSON → SQLite)
- **`reprocess_analytics.py`** - Rebuild analytics from raw sessions

### Backend Integration
- **`../api/analytics.py`** - Session tracking and event logging
- **`../api/analytics_db.py`** - SQLite database operations
- **`../api/analytics_partitioning.py`** - Table partitioning for performance
- **`../api/feature_analytics.py`** - Feature usage tracking

### Testing & Utilities
- **`test_api_endpoints.py`** - API endpoint testing
- **`test_partitioning.py`** - Database partitioning tests
- **`test_performance.py`** - Performance benchmarks

### Documentation
- **`ANALYTICS_JWT_SETUP.md`** - JWT authentication setup guide
- **`DEPLOYMENT_SUMMARY.md`** - Deployment checklist
- **`README.md`** - This file

## 🗄️ Database Structure

Analytics data is stored in **SQLite** with the following tables:

### Core Tables
- **`sessions`** - User sessions (id, user_id, device_info, timestamps)
- **`session_actions`** - Individual actions (session_id, endpoint, timestamp)
- **`active_sessions`** - Real-time session tracking (last_activity, is_active)

### Partitioned Tables (by Month)
- **`sessions_YYYYMM`** - Archived session data
- **`session_actions_YYYYMM`** - Archived action data

### Cache Tables
- **`aggregated_metrics`** - Pre-computed stats for fast queries
- **`daily_metrics`** - Daily rollup data

### Migration
Legacy JSON files (`app_analytics.json`) are automatically migrated to SQLite on first run.

## 🔗 Data Flow

```
User Action → Flask API (analytics.py)
            ↓
    Track Session (analytics_db.py)
            ↓
    SQLite Database (app_analytics.db)
            ↓
    Dashboard API (view_analytics.py)
            ↓
    HTML Dashboard (analytics_dashboard.html)
```

## 🎨 Design

- **Dark Mode** - Modern slate/navy theme (#0f172a, #1e293b, #334155)
- **Responsive** - Optimized for desktop, tablet, and mobile
- **Compact Layout** - Maximum information density
- **Interactive** - Hover tooltips, clickable legends, drill-down views
- **Real-time Updates** - Auto-refresh with visual indicators

## 🔐 Security

- **JWT Authentication** - Admin/mod role required
- **NGINX Integration** - `auth_request` directive for token verification
- **Bitwarden Support** - Password manager auto-fill compatible
- **Session Management** - Secure token storage and validation

## 🚀 API Endpoints

The analytics server provides REST API endpoints:

### Dashboard Data
- `GET /api/stats` - Overview metrics (users, sessions, actions)
- `GET /api/active-sessions` - Real-time active sessions list
- `GET /api/session/<session_id>` - Individual session details
- `GET /api/chart/user-growth` - User growth time series
- `GET /api/chart/devices` - Device distribution data
- `GET /api/chart/features` - Top features usage
- `GET /api/chart/peak-hours` - Hourly activity breakdown

### Filters
All endpoints support `?days=N` parameter (7, 30, 90, or omit for all-time).

## ⚡ Performance

- **Partitioning** - Monthly table partitioning for fast queries
- **Indexing** - Optimized indexes on user_id, timestamp, session_id
- **Caching** - Aggregated metrics for instant dashboard load
- **Pagination** - Large result sets are paginated

### Benchmarks
- Dashboard load: <100ms (cached metrics)
- Active sessions: <50ms (indexed queries)
- Session details: <20ms (direct lookup)
- Chart data: <200ms (pre-aggregated)

## 📝 Notes

- **Production-Ready** - Deployed with JWT auth and NGINX
- **Scalable** - SQLite handles millions of events efficiently
- **Maintainable** - Automated partitioning and cleanup
- **Observable** - Detailed logging and error tracking
- **Documented** - Comprehensive setup guides included

## 🛠️ Maintenance

### Database Cleanup
```bash
# Archive old data (older than 90 days)
python analytics_partitioning.py --archive

# Vacuum database (reclaim space)
sqlite3 ../Data/app_analytics.db "VACUUM;"
```

### Reprocess Data
```bash
# Rebuild all analytics from session data
python reprocess_analytics.py
```

### Migration
```bash
# Migrate legacy JSON to SQLite
python json_to_sqlite.py
```

## 📚 Documentation

### Analytics-Specific
- **Setup**: `ANALYTICS_JWT_SETUP.md` - Complete JWT authentication and deployment guide
- **Deployment**: `DEPLOYMENT_SUMMARY.md` - Quick reference deployment checklist
- **Browser Helper**: `browser_helper.js` - Console helper functions for testing

### Related Documentation
- **API**: `../api/README.md` - Backend API endpoints and WebSocket documentation
- **Main README**: `../README.md` - HazeBot overview and general setup
- **Bot Setup**: `../docs/BOT_SETUP.md` - Discord bot installation guide
