#!/usr/bin/env python3
"""
Performance test for analytics system

Tests:
1. Load test with 1k, 10k, 50k sessions
2. Benchmark read operations (cached vs uncached)
3. Benchmark write operations (batch vs real-time)
4. Memory usage analysis

Usage:
  python3 analytics/test_performance.py              # Uses TestData (local dev)
  python3 analytics/test_performance.py --prod       # Uses Data (production)
"""

import json
import time
import tempfile
from pathlib import Path
import uuid
from datetime import datetime, timedelta
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.analytics import AnalyticsAggregator


# Detect PROD_MODE from environment
def get_data_dir():
    """Determine data directory based on PROD_MODE"""
    # Check .env file
    env_file = Path(__file__).parent.parent / ".env"
    prod_mode = False

    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if line.strip().startswith("PROD_MODE="):
                    value = line.split("=", 1)[1].strip().lower()
                    prod_mode = value in ("true", "1", "yes")
                    break

    # Check command line args
    if "--prod" in sys.argv:
        prod_mode = True

    data_dir = "Data" if prod_mode else "TestData"
    print(f"ℹ️  Using data directory: {data_dir}/ (PROD_MODE={prod_mode})")
    return Path(__file__).parent.parent / data_dir


def generate_fake_sessions(count: int) -> list:
    """Generate fake session data for testing"""
    sessions = []
    base_date = datetime.utcnow() - timedelta(days=30)

    users = [f"user_{i}" for i in range(min(count // 10, 1000))]  # 10 sessions per user avg
    endpoints = [
        "gaming_members.get_members",
        "rocket_league.get_stats",
        "meme.get_random",
        "config.get_settings",
        "ticket.create",
        "admin.get_logs",
    ]
    devices = ["Android 13", "iOS 17", "Android 12", "iOS 16"]
    platforms = ["Android", "iOS"]

    for i in range(count):
        user_id = str(uuid.uuid4())
        username = users[i % len(users)]
        started_at = base_date + timedelta(minutes=i * 5)
        ended_at = started_at + timedelta(minutes=5 + (i % 20))
        duration = (ended_at - started_at).total_seconds() / 60

        session = {
            "session_id": str(uuid.uuid4()),
            "discord_id": user_id,
            "username": username,
            "device_info": devices[i % len(devices)],
            "platform": platforms[i % len(platforms)],
            "app_version": "3.9.0",
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat(),
            "duration_minutes": round(duration, 2),
            "ip_address": f"192.168.1.{i % 255}",
            "screens_visited": ["home", "settings"],
            "actions_count": 5 + (i % 50),
            "endpoints_used": {endpoints[i % len(endpoints)]: 3 + (i % 10)},
        }
        sessions.append(session)

    return sessions


def test_load_performance(session_counts: list):
    """Test analytics performance with different session counts"""
    print("\n" + "=" * 70)
    print("📊 LOAD PERFORMANCE TEST")
    print("=" * 70)

    results = {}

    for count in session_counts:
        print(f"\n🧪 Testing with {count:,} sessions...")

        # Create temporary analytics file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_file = Path(f.name)

        try:
            # Generate sessions
            print("  ├─ Generating fake sessions...", end=" ", flush=True)
            start = time.time()
            sessions = generate_fake_sessions(count)
            gen_time = time.time() - start
            print(f"✓ ({gen_time:.2f}s)")

            # Write sessions to file
            print("  ├─ Writing to disk...", end=" ", flush=True)
            start = time.time()
            data = {"sessions": sessions, "daily_stats": {}, "user_stats": {}}
            with open(temp_file, "w") as f:
                json.dump(data, f)
            write_time = time.time() - start
            print(f"✓ ({write_time:.2f}s)")

            # Initialize analytics
            print("  ├─ Loading analytics...", end=" ", flush=True)
            start = time.time()
            analytics = AnalyticsAggregator(temp_file, batch_interval=60, cache_ttl=300)
            load_time = time.time() - start
            print(f"✓ ({load_time:.2f}s)")

            # Test reprocessing
            print("  ├─ Reprocessing aggregations...", end=" ", flush=True)
            start = time.time()
            result = analytics.reprocess_all_sessions()
            reprocess_time = time.time() - start
            print(f"✓ ({reprocess_time:.2f}s)")
            print(f"  │  └─ Users: {result['total_users']}, Days: {result['total_days']}")

            # Test export (uncached)
            print("  ├─ Export (uncached)...", end=" ", flush=True)
            analytics.cache.invalidate()
            start = time.time()
            _export_data = analytics.get_export_data(days=7)
            export_uncached_time = time.time() - start
            print(f"✓ ({export_uncached_time:.2f}s)")

            # Test export (cached)
            print("  ├─ Export (cached)...", end=" ", flush=True)
            start = time.time()
            _export_data = analytics.get_export_data(days=7)
            export_cached_time = time.time() - start
            print(f"✓ ({export_cached_time:.2f}s)")

            # Test summary (uncached)
            print("  ├─ Summary (uncached)...", end=" ", flush=True)
            analytics.cache.invalidate()
            start = time.time()
            _summary = analytics.get_summary_stats()
            summary_uncached_time = time.time() - start
            print(f"✓ ({summary_uncached_time:.2f}s)")

            # Test summary (cached)
            print("  ├─ Summary (cached)...", end=" ", flush=True)
            start = time.time()
            _summary = analytics.get_summary_stats()
            summary_cached_time = time.time() - start
            print(f"✓ ({summary_cached_time:.2f}s)")

            # Calculate speedup
            export_speedup = export_uncached_time / export_cached_time if export_cached_time > 0 else 0
            summary_speedup = summary_uncached_time / summary_cached_time if summary_cached_time > 0 else 0

            print(f"  └─ Cache Speedup: Export {export_speedup:.1f}x, Summary {summary_speedup:.1f}x")

            results[count] = {
                "load_time": load_time,
                "reprocess_time": reprocess_time,
                "export_uncached": export_uncached_time,
                "export_cached": export_cached_time,
                "export_speedup": export_speedup,
                "summary_uncached": summary_uncached_time,
                "summary_cached": summary_cached_time,
                "summary_speedup": summary_speedup,
                "users": result["total_users"],
                "days": result["total_days"],
            }

            analytics.shutdown()

        finally:
            # Cleanup
            if temp_file.exists():
                temp_file.unlink()

    return results


def test_batch_performance():
    """Test batch update performance"""
    print("\n" + "=" * 70)
    print("⚡ BATCH UPDATE PERFORMANCE TEST")
    print("=" * 70)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        temp_file = Path(f.name)

    try:
        # Initialize empty analytics
        analytics = AnalyticsAggregator(temp_file, batch_interval=5, cache_ttl=60)

        # Test 1: Queue 1000 updates
        print("\n🧪 Queueing 1000 session updates...")
        start = time.time()

        for i in range(1000):
            analytics.start_session(
                session_id=f"session_{i}",
                discord_id=f"user_{i % 100}",
                username=f"User{i % 100}",
                device_info="Android 13",
                platform="Android",
                app_version="3.9.0",
                ip_address="127.0.0.1",
            )

            # Add some activity
            for j in range(5):
                analytics.update_session(f"session_{i}", f"endpoint_{j % 3}")

        queue_time = time.time() - start
        queue_size = analytics.update_queue.size()

        print(f"  ├─ Queued {queue_size} updates in {queue_time:.2f}s")
        print(f"  └─ Rate: {queue_size / queue_time:.0f} updates/sec")

        # Test 2: Force flush
        print("\n🧪 Force flushing batch...")
        start = time.time()
        flushed = analytics.force_flush()
        flush_time = time.time() - start

        print(f"  ├─ Flushed {flushed} updates in {flush_time:.2f}s")
        print(f"  ├─ Rate: {flushed / flush_time:.0f} updates/sec")
        print(f"  └─ Total sessions: {len(analytics.data['sessions'])}")

        analytics.shutdown()

        return {
            "queue_count": queue_size,
            "queue_time": queue_time,
            "queue_rate": queue_size / queue_time,
            "flush_count": flushed,
            "flush_time": flush_time,
            "flush_rate": flushed / flush_time,
        }

    finally:
        if temp_file.exists():
            temp_file.unlink()


def print_summary(load_results: dict, batch_results: dict):
    """Print test summary"""
    print("\n" + "=" * 70)
    print("📈 PERFORMANCE SUMMARY")
    print("=" * 70)

    print("\n📊 Load Test Results:")
    print(f"{'Sessions':<15} {'Load':<10} {'Reprocess':<12} {'Cache Speedup':<15}")
    print("-" * 70)
    for count, results in load_results.items():
        print(
            f"{count:>10,} {results['load_time']:>8.2f}s {results['reprocess_time']:>10.2f}s "
            f"{results['export_speedup']:>6.1f}x / {results['summary_speedup']:>6.1f}x"
        )

    print("\n⚡ Batch Update Results:")
    print(f"  Queue Rate:  {batch_results['queue_rate']:>8.0f} updates/sec")
    print(f"  Flush Rate:  {batch_results['flush_rate']:>8.0f} updates/sec")
    print(f"  Flush Time:  {batch_results['flush_time']:>8.2f}s for {batch_results['flush_count']} updates")

    print("\n✅ Key Findings:")
    # Get largest test
    max_sessions = max(load_results.keys())
    max_result = load_results[max_sessions]

    print(f"  • Successfully tested with {max_sessions:,} sessions")
    print(f"  • Load time: {max_result['load_time']:.2f}s")
    print(f"  • Reprocess time: {max_result['reprocess_time']:.2f}s")
    print(
        f"  • Cache speedup: {max_result['export_speedup']:.1f}x (export), "
        f"{max_result['summary_speedup']:.1f}x (summary)"
    )
    print(f"  • Batch queue: {batch_results['queue_rate']:.0f} updates/sec")
    print(f"  • Batch flush: {batch_results['flush_rate']:.0f} updates/sec")

    # Performance targets
    print("\n🎯 Performance Targets:")
    if max_result["load_time"] < 5:
        print("  ✅ Load time < 5s: PASS")
    else:
        print(f"  ❌ Load time < 5s: FAIL ({max_result['load_time']:.2f}s)")

    if max_result["export_speedup"] > 5:
        print(f"  ✅ Cache speedup > 5x: PASS ({max_result['export_speedup']:.1f}x)")
    else:
        print(f"  ❌ Cache speedup > 5x: FAIL ({max_result['export_speedup']:.1f}x)")

    if batch_results["queue_rate"] > 1000:
        print(f"  ✅ Queue rate > 1000/s: PASS ({batch_results['queue_rate']:.0f}/s)")
    else:
        print(f"  ❌ Queue rate > 1000/s: FAIL ({batch_results['queue_rate']:.0f}/s)")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    print("\n🚀 Analytics Performance Test Suite")
    print("=" * 70)

    # Run tests
    load_results = test_load_performance([1000, 10000, 50000])
    batch_results = test_batch_performance()

    # Print summary
    print_summary(load_results, batch_results)

    print("\n✨ All tests completed!\n")
