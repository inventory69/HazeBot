-- ============================================================================
-- Community Posts Database Initialization Script
-- ============================================================================
-- This script initializes the community_posts database for storing user posts
-- that are shared in Discord channels and displayed in the HazeBot Admin Panel.
--
-- Auto-executed on first access via get_posts_db() helper function.
-- ============================================================================

CREATE TABLE IF NOT EXISTS community_posts (
    -- Primary Key
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Content
    content TEXT,                          -- Post text (optional if only image)
    image_url TEXT,                        -- Relative path to image file (optional)
    
    -- Author Metadata (cached from Discord)
    author_id INTEGER NOT NULL,            -- Discord User ID
    author_name TEXT NOT NULL,             -- Discord Username
    author_avatar TEXT,                    -- Discord Avatar URL
    
    -- Post Type & Classification
    post_type TEXT DEFAULT 'normal',       -- 'normal', 'admin', 'announcement'
    is_announcement INTEGER DEFAULT 0,     -- 0=false, 1=true (SQLite boolean)
    
    -- Discord Integration
    discord_message_id INTEGER,            -- Message ID in Discord Channel
    discord_channel_id INTEGER,            -- Channel ID (from Config)
    
    -- Timestamps
    created_at TEXT DEFAULT (datetime('now')),  -- ISO 8601 format
    updated_at TEXT DEFAULT (datetime('now')),  -- Updated on every modification
    edited_at TEXT,                             -- NULL if never edited
    
    -- Soft Delete & Moderation
    is_deleted INTEGER DEFAULT 0,          -- 0=false, 1=true (soft delete)
    deleted_at TEXT,                       -- When post was deleted
    deleted_by_id INTEGER                  -- Discord User ID who deleted it
);

-- ============================================================================
-- Indexes for Query Performance
-- ============================================================================

-- Most common query: Get latest non-deleted posts
CREATE INDEX IF NOT EXISTS idx_posts_created_at 
    ON community_posts(created_at DESC);

-- Filter by author
CREATE INDEX IF NOT EXISTS idx_posts_author 
    ON community_posts(author_id);

-- Filter by post type (normal, admin, announcement)
CREATE INDEX IF NOT EXISTS idx_posts_type 
    ON community_posts(post_type);

-- Optimize queries that filter out deleted posts
CREATE INDEX IF NOT EXISTS idx_posts_not_deleted 
    ON community_posts(is_deleted) 
    WHERE is_deleted = 0;

-- Composite index for common query pattern (non-deleted, sorted by date)
CREATE INDEX IF NOT EXISTS idx_posts_active_by_date 
    ON community_posts(is_deleted, created_at DESC) 
    WHERE is_deleted = 0;

-- ============================================================================
-- Database Metadata
-- ============================================================================

-- Store schema version for future migrations
CREATE TABLE IF NOT EXISTS schema_info (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

INSERT OR REPLACE INTO schema_info (key, value) 
VALUES ('version', '1.0.0');

INSERT OR REPLACE INTO schema_info (key, value) 
VALUES ('created_at', datetime('now'));

-- ============================================================================
-- Initialization Complete
-- ============================================================================
