import discord
from discord.ext import commands
from discord import app_commands
import aiohttp
import logging
import asyncio
from typing import Optional, Dict, Any, List
from difflib import get_close_matches

from Config import PINK, get_guild_id
from Utils.EmbedUtils import set_pink_footer
from Utils.CacheUtils import file_cache

logger = logging.getLogger(__name__)


class WarframeHubView(discord.ui.View):
    """Interactive view for Warframe Hub with all features"""

    def __init__(self, cog: "Warframe"):
        super().__init__(timeout=None)  # Persistent view
        self.cog = cog

    @discord.ui.button(label="Game Status", style=discord.ButtonStyle.primary, emoji="🌌", custom_id="wf_status_button")
    async def status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show current Warframe status"""
        await interaction.response.defer(ephemeral=True)

        try:
            embed = await self.cog.create_status_embed()
            view = WarframeStatusView(self.cog)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            logger.info(f"Warframe status viewed by {interaction.user} (hub button)")
        except Exception as e:
            logger.error(f"Error in status_button: {e}")
            await interaction.followup.send("❌ Error fetching Warframe status.", ephemeral=True)

    @discord.ui.button(
        label="Market Search", style=discord.ButtonStyle.primary, emoji="💰", custom_id="wf_market_button"
    )
    async def market_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Open modal for market search"""
        await interaction.response.send_modal(WarframeMarketModal(self.cog))

    @discord.ui.button(
        label="Invasions", style=discord.ButtonStyle.primary, emoji="🌍", custom_id="wf_invasions_button"
    )
    async def invasions_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show active invasions"""
        await interaction.response.defer(ephemeral=True)

        try:
            invasions = await self.cog.get_invasions()
            if not invasions:
                await interaction.followup.send("❌ No active invasions found.", ephemeral=True)
                return

            embed = discord.Embed(title="🌍 Active Invasions", color=PINK)

            for invasion in invasions[:5]:  # Max 5 invasions
                node = invasion.get("node", "Unknown")
                attacker = invasion.get("attackerReward", {}).get("item", "Unknown")
                defender = invasion.get("defenderReward", {}).get("item", "Unknown")
                completion = invasion.get("completion", 0)

                embed.add_field(
                    name=f"📍 {node}",
                    value=f"**Attacker:** {attacker}\n**Defender:** {defender}\n**Progress:** {completion}%",
                    inline=True,
                )

            set_pink_footer(embed, bot=self.cog.bot.user)
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Invasions viewed by {interaction.user} (hub button)")
        except Exception as e:
            logger.error(f"Error in invasions_button: {e}")
            await interaction.followup.send("❌ Error fetching invasion data.", ephemeral=True)

    @discord.ui.button(label="Sortie", style=discord.ButtonStyle.primary, emoji="⚔️", custom_id="wf_sortie_button")
    async def sortie_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show current sortie"""
        await interaction.response.defer(ephemeral=True)

        try:
            sortie = await self.cog.get_sortie()
            if not sortie:
                await interaction.followup.send("❌ No active sortie found.", ephemeral=True)
                return

            embed = discord.Embed(title="⚔️ Current Sortie", color=PINK)

            boss = sortie.get("boss", "Unknown")
            faction = sortie.get("faction", "Unknown")
            embed.add_field(name="Boss", value=f"**{boss}** ({faction})", inline=False)

            # Variants
            variants = sortie.get("variants", [])
            for i, variant in enumerate(variants, 1):
                mission = variant.get("missionType", "Unknown")
                modifier = variant.get("modifier", "Unknown")
                node = variant.get("node", "Unknown")
                embed.add_field(name=f"Mission {i}", value=f"**{mission}**\n{modifier}\n*{node}*", inline=True)

            set_pink_footer(embed, bot=self.cog.bot.user)
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"Sortie viewed by {interaction.user} (hub button)")
        except Exception as e:
            logger.error(f"Error in sortie_button: {e}")
            await interaction.followup.send("❌ Error fetching sortie data.", ephemeral=True)


class WarframeMarketModal(discord.ui.Modal, title="🔍 Search Warframe Market"):
    """Modal for searching items on the market"""

    item_name = discord.ui.TextInput(
        label="Item Name",
        placeholder="e.g., ash prime set, vasto prime barrel",
        required=True,
        max_length=100,
    )

    def __init__(self, cog: "Warframe"):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        """Handle market search submission"""
        await interaction.response.defer(ephemeral=True)

        item_name = self.item_name.value

        try:
            items = await self.cog.search_items(item_name)
            if not items:
                suggestion_text = (
                    f"❌ No items found matching **'{item_name}'**.\n\n"
                    "**Tips:**\n"
                    "• Try a different search term (e.g., 'ash prime' instead of 'ash p')\n"
                    "• Use the full item name\n"
                    "• Try searching for individual parts (e.g., 'ash prime blueprint')"
                )
                await interaction.followup.send(suggestion_text, ephemeral=True)
                return

            # Show first result with interactive buttons
            item = items[0]
            item_name_display = item.get("i18n", {}).get("en", {}).get("name", "Unknown Item")
            stats = await self.cog.get_item_stats(item["slug"])

            if stats:
                embed = await self.cog.create_market_embed(stats, item_name_display)
                view = WarframeMarketView(self.cog, item)
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            else:
                embed = discord.Embed(
                    title=f"📦 {item_name_display}", description="Market data temporarily unavailable.", color=PINK
                )
                set_pink_footer(embed, bot=self.cog.bot.user)
                await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(f"Market search for '{item_name}' by {interaction.user} (hub modal)")

        except Exception as e:
            logger.error(f"Error in market modal: {e}")
            await interaction.followup.send("❌ Error searching market. Please try again later.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        """Handle modal errors"""
        logger.error(f"Modal error for {interaction.user}: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ An unexpected error occurred. Please try again later.", ephemeral=True
            )
        else:
            await interaction.followup.send("❌ An unexpected error occurred. Please try again later.", ephemeral=True)


class WarframeStatusView(discord.ui.View):
    """Interactive view for Warframe status dashboard"""

    def __init__(self, cog: "Warframe"):
        super().__init__(timeout=300)  # 5 minutes
        self.cog = cog

    async def on_timeout(self):
        """Disable all buttons when view times out"""
        for item in self.children:
            item.disabled = True
        self.stop()

    @discord.ui.button(label="Alerts", style=discord.ButtonStyle.primary, emoji="🚨")
    async def show_alerts(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show active alerts"""
        await interaction.response.defer(ephemeral=True)

        alerts = await self.cog.get_alerts()
        embed = discord.Embed(title="🚨 Active Alerts", color=PINK)

        if alerts:
            for alert in alerts[:5]:
                mission = alert.get("mission", {})
                reward_types = alert.get("rewardTypes", ["Unknown"])
                embed.add_field(
                    name=f"{mission.get('type', 'Unknown')}", value=f"Rewards: {', '.join(reward_types)}", inline=False
                )
        else:
            embed.add_field(
                name="No Active Alerts",
                value="No alerts are currently active in the game.",
                inline=False,
            )

        set_pink_footer(embed, bot=self.cog.bot.user)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Fissures", style=discord.ButtonStyle.primary, emoji="🌌")
    async def show_fissures(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show active void fissures"""
        await interaction.response.defer(ephemeral=True)

        fissures = await self.cog.get_fissures()
        embed = discord.Embed(title="🌌 Void Fissures", color=PINK)

        if fissures:
            for fissure in fissures[:5]:
                mission = fissure.get("mission", {})
                tier = fissure.get("tier", "Unknown")
                embed.add_field(
                    name=f"{tier} - {mission.get('type', 'Unknown')}",
                    value=f"Location: {fissure.get('node', 'Unknown')}",
                    inline=False,
                )
        else:
            embed.add_field(
                name="No Active Fissures",
                value="No void fissures are currently active in the game.",
                inline=False,
            )

        set_pink_footer(embed, bot=self.cog.bot.user)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Sortie", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def show_sortie(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show current sortie"""
        await interaction.response.defer(ephemeral=True)

        sortie = await self.cog.get_sortie()
        embed = discord.Embed(title="⚔️ Current Sortie", color=PINK)

        if sortie and not sortie.get("expired", True):
            boss = sortie.get("boss", "Unknown")
            faction = sortie.get("faction", "Unknown")
            embed.add_field(name="Boss", value=f"**{boss}** ({faction})", inline=False)

            variants = sortie.get("variants", [])
            for i, variant in enumerate(variants, 1):
                mission = variant.get("missionType", "Unknown")
                modifier = variant.get("modifier", "Unknown")
                embed.add_field(name=f"Mission {i}", value=f"**{mission}**\n{modifier}", inline=True)
        else:
            embed.add_field(
                name="No Active Sortie",
                value="No sortie is currently active.",
                inline=False,
            )

        set_pink_footer(embed, bot=self.cog.bot.user)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Invasions", style=discord.ButtonStyle.primary, emoji="🌍")
    async def show_invasions(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show active invasions"""
        await interaction.response.defer(ephemeral=True)

        invasions = await self.cog.get_invasions()
        embed = discord.Embed(title="🌍 Active Invasions", color=PINK)

        if invasions:
            for invasion in invasions[:3]:
                node = invasion.get("node", "Unknown")
                attacker = invasion.get("attackerReward", {}).get("item", "Unknown")
                defender = invasion.get("defenderReward", {}).get("item", "Unknown")
                completion = invasion.get("completion", 0)
                embed.add_field(
                    name=f"📍 {node}",
                    value=f"**Attacker:** {attacker}\n**Defender:** {defender}\n**Progress:** {completion}%",
                    inline=False,
                )
        else:
            embed.add_field(
                name="No Active Invasions",
                value="No invasions are currently active in the game.",
                inline=False,
            )

        set_pink_footer(embed, bot=self.cog.bot.user)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh all status data"""
        await interaction.response.defer(ephemeral=True)

        embed = await self.cog.create_status_embed()
        embed.set_footer(text=f"🔄 Refreshed • {embed.footer.text if embed.footer else ''}")
        await interaction.followup.send(embed=embed, ephemeral=True)


class WarframeOrderSelectView(discord.ui.View):
    """View for selecting specific orders to copy trade messages"""

    def __init__(self, cog: "Warframe", item_data: Dict[str, Any], orders_data: Dict[str, Any]):
        super().__init__(timeout=300)
        self.cog = cog
        self.item_data = item_data
        self.orders_data = orders_data

        # Add select menu for orders
        self.add_order_select()

    def add_order_select(self):
        """Add select menu with top orders"""
        sell_orders = self.orders_data.get("sell_orders", [])
        buy_orders = self.orders_data.get("buy_orders", [])

        options = []

        # Add top 3 sell orders (best prices to buy from)
        sorted_sell = sorted(sell_orders, key=lambda x: x.get("platinum", 0))[:3]
        for i, order in enumerate(sorted_sell, 1):
            price = order.get("platinum", 0)
            user_data = order.get("user", {})
            user = user_data.get("ingameName") or user_data.get("ingame_name", "Unknown")
            status = user_data.get("status", "offline")
            emoji = "🟢" if status in ["ingame", "online"] else "⚫"

            options.append(
                discord.SelectOption(
                    label=f"Buy: {price}💎 from {user}",
                    description=f"{emoji} {status.capitalize()} • Click to copy trade message",
                    value=f"buy_{order.get('id', i)}",
                    emoji="💰",
                )
            )

        # Add top 3 buy orders (best prices to sell to)
        sorted_buy = sorted(buy_orders, key=lambda x: x.get("platinum", 0), reverse=True)[:3]
        for i, order in enumerate(sorted_buy, 1):
            price = order.get("platinum", 0)
            user_data = order.get("user", {})
            user = user_data.get("ingameName") or user_data.get("ingame_name", "Unknown")
            status = user_data.get("status", "offline")
            emoji = "🟢" if status in ["ingame", "online"] else "⚫"

            options.append(
                discord.SelectOption(
                    label=f"Sell: {price}💎 to {user}",
                    description=f"{emoji} {status.capitalize()} • Click to copy trade message",
                    value=f"sell_{order.get('id', i)}",
                    emoji="🛒",
                )
            )

        if options:
            select = discord.ui.Select(
                placeholder="Select an order to copy trade message...",
                options=options[:25],  # Discord limit
                custom_id="order_select",
            )
            select.callback = self.order_select_callback
            self.add_item(select)

    async def order_select_callback(self, interaction: discord.Interaction):
        """Handle order selection"""
        selection = interaction.data["values"][0]
        order_type, order_id = selection.split("_", 1)

        # Find the selected order
        if order_type == "buy":
            orders = sorted(self.orders_data.get("sell_orders", []), key=lambda x: x.get("platinum", 0))
        else:
            orders = sorted(self.orders_data.get("buy_orders", []), key=lambda x: x.get("platinum", 0), reverse=True)

        # Find order by ID or index
        selected_order = None
        for order in orders:
            if str(order.get("id", "")) == order_id:
                selected_order = order
                break

        if not selected_order and orders:
            # Fallback to index if ID doesn't match
            try:
                idx = int(order_id) - 1
                if 0 <= idx < len(orders):
                    selected_order = orders[idx]
            except (ValueError, IndexError):
                pass

        if not selected_order:
            await interaction.response.send_message("❌ Order not found.", ephemeral=True)
            return

        # Extract order details
        price = selected_order.get("platinum", 0)
        user_data = selected_order.get("user", {})
        username = user_data.get("ingameName") or user_data.get("ingame_name", "Unknown")
        item_name = self.item_data.get("i18n", {}).get("en", {}).get("name", "Unknown")

        # Create trade message (warframe.market style)
        if order_type == "buy":
            trade_msg = f"/w {username} Hi! I want to buy: {item_name} for {price} platinum. (warframe.market)"
            action = "buy from"
        else:
            trade_msg = f"/w {username} Hi! I want to sell: {item_name} for {price} platinum. (warframe.market)"
            action = "sell to"

        # Send message with copy instructions
        embed = discord.Embed(
            title="📋 Trade Message Ready",
            description=f"Copy this message and paste it in Warframe's in-game chat to {action} **{username}**:",
            color=PINK,
        )

        embed.add_field(
            name="💬 Message",
            value=f"```\n{trade_msg}\n```",
            inline=False,
        )

        embed.add_field(
            name="📝 Instructions",
            value=(
                "1. Copy the message above\n"
                "2. Open Warframe and press **T** to open chat\n"
                "3. Paste the message and press Enter\n"
                "4. Wait for the seller/buyer to respond"
            ),
            inline=False,
        )

        embed.add_field(
            name="💡 Tip",
            value=f"Make sure **{username}** is online/ingame before messaging!",
            inline=False,
        )

        set_pink_footer(embed, bot=self.cog.bot.user)

        await interaction.response.send_message(embed=embed, ephemeral=True)
        logger.info(f"Trade message copied by {interaction.user} for {item_name} @ {price}💎")

    async def on_timeout(self):
        """Disable all items when view times out"""
        for item in self.children:
            item.disabled = True
        self.stop()


class WarframeOrdersView(discord.ui.View):
    """Interactive view for order listings with trade message copy"""

    def __init__(self, cog: "Warframe", item_data: Dict[str, Any]):
        super().__init__(timeout=300)  # 5 minutes
        self.cog = cog
        self.item_data = item_data

    async def on_timeout(self):
        """Disable all buttons when view times out"""
        for item in self.children:
            item.disabled = True
        self.stop()

    @discord.ui.button(label="Copy Trade Msg", style=discord.ButtonStyle.success, emoji="📝")
    async def copy_trade_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show order selection for copying trade messages"""
        await interaction.response.defer(ephemeral=True)

        # Get top orders
        top_data = await self.cog.get_item_top_orders(self.item_data["slug"])
        if not top_data:
            await interaction.followup.send(
                "❌ Unable to fetch orders. The market API may be temporarily unavailable.", ephemeral=True
            )
            return

        # Show selection view
        view = WarframeOrderSelectView(self.cog, self.item_data, top_data)
        embed = discord.Embed(
            title="📝 Select Order to Trade",
            description=(
                "Choose an order from the list below to copy the trade message.\n"
                "🟢 = Online/Ingame • ⚫ = Offline\n\n"
                "The message will be formatted exactly like warframe.market for easy copy-paste!"
            ),
            color=PINK,
        )

        item_name = self.item_data.get("i18n", {}).get("en", {}).get("name", "Unknown")
        embed.set_footer(text=f"Trading: {item_name}")

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh_orders(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the orders"""
        await interaction.response.defer(ephemeral=True)

        # Fetch fresh orders
        orders = await self.cog.get_item_orders(self.item_data["slug"])
        if orders:
            embed = await self.cog.create_orders_embed(self.item_data, orders)
            embed.set_footer(text=f"🔄 Refreshed • {embed.footer.text if embed.footer else ''}")
            # Create new view with same item data
            view = WarframeOrdersView(self.cog, self.item_data)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        else:
            await interaction.followup.send(
                "❌ Unable to refresh orders. The market API may be temporarily unavailable.", ephemeral=True
            )


class WarframeMarketView(discord.ui.View):
    """Interactive view for Warframe market browsing"""

    def __init__(self, cog: "Warframe", item_data: Dict[str, Any]):
        super().__init__(timeout=300)  # 5 minutes
        self.cog = cog
        self.item_data = item_data
        self.current_page = 0

    async def on_timeout(self):
        """Disable all buttons when view times out"""
        for item in self.children:
            item.disabled = True
        self.stop()

    @discord.ui.button(label="View Orders", style=discord.ButtonStyle.primary, emoji="📋")
    async def view_orders(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show buy/sell orders for this item"""
        await interaction.response.defer(ephemeral=True)

        orders = await self.cog.get_item_orders(self.item_data["slug"])
        if not orders:
            await interaction.followup.send(
                "❌ Unable to fetch orders right now. The market API may be temporarily unavailable.", ephemeral=True
            )
            return

        embed = await self.cog.create_orders_embed(self.item_data, orders)
        # Use WarframeOrdersView instead of sending embed alone
        view = WarframeOrdersView(self.cog, self.item_data)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Copy Trade Msg", style=discord.ButtonStyle.success, emoji="📝")
    async def copy_trade_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Show order selection for copying trade messages"""
        await interaction.response.defer(ephemeral=True)

        # Get top orders
        top_data = await self.cog.get_item_top_orders(self.item_data["slug"])
        if not top_data:
            await interaction.followup.send(
                "❌ Unable to fetch orders. The market API may be temporarily unavailable.", ephemeral=True
            )
            return

        # Show selection view
        view = WarframeOrderSelectView(self.cog, self.item_data, top_data)
        embed = discord.Embed(
            title="📝 Select Order to Trade",
            description=(
                "Choose an order from the list below to copy the trade message.\n"
                "🟢 = Online/Ingame • ⚫ = Offline\n\n"
                "The message will be formatted exactly like warframe.market for easy copy-paste!"
            ),
            color=PINK,
        )

        item_name = self.item_data.get("i18n", {}).get("en", {}).get("name", "Unknown")
        embed.set_footer(text=f"Trading: {item_name}")

        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="Refresh Price", style=discord.ButtonStyle.secondary, emoji="🔄")
    async def refresh_price(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Refresh the price data"""
        await interaction.response.defer(ephemeral=True)

        # Force refresh by bypassing cache
        fresh_data = await self.cog.get_item_stats(self.item_data["slug"], force_refresh=True)
        if fresh_data:
            item_name = self.item_data.get("i18n", {}).get("en", {}).get("name", "Unknown Item")
            embed = await self.cog.create_market_embed(fresh_data, item_name)
            embed.set_footer(text=f"🔄 Refreshed • {embed.footer.text if embed.footer else ''}")
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(
                "❌ Unable to refresh price data. The market API may be temporarily unavailable.", ephemeral=True
            )


class Warframe(commands.Cog):
    """Warframe tracking, market, and information cog"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        # Multiple API sources for redundancy
        self.apis = {
            "warframestat": "https://api.warframestat.us/pc",  # Currently broken (404s)
            "warframestat_alt": "https://api.warframestat.us",  # Alternative base URL
            "tenno_tools": "https://api.tenno.tools/worldstate/pc",  # Working alternative!
            "market": "https://api.warframe.market/v2",
            "wfcd": "https://api.wfcd.gg",
        }
        # Keep backward compatibility
        self.market_api = self.apis["market"]
        self.wfcd_api = self.apis["wfcd"]

    async def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if hasattr(self, "session") and not self.session.closed:
            await self.session.close()
            logger.info("Warframe HTTP session closed.")

    async def fetch_api_data(self, url: str, cache_key: str = None, ttl: int = 300) -> Optional[Any]:
        """Fetch data from API with caching and error handling"""

        async def _fetch():
            try:
                # Allow redirects and increase timeout
                async with self.session.get(
                    url, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=True
                ) as response:
                    if response.status == 200:
                        content_type = response.headers.get("content-type", "")
                        if "application/json" in content_type:
                            return await response.json()
                        else:
                            logger.warning(f"Unexpected content type for {url}: {content_type}")
                            return None
                    else:
                        logger.warning(f"API error {response.status} for {url}")
                        # Log the response text for debugging
                        text = await response.text()
                        logger.warning(f"Response text: {text[:200]}...")
                        return None
            except asyncio.TimeoutError:
                logger.warning(f"Timeout fetching {url}")
                return None
            except Exception as e:
                logger.error(f"Error fetching {url}: {e}")
                return None

        if cache_key:
            return await file_cache.get_or_set(cache_key, _fetch, ttl=ttl)
        else:
            return await _fetch()

    # Warframe Status Methods with Fallbacks
    async def get_alerts(self) -> Optional[List[Dict[str, Any]]]:
        """Get active alerts with fallback handling"""
        # Try tenno.tools API first (working alternative)
        try:
            data = await self.fetch_api_data(f"{self.apis['tenno_tools']}", "warframe_tenno_tools", 60)
            if data and isinstance(data, dict) and "alerts" in data:
                alerts_data = data["alerts"].get("data", [])
                if alerts_data:
                    # Convert tenno.tools format to expected format
                    converted_alerts = []
                    for alert in alerts_data:
                        converted_alert = {
                            "id": alert.get("id"),
                            "expired": False,  # tenno.tools only shows active ones
                            "mission": {
                                "type": alert.get("missionType", "Unknown"),
                                "node": alert.get("location", "Unknown"),
                                "faction": alert.get("faction", "Unknown"),
                            },
                            "rewardTypes": [],
                        }
                        # Extract reward types
                        rewards = alert.get("rewards", {})
                        items = rewards.get("items", [])
                        for item in items:
                            converted_alert["rewardTypes"].append(item.get("name", "Unknown"))

                        converted_alerts.append(converted_alert)

                    logger.info(f"Successfully fetched {len(converted_alerts)} alerts from tenno.tools")
                    return converted_alerts
        except Exception as e:
            logger.warning(f"Failed to get alerts from tenno.tools: {e}")

        # Fallback to warframestat.us (likely to fail)
        apis_to_try = [
            (f"{self.apis['warframestat']}/alerts", "warframe_alerts"),
            (f"{self.apis['warframestat_alt']}/alerts", "warframe_alerts_alt"),
        ]

        for url, cache_key in apis_to_try:
            try:
                data = await self.fetch_api_data(url, cache_key, 60)
                if data and isinstance(data, list):
                    return [alert for alert in data if not alert.get("expired", True)]
                elif data and isinstance(data, dict) and "data" in data:
                    alerts = data.get("data", [])
                    return [alert for alert in alerts if not alert.get("expired", True)]
            except Exception as e:
                logger.warning(f"Failed to get alerts from {url}: {e}")
                continue

        logger.info("Using fallback: No alerts available (all APIs failed)")
        return []

    async def get_fissures(self) -> Optional[List[Dict[str, Any]]]:
        """Get active void fissures with fallback handling"""
        # Try tenno.tools API first (working alternative)
        try:
            data = await self.fetch_api_data(f"{self.apis['tenno_tools']}", "warframe_tenno_tools", 60)
            if data and isinstance(data, dict) and "fissures" in data:
                fissures_data = data["fissures"].get("data", [])
                if fissures_data:
                    # Convert tenno.tools format to expected format
                    converted_fissures = []
                    for fissure in fissures_data:
                        converted_fissure = {
                            "id": fissure.get("id"),
                            "expired": False,  # tenno.tools only shows active ones
                            "mission": {
                                "type": fissure.get("missionType", "Unknown"),
                                "node": fissure.get("location", "Unknown"),
                                "faction": fissure.get("faction", "Unknown"),
                            },
                            "tier": fissure.get("tier", "Unknown"),
                            "node": fissure.get("location", "Unknown"),
                        }
                        converted_fissures.append(converted_fissure)

                    logger.info(f"Successfully fetched {len(converted_fissures)} fissures from tenno.tools")
                    return converted_fissures
        except Exception as e:
            logger.warning(f"Failed to get fissures from tenno.tools: {e}")

        # Fallback to warframestat.us (likely to fail)
        apis_to_try = [
            (f"{self.apis['warframestat']}/fissures", "warframe_fissures"),
            (f"{self.apis['warframestat_alt']}/fissures", "warframe_fissures_alt"),
        ]

        for url, cache_key in apis_to_try:
            try:
                data = await self.fetch_api_data(url, cache_key, 60)
                if data and isinstance(data, list):
                    return [fissure for fissure in data if not fissure.get("expired", True)]
                elif data and isinstance(data, dict) and "data" in data:
                    fissures = data.get("data", [])
                    return [fissure for fissure in fissures if not fissure.get("expired", True)]
            except Exception as e:
                logger.warning(f"Failed to get fissures from {url}: {e}")
                continue

        logger.info("Using fallback: No fissures available (all APIs failed)")
        return []

    async def get_invasions(self) -> Optional[List[Dict[str, Any]]]:
        """Get active invasions with fallback handling"""
        # Try tenno.tools API first (working alternative)
        try:
            data = await self.fetch_api_data(f"{self.apis['tenno_tools']}", "warframe_tenno_tools", 300)
            if data and isinstance(data, dict) and "invasions" in data:
                invasions_data = data["invasions"].get("data", [])
                if invasions_data:
                    # Convert tenno.tools format to expected format
                    converted_invasions = []
                    for invasion in invasions_data:
                        # Calculate completion percentage
                        score = invasion.get("score", 0)
                        end_score = invasion.get("endScore", 1)
                        completion = round((score / end_score) * 100) if end_score > 0 else 0

                        converted_invasion = {
                            "id": invasion.get("id"),
                            "completed": completion >= 100,
                            "node": invasion.get("location", "Unknown"),
                            "completion": completion,
                            "attackerReward": {
                                "item": (
                                    invasion.get("rewardsAttacker", {}).get("items", [{}])[0].get("name", "Unknown")
                                    if invasion.get("rewardsAttacker", {}).get("items")
                                    else "Unknown"
                                )
                            },
                            "defenderReward": {
                                "item": (
                                    invasion.get("rewardsDefender", {}).get("items", [{}])[0].get("name", "Unknown")
                                    if invasion.get("rewardsDefender", {}).get("items")
                                    else "Unknown"
                                )
                            },
                        }
                        converted_invasions.append(converted_invasion)

                    # Filter out completed invasions
                    active_invasions = [inv for inv in converted_invasions if not inv["completed"]]
                    logger.info(f"Successfully fetched {len(active_invasions)} active invasions from tenno.tools")
                    return active_invasions
        except Exception as e:
            logger.warning(f"Failed to get invasions from tenno.tools: {e}")

        # Fallback to warframestat.us (likely to fail)
        apis_to_try = [
            (f"{self.apis['warframestat']}/invasions", "warframe_invasions"),
            (f"{self.apis['warframestat_alt']}/invasions", "warframe_invasions_alt"),
        ]

        for url, cache_key in apis_to_try:
            try:
                data = await self.fetch_api_data(url, cache_key, 300)
                if data and isinstance(data, list):
                    return [inv for inv in data if not inv.get("completed", True)]
                elif data and isinstance(data, dict) and "data" in data:
                    invasions = data.get("data", [])
                    return [inv for inv in invasions if not inv.get("completed", True)]
            except Exception as e:
                logger.warning(f"Failed to get invasions from {url}: {e}")
                continue

        logger.info("Using fallback: No invasions available (all APIs failed)")
        return []

    async def get_sortie(self) -> Optional[Dict[str, Any]]:
        """Get current sortie with fallback handling"""
        # Try tenno.tools API first (working alternative)
        try:
            data = await self.fetch_api_data(f"{self.apis['tenno_tools']}", "warframe_tenno_tools", 1800)
            if data and isinstance(data, dict) and "sorties" in data:
                sorties_data = data["sorties"].get("data", [])
                if sorties_data and len(sorties_data) > 0:
                    sortie = sorties_data[0]  # Get first (current) sortie

                    # Convert tenno.tools format to expected format
                    converted_sortie = {
                        "id": sortie.get("id"),
                        "expired": False,  # tenno.tools only shows active ones
                        "boss": sortie.get("bossName", "Unknown"),
                        "faction": sortie.get("faction", "Unknown"),
                        "variants": [],
                    }

                    # Convert missions
                    missions = sortie.get("missions", [])
                    for mission in missions:
                        variant = {
                            "missionType": mission.get("missionType", "Unknown"),
                            "modifier": mission.get("modifier", "Unknown"),
                            "node": mission.get("location", "Unknown"),
                        }
                        converted_sortie["variants"].append(variant)

                    logger.info("Successfully fetched sortie from tenno.tools")
                    return converted_sortie
        except Exception as e:
            logger.warning(f"Failed to get sortie from tenno.tools: {e}")

        # Fallback to warframestat.us (likely to fail)
        apis_to_try = [
            (f"{self.apis['warframestat']}/sortie", "warframe_sortie"),
            (f"{self.apis['warframestat_alt']}/sortie", "warframe_sortie_alt"),
        ]

        for url, cache_key in apis_to_try:
            try:
                data = await self.fetch_api_data(url, cache_key, 1800)
                if data and isinstance(data, dict):
                    return data
            except Exception as e:
                logger.warning(f"Failed to get sortie from {url}: {e}")
                continue

        logger.info("Using fallback: No sortie available (all APIs failed)")
        return None

    # Warframe Market API Methods
    async def search_items(self, query: str) -> Optional[List[Dict[str, Any]]]:
        """Search for items by name with improved fuzzy matching"""
        all_items = await self.fetch_api_data(f"{self.market_api}/items", "warframe_items", 3600)
        if not all_items:
            return None

        # Handle v2 API response structure with data key
        if isinstance(all_items, dict) and "data" in all_items:
            items_list = all_items["data"]
        elif isinstance(all_items, list):
            items_list = all_items
        else:
            return None

        if not items_list or not isinstance(items_list, list):
            return None

        query_lower = query.lower()

        # First, try exact substring matches (highest priority)
        exact_matches = [
            item for item in items_list if query_lower in item.get("i18n", {}).get("en", {}).get("name", "").lower()
        ]

        if exact_matches:
            # Sort by relevance (shortest names first = more specific)
            exact_matches.sort(key=lambda x: len(x.get("i18n", {}).get("en", {}).get("name", "")))
            return exact_matches[:5]

        # Fallback to fuzzy matching with higher cutoff for better accuracy
        item_names = [item.get("i18n", {}).get("en", {}).get("name", "").lower() for item in items_list]
        matches = get_close_matches(query_lower, item_names, n=5, cutoff=0.6)

        return [item for item in items_list if item.get("i18n", {}).get("en", {}).get("name", "").lower() in matches]

    async def get_item_stats(self, url_name: str, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Get item statistics calculated from orders (uses top orders for efficiency)"""
        cache_key = f"warframe_item_stats_{url_name}"
        if force_refresh:
            # Clear cache by using different key temporarily
            cache_key = f"{cache_key}_fresh"

        async def _calculate_stats():
            # Try to get top orders first (more efficient)
            top_data = await self.get_item_top_orders(url_name)
            if top_data:
                # Use top orders data directly
                sell_orders = top_data.get("sell_orders", [])
                buy_orders = top_data.get("buy_orders", [])
            else:
                # Fallback to all orders
                orders = await self.get_item_orders(url_name)
                if not orders:
                    return None
                sell_orders = [o for o in orders if o.get("type") == "sell" and o.get("visible", True)]
                buy_orders = [o for o in orders if o.get("type") == "buy" and o.get("visible", True)]

            if not sell_orders:
                return {
                    "sell_orders": [],
                    "buy_orders": buy_orders,
                    "avg_price": 0,
                    "min_price": 0,
                    "max_price": 0,
                    "volume": 0,
                }

            prices = [order["platinum"] for order in sell_orders]
            avg_price = sum(prices) / len(prices)
            min_price = min(prices)
            max_price = max(prices)
            volume = sum(order["quantity"] for order in sell_orders)

            return {
                "sell_orders": sell_orders,
                "buy_orders": buy_orders,
                "avg_price": round(avg_price),
                "min_price": min_price,
                "max_price": max_price,
                "volume": volume,
            }

        return await file_cache.get_or_set(cache_key, _calculate_stats, ttl=600)  # 10 minutes cache

    async def get_item_orders(self, url_name: str) -> Optional[List[Dict[str, Any]]]:
        """Get buy/sell orders for an item"""
        data = await self.fetch_api_data(
            f"{self.market_api}/orders/item/{url_name}",
            f"warframe_orders_{url_name}",
            60,  # 1 minute cache
        )
        if data and isinstance(data, dict) and "data" in data:
            return data["data"]
        return None

    async def get_item_top_orders(self, url_name: str) -> Optional[Dict[str, Any]]:
        """Get top buy/sell orders for an item (more efficient than getting all orders)"""
        data = await self.fetch_api_data(
            f"{self.market_api}/orders/item/{url_name}/top",
            f"warframe_top_orders_{url_name}",
            60,  # 1 minute cache
        )
        if data and isinstance(data, dict) and "data" in data:
            # Convert v2 format to expected format
            return {"sell_orders": data["data"].get("sell", []), "buy_orders": data["data"].get("buy", [])}
        return None

    # WFCD API Methods
    async def search_wfcd_items(self, query: str, category: str = "weapons") -> Optional[List[Dict[str, Any]]]:
        """Search items in WFCD database"""
        data = await self.fetch_api_data(f"{self.wfcd_api}/{category}", f"wfcd_{category}", 3600)
        if not data:
            return None

        # Find close matches
        if category == "weapons":
            item_names = [item.get("name", "").lower() for item in data]
        else:
            item_names = [item.get("name", "").lower() for item in data]

        matches = get_close_matches(query.lower(), item_names, n=3, cutoff=0.7)

        if category == "weapons":
            return [item for item in data if item.get("name", "").lower() in matches]
        else:
            return [item for item in data if item.get("name", "").lower() in matches]

    # Embed Creation Methods
    async def create_status_embed(self) -> discord.Embed:
        """Create embed with current Warframe status"""
        embed = discord.Embed(title="🌌 Warframe Status", color=PINK)

        # Get data with error handling
        alerts = await self.get_alerts()
        fissures = await self.get_fissures()
        sortie = await self.get_sortie()

        # Active Alerts
        if alerts:
            alert_text = ""
            for alert in alerts[:3]:  # Show max 3 alerts
                mission = alert.get("mission", {})
                reward_types = alert.get("rewardTypes", ["Unknown"])
                alert_text += f"• **{mission.get('type', 'Unknown')}** - {', '.join(reward_types)}\n"
            embed.add_field(name="🚨 Active Alerts", value=alert_text[:1024], inline=False)
        else:
            embed.add_field(
                name="🚨 Active Alerts",
                value="No alerts are currently active.",
                inline=False,
            )

        # Void Fissures
        if fissures:
            fissure_text = ""
            for fissure in fissures[:3]:  # Show max 3 fissures
                mission = fissure.get("mission", {})
                tier = fissure.get("tier", "Unknown")
                fissure_text += f"• **{tier}** - {mission.get('type', 'Unknown')}\n"
            embed.add_field(name="🌌 Void Fissures", value=fissure_text[:1024], inline=False)
        else:
            embed.add_field(
                name="🌌 Void Fissures",
                value="No void fissures are currently active.",
                inline=False,
            )

        # Sortie
        if sortie and not sortie.get("expired", True):
            boss = sortie.get("boss", "Unknown")
            faction = sortie.get("faction", "Unknown")
            embed.add_field(name="⚔️ Sortie", value=f"**{boss}** ({faction})", inline=False)
        else:
            embed.add_field(
                name="⚔️ Sortie",
                value="No sortie is currently active.",
                inline=False,
            )

        set_pink_footer(embed, bot=self.bot.user)
        return embed

    async def create_market_embed(self, item_data: Dict[str, Any], item_name: str = None) -> discord.Embed:
        """Create embed for market item"""
        if not item_data:
            return discord.Embed(
                title="❌ No Market Data",
                description="No recent trading data available for this item.",
                color=discord.Color.red(),
            )

        # Get stats from the new structure
        avg_price = item_data.get("avg_price", 0)
        min_price = item_data.get("min_price", 0)
        max_price = item_data.get("max_price", 0)
        volume = item_data.get("volume", 0)

        embed = discord.Embed(title=f"💰 {item_name or 'Unknown Item'}", color=PINK)

        # Add timestamp to show data freshness
        import datetime

        now = datetime.datetime.now(datetime.timezone.utc)

        embed.add_field(
            name="📊 Price Statistics",
            value=f"**Average:** {avg_price:,}💎\n**Range:** {min_price:,} - {max_price:,}💎\n"
            f"**Volume:** {volume:,} orders",
            inline=False,
        )

        embed.timestamp = now

        # Try to get thumbnail from item data if available
        # Note: v2 items have thumb in i18n.en.thumb
        set_pink_footer(embed, bot=self.bot.user)
        return embed

    async def create_orders_embed(self, item_data: Dict[str, Any], orders: List[Dict[str, Any]]) -> discord.Embed:
        """Create embed showing buy/sell orders (improved with top orders)"""
        item_name = item_data.get("i18n", {}).get("en", {}).get("name", "Unknown")
        embed = discord.Embed(title=f"📋 Orders: {item_name}", color=PINK)

        # Try to get top orders for better performance
        top_data = await self.get_item_top_orders(item_data["slug"])

        if top_data:
            # Use top orders data
            sell_orders = top_data.get("sell_orders", [])
            buy_orders = top_data.get("buy_orders", [])
            source_text = "Showing top orders (most competitive prices)"
        else:
            # Fallback to provided orders
            buy_orders = [o for o in orders if o.get("type") == "buy" and o.get("visible", True)]
            sell_orders = [o for o in orders if o.get("type") == "sell" and o.get("visible", True)]
            source_text = "Showing all available orders"

        # Always show source info for clarity
        embed.add_field(
            name="ℹ️ Order Source",
            value=source_text,
            inline=False,
        )

        # Show top 5 buy orders (highest price first)
        if buy_orders:
            buy_text = ""
            for order in sorted(buy_orders, key=lambda x: x.get("platinum", 0), reverse=True)[:5]:
                price = order.get("platinum", 0)
                quantity = order.get("quantity", 1)
                # Try both camelCase (v2 API) and snake_case (v1 API) for compatibility
                user_data = order.get("user", {})
                user = user_data.get("ingameName") or user_data.get("ingame_name", "Unknown")
                buy_text += f"• {price:,}💎 x{quantity} - {user}\n"
            embed.add_field(name="🛒 Buy Orders", value=buy_text[:1024], inline=False)

        # Show top 5 sell orders (lowest price first)
        if sell_orders:
            sell_text = ""
            for order in sorted(sell_orders, key=lambda x: x.get("platinum", 0))[:5]:
                price = order.get("platinum", 0)
                quantity = order.get("quantity", 1)
                # Try both camelCase (v2 API) and snake_case (v1 API) for compatibility
                user_data = order.get("user", {})
                user = user_data.get("ingameName") or user_data.get("ingame_name", "Unknown")
                sell_text += f"• {price:,}💎 x{quantity} - {user}\n"
            embed.add_field(name="💰 Sell Orders", value=sell_text[:1024], inline=False)

        if not buy_orders and not sell_orders:
            embed.add_field(name="📋 No Orders", value="No active orders found for this item.", inline=False)

        set_pink_footer(embed, bot=self.bot.user)
        return embed

    # Commands
    async def show_warframe_hub(self, interaction: discord.Interaction) -> None:
        """Show the Warframe hub with all features"""
        embed = discord.Embed(
            title="🌌 Warframe Hub",
            description=(
                "Welcome to the Warframe tracking and market system!\n\n"
                "⚠️ **Beta Feature** - These features are currently in testing. "
                "Please report any issues you encounter!\n\n"
                "**Features:**\n"
                "• View current game status (alerts, fissures, sortie, invasions)\n"
                "• Search Warframe market for items and prices\n"
                "• Track buy/sell orders\n"
                "• Get real-time game information\n\n"
                "**Quick Access:**\n"
                "Use the buttons below to access all features instantly!"
            ),
            color=PINK,
        )

        # Add status overview
        embed.add_field(
            name="🎮 Game Status",
            value="View current alerts, fissures, sortie, and invasions in-game",
            inline=False,
        )

        embed.add_field(
            name="💰 Market",
            value="Search for items and view live trading prices",
            inline=False,
        )

        embed.add_field(
            name="💡 Quick Start",
            value=(
                "1. Click **Game Status** to see what's active right now\n"
                "2. Use **Market Search** to find item prices\n"
                "3. Click **Invasions** or **Sortie** for specific info"
            ),
            inline=False,
        )

        embed.set_footer(
            text="🧪 Beta - Features in testing | Report issues to server staff",
            icon_url=interaction.client.user.display_avatar.url if interaction.client.user else None,
        )

        view = WarframeHubView(self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        logger.info(f"Warframe hub opened by {interaction.user}")

    @commands.command(name="warframe")
    async def warframe_info(self, ctx: commands.Context):
        """🌌 Warframe Hub - Game status, market, and more (Beta)"""

        # Create a mock interaction object to use the same helper
        class MockInteraction:
            def __init__(self, ctx):
                self.user = ctx.author
                self.client = ctx.bot
                self.guild = ctx.guild
                self.channel = ctx.channel
                self._responded = False

            async def response_send_message(self, **kwargs):
                # Remove ephemeral for prefix commands (not supported)
                kwargs.pop("ephemeral", None)
                await self.channel.send(**kwargs)

        # Create mock interaction and call helper
        mock_interaction = MockInteraction(ctx)
        mock_interaction.response = type("Response", (), {"send_message": mock_interaction.response_send_message})()
        await self.show_warframe_hub(mock_interaction)

    @app_commands.command(name="warframe", description="🌌 Warframe Hub - Game status, market, and more (Beta)")
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    async def warframe_hub(self, interaction: discord.Interaction):
        """Warframe hub with all features"""
        await self.show_warframe_hub(interaction)

    @commands.command(name="warframestatus")
    async def warframe_status_legacy(self, ctx: commands.Context):
        """Show current Warframe status (legacy command)"""
        await ctx.send("🔍 Fetching Warframe information...")

        try:
            embed = await self.create_status_embed()
            view = WarframeStatusView(self)
            await ctx.send(embed=embed, view=view)
            logger.info(f"Warframe status displayed for {ctx.author}")
        except Exception as e:
            logger.error(f"Error in warframe_status_legacy: {e}")
            await ctx.send("❌ Error fetching Warframe data. Please try again later.")

    @commands.command(name="warframemarket")
    async def warframe_market(self, ctx: commands.Context, *, item_name: str):
        """Search for items on the Warframe market"""
        await ctx.send(f"🔍 Searching for **{item_name}** on Warframe Market...")

        try:
            items = await self.search_items(item_name)
            if not items:
                suggestion_text = (
                    f"❌ No items found matching **'{item_name}'**.\n\n"
                    "**Tips:**\n"
                    "• Try a different search term (e.g., 'ash prime' instead of 'ash p')\n"
                    "• Use the full item name\n"
                    "• Try searching for individual parts (e.g., 'ash prime blueprint')"
                )
                await ctx.send(suggestion_text)
                return

            # Show first result with interactive buttons
            item = items[0]
            item_name = item.get("i18n", {}).get("en", {}).get("name", "Unknown Item")
            stats = await self.get_item_stats(item["slug"])

            if stats:
                embed = await self.create_market_embed(stats, item_name)
                view = WarframeMarketView(self, item)
                await ctx.send(embed=embed, view=view)
            else:
                embed = discord.Embed(
                    title=f"📦 {item_name}", description="Market data temporarily unavailable.", color=PINK
                )
                set_pink_footer(embed, bot=self.bot.user)
                await ctx.send(embed=embed)

            logger.info(f"Warframe market search for '{item_name}' by {ctx.author}")

        except Exception as e:
            logger.error(f"Error in warframe_market: {e}")
            await ctx.send("❌ Error searching market. Please try again later.")

    @app_commands.command(name="warframemarket", description="Search Warframe market for items")
    @app_commands.guilds(discord.Object(id=get_guild_id()))
    @app_commands.describe(item_name="Name of the item to search for")
    async def warframe_market_slash(self, interaction: discord.Interaction, item_name: str):
        """Slash command for market search"""
        await interaction.response.defer()

        try:
            items = await self.search_items(item_name)
            if not items:
                suggestion_text = (
                    f"❌ No items found matching **'{item_name}'**.\n\n"
                    "**Tips:**\n"
                    "• Try a different search term (e.g., 'ash prime' instead of 'ash p')\n"
                    "• Use the full item name\n"
                    "• Try searching for individual parts (e.g., 'ash prime blueprint')"
                )
                await interaction.followup.send(suggestion_text, ephemeral=True)
                return

            # Show first result with interactive buttons
            item = items[0]
            item_name = item.get("i18n", {}).get("en", {}).get("name", "Unknown Item")
            stats = await self.get_item_stats(item["slug"])

            if stats:
                embed = await self.create_market_embed(stats, item_name)
                view = WarframeMarketView(self, item)
                await interaction.followup.send(embed=embed, view=view)
            else:
                embed = discord.Embed(
                    title=f"📦 {item_name}", description="Market data temporarily unavailable.", color=PINK
                )
                set_pink_footer(embed, bot=self.bot.user)
                await interaction.followup.send(embed=embed, ephemeral=True)

            logger.info(f"Warframe market search for '{item_name}' by {interaction.user} (slash)")

        except Exception as e:
            logger.error(f"Error in warframe_market_slash: {e}")
            await interaction.followup.send("❌ Error searching market. Please try again later.", ephemeral=True)

    @commands.command(name="warframeprofile")
    async def warframe_profile(self, ctx: commands.Context, username: str = None):
        """Show Warframe player profile (Note: Limited data available due to API restrictions)"""
        if not username:
            await ctx.send("❌ Please provide a Warframe username: `!warframeprofile <username>`")
            return

        await ctx.send(f"🔍 Searching for Warframe profile: **{username}**")

        # Note: Warframe doesn't have a public API for player profiles
        embed = discord.Embed(
            title=f"👤 Warframe Profile: {username}",
            description="⚠️ **Note**: Warframe player profiles are not publicly accessible via API.\n\n"
            "Warframe does not provide public APIs for player statistics or profiles. "
            "This feature would require web scraping from warframe.com, which is against their Terms of Service.\n\n"
            "**Available Features:**\n"
            "• `!warframe` - Current alerts and fissures\n"
            "• `!warframemarket <item>` - Market prices and orders\n"
            "• `!warframeinvasions` - Active invasions\n"
            "• `!warframesortie` - Current sortie",
            color=discord.Color.orange(),
        )

        set_pink_footer(embed, bot=self.bot.user)
        await ctx.send(embed=embed)
        logger.info(f"Warframe profile requested for {username} by {ctx.author}")

    @commands.command(name="warframeinvasions")
    async def warframe_invasions(self, ctx: commands.Context):
        """Show active invasions"""
        await ctx.send("🔍 Fetching invasion data...")

        try:
            invasions = await self.get_invasions()
            if not invasions:
                await ctx.send("❌ No active invasions found.")
                return

            embed = discord.Embed(title="🌍 Active Invasions", color=PINK)

            for invasion in invasions[:5]:  # Max 5 invasions
                node = invasion.get("node", "Unknown")
                attacker = invasion.get("attackerReward", {}).get("item", "Unknown")
                defender = invasion.get("defenderReward", {}).get("item", "Unknown")
                completion = invasion.get("completion", 0)

                embed.add_field(
                    name=f"📍 {node}",
                    value=f"**Attacker:** {attacker}\n**Defender:** {defender}\n**Progress:** {completion}%",
                    inline=True,
                )

            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed)
            logger.info(f"Invasions displayed for {ctx.author}")

        except Exception as e:
            logger.error(f"Error in warframe_invasions: {e}")
            await ctx.send("❌ Error fetching invasion data.")

    @commands.command(name="warframesortie")
    async def warframe_sortie(self, ctx: commands.Context):
        """Show current sortie"""
        await ctx.send("🔍 Fetching sortie data...")

        try:
            sortie = await self.get_sortie()
            if not sortie:
                await ctx.send("❌ No active sortie found.")
                return

            embed = discord.Embed(title="⚔️ Current Sortie", color=PINK)

            boss = sortie.get("boss", "Unknown")
            faction = sortie.get("faction", "Unknown")
            embed.add_field(name="Boss", value=f"**{boss}** ({faction})", inline=False)

            # Variants
            variants = sortie.get("variants", [])
            for i, variant in enumerate(variants, 1):
                mission = variant.get("missionType", "Unknown")
                modifier = variant.get("modifier", "Unknown")
                node = variant.get("node", "Unknown")
                embed.add_field(name=f"Mission {i}", value=f"**{mission}**\n{modifier}\n*{node}*", inline=True)

            set_pink_footer(embed, bot=self.bot.user)
            await ctx.send(embed=embed)
            logger.info(f"Sortie displayed for {ctx.author}")

        except Exception as e:
            logger.error(f"Error in warframe_sortie: {e}")
            await ctx.send("❌ Error fetching sortie data.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Warframe(bot))
