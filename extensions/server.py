from datetime import datetime, timedelta

import discord
import pytz
from discord.ext import commands

from helpers.embeds import Embeds


class Server(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.db = bot.db
        self.log = bot.log
        self.config = bot.config
        self.embed = Embeds()

    _welcome = discord.commands.SlashCommandGroup(
        name="welcome", description="Welcome messages"
    )

    @_welcome.command(name="enable", description="Enable welcome messages")
    @commands.has_permissions(manage_guild=True)
    async def _welcome_enable(self, ctx: discord.ApplicationContext):
        await self.db.guilds.update_one(
            {"guild_id": ctx.guild.id}, {"$set": {"welcome_enabled": 1}}
        )
        await ctx.respond(
            embed=self.embed.success("Welcome messages enabled."), ephemeral=True
        )

    @_welcome.command(name="disable", description="Disable welcome messages")
    @commands.has_permissions(manage_guild=True)
    async def _welcome_disable(self, ctx: discord.ApplicationContext):
        await self.db.guilds.update_one(
            {"guild_id": ctx.guild.id}, {"$set": {"welcome_enabled": 0}}
        )
        await ctx.respond(
            embed=self.embed.success("Welcome messages disabled."), ephemeral=True
        )

    @_welcome.command(name="channel", description="Set the welcome channel")
    @commands.has_permissions(manage_guild=True)
    async def _welcome_channel(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.Option(discord.TextChannel, "Select a channel"),
    ):
        await self.db.guilds.update_one(
            {"guild_id": ctx.guild.id}, {"$set": {"welcome_channel": channel.id}}
        )
        await ctx.respond(
            embed=self.embed.success(f"Welcome channel set to {channel.mention}."),
            ephemeral=True,
        )

    _leave = discord.commands.SlashCommandGroup(
        name="leave", description="Leave messages"
    )

    @_leave.command(name="enable", description="Enable leave messages")
    @commands.has_permissions(manage_guild=True)
    async def _leave_enable(self, ctx: discord.ApplicationContext):
        await self.db.guilds.update_one(
            {"guild_id": ctx.guild.id}, {"$set": {"leave_enabled": 1}}
        )
        await ctx.respond(
            embed=self.embed.success("Leave messages enabled."), ephemeral=True
        )

    @_leave.command(name="disable", description="Disable leave messages")
    @commands.has_permissions(manage_guild=True)
    async def _leave_disable(self, ctx: discord.ApplicationContext):
        await self.db.guilds.update_one(
            {"guild_id": ctx.guild.id}, {"$set": {"leave_enabled": 0}}
        )
        await ctx.respond(
            embed=self.embed.success("Leave messages disabled."), ephemeral=True
        )

    @_leave.command(name="channel", description="Set the leave channel")
    @commands.has_permissions(manage_guild=True)
    async def _leave_channel(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.Option(discord.TextChannel, "Select a channel"),
    ):
        await self.db.guilds.update_one(
            {"guild_id": ctx.guild.id}, {"$set": {"leave_channel": channel.id}}
        )
        await ctx.respond(
            embed=self.embed.success(f"Leave channel set to {channel.mention}."),
            ephemeral=True,
        )

    @discord.slash_command(name="seticon", description="Set a new guild icon")
    @commands.has_permissions(manage_guild=True)
    async def _set_icon(
        self,
        ctx: discord.ApplicationContext,
        icon: discord.Option(discord.Attachment, description="The icon to set"),
    ):
        try:
            await ctx.guild.edit(icon=await icon.read())
            await ctx.respond(
                embed=self.embed.success("Guild icon updated."), ephemeral=True
            )

        except Exception:
            await ctx.respond(
                embed=self.embed.error("Failed to update the guild icon. {e}"),
                ephemeral=True,
            )

    @discord.slash_command(
        name="setsplash", description="Set a new guild splash background"
    )
    @commands.has_permissions(manage_guild=True)
    async def _set_splash(
        self,
        ctx: discord.ApplicationContext,
        splash: discord.Option(discord.Attachment, description="The splash to set"),
    ):
        try:
            await ctx.guild.edit(splash=await splash.read())
            await ctx.respond(
                embed=self.embed.success("Guild splash background updated."),
                ephemeral=True,
            )
        except Exception:
            await ctx.respond(
                embed=self.embed.error("Failed to update the guild splash background."),
                ephemeral=True,
            )

    @discord.slash_command(name="setbanner", description="Set a new guild banner")
    @commands.has_permissions(manage_guild=True)
    async def _set_banner(
        self,
        ctx: discord.ApplicationContext,
        banner: discord.Option(discord.Attachment, description="The banner to set"),
    ):
        try:
            await ctx.guild.edit(banner=await banner.read())
            await ctx.respond(
                embed=self.embed.success("Guild banner background updated."),
                ephemeral=True,
            )
        except Exception:
            await ctx.respond(
                embed=self.embed.error("Failed to update the guild banner background."),
                ephemeral=True,
            )

    @discord.slash_command(
        name="pin", description="Pin the most recent message in the channel"
    )
    @commands.has_permissions(manage_messages=True)
    async def _pin(self, ctx: discord.ApplicationContext):
        async for message in ctx.channel.history(limit=1):
            await message.pin()

    @discord.slash_command(
        name="server",
        description="Get some information about the server",
    )
    async def _server(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        total_members = len(ctx.guild.members)
        botcount = sum(member.bot for member in ctx.guild.members)
        online_count = sum(
            member.status != discord.Status.offline for member in ctx.guild.members
        )

        created = f"<t:{int(ctx.guild.created_at.timestamp())}:R>"
        security = f"Verification Level: {ctx.guild.verification_level}\nExplicit Content Filter: {ctx.guild.explicit_content_filter}"

        text_channels = len(ctx.guild.text_channels)
        voice_channels = len(ctx.guild.voice_channels)
        roles = len(ctx.guild.roles)
        emojis = len(ctx.guild.emojis)

        embed = discord.Embed(
            title=ctx.guild.name, color=self.config["colors"]["default"]
        )
        embed.description = (
            f"👥 {total_members} members (🤖 {botcount} bots) | 🟢 {online_count} online\n\n"
            f"**Owner:** {ctx.guild.owner}\n**Created:** {created}\n**Security:** {security}\n\n"
            f"💬 {text_channels} channels | 🔈 {voice_channels} voice channels | "
            f"👤 {roles} roles | 🐸 {emojis} emotes"
        )

        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="whois",
        description="Get information about a user.",
    )
    async def user_info(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(
            discord.Member, "The user to get information about", required=False
        ),
    ):
        await ctx.defer()

        user = member or ctx.author

        status = str(user.status).title()
        if status == "Dnd":
            status = "🔴 DND"
        if status == "Idle":
            status = "🌙 Idle"
        if status == "Offline":
            status = "⚫ Offline"
        if status == "Online":
            status = "🟢 Online"

        created = f"<t:{int(user.created_at.timestamp())}:R>"
        joined = f"<t:{int(user.joined_at.timestamp())}:R>"

        roles = ", ".join(
            [role.mention for role in user.roles if role != ctx.guild.default_role]
        )

        fetched_user = await self.bot.fetch_user(user.id)

        activity_phrase = (
            self.format_activity(user.activities[0]) if user.activities else "None"
        )

        embed = discord.Embed(color=self.config["colors"]["default"])
        embed.description = f"{status} {activity_phrase}\n\n"
        embed.add_field(name="Created", value=created, inline=True)
        embed.add_field(name="Joined", value=joined, inline=True)
        embed.add_field(name="Roles", value=roles, inline=False)

        if fetched_user.banner:
            embed.description += f"\n**Banner:** [Link]({fetched_user.banner.url})"
            embed.set_image(url=fetched_user.banner.url)

        embed.set_thumbnail(url=user.display_avatar.url)
        await ctx.respond(embed=embed)

    @discord.slash_command(
        name="statistics", description="Get simple statistics about the server."
    )
    async def _statistics(self, ctx: discord.ApplicationContext):
        await ctx.defer()

        members = ctx.guild.members
        bots = [member for member in members if member.bot]
        online = [
            member for member in members if member.status != discord.Status.offline
        ]

        now = datetime.now(pytz.UTC)
        day_ago = now - timedelta(days=1)
        day_joined = [
            member
            for member in members
            if member.joined_at and member.joined_at.replace(tzinfo=pytz.UTC) > day_ago
        ]

        week_ago = now - timedelta(days=7)
        week_joined = [
            member
            for member in members
            if member.joined_at and member.joined_at.replace(tzinfo=pytz.UTC) > week_ago
        ]

        bans_count = 0
        async for ban in ctx.guild.bans(limit=None):
            bans_count += 1

        embed = discord.Embed(
            description=f"👥 **{len(members)}** Members | 💚 **{len(online)}** Online | 🤖 **{len(bots)}** Bots",
            color=self.config["colors"]["default"],
        )
        embed.add_field(
            name="New Members",
            value=f"👥 Today: **{len(day_joined)}**\n👥 This Week: **{len(week_joined)}**",
            inline=False,
        )
        embed.add_field(
            name="Bans and Boosts",
            value=f"🔨 Bans: **{bans_count}**\n🚀 Boosts: **{ctx.guild.premium_subscription_count}**",
            inline=False,
        )
        if ctx.guild.splash:
            embed.set_image(url=ctx.guild.splash.url)
        embed.set_thumbnail(url=ctx.guild.icon.url)

        await ctx.respond(embed=embed)


def setup(bot: discord.Bot):
    bot.add_cog(Server(bot))
