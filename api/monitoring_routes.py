"""
Monitoring Routes - Uptime Kuma Proxy
Provides monitoring data to Discord bot from Uptime Kuma status page
"""

from flask import Blueprint, jsonify
import aiohttp
from datetime import datetime
import logging
import Config

logger = logging.getLogger(__name__)

monitoring_bp = Blueprint('monitoring', __name__)

# Uptime Kuma URL from Config/ENV
UPTIME_KUMA_URL = Config.UPTIME_KUMA_URL


@monitoring_bp.route('/api/monitoring/status', methods=['GET'])
async def get_monitoring_status():
    """
    Get all monitor statuses from Uptime Kuma status page
    
    Returns:
        200: {
            "monitors": [
                {
                    "name": "HazeBot API - Health Check",
                    "type": "http",
                    "status": "up",
                    "uptime": 99.93,
                    "category": "core",
                    "last_check": "2025-12-06T18:01:00Z"
                },
                ...
            ],
            "overall_status": "operational",
            "last_update": "2025-12-06T18:01:00Z"
        }
        
        503: Uptime Kuma not configured (UPTIME_KUMA_URL not set)
        502: Uptime Kuma API error
        500: Internal server error
    """
    # Check if Uptime Kuma is configured
    if not UPTIME_KUMA_URL:
        logger.debug("Uptime Kuma not configured (UPTIME_KUMA_URL not set)")
        return jsonify({
            "error": "Uptime Kuma not configured",
            "message": "UPTIME_KUMA_URL environment variable not set"
        }), 503
    
    try:
        # Fetch from Uptime Kuma Status Page (base + heartbeat endpoints)
        async with aiohttp.ClientSession() as session:
            logger.debug(f"Fetching monitoring data from: {UPTIME_KUMA_URL}")
            
            # Fetch base data (monitor list, groups, tags)
            async with session.get(UPTIME_KUMA_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.warning(f"Uptime Kuma returned status {resp.status}")
                    return jsonify({
                        "error": f"Uptime Kuma returned status {resp.status}",
                        "status_code": resp.status
                    }), 502
                
                # Get JSON data (API endpoint returns JSON directly)
                base_data = await resp.json()
                logger.debug(f"Received base data from Uptime Kuma: {list(base_data.keys())}")
            
            # Fetch heartbeat data (real uptime, ping, status)
            heartbeat_url = UPTIME_KUMA_URL.replace("/status-page/", "/status-page/heartbeat/")
            heartbeat_data = {}
            
            try:
                async with session.get(heartbeat_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        heartbeat_data = await resp.json()
                        logger.debug(f"Received heartbeat data: heartbeatList={len(heartbeat_data.get('heartbeatList', {}))}, uptimeList={len(heartbeat_data.get('uptimeList', {}))}")
                    else:
                        logger.warning(f"Heartbeat endpoint returned status {resp.status}, continuing without heartbeat data")
            except Exception as e:
                logger.warning(f"Failed to fetch heartbeat data: {e}, continuing without heartbeat data")
            
            # Parse monitors from response (merge base + heartbeat data)
            monitors = parse_uptime_kuma_data(base_data, heartbeat_data)
            
            if not monitors:
                logger.warning("No monitors found in Uptime Kuma response")
        
        return jsonify({
            "monitors": monitors,
            "overall_status": calculate_overall_status(monitors),
            "last_update": datetime.utcnow().isoformat() + 'Z'
        })
        
    except aiohttp.ClientError as e:
        logger.error(f"Network error fetching Uptime Kuma data: {e}")
        return jsonify({
            "error": "Network error connecting to Uptime Kuma",
            "details": str(e)
        }), 502
        
    except Exception as e:
        logger.error(f"Error fetching Uptime Kuma data: {e}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "details": str(e)
        }), 500


def parse_uptime_kuma_data(base_data: dict, heartbeat_data: dict = None) -> list:
    """
    Parse Uptime Kuma status page data into standardized monitor format
    
    Args:
        base_data: Raw JSON response from Uptime Kuma status page
        heartbeat_data: Optional heartbeat data with real uptime/ping
        
    Returns:
        List of monitor dictionaries
    """
    monitors = []
    
    try:
        # Uptime Kuma status page structure
        # Expected format: {"publicGroupList": [...]}
        public_groups = base_data.get("publicGroupList", [])
        
        # Extract heartbeat and uptime maps if available
        heartbeat_list = heartbeat_data.get("heartbeatList", {}) if heartbeat_data else {}
        uptime_list = heartbeat_data.get("uptimeList", {}) if heartbeat_data else {}
        
        for group in public_groups:
            monitor_list = group.get("monitorList", [])
            
            for monitor in monitor_list:
                # Extract monitor data
                monitor_id = str(monitor.get("id"))
                name = monitor.get("name", "Unknown")
                monitor_type = monitor.get("type", "http")
                
                # Get real uptime from heartbeat data (24h)
                uptime_key = f"{monitor_id}_24"
                uptime_24h = uptime_list.get(uptime_key)
                
                # Convert decimal to percentage (0.9993 -> 99.93)
                if uptime_24h is not None:
                    uptime_24h = round(uptime_24h * 100, 2)
                else:
                    # Fallback to old method (usually 100)
                    uptime_24h = monitor.get("uptime24h", monitor.get("uptime", 100))
                
                # Get heartbeat data for this monitor
                heartbeats = heartbeat_list.get(monitor_id, [])
                
                # Get status from latest heartbeat (status: 1=up, 0=down)
                if heartbeats:
                    latest_heartbeat = heartbeats[-1]  # Last heartbeat = most recent
                    status_code = latest_heartbeat.get("status", 1)
                    last_ping = latest_heartbeat.get("ping")  # Response time in ms
                    last_check = latest_heartbeat.get("time")  # Timestamp
                else:
                    # Fallback to monitor status
                    status_code = monitor.get("status", 1)
                    last_ping = None
                    last_check = None
                
                # Convert status code to string with smart pending logic
                # Status codes: 1=up, 0=down, 2=pending
                if status_code == 1:
                    status = "up"
                elif status_code == 0:
                    status = "down"
                else:  # status_code == 2 (pending)
                    # Smart logic: if uptime is good (>98%), treat as operational with monitoring note
                    if uptime_24h >= 98:
                        status = "up-pending"  # Working but monitoring unclear
                    else:
                        status = "pending"  # Real issue - low uptime
                
                # Calculate average ping from heartbeats (if available)
                avg_ping = None
                if heartbeats:
                    ping_values = [h.get("ping") for h in heartbeats if h.get("ping") is not None]
                    if ping_values:
                        avg_ping = round(sum(ping_values) / len(ping_values), 1)
                
                # Categorize monitor
                category = categorize_monitor(name)
                
                # Get tags for priority
                tags = monitor.get("tags", [])
                tag_names = [tag.get("name", "").lower() for tag in tags if isinstance(tag, dict)]
                
                # Determine priority from tags
                if "critical" in tag_names:
                    priority = "critical"
                elif "high" in tag_names:
                    priority = "high"
                elif "medium" in tag_names:
                    priority = "medium"
                else:
                    priority = "low"
                
                monitors.append({
                    "id": monitor_id,
                    "name": name,
                    "type": monitor_type,
                    "status": status,
                    "uptime": uptime_24h,
                    "ping": last_ping,
                    "avg_ping": avg_ping,
                    "category": category,
                    "priority": priority,
                    "tags": tag_names,
                    "last_check": last_check or datetime.utcnow().isoformat() + 'Z'
                })
        
        logger.debug(f"Parsed {len(monitors)} monitors from Uptime Kuma")
        
    except Exception as e:
        logger.error(f"Error parsing Uptime Kuma data: {e}", exc_info=True)
    
    return monitors


def categorize_monitor(name: str) -> str:
    """
    Categorize monitor based on name
    
    Args:
        name: Monitor name (e.g., "HazeBot API - Health Check")
        
    Returns:
        Category: "core", "features", "frontend", or "other"
    """
    name_lower = name.lower()
    
    # Check against configured categories
    for category, keywords in Config.UPTIME_KUMA_MONITORS.items():
        for keyword in keywords:
            if keyword.lower() in name_lower:
                return category
    
    return "other"


def calculate_overall_status(monitors: list) -> str:
    """
    Calculate overall system status from monitors
    
    Args:
        monitors: List of monitor data
        
    Returns:
        Status string: "operational", "degraded", "down", or "unknown"
    """
    if not monitors:
        return "unknown"
    
    # Count monitors by status
    down_count = sum(1 for m in monitors if m.get("status") == "down")
    # Only count pending with low uptime as degraded
    pending_with_low_uptime = sum(1 for m in monitors 
                                   if m.get("status") == "pending" 
                                   and m.get("uptime", 100) < 98)
    
    # Determine overall status
    # Note: "up-pending" is treated as operational (monitoring issue, not service issue)
    if down_count > 0:
        return "down"
    elif pending_with_low_uptime > 0:
        return "degraded"
    else:
        return "operational"
