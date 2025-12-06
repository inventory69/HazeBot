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
        # Fetch from Uptime Kuma Status Page
        async with aiohttp.ClientSession() as session:
            logger.debug(f"Fetching monitoring data from: {UPTIME_KUMA_URL}")
            
            async with session.get(UPTIME_KUMA_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    logger.warning(f"Uptime Kuma returned status {resp.status}")
                    return jsonify({
                        "error": f"Uptime Kuma returned status {resp.status}",
                        "status_code": resp.status
                    }), 502
                
                # Get JSON data
                content_type = resp.headers.get('Content-Type', '')
                if 'application/json' not in content_type:
                    logger.warning(f"Uptime Kuma returned unexpected content type: {content_type}")
                    return jsonify({
                        "error": "Uptime Kuma did not return JSON",
                        "content_type": content_type
                    }), 502
                
                data = await resp.json()
                logger.debug(f"Received data from Uptime Kuma: {list(data.keys())}")
                
                # Parse monitors from response
                monitors = parse_uptime_kuma_data(data)
                
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


def parse_uptime_kuma_data(data: dict) -> list:
    """
    Parse Uptime Kuma status page data into standardized monitor format
    
    Args:
        data: Raw JSON response from Uptime Kuma status page
        
    Returns:
        List of monitor dictionaries
    """
    monitors = []
    
    try:
        # Uptime Kuma status page structure
        # Expected format: {"publicGroupList": [...]}
        public_groups = data.get("publicGroupList", [])
        
        for group in public_groups:
            monitor_list = group.get("monitorList", [])
            
            for monitor in monitor_list:
                # Extract monitor data
                name = monitor.get("name", "Unknown")
                monitor_type = monitor.get("type", "http")
                
                # Get uptime (24h, 30d, etc.)
                uptime_24h = monitor.get("uptime24h", monitor.get("uptime", 100))
                
                # Status: up (1), down (0), pending (2)
                status_code = monitor.get("status", 1)
                status = "up" if status_code == 1 else "down" if status_code == 0 else "pending"
                
                # Categorize monitor
                category = categorize_monitor(name)
                
                monitors.append({
                    "name": name,
                    "type": monitor_type,
                    "status": status,
                    "uptime": uptime_24h,
                    "category": category,
                    "last_check": datetime.utcnow().isoformat() + 'Z'
                })
        
        logger.info(f"Parsed {len(monitors)} monitors from Uptime Kuma")
        
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
    pending_count = sum(1 for m in monitors if m.get("status") == "pending")
    
    # Determine overall status
    if down_count > 0:
        return "down"
    elif pending_count > 0:
        return "degraded"
    else:
        return "operational"
