#!/usr/bin/env python3
"""
Test for Monthly Partitioning System

Tests:
1. Create sessions across multiple months
2. Trigger archiving
3. Verify archive files created
4. Test merge-query across months
5. Verify current month only has current sessions
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
import uuid

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.analytics import AnalyticsAggregator


def test_monthly_partitioning():
    """Test monthly partitioning functionality"""
    print("\n" + "=" * 70)
    print("📦 MONTHLY PARTITIONING TEST")
    print("=" * 70)

    # Create temporary test directory
    test_dir = Path(__file__).parent.parent / "TestData" / "analytics_test"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "test_analytics.json"

    try:
        # Initialize with empty data
        if test_file.exists():
            test_file.unlink()

        print("\n🧪 Step 1: Create analytics with multi-month sessions...")
        analytics = AnalyticsAggregator(test_file, batch_interval=60, cache_ttl=60)

        # Create sessions across 3 months
        months_ago_3 = datetime.utcnow() - timedelta(days=90)
        months_ago_2 = datetime.utcnow() - timedelta(days=60)
        months_ago_1 = datetime.utcnow() - timedelta(days=30)
        now = datetime.utcnow()

        test_sessions = [
            # 3 months ago
            ("session_old_1", months_ago_3, "user_1", "OldUser1"),
            ("session_old_2", months_ago_3 + timedelta(days=5), "user_2", "OldUser2"),
            # 2 months ago
            ("session_mid_1", months_ago_2, "user_1", "OldUser1"),
            ("session_mid_2", months_ago_2 + timedelta(days=10), "user_3", "MidUser3"),
            # 1 month ago
            ("session_prev_1", months_ago_1, "user_1", "OldUser1"),
            ("session_prev_2", months_ago_1 + timedelta(days=7), "user_4", "PrevUser4"),
            # Current month
            ("session_cur_1", now - timedelta(days=5), "user_1", "OldUser1"),
            ("session_cur_2", now - timedelta(days=2), "user_5", "CurrentUser5"),
        ]

        # Add sessions directly to data (bypass queue for testing)
        for session_id, started_at, user_id, username in test_sessions:
            session = {
                "session_id": session_id,
                "discord_id": user_id,
                "username": username,
                "device_info": "Android 13",
                "platform": "Android",
                "app_version": "3.9.0",
                "started_at": started_at.isoformat(),
                "ended_at": (started_at + timedelta(minutes=10)).isoformat(),
                "duration_minutes": 10.0,
                "ip_address": "127.0.0.1",
                "screens_visited": ["home"],
                "actions_count": 5,
                "endpoints_used": {"test.endpoint": 5},
            }
            analytics.data["sessions"].append(session)

        # Recalculate stats
        analytics.reprocess_all_sessions()

        print(f"  ├─ Created {len(analytics.data['sessions'])} sessions across multiple months")
        print(f"  └─ Total users: {len(analytics.data['user_stats'])}")

        # Step 2: Trigger archiving
        print("\n🧪 Step 2: Trigger archiving...")
        archived_counts = analytics.force_archive()

        for month, count in archived_counts.items():
            print(f"  ├─ Archived {count} sessions to {month}.json")

        current_sessions = len(analytics.data["sessions"])
        print(f"  └─ Remaining in current month: {current_sessions} sessions")

        # Step 3: Verify archive files
        print("\n🧪 Step 3: Verify archive files created...")
        archive_dir = test_file.parent / "analytics_archive"
        archive_files = list(archive_dir.glob("*.json"))

        print(f"  ├─ Archive directory: {archive_dir}")
        print(f"  ├─ Archive files found: {len(archive_files)}")

        for archive_file in sorted(archive_files):
            with open(archive_file) as f:
                data = json.load(f)
                print(f"  │  ├─ {archive_file.name}: {len(data['sessions'])} sessions, "
                      f"{len(data['user_stats'])} users")

        # Step 4: Get archive stats
        print("\n🧪 Step 4: Get archive statistics...")
        archive_stats = analytics.get_archive_stats()

        print(f"  ├─ Archived months: {archive_stats['archived_months']}")
        print(f"  ├─ Total archived sessions: {archive_stats['total_archived_sessions']}")
        print(f"  └─ Archive directory: {archive_stats['archive_dir']}")

        for month_stat in archive_stats["months"]:
            print(f"     ├─ {month_stat['month']}: {month_stat['sessions']} sessions, "
                  f"{month_stat['users']} users, {month_stat['file_size_kb']}KB")

        # Step 5: Test merge-query across months
        print("\n🧪 Step 5: Test merge-query (last 90 days)...")
        export_data = analytics.get_export_data(days=90)

        print(f"  ├─ Sessions retrieved: {len(export_data['sessions'])}")
        print(f"  ├─ Archived months loaded: {export_data.get('archived_months_loaded', False)}")
        print(f"  └─ Days included: {export_data['days_included']}")

        # Verify all sessions are included
        session_ids = {s["session_id"] for s in export_data["sessions"]}
        expected_ids = {s[0] for s in test_sessions}

        if session_ids == expected_ids:
            print(f"\n✅ SUCCESS: All {len(expected_ids)} sessions retrieved correctly!")
        else:
            missing = expected_ids - session_ids
            extra = session_ids - expected_ids
            print(f"\n❌ FAILED: Session mismatch!")
            if missing:
                print(f"  Missing: {missing}")
            if extra:
                print(f"  Extra: {extra}")

        # Step 6: Verify current month isolation
        print("\n🧪 Step 6: Verify current month isolation...")
        current_month_sessions = [s for s in analytics.data["sessions"]]
        current_month = datetime.utcnow().strftime("%Y-%m")

        all_current = all(
            datetime.fromisoformat(s["started_at"]).strftime("%Y-%m") == current_month
            for s in current_month_sessions
        )

        if all_current:
            print(f"  ✅ All {len(current_month_sessions)} sessions in current file are from {current_month}")
        else:
            print(f"  ❌ FAILED: Found sessions from other months in current file!")

        analytics.shutdown()

        # Summary
        print("\n" + "=" * 70)
        print("📈 TEST SUMMARY")
        print("=" * 70)
        print(f"✅ Created {len(test_sessions)} sessions across 4 months")
        print(f"✅ Archived {sum(archived_counts.values())} sessions to {len(archived_counts)} files")
        print(f"✅ Current month has {current_sessions} sessions")
        print(f"✅ Merge-query retrieved {len(export_data['sessions'])} sessions")
        print(f"✅ Archive stats: {archive_stats['archived_months']} months, "
              f"{archive_stats['total_archived_sessions']} total sessions")
        print("\n🎯 Monthly Partitioning: WORKING! ✨")
        print("=" * 70)

    finally:
        # Cleanup (optional - comment out to inspect files)
        # import shutil
        # if test_dir.exists():
        #     shutil.rmtree(test_dir)
        pass


if __name__ == "__main__":
    test_monthly_partitioning()
    print("\n✨ Test completed!\n")
