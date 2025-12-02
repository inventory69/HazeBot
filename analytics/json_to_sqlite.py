"""
JSON to SQLite Migration Script
Migrates existing analytics data from JSON files to SQLite database.

Usage:
    python json_to_sqlite.py [--data-dir DATA_DIR] [--db-path DB_PATH] [--dry-run]
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.analytics_db import AnalyticsDatabase
from Utils.Logger import Logger as logger


def migrate_analytics_data(
    json_file: Path,
    db: AnalyticsDatabase,
    dry_run: bool = False
) -> dict:
    """
    Migrate app_analytics.json to SQLite
    
    Returns:
        Dictionary with migration statistics
    """
    stats = {
        'sessions_migrated': 0,
        'user_stats_migrated': 0,
        'daily_stats_migrated': 0,
        'errors': []
    }
    
    try:
        logger.info(f"📖 Reading {json_file}...")
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Migrate sessions
        sessions = data.get('sessions', [])
        logger.info(f"🔄 Migrating {len(sessions)} sessions...")
        
        for session in sessions:
            if dry_run:
                stats['sessions_migrated'] += 1
            else:
                if db.create_session(session):
                    stats['sessions_migrated'] += 1
                else:
                    stats['errors'].append(f"Failed to migrate session {session.get('session_id')}")
        
        # Migrate user stats
        user_stats = data.get('user_stats', {})
        logger.info(f"🔄 Migrating {len(user_stats)} user stats...")
        
        for discord_id, user_data in user_stats.items():
            user_data['discord_id'] = discord_id
            if dry_run:
                stats['user_stats_migrated'] += 1
            else:
                if db.upsert_user_stats(user_data):
                    stats['user_stats_migrated'] += 1
                else:
                    stats['errors'].append(f"Failed to migrate user stats for {discord_id}")
        
        # Migrate daily stats
        daily_stats = data.get('daily_stats', {})
        logger.info(f"🔄 Migrating {len(daily_stats)} daily stats...")
        
        for date, stats_data in daily_stats.items():
            if dry_run:
                stats['daily_stats_migrated'] += 1
            else:
                if db.upsert_daily_stats(date, stats_data):
                    stats['daily_stats_migrated'] += 1
                else:
                    stats['errors'].append(f"Failed to migrate daily stats for {date}")
        
        return stats
        
    except FileNotFoundError:
        logger.error(f"❌ File not found: {json_file}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON in {json_file}: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        raise


def migrate_error_analytics(
    json_file: Path,
    db: AnalyticsDatabase,
    dry_run: bool = False
) -> dict:
    """
    Migrate error_analytics.json to SQLite
    
    Returns:
        Dictionary with migration statistics
    """
    stats = {
        'errors_migrated': 0,
        'errors': []
    }
    
    try:
        if not json_file.exists():
            logger.warning(f"⚠️ Error analytics file not found: {json_file}")
            return stats
        
        logger.info(f"📖 Reading {json_file}...")
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        errors = data.get('errors', {})
        logger.info(f"🔄 Migrating {len(errors)} error signatures...")
        
        total_errors = 0
        for signature, error_group in errors.items():
            occurrences = error_group.get('occurrences', [])
            
            for occurrence in occurrences:
                error_data = {
                    'signature': signature,
                    'error_type': error_group.get('error_type', 'Unknown'),
                    'message': error_group.get('message', ''),
                    'endpoint': error_group.get('endpoint'),
                    'discord_id': occurrence.get('discord_id'),
                    'username': occurrence.get('username'),
                    'occurred_at': occurrence.get('timestamp'),
                    'stack_trace': occurrence.get('stack_trace')
                }
                
                if dry_run:
                    total_errors += 1
                else:
                    if db.create_error_log(error_data):
                        total_errors += 1
                    else:
                        stats['errors'].append(f"Failed to migrate error occurrence {signature}")
        
        stats['errors_migrated'] = total_errors
        return stats
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON in {json_file}: {e}")
        raise
    except Exception as e:
        logger.error(f"❌ Error migration failed: {e}")
        raise


def migrate_archived_data(
    archive_dir: Path,
    db: AnalyticsDatabase,
    dry_run: bool = False
) -> dict:
    """
    Migrate archived monthly JSON files to SQLite
    
    Returns:
        Dictionary with migration statistics
    """
    stats = {
        'files_migrated': 0,
        'sessions_migrated': 0,
        'errors': []
    }
    
    if not archive_dir.exists():
        logger.info(f"ℹ️ No archive directory found: {archive_dir}")
        return stats
    
    archive_files = sorted(archive_dir.glob('*.json'))
    logger.info(f"📦 Found {len(archive_files)} archived files...")
    
    for archive_file in archive_files:
        try:
            logger.info(f"📖 Reading {archive_file.name}...")
            with open(archive_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            sessions = data.get('sessions', [])
            logger.info(f"🔄 Migrating {len(sessions)} sessions from {archive_file.name}...")
            
            for session in sessions:
                if dry_run:
                    stats['sessions_migrated'] += 1
                else:
                    if db.create_session(session):
                        stats['sessions_migrated'] += 1
                    else:
                        stats['errors'].append(f"Failed to migrate archived session from {archive_file.name}")
            
            stats['files_migrated'] += 1
            
        except Exception as e:
            logger.error(f"❌ Failed to migrate {archive_file.name}: {e}")
            stats['errors'].append(f"Failed to migrate {archive_file.name}: {str(e)}")
    
    return stats


def main():
    parser = argparse.ArgumentParser(description='Migrate analytics data from JSON to SQLite')
    parser.add_argument(
        '--data-dir',
        type=str,
        default='Data',
        help='Data directory containing JSON files (default: Data)'
    )
    parser.add_argument(
        '--db-path',
        type=str,
        default='Data/analytics.db',
        help='SQLite database path (default: Data/analytics.db)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Simulate migration without writing to database'
    )
    parser.add_argument(
        '--skip-archives',
        action='store_true',
        help='Skip migrating archived monthly files'
    )
    
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    db_path = Path(args.db_path)
    
    logger.info("=" * 60)
    logger.info("📊 Analytics Migration: JSON → SQLite")
    logger.info("=" * 60)
    logger.info(f"Data directory: {data_dir}")
    logger.info(f"Database path: {db_path}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("")
    
    if args.dry_run:
        logger.info("⚠️ DRY RUN MODE - No data will be written to database")
        logger.info("")
    
    # Initialize database
    db = AnalyticsDatabase(db_path)
    
    # Migrate main analytics file
    analytics_file = data_dir / 'app_analytics.json'
    if analytics_file.exists():
        logger.info("📊 Migrating main analytics data...")
        analytics_stats = migrate_analytics_data(analytics_file, db, args.dry_run)
        logger.info(f"✅ Sessions: {analytics_stats['sessions_migrated']}")
        logger.info(f"✅ User stats: {analytics_stats['user_stats_migrated']}")
        logger.info(f"✅ Daily stats: {analytics_stats['daily_stats_migrated']}")
        if analytics_stats['errors']:
            logger.warning(f"⚠️ Errors: {len(analytics_stats['errors'])}")
        logger.info("")
    else:
        logger.warning(f"⚠️ Analytics file not found: {analytics_file}")
        logger.info("")
    
    # Migrate error analytics
    error_file = data_dir / 'error_analytics.json'
    logger.info("🐛 Migrating error analytics...")
    error_stats = migrate_error_analytics(error_file, db, args.dry_run)
    logger.info(f"✅ Error logs: {error_stats['errors_migrated']}")
    if error_stats['errors']:
        logger.warning(f"⚠️ Errors: {len(error_stats['errors'])}")
    logger.info("")
    
    # Migrate archived data
    if not args.skip_archives:
        archive_dir = data_dir / 'analytics_archive'
        logger.info("📦 Migrating archived data...")
        archive_stats = migrate_archived_data(archive_dir, db, args.dry_run)
        logger.info(f"✅ Files: {archive_stats['files_migrated']}")
        logger.info(f"✅ Archived sessions: {archive_stats['sessions_migrated']}")
        if archive_stats['errors']:
            logger.warning(f"⚠️ Errors: {len(archive_stats['errors'])}")
        logger.info("")
    
    # Optimize database
    if not args.dry_run:
        logger.info("🔧 Optimizing database...")
        db.vacuum()
        
        # Show database size
        db_size_mb = db.get_database_size() / (1024 * 1024)
        logger.info(f"📊 Database size: {db_size_mb:.2f} MB")
    
    logger.info("")
    logger.info("=" * 60)
    logger.info("✅ Migration completed!")
    logger.info("=" * 60)
    
    if args.dry_run:
        logger.info("")
        logger.info("ℹ️ This was a dry run. Run without --dry-run to perform actual migration.")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\n⚠️ Migration cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Migration failed: {e}")
        sys.exit(1)
