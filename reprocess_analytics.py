#!/usr/bin/env python3
"""
Reprocess Analytics Data
Rebuilds user_stats and daily_stats from existing session data
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from api.analytics import AnalyticsAggregator
import Config

def main():
    print("=" * 60)
    print("📊 Analytics Data Reprocessing Tool")
    print("=" * 60)
    
    # Determine analytics file path based on PROD_MODE
    analytics_file = Path(Config.DATA_DIR) / "app_analytics.json"
    
    print(f"\n🔧 Mode: {'PRODUCTION' if Config.PROD_MODE else 'DEVELOPMENT'}")
    print(f"📂 Data Directory: {Config.DATA_DIR}/")
    print(f"📁 Analytics File: {analytics_file}")
    
    if not analytics_file.exists():
        print(f"\n❌ Error: Analytics file not found!")
        print(f"   Expected: {analytics_file}")
        return 1
    
    print(f"\n✅ Found analytics file ({analytics_file.stat().st_size:,} bytes)")
    
    # Load analytics
    print("\n🔄 Loading analytics data...")
    analytics = AnalyticsAggregator(analytics_file)
    
    print(f"   📦 Sessions loaded: {len(analytics.data['sessions'])}")
    print(f"   👥 User stats (before): {len(analytics.data['user_stats'])}")
    print(f"   📅 Daily stats (before): {len(analytics.data['daily_stats'])}")
    
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
    if analytics.data['daily_stats']:
        print("\n📅 Daily Stats Summary:")
        sorted_dates = sorted(analytics.data['daily_stats'].keys(), reverse=True)
        for date in sorted_dates[:7]:  # Last 7 days
            stats = analytics.data['daily_stats'][date]
            print(f"   {date}:")
            print(f"      Users: {len(stats['unique_users'])}")
            print(f"      Sessions: {stats['total_sessions']}")
            print(f"      Actions: {stats['total_actions']}")
            print(f"      Avg Duration: {stats['avg_session_duration']:.2f} min")
    
    print("\n💾 Data saved to:", analytics_file)
    print("🎉 Done! Refresh your analytics dashboard to see updated data.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
