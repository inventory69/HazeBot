"""
Feature Usage Analytics

Tracks which features are actually used, adoption rates, and power users.
Categorizes endpoints into features and provides insights.
"""

import logging
from typing import Dict, Any, List
from collections import defaultdict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# Feature categorization mapping
FEATURE_CATEGORIES = {
    "Gaming Members": [
        "gaming_members.get_members",
        "gaming_members.add_member",
        "gaming_members.remove_member",
        "gaming_members.update_member",
    ],
    "Rocket League": [
        "rocket_league.get_stats",
        "rocket_league.link_account",
        "rocket_league.unlink_account",
        "rocket_league.refresh_stats",
        "rocket_league.get_user_rl_account",
        "rocket_league.get_profile",
    ],
    "Memes": [
        "meme.get_random",
        "meme.get_categories",
        "meme.send_to_discord",
        "meme.favorite",
        "memes.get_latest_memes",
        "memes.upload",
        "memes.vote",
    ],
    "Config": [
        "config.get_settings",
        "config.update_settings",
        "config.get_channels",
        "config.update_channel",
        "config.get_config",
    ],
    "Tickets": [
        "ticket.create",
        "ticket.list",
        "ticket.get",
        "ticket.close",
        "ticket.add_message",
        "tickets.get_tickets",
    ],
    "Admin": [
        "admin.get_logs",
        "admin.get_stats",
        "admin.manage_users",
        "admin.system_status",
        "admin.get_active_sessions",
    ],
    "Notifications": [
        "notification.subscribe",
        "notification.unsubscribe",
        "notification.get_preferences",
        "notifications.get_notifications",
    ],
    "User Profile": [
        "user.get_profile",
        "user.update_profile",
        "user.get_achievements",
        "user.get_gaming_members",
        "user.me",
    ],
    "HazeHub": [
        "hazehub.get_cogs",
        "hazehub.install_cog",
        "hazehub.uninstall_cog",
    ],
    "Community Posts": [
        "community_posts.get_posts",
        "community_posts.create_post",
        "community_posts.update_post",
        "community_posts.delete_post",
        "community_posts.get_post",
        "community_posts.toggle_like_post",
        "community_posts.get_post_likes",
    ],
}


def categorize_endpoint(endpoint: str) -> str:
    """Categorize an endpoint into a feature category"""
    for category, endpoints in FEATURE_CATEGORIES.items():
        if endpoint in endpoints:
            return category
    return "Other"


class FeatureUsageAnalyzer:
    """Analyzes feature usage patterns from analytics data"""

    def __init__(self):
        pass

    def analyze_feature_usage(self, sessions: List[Dict[str, Any]], days: int = 30) -> Dict[str, Any]:
        """
        Analyze feature usage across sessions

        Returns:
        {
            "total_users": int,
            "total_actions": int,
            "features": {
                "Gaming Members": {
                    "total_uses": int,
                    "unique_users": int,
                    "adoption_rate": float (0-1),
                    "avg_uses_per_user": float,
                    "top_users": [(username, count), ...],
                    "endpoints": {endpoint: count}
                },
                ...
            },
            "feature_ranking": [(feature_name, uses), ...],  # sorted by usage
            "power_users": {
                username: {"features_used": [feature_name, ...], "total_actions": int}
            }
        }
        """
        # Filter sessions by date
        cutoff = datetime.utcnow() - timedelta(days=days)
        recent_sessions = [s for s in sessions if datetime.fromisoformat(s["started_at"]) > cutoff]

        if not recent_sessions:
            return self._get_empty_analysis()

        # Track feature usage
        feature_data = defaultdict(
            lambda: {"total_uses": 0, "users": set(), "user_counts": defaultdict(int), "endpoints": defaultdict(int)}
        )

        total_users = set()
        total_actions = 0

        # Process each session
        for session in recent_sessions:
            user_id = session["discord_id"]
            username = session["username"]
            total_users.add(user_id)

            endpoints_used = session.get("endpoints_used", {})
            total_actions += sum(endpoints_used.values())

            # Categorize each endpoint
            for endpoint, count in endpoints_used.items():
                category = categorize_endpoint(endpoint)

                feature_data[category]["total_uses"] += count
                feature_data[category]["users"].add(user_id)
                feature_data[category]["user_counts"][username] += count
                feature_data[category]["endpoints"][endpoint] += count

        # Calculate metrics
        total_unique_users = len(total_users)
        features = {}

        for category, data in feature_data.items():
            unique_users = len(data["users"])
            total_uses = data["total_uses"]
            adoption_rate = unique_users / total_unique_users if total_unique_users > 0 else 0
            avg_uses = total_uses / unique_users if unique_users > 0 else 0

            # Top users for this feature
            top_users = sorted(data["user_counts"].items(), key=lambda x: x[1], reverse=True)[:10]

            features[category] = {
                "total_uses": total_uses,
                "unique_users": unique_users,
                "adoption_rate": round(adoption_rate, 3),
                "avg_uses_per_user": round(avg_uses, 2),
                "top_users": top_users,
                "endpoints": dict(data["endpoints"]),
            }

        # Feature ranking by total uses
        feature_ranking = sorted(
            [(name, stats["total_uses"]) for name, stats in features.items()], key=lambda x: x[1], reverse=True
        )

        # Power users analysis
        power_users = defaultdict(lambda: {"features": set(), "total_actions": 0})

        for session in recent_sessions:
            username = session["username"]
            endpoints_used = session.get("endpoints_used", {})

            for endpoint, count in endpoints_used.items():
                category = categorize_endpoint(endpoint)
                power_users[username]["features"].add(category)
                power_users[username]["total_actions"] += count

        # Convert to sorted list
        power_users_list = {
            username: {
                "features_used": sorted(list(data["features"])),
                "feature_count": len(data["features"]),
                "total_actions": data["total_actions"],
            }
            for username, data in power_users.items()
        }

        # Sort by total actions
        power_users_sorted = dict(
            sorted(power_users_list.items(), key=lambda x: x[1]["total_actions"], reverse=True)[:20]
        )  # Top 20 power users

        return {
            "total_users": total_unique_users,
            "total_actions": total_actions,
            "days_analyzed": days,
            "features": features,
            "feature_ranking": feature_ranking,
            "power_users": power_users_sorted,
            "analysis_date": datetime.utcnow().isoformat(),
        }

    def _get_empty_analysis(self) -> Dict[str, Any]:
        """Return empty analysis structure"""
        return {
            "total_users": 0,
            "total_actions": 0,
            "days_analyzed": 0,
            "features": {},
            "feature_ranking": [],
            "power_users": {},
            "analysis_date": datetime.utcnow().isoformat(),
        }

    def get_feature_comparison(self, sessions: List[Dict[str, Any]], days1: int = 7, days2: int = 30) -> Dict[str, Any]:
        """
        Compare feature usage between two time periods

        Returns comparison metrics showing growth/decline
        """
        analysis1 = self.analyze_feature_usage(sessions, days=days1)
        analysis2 = self.analyze_feature_usage(sessions, days=days2)

        comparison = {}

        for feature_name in set(list(analysis1["features"].keys()) + list(analysis2["features"].keys())):
            stats1 = analysis1["features"].get(feature_name, {"total_uses": 0, "unique_users": 0})
            stats2 = analysis2["features"].get(feature_name, {"total_uses": 0, "unique_users": 0})

            # Calculate growth rate
            uses_growth = 0
            if stats2["total_uses"] > 0:
                uses_growth = ((stats1["total_uses"] - stats2["total_uses"]) / stats2["total_uses"]) * 100

            users_growth = 0
            if stats2["unique_users"] > 0:
                users_growth = ((stats1["unique_users"] - stats2["unique_users"]) / stats2["unique_users"]) * 100

            comparison[feature_name] = {
                f"uses_last_{days1}d": stats1["total_uses"],
                f"uses_last_{days2}d": stats2["total_uses"],
                "uses_growth_pct": round(uses_growth, 1),
                f"users_last_{days1}d": stats1["unique_users"],
                f"users_last_{days2}d": stats2["unique_users"],
                "users_growth_pct": round(users_growth, 1),
            }

        return {
            "period1_days": days1,
            "period2_days": days2,
            "comparison": comparison,
            "analysis_date": datetime.utcnow().isoformat(),
        }
