import discord
import aiosqlite
import yaml
import datetime
import re
import aiohttp
import pytz

from discord.ext import commands
from helpers.utils import log


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class Moderation(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.db_path = "kino.db"
        self.bot.loop.create_task(self.setup_db())

    async def setup_db(self):
        self.conn = await aiosqlite.connect(self.db_path)

    async def cog_before_invoke(self, ctx: discord.ApplicationContext):
        command_name = ctx.command.name

        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM disabled_commands WHERE command = ?", (command_name,)
            )
            if await cur.fetchone():
                embed = discord.Embed(
                    title="Command Disabled",
                    description=f"The command `{command_name}` is currently disabled in this guild.",
                    color=discord.Color.red(),
                )
                embed.set_footer(text="This message will be deleted in 10 seconds.")
                embed.set_author(
                    name=self.bot.user.display_name, icon_url=self.bot.user.avatar.url
                )
                await ctx.respond(embed=embed, ephemeral=True, delete_after=10)
                raise commands.CommandInvokeError(
                    f"Command `{command_name}` is disabled."
                )

    async def member_autocomplete(self, ctx: discord.ApplicationContext, string: str):
        members = ctx.guild.members
        return [
            member
            for member in members
            if string.lower() in member.display_name.lower()
        ]

    async def role_autocomplete(self, ctx: discord.ApplicationContext, string: str):
        roles = ctx.guild.roles
        return [role for role in roles if string.lower() in role.name.lower()]

    async def channel_autocomplete(self, ctx: discord.ApplicationContext, string: str):
        channels = ctx.guild.channels
        return [
            channel for channel in channels if string.lower() in channel.name.lower()
        ]

    @discord.slash_command(name="kick", description="Kick a member from the guild")
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(
            discord.Member, "Select a member", autocomplete=member_autocomplete
        ),
        reason: discord.Option(str, "Reason for the kick", required=False),
    ):
        try:
            await ctx.guild.kick(member, reason=reason)
            embed = discord.Embed(title="Member Kicked", color=int("313338", 16))
            embed.add_field(name="Member", value=member.mention, inline=False)
            embed.add_field(
                name="Reason", value=reason or "No reason provided", inline=False
            )
            await ctx.respond(embed=embed)

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Member Kicked",
                    description=f"{member.mention} has been kicked by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to kick {member}: {e}")

    @discord.slash_command(
        name="ban",
        description="Ban a member from the guild",
    )
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def ban(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(
            discord.Member, "Select a member", autocomplete=member_autocomplete
        ),
        reason: discord.Option(str, "Reason for the ban", required=False),
    ):
        try:
            await ctx.guild.ban(member, reason=reason)
            embed = discord.Embed(title="Member Banned", color=int("313338", 16))
            embed.add_field(name="Member", value=member.mention, inline=False)
            embed.add_field(
                name="Reason", value=reason or "No reason provided", inline=False
            )

            await ctx.respond(embed=embed)
            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Member Banned",
                    description=f"{member.mention} has been banned by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to ban {member}: {e}")

    @discord.slash_command(
        name="cleanup",
        description="Cleanup bot messages in the current channel",
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def cleanup(
        self,
        ctx: discord.ApplicationContext,
        amount: discord.Option(
            int, "Number of messages to cleanup", required=False, default=10
        ),
    ):
        def is_bot(m):
            return m.author == self.bot.user

        try:
            await ctx.channel.purge(limit=amount, check=is_bot)
            await ctx.respond(f"Successfully cleaned up {amount} messages.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Messages Cleaned Up",
                    description=f"{amount} bot messages have been cleaned up by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to cleanup messages: {e}")

    _thread = discord.commands.SlashCommandGroup(
        name="thread", description="Commands to manage threads and forum posts"
    )

    @_thread.command(
        name="lock",
        description="Lock a thread or forum post",
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def lock(
        self,
        ctx: discord.ApplicationContext,
        thread: discord.Option(discord.Thread, "Select a thread"),
    ):
        try:
            await thread.edit(locked=True)
            await ctx.respond(f"\🔒 Successfully locked {thread.mention}.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Thread Locked",
                    description=f"{thread.mention} has been locked by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to lock {thread.mention}: {e}")

    @_thread.command(
        name="unlock",
        description="Unlock a thread or forum post",
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def unlock(
        self,
        ctx: discord.ApplicationContext,
        thread: discord.Option(discord.Thread, "Select a thread"),
    ):
        try:
            await thread.edit(locked=False)
            await ctx.respond(f"\🔓 Successfully unlocked {thread.mention}.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Thread Unlocked",
                    description=f"{thread.mention} has been unlocked by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )
        except Exception as e:
            await ctx.respond(f"Failed to unlock {thread.mention}: {e}")

    @discord.slash_command(
        name="lockdown",
        description="Lockdown the current channel",
    )
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def lockdown(
        self,
        ctx: discord.ApplicationContext,
        reason: discord.Option(str, "Reason for the lockdown", required=False),
    ):
        try:
            await ctx.channel.set_permissions(
                ctx.guild.default_role, send_messages=False
            )
            embed = discord.Embed(
                title="Channel Locked",
                description=f"The channel has been locked by {ctx.author.mention}.",
                color=int("313338", 16),
            )
            embed.add_field(
                name="Reason", value=reason or "No reason provided", inline=False
            )

            await ctx.respond(embed=embed)

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Channel Locked",
                    description=f"The channel has been locked by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to lockdown channel: {e}")

    @discord.slash_command(
        name="unlock",
        description="Unlock the current channel",
    )
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def unlock(self, ctx: discord.ApplicationContext):
        try:
            await ctx.channel.set_permissions(
                ctx.guild.default_role, send_messages=True
            )
            embed = discord.Embed(
                title="Channel Unlocked",
                description=f"The channel has been unlocked by {ctx.author.mention}.",
                color=int("313338", 16),
            )
            await ctx.respond(embed=embed)
        except Exception as e:
            await ctx.respond(f"Failed to unlock channel: {e}")

    @discord.slash_command(
        name="moveall",
        description="Move all members in a voice channel to another voice channel",
    )
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def moveall(
        self,
        ctx: discord.ApplicationContext,
        source: discord.Option(discord.VoiceChannel, "Select a source voice channel"),
        destination: discord.Option(
            discord.VoiceChannel, "Select a destination voice channel"
        ),
    ):
        try:
            moved_members = []
            for member in source.members:
                await member.move_to(destination)
                moved_members.append(member)
            await ctx.respond(
                f"Successfully moved {len(moved_members)} members from {source.mention} to {destination.mention}."
            )

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Members Moved",
                    description=f"{len(moved_members)} members have been moved from {source.mention} to {destination.mention} by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to move members: {e}")

    @discord.slash_command(
        name="timeout",
        description="Mutes the selected member using Discord's timeout feature",
    )
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def timeout(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(
            discord.Member, "Select a member", autocomplete=member_autocomplete
        ),
        duration: discord.Option(
            str, "Duration of the timeout in hours", required=False, default=1
        ),
        reason: discord.Option(str, "Reason for the timeout", required=False),
    ):
        try:
            duration = int(duration)
            until = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
                hours=duration
            )
            await member.timeout(until=until, reason=reason)
            embed = discord.Embed(
                title="Member Timed Out",
                description=f"{member.mention} has been timed out.",
                color=int("313338", 16),
            )
            embed.add_field(name="Moderator", value=ctx.author.mention)
            embed.add_field(
                name="Duration",
                value=f"{duration} hours",
            )
            embed.add_field(name="Reason", value=reason or "No reason provided")
            await ctx.respond(embed=embed)

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Member Timed Out",
                    description=f"{member.mention} has been timed out by {ctx.author.mention} for {duration} hours.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to timeout member: {e}")

    @discord.slash_command(
        name="untimeout",
        description="Unmutes the selected member",
    )
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def untimeout(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(
            discord.Member, "Select a member", autocomplete=member_autocomplete
        ),
    ):
        try:
            await member.timeout(until=None)
            embed = discord.Embed(
                title="Member Timeout Removed",
                description=f"{member.mention} has been untimed out by {ctx.author.mention}.",
                color=int("313338", 16),
            )
            await ctx.respond(embed=embed)

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Member Timeout Removed",
                    description=f"{member.mention} has been untimed out by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to untimeout member: {e}")

    @discord.slash_command(
        name="imute",
        description="Removes selected member's permission to attach files and use embed links",
    )
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def imute(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(
            discord.Member, "Select a member", autocomplete=member_autocomplete
        ),
        reason: discord.Option(str, "Reason for the mute", required=False),
    ):
        role_name = "📸 Media Muted"
        mute_role = discord.utils.get(ctx.guild.roles, name=role_name)

        if mute_role is None:
            try:
                mute_permissions = discord.Permissions(
                    attach_files=False, embed_links=False
                )
                mute_role = await ctx.guild.create_role(
                    name=role_name, permissions=mute_permissions
                )
            except Exception as e:
                await ctx.respond(f"Failed to create mute role: {e}")
                return

        try:
            await member.add_roles(mute_role)
            embed = discord.Embed(
                title="📸 Media Muted",
                description=f"{member.mention} has been muted from sending attachments and embed links.",
                color=int("313338", 16),
            )
            embed.add_field(name="Moderator", value=ctx.author.mention)
            embed.add_field(name="Reason", value=reason or "No reason provided")
            await ctx.respond(embed=embed)

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Member Muted",
                    description=f"{member.mention} has been muted from sending attachments and embed links by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to mute member: {e}")

    @discord.slash_command(
        name="iunmute",
        description="Restores selected member'ss permission to attach files and use embed links",
    )
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def iunmute(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(
            discord.Member, "Select a member", autocomplete=member_autocomplete
        ),
    ):
        role_name = "📸 Media Muted"
        mute_role = discord.utils.get(ctx.guild.roles, name=role_name)

        if mute_role is None:
            return await ctx.respond("No members are muted.")

        try:
            await member.remove_roles(mute_role)
            embed = discord.Embed(
                title="📸 Media Unmuted",
                description=f"{member.mention} has been unmuted from sending attachments and embed links.",
                color=int("313338", 16),
            )
            embed.add_field(name="Moderator", value=ctx.author.mention)
            await ctx.respond(embed=embed)

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Member Unmuted",
                    description=f"{member.mention} has been unmuted from sending attachments and embed links by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to unmute member: {e}")

    _notes = discord.commands.SlashCommandGroup(
        name="notes", description="Commands to manage member notes"
    )

    @_notes.command(
        name="add",
        description="Add a note to a member",
    )
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def add(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(
            discord.Member, "Select a member", autocomplete=member_autocomplete
        ),
        note: discord.Option(str, "Note to add"),
    ):
        now_timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        try:
            async with self.conn.execute(
                "CREATE TABLE IF NOT EXISTS member_notes (guild_id INTEGER, member_id INTEGER, moderator_id INTEGER, note TEXT, timestamp TEXT, note_id INTEGER PRIMARY KEY AUTOINCREMENT)"
            ):
                pass

            async with self.conn.execute(
                "INSERT INTO member_notes VALUES (?, ?, ?, ?, ?, NULL)",
                (
                    ctx.guild.id,
                    member.id,
                    ctx.author.id,
                    note,
                    now_timestamp,
                ),
            ):
                pass

            embed = discord.Embed(
                title="Note Added",
                description=f"Successfully added a note to {member.mention}.",
                color=int("313338", 16),
            )
            embed.add_field(name="Note", value=note, inline=False)
            await ctx.respond(embed=embed)

        except Exception as e:
            await ctx.respond(f"Failed to add note: {e}")

    @_notes.command(
        name="remove",
        description="Remove a note from a member",
    )
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def remove(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(
            discord.Member, "Select a member", autocomplete=member_autocomplete
        ),
        note_id: discord.Option(int, "ID of the note to remove"),
    ):
        try:
            async with self.conn.execute(
                "SELECT note_id FROM member_notes WHERE guild_id = ? AND member_id = ? AND note_id = ?",
                (ctx.guild.id, member.id, note_id),
            ) as cursor:
                if not await cursor.fetchone():
                    return await ctx.respond("No note found with that ID.")

            async with self.conn.execute(
                "DELETE FROM member_notes WHERE guild_id = ? AND member_id = ? AND note_id = ?",
                (ctx.guild.id, member.id, note_id),
            ):
                pass

            await ctx.respond(f"Successfully removed note with ID `{note_id}`.")

        except Exception as e:
            await ctx.respond(f"Failed to remove note: {e}")

    @_notes.command(
        name="list",
        description="List notes for a member",
    )
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def list(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(
            discord.Member, "Select a member", autocomplete=member_autocomplete
        ),
    ):
        try:
            async with self.conn.execute(
                "SELECT note_id, note, timestamp FROM member_notes WHERE guild_id = ? AND member_id = ?",
                (ctx.guild.id, member.id),
            ) as cursor:
                notes = await cursor.fetchall()

            if not notes:
                return await ctx.respond("No notes found for that member.")

            embed = discord.Embed(
                title="Member Notes",
                description=f"Notes for {member.mention}",
                color=int("313338", 16),
            )

            for note in notes:
                note_id, note_text, timestamp = note
                embed.add_field(
                    name=f"Note #{note_id} - <t:{timestamp}:f>",
                    value=note_text,
                    inline=False,
                )

            await ctx.respond(embed=embed)

        except Exception as e:
            await ctx.respond(f"Failed to list notes: {e}")

    @_notes.command(
        name="clear",
        description="Clear all notes for a member",
    )
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def clear(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(
            discord.Member, "Select a member", autocomplete=member_autocomplete
        ),
    ):
        try:
            async with self.conn.execute(
                "SELECT note_id FROM member_notes WHERE guild_id = ? AND member_id = ?",
                (ctx.guild.id, member.id),
            ) as cursor:
                if not await cursor.fetchone():
                    return await ctx.respond("No notes found for that member.")

            async with self.conn.execute(
                "DELETE FROM member_notes WHERE guild_id = ? AND member_id = ?",
                (ctx.guild.id, member.id),
            ):
                pass

            await ctx.respond(f"Successfully cleared notes for {member.mention}.")

        except Exception as e:
            await ctx.respond(f"Failed to clear notes: {e}")

    @discord.slash_command(
        name="clearinvites",
        description="Remove all existing invites from the guild",
    )
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def clearinvites(self, ctx: discord.ApplicationContext):
        try:
            invites = await ctx.guild.invites()
            for invite in invites:
                await invite.delete()
            await ctx.respond(f"Successfully cleared {len(invites)} invites.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Invites Cleared",
                    description=f"{len(invites)} invites have been cleared by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to clear invites: {e}")

    _role = discord.commands.SlashCommandGroup(
        name="role", description="Commands to manage roles"
    )

    @_role.command(
        name="info",
        description="Get information about a role",
    )
    @commands.guild_only()
    async def info(
        self,
        ctx: discord.ApplicationContext,
        role: discord.Option(
            discord.Role, "Select a role", autocomplete=role_autocomplete
        ),
    ):
        online_members = sum(m.status != discord.Status.offline for m in role.members)
        key_permissions = ", ".join(
            perm.replace("_", " ").title() for perm, value in role.permissions if value
        )

        embed = discord.Embed(color=role.color, description=key_permissions)
        embed.add_field(
            name="Position",
            value=f"🔢 {role.position}/{len(ctx.guild.roles)}",
        )
        embed.add_field(name="Color", value=f"\🎨 #{str(role.color)[1:]}", inline=True)
        embed.add_field(
            name="Members",
            value=f"\👥 {len(role.members)} | \💚 {online_members} Online",
        )
        embed.add_field(
            name="Created",
            value=f"\📅 <t:{int(role.created_at.timestamp())}:R>",
        )
        await ctx.respond(embed=embed)

    @_role.command(
        name="add",
        description="Add a role to a member",
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def add(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(
            discord.Member, "Select a member", autocomplete=member_autocomplete
        ),
        role: discord.Option(discord.Role, "Select a role"),
    ):
        try:
            await member.add_roles(role)
            await ctx.respond(f"Successfully added {role.mention} to {member.mention}.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Role Added",
                    description=f"{role.mention} has been added to {member.mention} by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to add role: {e}")

    @_role.command(
        name="remove",
        description="Remove a role from a member",
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def remove(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(
            discord.Member, "Select a member", autocomplete=member_autocomplete
        ),
        role: discord.Option(discord.Role, "Select a role"),
    ):
        try:
            await member.remove_roles(role)
            await ctx.respond(
                f"Successfully removed {role.mention} from {member.mention}."
            )

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Role Removed",
                    description=f"{role.mention} has been removed from {member.mention} by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to remove role: {e}")

    @_role.command(
        name="topcolor",
        description="Changes your highest role's color, HEX value must be provided",
    )
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def topcolor(
        self,
        ctx: discord.ApplicationContext,
        color: discord.Option(str, "HEX value of the color"),
    ):
        color = color.replace("#", "")
        try:
            top_role = ctx.author.top_role
            await top_role.edit(color=discord.Color(int(color, 16)))
            await ctx.respond(f"Successfully changed color of {top_role.mention}.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Role Color Changed",
                    description=f"Color for {top_role.mention} has been changed by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ).set_thumbnail(url=f"https://dummyimage.com/40/{color}/&text=%20"),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to change color: {e}")

    @_role.command(
        name="color",
        description="Changes a role's color, HEX value must be provided",
    )
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def color(
        self,
        ctx: discord.ApplicationContext,
        role: discord.Option(
            discord.Role, "Select a role", autocomplete=role_autocomplete
        ),
        color: discord.Option(str, "HEX value of the color"),
    ):
        color = color.replace("#", "")
        try:
            await role.edit(color=discord.Color(int(color, 16)))
            await ctx.respond(f"Successfully changed color of {role.mention}.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Role Color Changed",
                    description=f"Color for {role.mention} has been changed by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ).set_thumbnail(url=f"https://dummyimage.com/40/{color}/&text=%20"),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to change color: {e}")

    @_role.command(
        name="humans",
        description="Add a role to all humans in the guild",
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def humans(
        self,
        ctx: discord.ApplicationContext,
        role: discord.Option(
            discord.Role, "Select a role", autocomplete=role_autocomplete
        ),
    ):
        try:
            for member in ctx.guild.members:
                if member.bot:
                    continue
                await member.add_roles(role)
            await ctx.respond(f"Successfully added {role.mention} to all humans.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Role Added",
                    description=f"{role.mention} has been added to all humans by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to add role: {e}")

    @_role.command(
        name="humansremove",
        description="Remove a role from all humans in the guild",
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def humansremove(
        self,
        ctx: discord.ApplicationContext,
        role: discord.Option(
            discord.Role, "Select a role", autocomplete=role_autocomplete
        ),
    ):
        try:
            for member in ctx.guild.members:
                if member.bot:
                    continue
                await member.remove_roles(role)
            await ctx.respond(f"Successfully removed {role.mention} from all humans.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Role Removed",
                    description=f"{role.mention} has been removed from all humans by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )
        except Exception as e:
            await ctx.respond(f"Failed to remove role: {e}")

    @_role.command(
        name="delete",
        description="Delete a role from the guild",
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def delete(
        self,
        ctx: discord.ApplicationContext,
        role: discord.Option(
            discord.Role, "Select a role", autocomplete=role_autocomplete
        ),
    ):
        try:
            await role.delete()
            await ctx.respond(f"Successfully deleted {role.mention}.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Role Deleted",
                    description=f"{role.mention} has been deleted by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to delete role: {e}")

    @_role.command(
        name="mentionable",
        description="Toggle mentioning a role",
    )
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def mentionable(
        self,
        ctx: discord.ApplicationContext,
        role: discord.Option(
            discord.Role, "Select a role", autocomplete=role_autocomplete
        ),
    ):
        try:
            if role.mentionable:
                await role.edit(mentionable=False)
                await ctx.respond(f"Successfully disabled mentioning {role.mention}.")
            else:
                await role.edit(mentionable=True)
                await ctx.respond(f"Successfully enabled mentioning {role.mention}.")
        except Exception as e:
            await ctx.respond(f"Failed to toggle mentionable: {e}")

    @_role.command(
        name="icon",
        description="Set an icon for a role",
    )
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def icon(
        self,
        ctx: discord.ApplicationContext,
        role: discord.Option(
            discord.Role, "Select a role", autocomplete=role_autocomplete
        ),
        icon_url: discord.Option(str, "URL of the icon"),
    ):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(icon_url) as response:
                    if response.status != 200:
                        return await ctx.respond("Failed to download icon.")
                    icon_data = (
                        await response.read()
                    )  # icon_data is a bytes-like object

            await role.edit(icon=icon_data)
            await ctx.respond(f"Successfully set icon for {role.mention}.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Role Icon Changed",
                    description=f"Icon for {role.mention} has been changed by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ).set_thumbnail(url=icon_url),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to set icon: {e}")

    _purge = discord.commands.SlashCommandGroup(
        name="purge", description="Commands to purge messages"
    )

    @_purge.command(
        name="amount",
        description="Purge a specific amount of messages",
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def amount(
        self,
        ctx: discord.ApplicationContext,
        amount: discord.Option(
            int, "Number of messages to purge", required=False, default=10
        ),
    ):
        try:
            deleted = await ctx.channel.purge(limit=amount)
            await ctx.respond(f"Successfully purged {len(deleted)} messages.")
        except Exception as e:
            await ctx.respond(f"Failed to purge messages: {e}")

    @_purge.command(
        name="embeds",
        description="Purge embeds from chat",
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def embeds(
        self,
        ctx: discord.ApplicationContext,
        amount: discord.Option(
            int, "Number of messages to purge", required=False, default=10
        ),
    ):
        def is_embed(m):
            return m.embeds

        try:
            deleted = await ctx.channel.purge(limit=amount, check=is_embed)
            await ctx.respond(f"Successfully purged {len(deleted)} messages.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Messages Purged",
                    description=f"{len(deleted)} messages (embeds) have been purged by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to purge messages: {e}")

    @_purge.command(
        name="files",
        description="Purge files/attachments from chat",
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def files(
        self,
        ctx: discord.ApplicationContext,
        amount: discord.Option(
            int, "Number of messages to purge", required=False, default=10
        ),
    ):
        def is_file(m):
            return m.attachments

        try:
            deleted = await ctx.channel.purge(limit=amount, check=is_file)
            await ctx.respond(f"Successfully purged {len(deleted)} messages.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Messages Purged",
                    description=f"{len(deleted)} messages (files) have been purged by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to purge messages: {e}")

    @_purge.command(
        name="images",
        description="Purge images (including links) from chat",
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def images(
        self,
        ctx: discord.ApplicationContext,
        amount: discord.Option(
            int, "Number of messages to purge", required=False, default=10
        ),
    ):
        def is_image(msg):
            if msg.attachments and any(
                att.filename.lower().endswith(
                    (".png", ".jpg", ".jpeg", ".gif", ".webp")
                )
                for att in msg.attachments
            ):
                return True

            if msg.content:
                url_regex = r"https?://[^\s]+"
                urls = re.findall(url_regex, msg.content)
                image_domains = [
                    "media.discordapp.net",
                    "imgur.com",
                    "i.redd.it",
                ]
                image_extensions = [".png", ".jpg", ".jpeg", ".gif", ".webp"]

                for url in urls:
                    if any(domain in url for domain in image_domains) and any(
                        url.split("?")[0].lower().endswith(ext)
                        for ext in image_extensions
                    ):
                        return True

            return False

        try:
            deleted = await ctx.channel.purge(limit=amount, check=is_image)
            await ctx.respond(f"Deleted {len(deleted)} image messages.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Messages Purged",
                    description=f"{len(deleted)} messages (images) have been purged by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to purge messages: {e}")

    @_purge.command(
        name="contains",
        description="Purge messages containing a string",
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def contains(
        self,
        ctx: discord.ApplicationContext,
        string: discord.Option(str, "String to search for"),
        amount: discord.Option(
            int, "Number of messages to purge", required=False, default=10
        ),
    ):
        def contains_string(m):
            return string in m.content

        try:
            deleted = await ctx.channel.purge(limit=amount, check=contains_string)
            await ctx.respond(
                f"Successfully purged {len(deleted)} messages that contained `{string}`."
            )

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Messages Purged",
                    description=f"{len(deleted)} messages (contains) have been purged by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to purge messages: {e}")

    @_purge.command(
        name="links",
        description="Purge messages containing links",
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def links(
        self,
        ctx: discord.ApplicationContext,
        amount: discord.Option(
            int, "Number of messages to purge", required=False, default=10
        ),
    ):
        def contains_link(m):
            url_regex = r"https?://[^\s]+"
            urls = re.findall(url_regex, m.content)
            return len(urls) > 0

        try:
            deleted = await ctx.channel.purge(limit=amount, check=contains_link)
            await ctx.respond(f"Successfully purged {len(deleted)} messages.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Messages Purged",
                    description=f"{len(deleted)} messages (links) have been purged by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to purge messages: {e}")

    @_purge.command(
        name="mentions",
        description="Purge messages containing mentions",
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def mentions(
        self,
        ctx: discord.ApplicationContext,
        amount: discord.Option(
            int, "Number of messages to purge", required=False, default=10
        ),
    ):
        def contains_mention(m):
            return len(m.mentions) > 0

        try:
            deleted = await ctx.channel.purge(limit=amount, check=contains_mention)
            await ctx.respond(f"Successfully purged {len(deleted)} messages.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Messages Purged",
                    description=f"{len(deleted)} messages (mentions) have been purged by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to purge messages: {e}")

    @discord.slash_command(
        name="nuke",
        description="Nuke (Clone) the current channel",
    )
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def nuke(self, ctx: discord.ApplicationContext):
        try:
            channel = await ctx.channel.clone()
            await ctx.channel.delete()
            await channel.send(
                "https://media1.tenor.com/m/2L8cGGO6_MIAAAAd/operation-teapot-nuke.gif"
            )

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Channel Nuked",
                    description=f"{ctx.channel.mention} has been nuked by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to nuke channel: {e}")

    @discord.slash_command(
        name="newusers",
        description="View a list of new users in the guild",
    )
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def newusers(self, ctx: discord.ApplicationContext):
        try:
            embed = discord.Embed(
                title="New Users",
                description="New users in the past 24 hours",
                color=int("313338", 16),
            )
            utc = pytz.utc
            now = datetime.now(utc)
            one_day_ago = now - datetime.timedelta(days=1)
            new_users = [
                member
                for member in ctx.guild.members
                if member.joined_at and member.joined_at > one_day_ago
            ]
            if not new_users:
                return await ctx.respond("No new users found.")
            for member in new_users:
                embed.add_field(name=member.display_name, value=member.mention)
            await ctx.respond(embed=embed)
        except Exception as e:
            await ctx.respond(f"Failed to get new users: {e}")

    @discord.slash_command(
        name="slowmode",
        description="Set the slowmode for the current channel",
    )
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def slowmode(
        self,
        ctx: discord.ApplicationContext,
        seconds: discord.Option(
            int,
            "Number of seconds to set the slowmode to. (0 to disable)",
            required=True,
        ),
    ):
        try:
            await ctx.channel.edit(slowmode_delay=seconds)
            await ctx.respond(f"Successfully set slowmode to {seconds} seconds.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Slowmode Changed",
                    description=f"Slowmode for {ctx.channel.mention} has been changed by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ).add_field(name="Slowmode", value=f"{seconds} seconds"),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to set slowmode: {e}")

    @discord.slash_command(
        name="rename",
        description="Assigns the selected user a new nickname in the guild",
    )
    @commands.has_permissions(manage_nicknames=True)
    @commands.guild_only()
    async def rename(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(
            discord.Member, "Select a member", autocomplete=member_autocomplete
        ),
        nickname: discord.Option(str, "New nickname for the member"),
    ):
        try:
            await member.edit(nick=nickname)
            await ctx.respond(f"Successfully renamed {member.mention}.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Member Renamed",
                    description=f"{member.mention} has been renamed by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ).add_field(name="Nickname", value=nickname),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to rename member: {e}")

    @discord.slash_command(
        name="topic",
        description="Sets the topic for the current channel",
    )
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def topic(
        self,
        ctx: discord.ApplicationContext,
        topic: discord.Option(str, "New topic for the channel"),
    ):
        try:
            await ctx.channel.edit(topic=topic)
            await ctx.respond(f"Successfully set topic to `{topic}`.")

            await log(
                guild=ctx.guild,
                embed=discord.Embed(
                    title="Channel Topic Changed",
                    description=f"Topic for {ctx.channel.mention} has been changed by {ctx.author.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                ).add_field(name="Topic", value=topic),
                conn=self.conn,
            )

        except Exception as e:
            await ctx.respond(f"Failed to set topic: {e}")

    _logging = discord.commands.SlashCommandGroup(
        name="logging", description="Commands to manage logging"
    )

    @_logging.command(
        name="enable",
        description="Enable logging in the guild",
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def enable(
        self,
        ctx: discord.ApplicationContext,
        channel: discord.Option(
            discord.TextChannel, "Select a channel", autocomplete=channel_autocomplete
        ),
    ):
        try:
            async with self.conn.execute(
                "CREATE TABLE IF NOT EXISTS logging (guild_id INTEGER, channel_id INTEGER, PRIMARY KEY(guild_id))"
            ):
                pass

            async with self.conn.execute(
                "INSERT INTO logging VALUES (?, ?)",
                (ctx.guild.id, channel.id),
            ):
                pass

            await ctx.respond(f"Successfully enabled logging in {channel.mention}.")

        except Exception as e:
            await ctx.respond(f"Failed to enable logging: {e}")

    @_logging.command(
        name="disable",
        description="Disable logging in the guild",
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def disable(self, ctx: discord.ApplicationContext):
        try:
            async with self.conn.execute(
                "DELETE FROM logging WHERE guild_id = ?",
                (ctx.guild.id,),
            ):
                pass

            await ctx.respond("Successfully disabled logging.")

        except Exception as e:
            await ctx.respond(f"Failed to disable logging: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        if message.author.guild_permissions.kick_members:
            return

        if message.guild.id != config["HOME_GUILD"]:
            return

        discord_invite_pattern = re.compile(
            r"discord\.gg\/[a-zA-Z0-9]+|discordapp\.com\/invite\/[a-zA-Z0-9]+"
        )
        if discord_invite_pattern.search(message.content):
            try:
                await message.delete()
                await message.author.timeout(
                    until=datetime.datetime.now(datetime.timezone.utc)
                    + datetime.timedelta(days=1),
                    reason="Posted a Discord invite link",
                )
                embed = discord.Embed(
                    title="Invite Link Posted",
                    description=f"{message.author.mention} posted a Discord invite link in {message.channel.mention}.",
                    color=config["COLORS"]["INVISIBLE"],
                )
                embed.add_field(name="Message", value=message.content)
                embed.add_field(name="Action", value="Message deleted, user timed out")

                await log(
                    guild=message.guild,
                    embed=embed,
                    conn=self.conn,
                )

            except Exception as e:
                print(f"An error occurred: {e}")


def setup(bot_: discord.Bot):
    bot_.add_cog(Moderation(bot_))
