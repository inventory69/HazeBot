"""
Community Posts API Routes
=============================
Handles CRUD operations for community posts with Discord integration.

Posts are stored in SQLite database ({DATA_DIR}/community_posts.db) and
automatically posted to Discord channel (based on PROD_MODE).

Features:
- Create posts (text, images, or both)
- Read posts with pagination and filtering
- Update posts (users can edit their own, admins can edit all)
- Delete posts (soft delete with audit trail)
- Discord integration (auto-post, edit, delete)
- Image storage in DATA_DIR
- Full PROD_MODE/Test-Mode support

Author: HazeBot Team
Date: 15. Dezember 2025
"""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from pathlib import Path
import sqlite3
import base64
import asyncio
import discord
import os

# Will be initialized by init_community_posts_routes()
Config = None
token_required = None

bp = Blueprint('community_posts', __name__)


def init_community_posts_routes(app, config, decorator_module):
    """
    Initialize community posts routes Blueprint with dependencies
    
    Args:
        app: Flask app instance
        config: Config module
        decorator_module: SimpleNamespace containing token_required decorator
    """
    global Config, token_required
    
    Config = config
    token_required = decorator_module.token_required
    
    # Register blueprint
    app.register_blueprint(bp)
    
    # NOW apply decorators to already-registered view functions
    vf = app.view_functions
    vf["community_posts.create_post"] = token_required(vf["community_posts.create_post"])
    vf["community_posts.get_posts"] = token_required(vf["community_posts.get_posts"])
    vf["community_posts.update_post"] = token_required(vf["community_posts.update_post"])
    vf["community_posts.delete_post"] = token_required(vf["community_posts.delete_post"])


# ============================================================================
# DATABASE HELPER
# ============================================================================

def get_posts_db():
    """
    Get database connection for community posts.
    Automatically uses correct directory based on PROD_MODE.
    Initializes database from init_community_posts.sql if it doesn't exist.
    
    Returns:
        sqlite3.Connection: Database connection with row_factory enabled
    """
    db_path = Path(Config.DATA_DIR) / "community_posts.db"
    
    # Initialize DB if it doesn't exist
    if not db_path.exists():
        init_script = Path(Config.DATA_DIR) / "init_community_posts.sql"
        if init_script.exists():
            conn = sqlite3.connect(str(db_path))
            with open(init_script, 'r', encoding='utf-8') as f:
                conn.executescript(f.read())
            conn.commit()
            conn.close()
            print(f"✅ Initialized community_posts.db in {Config.DATA_DIR}")
        else:
            print(f"⚠️ Warning: {init_script} not found, creating empty database")
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


# ============================================================================
# CREATE POST
# ============================================================================

@bp.route('/api/posts', methods=['POST'])
def create_post():
    """
    Create a new community post.
    
    Body:
    {
        "content": "Post text (optional if image provided)",
        "image": "base64_string or null",
        "is_announcement": false  // Only admins/mods can set true
    }
    
    Returns:
        201: Post created successfully with post_id and created_at
        400: Validation error (missing content/image, content too long)
        403: Permission denied (announcement without admin/mod role)
        500: Server error (image upload failed, database error)
    """
    try:
        data = request.json
        content = data.get('content', '').strip()
        image_data = data.get('image')
        is_announcement = data.get('is_announcement', False)
        
        # Validation
        if not content and not image_data:
            return jsonify({'error': 'Content or image required'}), 400
        
        if content and len(content) > 2000:
            return jsonify({'error': 'Content too long (max 2000 chars)'}), 400
        
        # Permission check for announcements
        user_id = request.discord_id
        user_role = request.user_role
        is_mod_or_admin = user_role in ['admin', 'mod']
        
        if is_announcement and not is_mod_or_admin:
            return jsonify({'error': 'Only admins/mods can create announcements'}), 403
        
        # Determine post type
        post_type = 'announcement' if is_announcement else ('admin' if is_mod_or_admin else 'normal')
        
        # Handle image upload
        image_url = None
        if image_data:
            try:
                image_url = _save_post_image(image_data, user_id)
            except Exception as e:
                print(f"❌ Image upload failed: {e}")
                return jsonify({'error': f'Image upload failed: {str(e)}'}), 500
        
        # Get avatar URL via bot instance
        bot = current_app.config.get("bot_instance")
        avatar_url = _get_user_avatar_url(user_id, bot)
        
        # Save to database
        conn = get_posts_db()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO community_posts 
            (content, image_url, author_id, author_name, author_avatar, 
             post_type, is_announcement, discord_channel_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            content or None,
            image_url,
            user_id,
            request.username,
            avatar_url,
            post_type,
            1 if is_announcement else 0,
            Config.COMMUNITY_POSTS_CHANNEL_ID
        ))
        
        post_id = cur.lastrowid
        created_at = datetime.now().isoformat()
        conn.commit()
        
        # Post to Discord asynchronously
        bot = current_app.config.get("bot_instance")
        if bot:
            try:
                # Run async function in bot's event loop
                user_data = {'username': request.username, 'id': user_id}
                discord_message_id = asyncio.run_coroutine_threadsafe(
                    _post_to_discord(bot, post_id, content, image_url, 
                                   user_data, post_type, is_announcement),
                    bot.loop
                ).result(timeout=10)
                
                # Update with Discord message ID
                cur.execute("""
                    UPDATE community_posts 
                    SET discord_message_id = ?
                    WHERE id = ?
                """, (discord_message_id, post_id))
                conn.commit()
                
                print(f"✅ Posted to Discord: Post #{post_id} → Message {discord_message_id}")
            except Exception as e:
                print(f"⚠️ Failed to post to Discord: {e}")
                # Don't fail the request - post is saved in database
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True,
            'post_id': post_id,
            'created_at': created_at
        }), 201
        
    except Exception as e:
        print(f"❌ Error creating post: {e}")
        return jsonify({'error': f'Failed to create post: {str(e)}'}), 500


# ============================================================================
# GET POSTS (with pagination)
# ============================================================================

@bp.route('/api/posts', methods=['GET'])
def get_posts():
    """
    Get community posts with pagination and filtering.
    
    Query params:
    - limit: int (default 20, max 100)
    - offset: int (default 0)
    - author_id: int (filter by author)
    - type: 'all'|'normal'|'admin'|'announcement' (default 'all')
    
    Returns:
        200: List of posts with pagination info
        500: Server error
    """
    try:
        limit = min(int(request.args.get('limit', 20)), 100)
        offset = int(request.args.get('offset', 0))
        author_id = request.args.get('author_id')
        post_type = request.args.get('type', 'all')
        
        conn = get_posts_db()
        cur = conn.cursor()
        
        # Build query (SQLite uses ? placeholders)
        query = """
            SELECT id, content, image_url, author_id, author_name, author_avatar,
                   post_type, is_announcement, created_at, updated_at, edited_at,
                   discord_message_id
            FROM community_posts
            WHERE is_deleted = 0
        """
        params = []
        
        if author_id:
            query += " AND author_id = ?"
            params.append(author_id)
        
        if post_type != 'all':
            query += " AND post_type = ?"
            params.append(post_type)
        
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        cur.execute(query, params)
        posts = cur.fetchall()
        
        # Get total count
        count_query = """
            SELECT COUNT(*) FROM community_posts 
            WHERE is_deleted = 0
        """
        count_params = []
        if author_id:
            count_query += " AND author_id = ?"
            count_params.append(author_id)
        if post_type != 'all':
            count_query += " AND post_type = ?"
            count_params.append(post_type)
        
        cur.execute(count_query, count_params)
        total_count = cur.fetchone()[0]
        
        cur.close()
        conn.close()
        
        return jsonify({
            'posts': [_format_post(p) for p in posts],
            'pagination': {
                'total': total_count,
                'limit': limit,
                'offset': offset,
                'has_more': offset + len(posts) < total_count
            }
        })
        
    except Exception as e:
        print(f"❌ Error fetching posts: {e}")
        return jsonify({'error': f'Failed to fetch posts: {str(e)}'}), 500


# ============================================================================
# UPDATE POST
# ============================================================================

@bp.route('/api/posts/<int:post_id>', methods=['PUT'])
def update_post(post_id):
    """
    Update a post (content and/or image).
    Admins/Mods can edit any post, users only their own.
    
    Body:
    {
        "content": "Updated text",
        "image": "base64_string or null"  // null = no change, empty = remove
    }
    
    Returns:
        200: Post updated successfully
        403: Permission denied
        404: Post not found
        500: Server error
    """
    try:
        data = request.json
        new_content = data.get('content', '').strip()
        new_image_data = data.get('image')
        
        # Get existing post
        conn = get_posts_db()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT author_id, content, image_url, discord_message_id
            FROM community_posts
            WHERE id = ? AND is_deleted = 0
        """, (post_id,))
        
        post = cur.fetchone()
        if not post:
            cur.close()
            conn.close()
            return jsonify({'error': 'Post not found'}), 404
        
        author_id, old_content, old_image_url, discord_msg_id = post
        
        # Permission check
        user_id = request.discord_id
        user_role = request.user_role
        is_mod_or_admin = user_role in ['admin', 'mod']
        
        if author_id != user_id and not is_mod_or_admin:
            cur.close()
            conn.close()
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Handle image update
        image_url = old_image_url
        if new_image_data is not None:  # None means no change, empty string means remove
            if new_image_data:
                try:
                    image_url = _save_post_image(new_image_data, user_id)
                    # TODO: Delete old image file if exists
                except Exception as e:
                    cur.close()
                    conn.close()
                    return jsonify({'error': f'Image upload failed: {str(e)}'}), 500
            else:
                image_url = None
                # TODO: Delete old image file if exists
        
        # Update database
        now = datetime.now().isoformat()
        cur.execute("""
            UPDATE community_posts
            SET content = ?, image_url = ?, edited_at = ?, updated_at = ?
            WHERE id = ?
        """, (new_content or None, image_url, now, now, post_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Update Discord message
        bot = current_app.config.get("bot_instance")
        if bot and discord_msg_id:
            try:
                asyncio.run_coroutine_threadsafe(
                    _update_discord_message(bot, discord_msg_id, new_content, image_url),
                    bot.loop
                ).result(timeout=10)
                print(f"✅ Updated Discord message: {discord_msg_id}")
            except Exception as e:
                print(f"⚠️ Failed to update Discord message: {e}")
        
        return jsonify({'success': True, 'edited_at': now})
        
    except Exception as e:
        print(f"❌ Error updating post: {e}")
        return jsonify({'error': f'Failed to update post: {str(e)}'}), 500


# ============================================================================
# DELETE POST
# ============================================================================

@bp.route('/api/posts/<int:post_id>', methods=['DELETE'])
def delete_post(post_id):
    """
    Delete a post (soft delete).
    Admins/Mods can delete any post, users only their own.
    
    Returns:
        200: Post deleted successfully
        403: Permission denied
        404: Post not found
        500: Server error
    """
    try:
        conn = get_posts_db()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT author_id, discord_message_id
            FROM community_posts
            WHERE id = ? AND is_deleted = 0
        """, (post_id,))
        
        post = cur.fetchone()
        if not post:
            cur.close()
            conn.close()
            return jsonify({'error': 'Post not found'}), 404
        
        author_id, discord_msg_id = post
        
        # Permission check
        user_id = request.discord_id
        user_role = request.user_role
        is_mod_or_admin = user_role in ['admin', 'mod']
        
        if author_id != user_id and not is_mod_or_admin:
            cur.close()
            conn.close()
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Soft delete
        now = datetime.now().isoformat()
        cur.execute("""
            UPDATE community_posts
            SET is_deleted = 1, deleted_at = ?, deleted_by_id = ?
            WHERE id = ?
        """, (now, user_id, post_id))
        
        conn.commit()
        cur.close()
        conn.close()
        
        # Delete Discord message
        bot = current_app.config.get("bot_instance")
        if bot and discord_msg_id:
            try:
                asyncio.run_coroutine_threadsafe(
                    _delete_discord_message(bot, discord_msg_id),
                    bot.loop
                ).result(timeout=10)
                print(f"✅ Deleted Discord message: {discord_msg_id}")
            except Exception as e:
                print(f"⚠️ Failed to delete Discord message: {e}")
        
        return jsonify({'success': True})
        
    except Exception as e:
        print(f"❌ Error deleting post: {e}")
        return jsonify({'error': f'Failed to delete post: {str(e)}'}), 500


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _save_post_image(base64_data: str, user_id: int) -> str:
    """
    Save uploaded image and return relative path.
    Images are stored in DATA_DIR (Data or TestData based on PROD_MODE).
    
    Args:
        base64_data: Base64-encoded image data (with or without data URL prefix)
        user_id: Discord user ID (used in filename)
    
    Returns:
        str: Relative path to saved image (e.g., "community_posts_images/post_123_1234567890.png")
    
    Raises:
        Exception: If image decoding or saving fails
    """
    # Remove data URL prefix if present
    if ',' in base64_data:
        base64_data = base64_data.split(',')[1]
    
    # Decode base64
    try:
        image_bytes = base64.b64decode(base64_data)
    except Exception as e:
        raise Exception(f"Failed to decode base64 image: {e}")
    
    # Generate filename
    timestamp = int(datetime.now().timestamp())
    filename = f"post_{user_id}_{timestamp}.png"
    
    # Save to DATA_DIR/community_posts_images/
    # This ensures test images are in TestData, prod images in Data
    upload_dir = Path(Config.DATA_DIR) / "community_posts_images"
    upload_dir.mkdir(exist_ok=True)
    
    filepath = upload_dir / filename
    try:
        with open(filepath, 'wb') as f:
            f.write(image_bytes)
    except Exception as e:
        raise Exception(f"Failed to save image file: {e}")
    
    # Return relative path (relative to DATA_DIR)
    return f"community_posts_images/{filename}"


async def _post_to_discord(bot, post_id, content, image_url, author, post_type, is_announcement):
    """
    Post to Discord channel and return message ID.
    Uses Config.COMMUNITY_POSTS_CHANNEL_ID (auto-selects Prod/Test).
    
    Args:
        bot: Discord bot instance
        post_id: Database post ID
        content: Post text content
        image_url: Relative path to image file
        author: User dict with username and avatar
        post_type: 'normal', 'admin', or 'announcement'
        is_announcement: Boolean
    
    Returns:
        int: Discord message ID
    
    Raises:
        Exception: If channel not found or message send fails
    """
    import discord
    
    # Get channel from config (PROD_MODE aware)
    channel_id = Config.COMMUNITY_POSTS_CHANNEL_ID
    if not channel_id:
        raise ValueError("Community posts channel not configured")
    
    channel = bot.get_channel(int(channel_id))
    if not channel:
        raise ValueError(f"Community posts channel {channel_id} not found")
    
    # Build embed
    embed = discord.Embed(
        description=content or "📷 Image Post",
        color=_get_embed_color(post_type, is_announcement),
        timestamp=datetime.utcnow()
    )
    
    # Author info
    embed.set_author(
        name=author.get('username', 'Unknown'),
        icon_url=author.get('avatar', '')
    )
    
    # Add badge/title
    if is_announcement:
        embed.title = "📢 ANNOUNCEMENT"
    elif post_type == 'admin':
        embed.title = "👑 Admin Post"
    
    # Add image
    if image_url:
        # Construct full filesystem path
        image_path = Path(Config.DATA_DIR) / image_url
        if image_path.exists():
            # Upload as file attachment
            file = discord.File(str(image_path), filename=image_path.name)
            embed.set_image(url=f"attachment://{image_path.name}")
            message = await channel.send(embed=embed, file=file)
        else:
            print(f"⚠️ Image file not found: {image_path}")
            message = await channel.send(embed=embed)
    else:
        message = await channel.send(embed=embed)
    
    # Footer with post ID
    embed.set_footer(text=f"Post ID: {post_id}")
    await message.edit(embed=embed)
    
    return message.id


def _get_embed_color(post_type, is_announcement):
    """
    Get Discord embed color based on post type.
    
    Returns:
        int: Color code in hex (e.g., 0xFF0000 for red)
    """
    if is_announcement:
        return 0xFF0000  # Red
    elif post_type == 'admin':
        return 0xFFD700  # Gold
    else:
        return 0x5865F2  # Discord Blue


async def _update_discord_message(bot, message_id, content, image_url):
    """
    Update existing Discord message.
    
    Args:
        bot: Discord bot instance
        message_id: Discord message ID to update
        content: New post text content
        image_url: New image path (or None)
    """
    channel_id = Config.COMMUNITY_POSTS_CHANNEL_ID
    if not channel_id:
        return
    
    channel = bot.get_channel(int(channel_id))
    if not channel:
        return
    
    try:
        message = await channel.fetch_message(message_id)
        
        # Get existing embed
        if message.embeds:
            embed = message.embeds[0]
            embed.description = content or "📷 Image Post"
            embed.timestamp = datetime.utcnow()
            
            # Update image if changed
            if image_url:
                image_path = Path(Config.DATA_DIR) / image_url
                if image_path.exists():
                    file = discord.File(str(image_path), filename=image_path.name)
                    embed.set_image(url=f"attachment://{image_path.name}")
                    await message.edit(embed=embed, attachments=[file])
                    return
            
            await message.edit(embed=embed)
    except Exception as e:
        print(f"Failed to update Discord message {message_id}: {e}")


async def _delete_discord_message(bot, message_id):
    """
    Delete Discord message.
    
    Args:
        bot: Discord bot instance
        message_id: Discord message ID to delete
    """
    channel_id = Config.COMMUNITY_POSTS_CHANNEL_ID
    if not channel_id:
        return
    
    channel = bot.get_channel(int(channel_id))
    if not channel:
        return
    
    try:
        message = await channel.fetch_message(message_id)
        await message.delete()
    except Exception as e:
        print(f"Failed to delete Discord message {message_id}: {e}")


def _format_post(post_row) -> dict:
    """
    Format SQLite row into JSON-friendly dict.
    
    Args:
        post_row: sqlite3.Row object
    
    Returns:
        dict: Formatted post data
    """
    return {
        'id': post_row['id'],
        'content': post_row['content'],
        'image_url': post_row['image_url'],
        'author': {
            'id': post_row['author_id'],
            'name': post_row['author_name'],
            'avatar': post_row['author_avatar']
        },
        'post_type': post_row['post_type'],
        'is_announcement': bool(post_row['is_announcement']),
        'created_at': post_row['created_at'],
        'updated_at': post_row['updated_at'],
        'edited_at': post_row['edited_at'],
        'discord_message_id': post_row['discord_message_id']
    }
