import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import os
import json
import random
from datetime import datetime, time
import logging
import asyncio
from bs4 import BeautifulSoup

import Config
from Config import (
    get_guild_id,
    get_data_dir,
    MEME_CHANNEL_ID,
    MEME_ROLE_ID,
    MEME_SUBREDDITS_FILE,
    DEFAULT_MEME_SUBREDDITS,
    MEME_LEMMY_FILE,
    DEFAULT_MEME_LEMMY,
    MEME_SOURCES,
)
from Utils.EmbedUtils import set_pink_footer

# Import all Views from separate module (prefixed with _ to avoid auto-loading as Cog)
from ._DailyMemeViews import (
    MemeHubView,
    is_mod_or_admin,
)

logger = logging.getLogger(__name__)


class DailyMeme(commands.Cog):
    """
    🎭 Daily Meme Cog: Posts trending memes from multiple sources (Reddit, Lemmy)
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.session = None
        self.subreddits_file = MEME_SUBREDDITS_FILE
        self.lemmy_file = MEME_LEMMY_FILE
        self.sources_file = os.path.join(get_data_dir(), "meme_sources.json")
        self.daily_config_file = os.path.join(get_data_dir(), "daily_meme_config.json")
        self._setup_done = False
        # Load daily meme configuration
        self.daily_config = self.load_daily_config()
        # Load subreddits from file or use defaults
        self.meme_subreddits = self.load_subreddits()
        # Load Lemmy communities from file or use defaults
        self.meme_lemmy = self.load_lemmy_communities()
        # Load meme sources from file or use defaults
        self.meme_sources = self.load_sources()
        # FlareSolverr for bypassing anti-bot measures (for future sources if needed)
        self.flaresolverr_url = os.getenv("FLARESOLVERR_URL")
        # Ensure HTTPS is used for FlareSolverr
        if self.flaresolverr_url and self.flaresolverr_url.startswith("http://"):
            self.flaresolverr_url = self.flaresolverr_url.replace("http://", "https://", 1)
            logger.warning(f"⚠️ FlareSolverr URL converted from HTTP to HTTPS: {self.flaresolverr_url}")
        # Rate limiting for FlareSolverr requests (2 seconds between calls - cache handles most requests)
        self._flaresolverr_lock = asyncio.Lock()
        self._last_flaresolverr_call = 0
        self._flaresolverr_rate_limit = 2  # seconds between FlareSolverr calls
        # Per-subreddit locks for true parallel fetching
        self._subreddit_locks = {}
        # Cache for Reddit responses (subreddit -> {timestamp, data})
        self._cache_duration = 3600  # 1 hour cache (Reddit hot posts stay relevant for a while)
        self._reddit_cache_file = os.path.join(get_data_dir(), "reddit_cache.json")
        self._reddit_cache = self.load_reddit_cache()
        # Cache for shown memes (URL -> timestamp)
        self.meme_cache_hours = 24  # Keep memes in cache for 24 hours
        self.shown_memes_file = os.path.join(get_data_dir(), "shown_memes.json")
        self.shown_memes = self.load_shown_memes()
        # Cache for meme requests (user_id -> count)
        self.meme_requests_file = os.path.join(get_data_dir(), "meme_requests.json")
        self.meme_requests = self.load_meme_requests()

    def load_daily_config(self) -> dict:
        """Load daily meme configuration from file"""
        default_config = {
            "enabled": True,
            "hour": 12,
            "minute": 0,
            "channel_id": MEME_CHANNEL_ID,
            "allow_nsfw": True,
            "role_id": MEME_ROLE_ID,  # Changed from ping_role_id for consistency
            # Selection preferences
            # Note: None = use all, [] = use none, ["a", "b"] = use specific
            "use_subreddits": None,  # None = use all configured
            "use_lemmy": None,  # None = use all configured
            "min_score": 100,  # Minimum upvotes
            "max_sources": 5,  # How many subreddits/communities to fetch from
            "pool_size": 50,  # Pick from top X memes
        }

        try:
            if os.path.exists(self.daily_config_file):
                with open(self.daily_config_file, "r") as f:
                    config = json.load(f)
                    # Migration: rename ping_role_id to role_id if it exists
                    if "ping_role_id" in config and "role_id" not in config:
                        config["role_id"] = config.pop("ping_role_id")
                    # Merge with defaults (in case new settings are added)
                    return {**default_config, **config}
        except Exception as e:
            logger.error(f"Error loading daily meme config: {e}")

        return default_config

    def save_daily_config(self) -> None:
        """Save daily meme configuration to file"""
        try:
            os.makedirs(os.path.dirname(self.daily_config_file), exist_ok=True)
            with open(self.daily_config_file, "w") as f:
                json.dump(self.daily_config, f, indent=4)
            logger.info("Saved daily meme configuration")
        except Exception as e:
            logger.error(f"Error saving daily meme config: {e}")

    def load_subreddits(self) -> list:
        """Load subreddit list from file or return defaults"""
        try:
            if os.path.exists(self.subreddits_file):
                with open(self.subreddits_file, "r") as f:
                    data = json.load(f)
                    subreddits = data.get("subreddits", DEFAULT_MEME_SUBREDDITS)
                    # Normalize all subreddit names to lowercase
                    return [sub.lower() for sub in subreddits]
        except Exception as e:
            logger.error(f"Error loading subreddits: {e}")

        # Normalize defaults to lowercase
        return [sub.lower() for sub in DEFAULT_MEME_SUBREDDITS]

    def save_subreddits(self) -> None:
        """Save current subreddit list to file"""
        try:
            os.makedirs(os.path.dirname(self.subreddits_file), exist_ok=True)
            with open(self.subreddits_file, "w") as f:
                json.dump({"subreddits": self.meme_subreddits}, f, indent=4)
            logger.info(f"Saved {len(self.meme_subreddits)} subreddits to config")
        except Exception as e:
            logger.error(f"Error saving subreddits: {e}")

    def load_lemmy_communities(self) -> list:
        """Load Lemmy communities from file or return defaults"""
        try:
            if os.path.exists(self.lemmy_file):
                with open(self.lemmy_file, "r") as f:
                    data = json.load(f)
                    communities = data.get("communities", DEFAULT_MEME_LEMMY)
                    return communities
        except Exception as e:
            logger.error(f"Error loading Lemmy communities: {e}")

        return DEFAULT_MEME_LEMMY.copy()

    def save_lemmy_communities(self) -> None:
        """Save current Lemmy community list to file"""
        try:
            os.makedirs(os.path.dirname(self.lemmy_file), exist_ok=True)
            with open(self.lemmy_file, "w") as f:
                json.dump({"communities": self.meme_lemmy}, f, indent=4)
            logger.info(f"Saved {len(self.meme_lemmy)} Lemmy communities to config")
        except Exception as e:
            logger.error(f"Error saving Lemmy communities: {e}")

    def load_sources(self) -> list:
        """Load meme sources from file or return defaults"""
        try:
            if os.path.exists(self.sources_file):
                with open(self.sources_file, "r") as f:
                    data = json.load(f)
                    sources = data.get("sources", MEME_SOURCES)
                    # Validate sources against available sources
                    valid_sources = ["reddit", "lemmy"]  # Extend when adding new sources
                    sources = [s for s in sources if s in valid_sources]
                    return sources if sources else MEME_SOURCES.copy()
        except Exception as e:
            logger.error(f"Error loading sources: {e}")

        return MEME_SOURCES.copy()

    def save_sources(self) -> None:
        """Save current source list to file"""
        try:
            os.makedirs(os.path.dirname(self.sources_file), exist_ok=True)
            with open(self.sources_file, "w") as f:
                json.dump({"sources": self.meme_sources}, f, indent=4)
            logger.info(f"Saved {len(self.meme_sources)} meme sources to config")
        except Exception as e:
            logger.error(f"Error saving sources: {e}")

    def load_shown_memes(self) -> dict:
        """Load shown memes cache from file"""
        try:
            if os.path.exists(self.shown_memes_file):
                with open(self.shown_memes_file, "r") as f:
                    data = json.load(f)
                    # Clean old entries (older than cache hours)
                    current_time = datetime.now().timestamp()
                    cache_seconds = self.meme_cache_hours * 3600
                    cleaned = {
                        url: timestamp for url, timestamp in data.items() if current_time - timestamp < cache_seconds
                    }
                    return cleaned
        except Exception as e:
            logger.error(f"Error loading shown memes cache: {e}")
        return {}

    def save_shown_memes(self) -> None:
        """Save shown memes cache to file"""
        try:
            os.makedirs(os.path.dirname(self.shown_memes_file), exist_ok=True)
            with open(self.shown_memes_file, "w") as f:
                json.dump(self.shown_memes, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving shown memes cache: {e}")

    def load_meme_requests(self) -> dict:
        """Load meme requests cache from file"""
        try:
            if os.path.exists(self.meme_requests_file):
                with open(self.meme_requests_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading meme requests: {e}")
        return {}

    def save_meme_requests(self) -> None:
        """Save meme requests cache to file"""
        try:
            os.makedirs(os.path.dirname(self.meme_requests_file), exist_ok=True)
            with open(self.meme_requests_file, "w") as f:
                json.dump(self.meme_requests, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving meme requests: {e}")

    def load_reddit_cache(self) -> dict:
        """Load Reddit API response cache from file"""
        try:
            if os.path.exists(self._reddit_cache_file):
                with open(self._reddit_cache_file, "r") as f:
                    data = json.load(f)
                    # Clean old entries (older than cache duration)
                    current_time = asyncio.get_event_loop().time()
                    cleaned = {}
                    for key, cache_entry in data.items():
                        if current_time - cache_entry.get("timestamp", 0) < self._cache_duration:
                            cleaned[key] = cache_entry
                    return cleaned
        except Exception as e:
            logger.error(f"Error loading Reddit cache: {e}")
        return {}

    def save_reddit_cache(self) -> None:
        """Save Reddit API response cache to file"""
        try:
            os.makedirs(os.path.dirname(self._reddit_cache_file), exist_ok=True)
            with open(self._reddit_cache_file, "w") as f:
                json.dump(self._reddit_cache, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving Reddit cache: {e}")

    def is_meme_shown_recently(self, url: str) -> bool:
        """Check if a meme was shown recently"""
        if url not in self.shown_memes:
            return False

        current_time = datetime.now().timestamp()
        cache_seconds = self.meme_cache_hours * 3600

        # Check if still in cache window
        if current_time - self.shown_memes[url] < cache_seconds:
            return True
        else:
            # Remove expired entry
            del self.shown_memes[url]
            return False

    def mark_meme_as_shown(self, url: str) -> None:
        """Mark a meme as shown"""
        self.shown_memes[url] = datetime.now().timestamp()
        self.save_shown_memes()

    async def _setup_cog(self) -> None:
        """Setup the cog - called on ready and after reload"""
        # Create HTTP session if not exists
        if not self.session or self.session.closed:
            self.session = aiohttp.ClientSession()

        # Configure and start the daily meme task with saved settings
        hour = self.daily_config.get("hour", 12)
        minute = self.daily_config.get("minute", 0)
        # Assuming local time is CET (UTC+1), convert to UTC for server
        adjusted_hour = (hour - 1) % 24
        self.daily_meme_task.change_interval(time=time(hour=adjusted_hour, minute=minute))

        if self.daily_config.get("enabled", True) and not self.daily_meme_task.is_running():
            self.daily_meme_task.start()
            logger.info(f"⏰ Daily meme task started for {hour:02d}:{minute:02d}")
            # Log Reddit cache status
            if self._reddit_cache:
                logger.info(f"💾 Loaded {len(self._reddit_cache)} cached Reddit responses from disk")
        elif not self.daily_config.get("enabled", True):
            logger.info("Daily meme task is disabled")

        # Log configuration (always, regardless of enabled state)
        if os.path.exists(self.subreddits_file):
            logger.info(f"Loaded {len(self.meme_subreddits)} subreddits from config")
        else:
            logger.info(f"Using default {len(self.meme_subreddits)} subreddits")

        # Load Lemmy communities
        if os.path.exists(self.lemmy_file):
            logger.info(f"Loaded {len(self.meme_lemmy)} Lemmy communities from config")
        else:
            logger.info(f"Using default {len(self.meme_lemmy)} Lemmy communities")

        # Log enabled meme sources
        sources_str = ", ".join(self.meme_sources)
        logger.info(f"Enabled meme sources: {sources_str}")

        # FlareSolverr check - Required for Reddit (always returns 403) and other sources
        if "reddit" in self.meme_sources or any(src in self.meme_sources for src in ["9gag", "4chan"]):
            if self.flaresolverr_url:
                logger.info(f"FlareSolverr configured: {self.flaresolverr_url}")
            else:
                logger.warning("⚠️ FlareSolverr required for Reddit but URL not configured!")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Set up Daily Meme when bot is ready"""
        if self._setup_done:
            return  # Only setup once

        self._setup_done = True
        await self._setup_cog()

    async def cog_load(self) -> None:
        """Called when the cog is loaded (including reloads)"""
        # Wait a moment for bot to be ready
        if self.bot.is_ready():
            await self._setup_cog()

    async def cog_unload(self):
        """Called when the cog is unloaded"""
        if self.daily_meme_task.is_running():
            self.daily_meme_task.cancel()
            logger.info("Daily Meme task cancelled")

        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("HTTP session closed")

    async def _fetch_with_flaresolverr(self, url: str, timeout: int = 60000) -> dict:
        """
        Fetch URL using FlareSolverr (allows parallel requests, no rate limiting needed)

        Args:
            url: The URL to fetch
            timeout: FlareSolverr maxTimeout in milliseconds

        Returns:
            dict with 'status' and 'response' keys, or None on error
        """
        if not self.flaresolverr_url:
            logger.warning("FlareSolverr URL not configured")
            return None

        payload = {
            "cmd": "request.get",
            "url": url,
            "maxTimeout": timeout,
        }

        try:
            async with self.session.post(self.flaresolverr_url, json=payload, timeout=30) as response:
                if response.status != 200:
                    logger.warning(f"FlareSolverr returned {response.status}")
                    return None

                data = await response.json()
                if data.get("status") != "ok":
                    logger.warning(f"FlareSolverr failed: {data.get('message')}")
                    return None

                # Get the response text from FlareSolverr
                solution = data.get("solution", {})
                response_text = solution.get("response")

                if not response_text:
                    logger.warning("No response content from FlareSolverr")
                    logger.debug(f"Full FlareSolverr response: {data}")
                    return None

                # Debug: Log response type and preview
                response_length = len(response_text) if response_text else 0
                logger.debug(f"FlareSolverr response type: {type(response_text)}, length: {response_length}")
                logger.debug(f"Response preview (first 200): {response_text[:200] if response_text else 'None'}")

                return {"status": "ok", "response": response_text}

        except asyncio.TimeoutError:
            logger.error(f"FlareSolverr timeout for {url}")
            return None
        except Exception as e:
            logger.error(f"FlareSolverr error: {e}")
            return None

    async def fetch_reddit_meme(self, subreddit: str, sort: str = "hot") -> dict:
        """
        Fetch a meme from Reddit using FlareSolverr (Reddit blocks direct API access)
        Uses 5-minute cache to avoid repeated FlareSolverr calls
        sort: hot, top, new
        """
        # Check cache first
        cache_key = f"{subreddit}_{sort}"
        if cache_key in self._reddit_cache:
            cached = self._reddit_cache[cache_key]
            cache_age = asyncio.get_event_loop().time() - cached["timestamp"]
            if cache_age < self._cache_duration:
                meme_count = len(cached["data"])
                logger.info(f"⚡ Using cached data for r/{subreddit} (age: {int(cache_age)}s, {meme_count} memes)")
                return cached["data"]
            else:
                logger.debug(f"⏰ Cache expired for r/{subreddit} (age: {cache_age:.1f}s)")

        url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit=50&t=day"

        try:
            # Use FlareSolverr directly since Reddit always returns 403
            if not self.flaresolverr_url:
                logger.error("FlareSolverr not configured, cannot fetch from Reddit")
                return None

            logger.debug(f"🌐 Fetching r/{subreddit} via FlareSolverr...")
            flare_response = await self._fetch_with_flaresolverr(url)

            if not flare_response or flare_response.get("status") != "ok":
                logger.error(f"FlareSolverr failed for r/{subreddit}")
                return None

            # Parse JSON from response
            response_text = flare_response.get("response", "")

            # FlareSolverr might return HTML instead of JSON if Reddit blocks it
            # Try to extract JSON from the response
            if not response_text or not response_text.strip():
                logger.error(f"Empty response from FlareSolverr for r/{subreddit}")
                return None

            # Check if response is HTML (starts with <!DOCTYPE or <html)
            if response_text.strip().startswith(("<", "<!DOCTYPE", "<!doctype")):
                logger.debug(f"FlareSolverr returned HTML for r/{subreddit}, attempting to extract JSON from <pre> tag")

                # Parse HTML and extract JSON from <pre> tag (Reddit returns JSON in HTML)
                soup = BeautifulSoup(response_text, "html.parser")
                pre_tag = soup.find("pre")

                if not pre_tag or not pre_tag.text.strip():
                    logger.error(f"No <pre> tag found in HTML response for r/{subreddit}")
                    logger.debug(f"HTML preview: {response_text[:500]}...")
                    return None

                response_text = pre_tag.text.strip()
                logger.debug(f"Extracted JSON from <pre> tag, length: {len(response_text)}")

            try:
                # FlareSolverr returns the JSON response as text
                data = json.loads(response_text)
                logger.debug(f"Successfully parsed JSON from r/{subreddit}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON from FlareSolverr response for r/{subreddit}: {e}")
                logger.debug(f"Response preview (first 500 chars): {response_text[:500]}...")
                logger.debug(f"Response preview (last 200 chars): ...{response_text[-200:]}")
                return None

            posts = data["data"]["children"]

            # Filter for image posts only
            image_posts = []
            for post in posts:
                post_data = post["data"]
                # Skip stickied posts, videos, and galleries
                if post_data.get("stickied") or post_data.get("is_video") or post_data.get("is_gallery"):
                    continue

                # Get image URL
                post_url = post_data.get("url", "")
                # Accept direct image links and imgur links
                image_extensions = [".jpg", ".jpeg", ".png", ".gif"]
                has_image_ext = any(ext in post_url.lower() for ext in image_extensions)
                if has_image_ext or "i.imgur.com" in post_url:
                    image_posts.append(
                        {
                            "title": post_data.get("title"),
                            "url": post_url,
                            "subreddit": subreddit,
                            "score": post_data.get("ups", 0),  # Use 'score' key for consistency
                            "upvotes": post_data.get("ups", 0),  # Keep upvotes for compatibility
                            "permalink": f"https://reddit.com{post_data.get('permalink')}",
                            "nsfw": post_data.get("over_18", False),
                            "author": post_data.get("author", "unknown"),
                        }
                    )

            logger.info(f"✅ Fetched {len(image_posts)} memes from r/{subreddit}")

            # Cache the result
            if image_posts:
                self._reddit_cache[cache_key] = {"timestamp": asyncio.get_event_loop().time(), "data": image_posts}
                logger.debug(f"💾 Cached {len(image_posts)} memes for r/{subreddit}")
                # Save cache to disk
                self.save_reddit_cache()

            return image_posts if image_posts else None

        except asyncio.TimeoutError:
            logger.error(f"Timeout fetching meme from r/{subreddit}")
            return None
        except Exception as e:
            logger.error(f"Error fetching meme from r/{subreddit}: {e}")
            return None

    async def fetch_lemmy_meme(self, community: str) -> list:
        """
        Fetch memes from Lemmy communities

        Args:
            community: Format "instance@community" (e.g., "lemmy.world@memes")

        Returns:
            List of meme dicts or None
        """
        try:
            # Parse instance@community format
            if "@" not in community:
                logger.warning(f"Invalid Lemmy community format: {community} (expected instance@community)")
                return None

            instance, community_name = community.split("@", 1)

            # Build API URL
            url = f"https://{instance}/api/v3/post/list"
            params = {
                "community_name": community_name,
                "sort": "Hot",
                "limit": 50,
            }
            headers = {"User-Agent": "HazeBot/1.0"}

            # Add timeout to prevent hanging on slow instances
            # connect: time to establish connection, total: overall request time
            timeout = aiohttp.ClientTimeout(total=15, connect=5)
            logger.debug(f"🌐 Requesting Lemmy API: {url}")
            async with self.session.get(url, headers=headers, params=params, timeout=timeout) as response:
                if response.status != 200:
                    logger.warning(f"Lemmy API returned {response.status} for {instance}@{community_name}")
                    return None

                logger.debug(f"✅ Lemmy API responded with status {response.status}")
                data = await response.json()
                posts = data.get("posts", [])

                # Filter for image posts
                image_posts = []
                for item in posts:
                    try:
                        post = item.get("post", {})
                        counts = item.get("counts", {})
                        creator = item.get("creator", {})

                        # Get image URL
                        post_url = post.get("url", "")
                        # Accept direct image links
                        image_extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
                        if post_url and any(ext in post_url.lower() for ext in image_extensions):
                            image_posts.append(
                                {
                                    "title": post.get("name", "Meme from Lemmy")[:256],
                                    "url": post_url,
                                    "subreddit": f"lemmy:{instance}@{community_name}",  # Special format for Lemmy
                                    "score": counts.get("score", 0),  # Use 'score' key for consistency
                                    "upvotes": counts.get("score", 0),  # Keep upvotes for compatibility
                                    "permalink": post.get("ap_id", ""),
                                    "nsfw": post.get("nsfw", False),
                                    "author": creator.get("name", "unknown"),
                                }
                            )
                    except Exception as e:
                        logger.debug(f"Error parsing Lemmy post: {e}")
                        continue

                logger.info(f"Fetched {len(image_posts)} memes from {instance}@{community_name}")
                return image_posts if image_posts else None

        except asyncio.TimeoutError:
            logger.warning(f"⏱️ Timeout fetching from Lemmy {community} (>15s) - Instance may be slow or overloaded")
            return None
        except aiohttp.ClientError as e:
            logger.warning(f"🌐 Network error fetching from Lemmy {community}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error fetching meme from Lemmy {community}: {e}")
            return None

    async def get_daily_meme(
        self,
        subreddit: str = None,
        allow_nsfw: bool = False,
        source: str = None,
        max_sources: int = None,
        min_score: int = None,
        pool_size: int = None,
        use_config: bool = False,
    ):
        """
        Get a high-quality meme from various sources

        Args:
            subreddit: Optional specific subreddit to fetch from. If None, uses random subreddits.
            allow_nsfw: Whether to allow NSFW content. True for daily posts, False for user commands.
            source: Optional specific source (e.g., "reddit"). If None, uses all enabled sources.
            max_sources: Maximum number of subreddits/communities to fetch from (for speed)
            min_score: Minimum upvotes required
            pool_size: Pick from top X memes
            use_config: Whether to use daily_config preferences (for daily task)
        """
        # Use config preferences if requested (daily task)
        if use_config:
            max_sources = self.daily_config.get("max_sources", 5)
            min_score = self.daily_config.get("min_score", 100)
            pool_size = self.daily_config.get("pool_size", 50)
            configured_subreddits = self.daily_config.get("use_subreddits")
            configured_lemmy = self.daily_config.get("use_lemmy")
        else:
            max_sources = max_sources or 3
            min_score = min_score or 0
            pool_size = pool_size or 50
            # None means use all available sources (not restricted)
            configured_subreddits = None
            configured_lemmy = None

        # Try to get hot memes from specified or all sources
        all_memes = []

        # Determine which source(s) to use
        if source:
            sources_to_use = [source] if source in self.meme_sources else self.meme_sources
        else:
            # Use all sources for variety
            sources_to_use = self.meme_sources

        for src in sources_to_use:
            if src == "reddit":
                if subreddit:
                    # Fetch from specific subreddit
                    memes = await self.fetch_reddit_meme(subreddit, sort="hot")
                    if memes:
                        all_memes.extend(memes)
                else:
                    # Use configured subreddits or all available
                    # None = use all, empty list [] = use none, list with items = use those
                    if configured_subreddits is None:
                        subreddits_pool = self.meme_subreddits
                    else:
                        subreddits_pool = configured_subreddits

                    if not subreddits_pool:
                        # Skip if explicitly set to empty
                        logger.debug("📊 Subreddit fetching skipped (none selected)")
                    else:
                        # Fetch from random subset of subreddits for speed (use cache if available)
                        selected_subs = random.sample(subreddits_pool, min(max_sources, len(subreddits_pool)))
                        logger.debug(f"📊 Fetching from {len(selected_subs)} random subreddits: {selected_subs}")

                        # Parallel fetching for speed
                        fetch_tasks = [self.fetch_reddit_meme(sub, sort="hot") for sub in selected_subs]
                        results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

                        for memes in results:
                            if memes and not isinstance(memes, Exception):
                                all_memes.extend(memes)

            elif src == "lemmy":
                # Use configured Lemmy communities or all available
                # None = use all, empty list [] = use none, list with items = use those
                if configured_lemmy is None:
                    lemmy_pool = self.meme_lemmy
                else:
                    lemmy_pool = configured_lemmy

                if not lemmy_pool:
                    # Skip if explicitly set to empty
                    logger.debug("📊 Lemmy fetching skipped (none selected)")
                else:
                    # Fetch from random subset of Lemmy communities for speed
                    selected_communities = random.sample(lemmy_pool, min(max_sources, len(lemmy_pool)))
                    logger.debug(
                        f"📊 Fetching from {len(selected_communities)} random Lemmy communities: {selected_communities}"
                    )

                    # Parallel fetching for speed
                    fetch_tasks = [self.fetch_lemmy_meme(community) for community in selected_communities]
                    results = await asyncio.gather(*fetch_tasks, return_exceptions=True)

                    for memes in results:
                        if memes and not isinstance(memes, Exception):
                            all_memes.extend(memes)

            # Add more source types here (e.g., elif src == "newsource":)

        if not all_memes:
            logger.warning(f"No memes found from {source or 'any source'}")
            return None

        # Filter by minimum score
        if min_score > 0:
            all_memes = [meme for meme in all_memes if meme.get("upvotes", 0) >= min_score]
            if not all_memes:
                logger.warning(f"No memes found with score >= {min_score}")
                return None

        # Filter NSFW if not allowed
        if not allow_nsfw:
            all_memes = [meme for meme in all_memes if not meme.get("nsfw", False)]
            if not all_memes:
                logger.warning("No SFW memes found")
                return None

        # Filter out recently shown memes
        fresh_memes = [meme for meme in all_memes if not self.is_meme_shown_recently(meme["url"])]

        # If all memes were shown recently, clear cache and use all memes
        if not fresh_memes:
            logger.info("All memes were shown recently, clearing cache")
            self.shown_memes.clear()
            self.save_shown_memes()
            fresh_memes = all_memes

        # Sort by upvotes to get quality memes
        fresh_memes.sort(key=lambda x: x["upvotes"], reverse=True)

        # Pick from top X to balance quality and variety
        # This prevents always showing the same top memes
        actual_pool_size = min(pool_size, len(fresh_memes))
        top_memes = fresh_memes[:actual_pool_size]

        logger.debug(
            f"Selecting from pool of {len(top_memes)} memes (out of {len(fresh_memes)} fresh, min_score: {min_score})"
        )

        # Random pick from top memes pool for variety
        selected_meme = random.choice(top_memes)

        # Mark this meme as shown
        self.mark_meme_as_shown(selected_meme["url"])

        return selected_meme

    async def post_meme(
        self, meme: dict, channel: discord.TextChannel, mention: str = "", requested_by: discord.Member = None
    ):
        """Post a meme to the channel"""
        embed = discord.Embed(
            title=meme["title"][:256],  # Discord title limit
            url=meme["permalink"],
            color=Config.PINK,
            timestamp=datetime.now(),
        )
        embed.set_image(url=meme["url"])
        embed.add_field(name="👍 Upvotes", value=f"{meme['upvotes']:,}", inline=True)

        # Display source appropriately
        source_name = f"r/{meme['subreddit']}"  # Default to subreddit format
        # Add custom mappings for non-reddit sources here if needed
        if meme["subreddit"].startswith("lemmy:"):
            # Format: "lemmy:instance@community" -> "instance@community"
            source_name = meme["subreddit"].replace("lemmy:", "")
        # e.g., if meme["subreddit"] == "othersource": source_name = "Other Source"

        embed.add_field(name="📍 Source", value=source_name, inline=True)
        embed.add_field(name="👤 Author", value=f"u/{meme['author']}", inline=True)

        if meme.get("nsfw"):
            embed.add_field(name="⚠️", value="NSFW Content", inline=False)

        set_pink_footer(embed, bot=self.bot.user)

        # Send with optional mention and requester
        if requested_by:
            message = f"🎭 Meme requested by {requested_by.mention}"
            if mention:
                message += f" {mention}"
        elif mention:
            message = f"🎭 Daily Meme Alert! {mention}"
        else:
            message = "🎭 Daily Meme Alert!"

        await channel.send(message.strip(), embed=embed)

        # Format source for logging
        if meme["subreddit"].startswith("lemmy:"):
            source_display = meme["subreddit"].replace("lemmy:", "")
        elif meme["subreddit"] not in ["9gag"]:
            source_display = f"r/{meme['subreddit']}"
        else:
            source_display = meme["subreddit"]
        logger.info(f"Posted meme: {meme['title'][:50]}... from {source_display} ({meme['upvotes']} upvotes)")

    async def fetch_meme_and_create_embed(
        self, subreddit: str = None, allow_nsfw: bool = False
    ) -> tuple[dict, discord.Embed]:
        """
        Shared helper: Fetch meme and create embed (for hybrid commands)

        Args:
            subreddit: Optional specific subreddit to fetch from
            allow_nsfw: Whether to allow NSFW content

        Returns: (meme_dict, embed)
        """
        # Force Reddit source if specific subreddit is requested
        source = "reddit" if subreddit else None
        meme = await self.get_daily_meme(subreddit=subreddit, allow_nsfw=allow_nsfw, source=source)

        if not meme:
            return None, None

        embed = discord.Embed(
            title=meme["title"][:256],
            url=meme["permalink"],
            color=Config.PINK,
        )
        embed.set_image(url=meme["url"])
        embed.add_field(name="👍 Upvotes", value=f"{meme['upvotes']:,}", inline=True)

        # Display source appropriately
        source_name = f"r/{meme['subreddit']}"  # Default to subreddit format
        # Add custom mappings for non-reddit sources here if needed
        if meme["subreddit"].startswith("lemmy:"):
            # Format: "lemmy:instance@community" -> "instance@community"
            source_name = meme["subreddit"].replace("lemmy:", "")

        embed.add_field(name="📍 Source", value=source_name, inline=True)
        embed.add_field(name="👤 Author", value=f"u/{meme['author']}", inline=True)

        if meme.get("nsfw"):
            embed.add_field(name="⚠️", value="NSFW Content", inline=False)

        set_pink_footer(embed, bot=self.bot.user)

        return meme, embed

    @tasks.loop(time=time(hour=12, minute=0))  # Default time, will be updated dynamically
    async def daily_meme_task(self):
        """Post a daily meme at configured time"""
        # Check if task is enabled
        if not self.daily_config.get("enabled", True):
            logger.debug("Daily meme task is disabled, skipping")
            return

        try:
            guild = self.bot.get_guild(get_guild_id())
            if not guild:
                logger.error("Guild not found")
                return

            channel_id = self.daily_config.get("channel_id", MEME_CHANNEL_ID)
            channel = guild.get_channel(channel_id)
            if not channel:
                logger.error(f"Meme channel {channel_id} not found")
                return

            logger.info("Fetching daily meme...")
            # Use configured NSFW setting and selection preferences
            allow_nsfw = self.daily_config.get("allow_nsfw", True)
            meme = await self.get_daily_meme(allow_nsfw=allow_nsfw, use_config=True)

            if meme:
                # Check if we should ping the role
                role_id = self.daily_config.get("role_id")
                mention = f"<@&{role_id}>" if role_id else ""
                await self.post_meme(meme, channel, mention=mention)
            else:
                logger.error("Failed to fetch daily meme")
                await channel.send("❌ Sorry, couldn't fetch today's meme. Try again later!")

        except Exception as e:
            logger.error(f"Error in daily_meme_task: {e}")

    def restart_daily_task(self):
        """Restart the daily meme task with updated time"""
        # Update task time
        hour = self.daily_config.get("hour", 12)
        minute = self.daily_config.get("minute", 0)
        # Assuming local time is CET (UTC+1), convert to UTC for server
        adjusted_hour = (hour - 1) % 24
        self.daily_meme_task.change_interval(time=time(hour=adjusted_hour, minute=minute))

        if self.daily_meme_task.is_running():
            # Task is already running, just update the interval
            logger.info(f"Daily meme task interval updated for {hour:02d}:{minute:02d}")
        elif self.daily_config.get("enabled", True):
            self.daily_meme_task.start()
            logger.info(f"Daily meme task started for {hour:02d}:{minute:02d}")
        else:
            logger.info("Daily meme task stopped (disabled)")

    @daily_meme_task.before_loop
    async def before_daily_meme(self):
        """Wait for bot to be ready before starting the task"""
        await self.bot.wait_until_ready()

    @commands.command(name="meme")
    async def meme_command(self, ctx: commands.Context, *, source: str = None):
        """
        🎭 Get a meme or open the Meme Hub
        Usage:
        - !meme - Open interactive Meme Hub
        - !meme memes - Get meme from r/memes
        - !meme lemmy.world@memes - Get meme from Lemmy community

        Regular users: Get memes with 10s cooldown
        Mods/Admins: Full management access + no cooldown
        """
        is_admin_or_mod = is_mod_or_admin(ctx.author)

        # Clean and validate source argument
        if source:
            source = source.strip()

        # If source is specified and not empty, fetch directly
        if source:
            # Check cooldown (skip for mods/admins)
            if not is_admin_or_mod:
                last_use = getattr(self, "_user_cooldowns", {}).get(ctx.author.id, 0)
                current_time = datetime.now().timestamp()
                if current_time - last_use < 10:
                    remaining = int(10 - (current_time - last_use))
                    await ctx.send(f"⏳ Please wait {remaining} seconds before requesting another meme!")
                    return

                # Update cooldown
                if not hasattr(self, "_user_cooldowns"):
                    self._user_cooldowns = {}
                self._user_cooldowns[ctx.author.id] = current_time

            # Determine if it's Lemmy or Reddit
            if "@" in source:
                # Lemmy community
                lemmy_source = source.lower()
                if lemmy_source not in self.meme_lemmy:
                    await ctx.send(
                        f"❌ `{source}` is not configured. Use `!lemmycommunities` to see available communities."
                    )
                    return

                await ctx.send(f"🔍 Fetching meme from {lemmy_source}...")
                memes = await self.fetch_lemmy_meme(lemmy_source)
                source_display = lemmy_source
            else:
                # Reddit subreddit - normalize the input
                subreddit = source.lower().strip().replace("r/", "")

                if not subreddit:  # Empty after stripping
                    await ctx.send("❌ Please provide a valid subreddit name.")
                    return

                if subreddit not in self.meme_subreddits:
                    await ctx.send(
                        f"❌ r/{subreddit} is not configured. Use `!memesubreddits` to see available subreddits."
                    )
                    return

                await ctx.send(f"🔍 Fetching meme from r/{subreddit}...")
                memes = await self.fetch_reddit_meme(subreddit)
                source_display = f"r/{subreddit}"

            if not memes:
                await ctx.send(f"❌ No memes found from {source_display}. Try another source!")
                return

            # Pick random meme and post it with requester mention
            meme = random.choice(memes)

            # Convert to the format expected by post_meme
            meme_data = {
                "title": meme.get("title", "Meme"),
                "permalink": meme.get("url"),
                "url": meme.get("url"),
                "upvotes": meme.get("score", 0),
                "subreddit": source.lower().strip().replace("r/", "") if "@" not in source else f"lemmy:{source}",
                "author": meme.get("author", "Unknown"),
                "nsfw": meme.get("nsfw", False),
            }

            await self.post_meme(meme_data, ctx.channel, requested_by=ctx.author)

            user_id = str(ctx.author.id)
            self.meme_requests[user_id] = self.meme_requests.get(user_id, 0) + 1
            self.save_meme_requests()
            logger.info(f"Meme fetched by {ctx.author} from {source_display} via command argument")
            return

        # No source specified, show Meme Hub
        embed = discord.Embed(
            title="🎭 Meme Hub",
            description=(
                "Welcome to the Meme Hub! Get trending memes from multiple sources.\n\n"
                "**Available Sources:** Reddit, Lemmy\n"
                "**Rate Limit:** 10 seconds between requests"
                if not is_admin_or_mod
                else "**Mod/Admin Access:** Full management + no cooldown"
            ),
            color=Config.PINK,
        )

        if is_admin_or_mod:
            embed.add_field(
                name="🔧 Management",
                value=(
                    "Use the buttons below to:\n"
                    "• Get random memes (no cooldown)\n"
                    "• Choose specific source\n"
                    "• Manage subreddit sources\n"
                    "• Manage Lemmy communities\n"
                    "• Toggle meme sources\n"
                    "• Test daily meme function"
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="📝 How to Use",
                value=(
                    "• **🎭 Get Random Meme** - Random from all sources\n"
                    "• **🎯 Choose Source** - Pick specific subreddit/community\n"
                    "• Or use: `!meme <source>` - e.g., `!meme memes` or `!meme lemmy.world@memes`\n"
                    "*10 second cooldown between requests*"
                ),
                inline=False,
            )

        set_pink_footer(embed, bot=self.bot.user)

        view = MemeHubView(self, is_admin_or_mod, post_to_channel_id=ctx.channel.id)
        await ctx.send(embed=embed, view=view)
        logger.info(f"Meme Hub opened by {ctx.author} (Mod: {is_admin_or_mod})")

    async def meme_source_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """Autocomplete for meme sources (subreddits and Lemmy communities)"""
        choices = []

        # Add Reddit subreddits
        for sub in self.meme_subreddits:
            display_name = f"🔥 r/{sub}"
            if current.lower() in sub.lower() or current.lower() in display_name.lower():
                choices.append(app_commands.Choice(name=display_name, value=sub))

        # Add Lemmy communities
        for comm in self.meme_lemmy:
            display_name = f"🌐 {comm}"
            if current.lower() in comm.lower() or current.lower() in display_name.lower():
                choices.append(app_commands.Choice(name=display_name, value=comm))

        # Limit to 25 choices (Discord limit)
        return choices[:25]

    @app_commands.command(name="meme", description="🎭 Get a meme from specific source or open Meme Hub")
    @app_commands.describe(source="Choose a subreddit or Lemmy community (optional)")
    @app_commands.autocomplete(source=meme_source_autocomplete)
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    async def meme_slash(self, interaction: discord.Interaction, source: str = None):
        """Slash command for Meme Hub with optional source"""
        is_admin_or_mod = is_mod_or_admin(interaction.user)

        # Clean and validate source argument
        if source:
            source = source.strip()

        # If source is specified and not empty, fetch directly
        if source:
            # Check cooldown (skip for mods/admins)
            if not is_admin_or_mod:
                last_use = getattr(self, "_user_cooldowns", {}).get(interaction.user.id, 0)
                current_time = datetime.now().timestamp()
                if current_time - last_use < 10:
                    remaining = int(10 - (current_time - last_use))
                    await interaction.response.send_message(
                        f"⏳ Please wait {remaining} seconds before requesting another meme!",
                        ephemeral=True,
                    )
                    return

                # Update cooldown
                if not hasattr(self, "_user_cooldowns"):
                    self._user_cooldowns = {}
                self._user_cooldowns[interaction.user.id] = current_time

            # Determine if it's Lemmy or Reddit
            if "@" in source:
                # Lemmy community
                lemmy_source = source.lower()
                if lemmy_source not in self.meme_lemmy:
                    await interaction.response.send_message(
                        f"❌ `{source}` is not in the configured Lemmy communities.",
                        ephemeral=True,
                    )
                    return

                await interaction.response.send_message(f"🔍 Fetching meme from {lemmy_source}...", ephemeral=True)
                memes = await self.fetch_lemmy_meme(lemmy_source)
                source_display = lemmy_source
            else:
                # Reddit subreddit - normalize the input
                subreddit = source.lower().strip().replace("r/", "")

                if not subreddit:  # Empty after stripping
                    await interaction.response.send_message("❌ Please provide a valid subreddit name.", ephemeral=True)
                    return

                if subreddit not in self.meme_subreddits:
                    await interaction.response.send_message(
                        f"❌ r/{subreddit} is not in the configured subreddits.", ephemeral=True
                    )
                    return

                await interaction.response.send_message(f"🔍 Fetching meme from r/{subreddit}...", ephemeral=True)
                memes = await self.fetch_reddit_meme(subreddit)
                source_display = f"r/{subreddit}"

            if not memes:
                await interaction.followup.send(
                    f"❌ No memes found from {source_display}. Try another source!", ephemeral=True
                )
                return

            # Pick random meme and post it with requester mention
            meme = random.choice(memes)

            # Convert to the format expected by post_meme
            meme_data = {
                "title": meme.get("title", "Meme"),
                "permalink": meme.get("url"),
                "url": meme.get("url"),
                "upvotes": meme.get("score", 0),
                "subreddit": source.lower().strip().replace("r/", "") if "@" not in source else f"lemmy:{source}",
                "author": meme.get("author", "Unknown"),
                "nsfw": meme.get("nsfw", False),
            }

            await self.post_meme(meme_data, interaction.channel, requested_by=interaction.user)

            # Send confirmation to user
            await interaction.followup.send("✅ Meme posted!", ephemeral=True)

            user_id = str(interaction.user.id)
            self.meme_requests[user_id] = self.meme_requests.get(user_id, 0) + 1
            self.save_meme_requests()
            logger.info(f"Meme fetched by {interaction.user} from {source_display} via slash command")
            return

        # No source specified, show Meme Hub
        embed = discord.Embed(
            title="🎭 Meme Hub",
            description=(
                "Welcome to the Meme Hub! Get trending memes from multiple sources.\n\n"
                "**Available Sources:** Reddit, Lemmy\n"
                "**Rate Limit:** 10 seconds between requests"
                if not is_admin_or_mod
                else "**Mod/Admin Access:** Full management + no cooldown"
            ),
            color=Config.PINK,
        )

        if is_admin_or_mod:
            embed.add_field(
                name="🔧 Management",
                value=(
                    "Use the buttons below to:\n"
                    "• Get random memes (no cooldown)\n"
                    "• Choose specific source\n"
                    "• Manage subreddit sources\n"
                    "• Manage Lemmy communities\n"
                    "• Toggle meme sources\n"
                    "• Test daily meme function"
                ),
                inline=False,
            )
        else:
            embed.add_field(
                name="📝 How to Use",
                value=(
                    "• **🎭 Get Random Meme** - Random from all sources\n"
                    "• **🎯 Choose Source** - Pick specific subreddit/community\n"
                    "• Or use: `/meme <source>` with autocomplete\n"
                    "*10 second cooldown between requests*"
                ),
                inline=False,
            )

        set_pink_footer(embed, bot=interaction.client.user)

        view = MemeHubView(self, is_admin_or_mod, post_to_channel_id=interaction.channel.id)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"Meme Hub opened by {interaction.user} (slash) (Mod: {is_admin_or_mod})")

    @commands.command(name="testmeme")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def test_meme(self, ctx: commands.Context):
        """
        🎭 Test the daily meme function (Mod/Admin only)
        Usage: !testmeme
        """
        await ctx.send("🧪 Testing daily meme...")

        guild = self.bot.get_guild(get_guild_id())
        if not guild:
            await ctx.send("❌ Guild not found")
            return

        channel = guild.get_channel(MEME_CHANNEL_ID)
        if not channel:
            await ctx.send(f"❌ Meme channel {MEME_CHANNEL_ID} not found")
            return

        # Allow NSFW for test posts in the configured channel
        meme = await self.get_daily_meme(allow_nsfw=True)

        if meme:
            await self.post_meme(meme, channel)
            await ctx.send(f"✅ Test meme posted to {channel.mention}")
        else:
            await ctx.send("❌ Failed to fetch test meme")

    @commands.command(name="memesubreddits")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def meme_subreddits(self, ctx: commands.Context):
        """
        🎭 List current meme subreddits (Mod/Admin only)
        Usage: !memesubreddits
        """
        embed = discord.Embed(
            title="🎭 Meme Subreddits Configuration",
            description=f"Currently using **{len(self.meme_subreddits)}** subreddits for meme sourcing.",
            color=Config.PINK,
        )

        # Split into chunks of 10 for better display
        subreddit_list = "\n".join([f"• r/{sub}" for sub in sorted(self.meme_subreddits)])
        embed.add_field(name="📍 Active Subreddits", value=subreddit_list or "None", inline=False)

        embed.add_field(
            name="🔧 Management Commands",
            value=(
                "**!addsubreddit <name>** - Add a subreddit\n"
                "**!removesubreddit <name>** - Remove a subreddit\n"
                "**!resetsubreddits** - Reset to defaults"
            ),
            inline=False,
        )

        set_pink_footer(embed, bot=self.bot.user)
        await ctx.send(embed=embed)
        logger.info(f"Subreddit list viewed by {ctx.author}")

    @commands.command(name="addsubreddit")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def add_subreddit(self, ctx: commands.Context, subreddit: str):
        """
        🎭 Add a subreddit to the meme source list (Mod/Admin only)
        Usage: !addsubreddit <subreddit_name>
        Example: !addsubreddit funny
        """
        # Clean subreddit name (remove r/ if present)
        subreddit = subreddit.lower().strip().replace("r/", "")

        if not subreddit:
            await ctx.send("❌ Please provide a subreddit name.")
            return

        if subreddit in self.meme_subreddits:
            await ctx.send(f"❌ r/{subreddit} is already in the list.")
            return

        # Test if subreddit exists and has content
        await ctx.send(f"🔍 Testing r/{subreddit}...")
        test_memes = await self.fetch_reddit_meme(subreddit)

        if not test_memes:
            await ctx.send(
                f"⚠️ r/{subreddit} returned no valid memes. It might not exist or has no image posts.\n"
                "Add anyway? React with ✅ to confirm or ❌ to cancel."
            )
            # Simple confirmation without complex reaction handling
            return

        self.meme_subreddits.append(subreddit)
        self.save_subreddits()

        await ctx.send(f"✅ Added r/{subreddit} to meme sources!\nNow using {len(self.meme_subreddits)} subreddits.")
        logger.info(f"Subreddit r/{subreddit} added by {ctx.author}")

    @commands.command(name="removesubreddit")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def remove_subreddit(self, ctx: commands.Context, subreddit: str):
        """
        🎭 Remove a subreddit from the meme source list (Mod/Admin only)
        Usage: !removesubreddit <subreddit_name>
        Example: !removesubreddit funny
        """
        # Clean subreddit name
        subreddit = subreddit.lower().strip().replace("r/", "")

        if not subreddit:
            await ctx.send("❌ Please provide a subreddit name.")
            return

        if subreddit not in self.meme_subreddits:
            await ctx.send(f"❌ r/{subreddit} is not in the current list.")
            return

        if len(self.meme_subreddits) <= 1:
            await ctx.send("❌ Cannot remove the last subreddit. Add another one first.")
            return

        self.meme_subreddits.remove(subreddit)
        self.save_subreddits()

        await ctx.send(
            f"✅ Removed r/{subreddit} from meme sources.\nNow using {len(self.meme_subreddits)} subreddits."
        )
        logger.info(f"Subreddit r/{subreddit} removed by {ctx.author}")

    @commands.command(name="resetsubreddits")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def reset_subreddits(self, ctx: commands.Context):
        """
        🎭 Reset subreddit list to defaults (Mod/Admin only)
        Usage: !resetsubreddits
        """
        self.meme_subreddits = DEFAULT_MEME_SUBREDDITS.copy()
        self.save_subreddits()

        embed = discord.Embed(
            title="🔄 Subreddits Reset",
            description=f"Reset to default configuration with **{len(self.meme_subreddits)}** subreddits.",
            color=Config.PINK,
        )

        subreddit_list = "\n".join([f"• r/{sub}" for sub in sorted(self.meme_subreddits)])
        embed.add_field(name="📍 Default Subreddits", value=subreddit_list, inline=False)

        set_pink_footer(embed, bot=self.bot.user)
        await ctx.send(embed=embed)
        logger.info(f"Subreddits reset to defaults by {ctx.author}")

    # === Lemmy Community Management Commands ===

    @commands.command(name="lemmycommunities")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def lemmy_communities(self, ctx: commands.Context):
        """
        🎭 List current Lemmy communities (Mod/Admin only)
        Usage: !lemmycommunities
        """
        embed = discord.Embed(
            title="🎭 Lemmy Communities Configuration",
            description=f"Currently using **{len(self.meme_lemmy)}** Lemmy communities for meme sourcing.",
            color=Config.PINK,
        )

        # Split into chunks for better display
        community_list = "\n".join([f"• {comm}" for comm in sorted(self.meme_lemmy)])
        embed.add_field(name="📍 Active Communities", value=community_list or "None", inline=False)

        embed.add_field(
            name="🔧 Management Commands",
            value=(
                "**!addlemmy <instance@community>** - Add a Lemmy community\n"
                "**!removelemmy <instance@community>** - Remove a community\n"
                "**!resetlemmy** - Reset to defaults\n\n"
                "Format: instance@community (e.g., lemmy.world@memes)"
            ),
            inline=False,
        )

        set_pink_footer(embed, bot=self.bot.user)
        await ctx.send(embed=embed)
        logger.info(f"Lemmy community list viewed by {ctx.author}")

    @commands.command(name="addlemmy")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def add_lemmy(self, ctx: commands.Context, community: str):
        """
        🎭 Add a Lemmy community to the meme source list (Mod/Admin only)
        Usage: !addlemmy <instance@community>
        Example: !addlemmy lemmy.world@memes
        """
        # Clean community name
        community = community.lower().strip()

        # Validate format
        if "@" not in community:
            await ctx.send("❌ Invalid format! Use instance@community (e.g., lemmy.world@memes)")
            return

        if not community:
            await ctx.send("❌ Please provide a Lemmy community in format: instance@community")
            return

        if community in self.meme_lemmy:
            await ctx.send(f"❌ {community} is already in the list.")
            return

        # Test if community exists and has content
        await ctx.send(f"🔍 Testing {community}...")
        test_memes = await self.fetch_lemmy_meme(community)

        if not test_memes:
            await ctx.send(
                f"⚠️ {community} returned no valid memes. It might not exist or has no image posts.\n"
                "Add anyway? React with ✅ to confirm or ❌ to cancel."
            )
            # Simple confirmation without complex reaction handling
            return

        self.meme_lemmy.append(community)
        self.save_lemmy_communities()

        await ctx.send(f"✅ Added {community} to meme sources!\nNow using {len(self.meme_lemmy)} Lemmy communities.")
        logger.info(f"Lemmy community {community} added by {ctx.author}")

    @commands.command(name="removelemmy")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def remove_lemmy(self, ctx: commands.Context, community: str):
        """
        🎭 Remove a Lemmy community from the meme source list (Mod/Admin only)
        Usage: !removelemmy <instance@community>
        Example: !removelemmy lemmy.world@memes
        """
        # Clean community name
        community = community.lower().strip()

        if not community:
            await ctx.send("❌ Please provide a Lemmy community.")
            return

        if community not in self.meme_lemmy:
            await ctx.send(f"❌ {community} is not in the current list.")
            return

        if len(self.meme_lemmy) <= 1:
            await ctx.send("❌ Cannot remove the last Lemmy community. Add another one first.")
            return

        self.meme_lemmy.remove(community)
        self.save_lemmy_communities()

        await ctx.send(
            f"✅ Removed {community} from meme sources.\nNow using {len(self.meme_lemmy)} Lemmy communities."
        )
        logger.info(f"Lemmy community {community} removed by {ctx.author}")

    @commands.command(name="resetlemmy")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def reset_lemmy(self, ctx: commands.Context):
        """
        🎭 Reset Lemmy community list to defaults (Mod/Admin only)
        Usage: !resetlemmy
        """
        self.meme_lemmy = DEFAULT_MEME_LEMMY.copy()
        self.save_lemmy_communities()

        embed = discord.Embed(
            title="🔄 Lemmy Communities Reset",
            description=f"Reset to default configuration with **{len(self.meme_lemmy)}** Lemmy communities.",
            color=Config.PINK,
        )

        community_list = "\n".join([f"• {comm}" for comm in sorted(self.meme_lemmy)])
        embed.add_field(name="📍 Default Communities", value=community_list, inline=False)

        set_pink_footer(embed, bot=self.bot.user)
        await ctx.send(embed=embed)
        logger.info(f"Lemmy communities reset to defaults by {ctx.author}")

    # === Source Management Commands ===

    @commands.command(name="memesources")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def meme_sources_cmd(self, ctx: commands.Context):
        """
        🎭 List all enabled meme sources (Mod/Admin only)
        Usage: !memesources
        """
        embed = discord.Embed(
            title="🎭 Active Meme Sources",
            description=f"Currently using **{len(self.meme_sources)}** meme sources.",
            color=Config.PINK,
        )

        # Show enabled sources (extend source_display when adding new sources)
        source_display = {"reddit": "🔥 Reddit"}

        enabled_list = "\n".join([f"• {source_display.get(src, src)}" for src in self.meme_sources])
        embed.add_field(name="✅ Enabled Sources", value=enabled_list if enabled_list else "None", inline=False)

        # Show disabled sources (extend all_sources when adding new sources)
        all_sources = ["reddit"]
        disabled = [src for src in all_sources if src not in self.meme_sources]
        if disabled:
            disabled_list = "\n".join([f"• {source_display.get(src, src)}" for src in disabled])
            embed.add_field(name="❌ Disabled Sources", value=disabled_list, inline=False)

        embed.add_field(
            name="💡 Management",
            value=(
                "Use `!enablesource <source>` and `!disablesource <source>` to toggle sources.\n"
                "Currently available: `reddit`\n\n"
                "More sources can be added in the future"
            ),
            inline=False,
        )

        set_pink_footer(embed, bot=self.bot.user)
        await ctx.send(embed=embed)

    @commands.command(name="enablesource")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def enable_source(self, ctx: commands.Context, source: str):
        """
        🎭 Enable a meme source (Mod/Admin only)
        Usage: !enablesource <source>
        Example: !enablesource reddit
        """
        source = source.lower().strip()
        valid_sources = ["reddit"]  # Extend when adding new sources

        if source not in valid_sources:
            valid_list = ", ".join([f"`{s}`" for s in valid_sources])
            await ctx.send(f"❌ Invalid source: `{source}`\nValid sources: {valid_list}")
            return

        if source in self.meme_sources:
            await ctx.send(f"⚠️ Source `{source}` is already enabled!")
            return

        self.meme_sources.append(source)
        self.save_sources()

        await ctx.send(f"✅ Enabled `{source}` meme source.\nNow using {len(self.meme_sources)} sources.")
        logger.info(f"Source {source} enabled by {ctx.author}")

    @commands.command(name="disablesource")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def disable_source(self, ctx: commands.Context, source: str):
        """
        🎭 Disable a meme source (Mod/Admin only)
        Usage: !disablesource <source>
        Example: !disablesource 4chan
        """
        source = source.lower().strip()

        if source not in self.meme_sources:
            await ctx.send(f"⚠️ Source `{source}` is not currently enabled!")
            return

        if len(self.meme_sources) <= 1:
            await ctx.send("❌ Cannot disable last source! At least one source must be enabled.")
            return

        self.meme_sources.remove(source)
        self.save_sources()

        await ctx.send(f"✅ Disabled `{source}` meme source.\nNow using {len(self.meme_sources)} sources.")
        logger.info(f"Source {source} disabled by {ctx.author}")

    @commands.command(name="resetsources")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def reset_sources(self, ctx: commands.Context):
        """
        🎭 Reset meme sources to defaults (Mod/Admin only)
        Usage: !resetsources
        """
        self.meme_sources = MEME_SOURCES.copy()
        self.save_sources()

        embed = discord.Embed(
            title="🔄 Sources Reset",
            description=f"Reset to default configuration with **{len(self.meme_sources)}** sources.",
            color=Config.PINK,
        )

        # Extend source_display when adding new sources
        source_display = {"reddit": "🔥 Reddit"}
        source_list = "\n".join([f"• {source_display.get(src, src)}" for src in self.meme_sources])
        embed.add_field(name="📍 Default Sources", value=source_list, inline=False)

        set_pink_footer(embed, bot=self.bot.user)
        await ctx.send(embed=embed)
        logger.info(f"Sources reset to defaults by {ctx.author}")

    @commands.command(name="dailyconfig")
    @commands.check(lambda ctx: is_mod_or_admin(ctx.author))
    async def daily_config_command(self, ctx: commands.Context):
        """
        ⚙️ Configure daily meme task settings (Mod/Admin only)
        Usage: !dailyconfig
        """
        from ._DailyMemeViews import DailyConfigView

        embed = self.get_daily_config_embed()
        view = DailyConfigView(self)
        await ctx.send(embed=embed, view=view)
        logger.info(f"Daily config opened by {ctx.author}")

    def get_daily_config_embed(self) -> discord.Embed:
        """Create embed showing current daily meme configuration"""
        config = self.daily_config

        embed = discord.Embed(
            title="⚙️ Daily Meme Configuration",
            description="Configure when and how the daily meme is posted.",
            color=Config.PINK,
        )

        # Status
        status = "✅ Enabled" if config.get("enabled") else "❌ Disabled"
        embed.add_field(name="📊 Status", value=status, inline=True)

        # Time
        hour = config.get("hour", 12)
        minute = config.get("minute", 0)
        embed.add_field(name="⏰ Time", value=f"{hour:02d}:{minute:02d}", inline=True)

        # Channel
        channel_id = config.get("channel_id", MEME_CHANNEL_ID)
        embed.add_field(name="📺 Channel", value=f"<#{channel_id}>", inline=True)

        # NSFW
        nsfw_status = "✅ Allowed" if config.get("allow_nsfw") else "❌ Disabled"
        embed.add_field(name="🔞 NSFW", value=nsfw_status, inline=True)

        # Ping Role
        role_id = config.get("role_id")
        role_display = f"<@&{role_id}>" if role_id else "None"
        embed.add_field(name="🔔 Ping Role", value=role_display, inline=True)

        # Empty field for spacing
        embed.add_field(name="\u200b", value="\u200b", inline=True)

        # Selection Preferences
        embed.add_field(
            name="🎯 Selection Preferences",
            value=(
                f"**Min Score:** {config.get('min_score', 100):,} upvotes\n"
                f"**Max Sources:** {config.get('max_sources', 5)} subreddits/communities\n"
                f"**Pool Size:** Top {config.get('pool_size', 50)} memes"
            ),
            inline=False,
        )

        # Configured Subreddits
        use_subs = config.get("use_subreddits", [])
        if use_subs:
            subs_display = ", ".join([f"r/{sub}" for sub in use_subs[:10]])
            if len(use_subs) > 10:
                subs_display += f" (+{len(use_subs) - 10} more)"
            embed.add_field(name="📍 Reddit Sources", value=subs_display, inline=False)
        else:
            embed.add_field(name="📍 Reddit Sources", value="*All configured subreddits*", inline=False)

        # Configured Lemmy
        use_lemmy = config.get("use_lemmy", [])
        if use_lemmy:
            lemmy_display = ", ".join(use_lemmy[:10])
            if len(use_lemmy) > 10:
                lemmy_display += f" (+{len(use_lemmy) - 10} more)"
            embed.add_field(name="🌐 Lemmy Sources", value=lemmy_display, inline=False)
        else:
            embed.add_field(name="🌐 Lemmy Sources", value="*All configured communities*", inline=False)

        set_pink_footer(embed, bot=self.bot.user)
        return embed


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(DailyMeme(bot))
