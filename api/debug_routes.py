"""
Debug and error reporting routes for Flutter app
Allows user-consented error reports to be sent to backend logs
"""

from flask import Blueprint, request, jsonify
import logging

logger = logging.getLogger(__name__)

debug_bp = Blueprint("debug", __name__)


@debug_bp.route("/api/debug/error-report", methods=["POST"])
def receive_error_report():
    """
    Receive error report from Flutter frontend (user-consented only)
    
    Expected JSON:
    {
        "user_consented": true,
        "error": {
            "message": "Exception: Something went wrong",
            "type": "Exception",
            "stackTrace": "...",
            "timestamp": "2025-12-07T15:30:00.000Z"
        },
        "context": {
            "screen": "UserTicketsScreen",
            "action": "closeTicket",
            "ticket_id": "abc-123",
            ...additional context
        },
        "logs": [
            {"level": "info", "message": "Action started", "timestamp": "..."},
            {"level": "error", "message": "Error occurred", "timestamp": "..."}
        ],
        "device": {
            "platform": "Android",
            "version": "14",
            "app_version": "2025.12.07+123"
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data or "error" not in data:
            return jsonify({"error": "Missing error field"}), 400
        
        # Verify user consent
        if not data.get("user_consented", False):
            return jsonify({"error": "User consent required"}), 400
        
        # Extract error details
        error_info = data.get("error", {})
        error_message = error_info.get("message", "Unknown error")
        error_type = error_info.get("type", "Unknown")
        error_trace = error_info.get("stackTrace", "")
        error_timestamp = error_info.get("timestamp", "")
        
        # Extract context
        context = data.get("context", {})
        context_str = " | ".join([f"{k}={v}" for k, v in context.items()]) if context else "No context"
        
        # Extract device info
        device = data.get("device", {})
        platform = device.get('platform', 'Unknown')
        version = device.get('version', '')
        app_version = device.get('app_version', 'Unknown')
        device_str = f"{platform} {version} | App: {app_version}"
        
        # Log error report header
        logger.error("=" * 80)
        logger.error("[FLUTTER ERROR REPORT] User-consented error report received")
        logger.error(f"[FLUTTER ERROR REPORT] Error: {error_type}: {error_message}")
        logger.error(f"[FLUTTER ERROR REPORT] Context: {context_str}")
        logger.error(f"[FLUTTER ERROR REPORT] Device: {device_str}")
        logger.error(f"[FLUTTER ERROR REPORT] Time: {error_timestamp}")
        
        # Log the trace leading to error
        logs = data.get("logs", [])
        if logs:
            logger.error(f"[FLUTTER ERROR REPORT] Log trace ({len(logs)} entries):")
            for idx, log_entry in enumerate(logs, 1):
                level = log_entry.get("level", "info").upper()
                message = log_entry.get("message", "")
                timestamp = log_entry.get("timestamp", "")
                logger.error(f"[FLUTTER ERROR REPORT]   [{idx}] [{level}] {message} | {timestamp}")
        
        # Log stack trace if available
        if error_trace:
            logger.error("[FLUTTER ERROR REPORT] Stack trace:")
            for line in error_trace.split('\n'):
                if line.strip():
                    logger.error(f"[FLUTTER ERROR REPORT]   {line}")
        
        logger.error("=" * 80)
        
        return jsonify({"status": "report_received", "thank_you": True}), 200
        
    except Exception as e:
        logger.error(f"[FLUTTER ERROR REPORT] Error processing error report: {e}")
        return jsonify({"error": "Internal error"}), 500
