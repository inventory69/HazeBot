#!/usr/bin/env python3
"""
Reprocess Analytics Data
Rebuilds user_stats and daily_stats from existing session data
Usage: python3 analytics/reprocess_analytics.py [--data-dir Data]
"""

import sys
from pathlib import Path
import argparse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.analytics import AnalyticsAggregator


def load_prod_mode():
    """Load PROD_MODE from .env file"""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("PROD_MODE="):
                        value = line.split("=", 1)[1].strip().strip('"').strip("'")
                        return value.lower() == "true"
        except Exception as e:
            print(f"⚠️  Warning: Could not read .env: {e}")
    return False


def main():
    parser = argparse.ArgumentParser(description="Reprocess analytics data")
    parser.add_argument(
        "--data-dir",
        type=str,
        help="Data directory (default: auto-detect from PROD_MODE)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("📊 Analytics Data Reprocessing Tool")
    print("=" * 60)

    # Determine data directory
    if args.data_dir:
        data_dir = args.data_dir
        prod_mode = data_dir == "Data"
        print("\n🔧 Mode: Manual override")
    else:
        prod_mode = load_prod_mode()
        data_dir = "Data" if prod_mode else "TestData"
        print(f"\n🔧 Mode: {'PRODUCTION' if prod_mode else 'DEVELOPMENT'} (from .env)")

    # Determine analytics file path
    analytics_file = Path(__file__).parent.parent / data_dir / "app_analytics.json"

    print(f"📂 Data Directory: {data_dir}/")
    print(f"📁 Analytics File: {analytics_file}")

    if not analytics_file.exists():
        print("\n❌ Error: Analytics file not found!")
        print(f"   Expected: {analytics_file}")
        print("\n💡 Tip: Make sure the bot has created some analytics data first.")
        return 1

    print(f"\n✅ Found analytics file ({analytics_file.stat().st_size:,} bytes)")

    # Load analytics
    print("\n🔄 Loading analytics data...")
    analytics = AnalyticsAggregator(analytics_file)

    print(f"   📦 Sessions loaded: {len(analytics.data['sessions'])}")
    print(f"   👥 User stats (before): {len(analytics.data['user_stats'])}")
    print(f"   📅 Daily stats (before): {len(analytics.data['daily_stats'])}")

    if len(analytics.data["sessions"]) == 0:
        print("\n⚠️  No sessions found to process!")
        return 0

    # Reprocess
    print("\n⚙️  Reprocessing all sessions...")
    result = analytics.reprocess_all_sessions()

    print("\n" + "=" * 60)
    print("✅ Reprocessing Complete!")
    print("=" * 60)
    print(f"📊 Sessions processed: {result['sessions_processed']}")
    print(f"👥 Total users: {result['total_users']}")
    print(f"📅 Total days: {result['total_days']}")

    # Show sample of daily stats
    if analytics.data["daily_stats"]:
        print("\n📅 Daily Stats Summary:")
        sorted_dates = sorted(analytics.data["daily_stats"].keys(), reverse=True)
        for date in sorted_dates[:7]:  # Last 7 days
            stats = analytics.data["daily_stats"][date]
            print(f"   {date}:")
            print(f"      Users: {len(stats['unique_users'])}")
            print(f"      Sessions: {stats['total_sessions']}")
            print(f"      Actions: {stats['total_actions']}")
            print(f"      Avg Duration: {stats['avg_session_duration']:.2f} min")

    # Show user stats summary
    if analytics.data["user_stats"]:
        print("\n👥 User Stats Summary:")
        for discord_id, user in list(analytics.data["user_stats"].items())[:5]:
            print(f"   {user['username']}:")
            print(f"      Total Sessions: {user['total_sessions']}")
            print(f"      Total Time: {user['total_time_minutes']:.2f} min")
            print(f"      Avg Duration: {user['avg_session_duration']:.2f} min")
            print(f"      Devices: {len(user['device_history'])}")

    print("\n💾 Data saved to:", analytics_file)
    print("🎉 Done! Refresh your analytics dashboard to see updated data.")
    print("\n📊 View dashboard: python3 analytics/view_analytics.py --host 0.0.0.0 --port 8089 --no-browser")

    return 0


if __name__ == "__main__":
    sys.exit(main())
