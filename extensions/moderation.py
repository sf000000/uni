import datetime
import re

import discord
from discord.ext import commands

from helpers.embeds import Embeds


class Moderation(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.config = bot.config
        self.log = bot.log
        self.embed = Embeds()

    @discord.slash_command(
        name="invites",
        description="View all active invites in the server",
    )
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def _invites(self, ctx: discord.ApplicationContext):
        invites = await ctx.guild.invites()
        embed = discord.Embed(
            title=f"Active Invites ({len(invites)})",
            color=self.config["colors"]["info"],
        )
        for invite in invites:
            embed.add_field(
                name=invite.code,
                value=f"**Creator**: {invite.inviter.mention}\n**Uses**: {invite.uses}\n**Channel**: {invite.channel.mention}",
            )
        await ctx.respond(embed=embed)

    @discord.slash_command(name="kick", description="Kick a member from the guild")
    @commands.has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(discord.Member, "Select a member"),
        reason: discord.Option(str, "Reason for the kick", required=False),
    ):
        try:
            await ctx.guild.kick(member, reason=reason)
            embed = discord.Embed(
                title="Member Kicked", color=self.config["colors"]["success"]
            )
            embed.add_field(name="Member", value=member.mention, inline=False)
            embed.add_field(
                name="Reason", value=reason or "No reason provided", inline=False
            )
            await ctx.respond(embed=embed)

        except Exception as e:
            await ctx.respond(
                self.embed.error(f"Failed to kick {member}: {e}", ephemeral=True)
            )

    @discord.slash_command(
        name="ban",
        description="Ban a member from the guild",
    )
    @commands.has_permissions(ban_members=True)
    @commands.guild_only()
    async def ban(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(discord.Member, "Select a member"),
        reason: discord.Option(str, "Reason for the ban", required=False),
    ):
        try:
            await ctx.guild.ban(member, reason=reason)
            embed = discord.Embed(
                title="Member Banned", color=self.config["colors"]["success"]
            )
            embed.add_field(name="Member", value=member.mention, inline=False)
            embed.add_field(
                name="Reason", value=reason or "No reason provided", inline=False
            )

            await ctx.respond(embed=embed)
        except Exception as e:
            await ctx.respond(
                self.embed.error(f"Failed to ban {member}: {e}", ephemeral=True)
            )

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
                color=self.config["colors"]["success"],
            )
            embed.add_field(
                name="Reason", value=reason or "No reason provided", inline=False
            )

            await ctx.respond(embed=embed)
        except Exception as e:
            await ctx.respond(self.embed.error(f"Failed to lockdown channel: {e}"))

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
                color=self.config["colors"]["success"],
            )
            await ctx.respond(embed=embed)
        except Exception as e:
            await ctx.respond(self.embed.error(f"Failed to unlock channel: {e}"))

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
                embed=self.embed.success(
                    f"Successfully moved {len(moved_members)} members from {source.mention} to {destination.mention}."
                )
            )
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to move members: {e}"), ephemeral=True
            )

    @discord.slash_command(
        name="timeout",
        description="Mutes the selected member using Discord's timeout feature",
    )
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def timeout(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(discord.Member, "Select a member"),
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
                color=self.config["colors"]["success"],
            )
            embed.add_field(name="Moderator", value=ctx.author.mention)
            embed.add_field(
                name="Duration",
                value=f"{duration} hours",
            )
            embed.add_field(name="Reason", value=reason or "No reason provided")
            await ctx.respond(embed=embed)
        except Exception as e:
            await ctx.respond(
                self.embed.error(f"Failed to timeout member: {e}"), ephemeral=True
            )

    @discord.slash_command(
        name="untimeout",
        description="Unmutes the selected member",
    )
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def untimeout(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(discord.Member, "Select a member"),
    ):
        try:
            await member.timeout(until=None)
            embed = discord.Embed(
                title="Member Timeout Removed",
                description=f"{member.mention} has been untimed out by {ctx.author.mention}.",
                color=self.config["colors"]["success"],
            )
            await ctx.respond(embed=embed)
        except Exception as e:
            await ctx.respond(
                self.embed.error(f"Failed to untimeout member: {e}"), ephemeral=True
            )

    @discord.slash_command(
        name="imute",
        description="Removes selected member's permission to attach files and use embed links",
    )
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def imute(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(discord.Member, "Select a member"),
        reason: discord.Option(str, "Reason for the mute", required=False),
    ):
        role_name = self.config["roles"]["media_muted"]
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
                return await ctx.respond(
                    embed=self.embed.error(f"Failed to create mute role: {e}"),
                    ephemeral=True,
                )

        try:
            await member.add_roles(mute_role)
            embed = discord.Embed(
                title="Media Muted",
                description=f"{member.mention} has been muted from sending attachments and embed links.",
                color=self.config["colors"]["success"],
            )
            embed.add_field(name="Moderator", value=ctx.author.mention)
            embed.add_field(name="Reason", value=reason or "No reason provided")
            await ctx.respond(embed=embed)
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to mute member: {e}"), ephemeral=True
            )

    @discord.slash_command(
        name="iunmute",
        description="Restores selected member'ss permission to attach files and use embed links",
    )
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def iunmute(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(discord.Member, "Select a member"),
    ):
        role_name = self.config["roles"]["media_muted"]
        mute_role = discord.utils.get(ctx.guild.roles, name=role_name)

        if mute_role is None:
            return await ctx.respond(
                embed=self.embed.error("Mute role not found."), ephemeral=True
            )

        try:
            await member.remove_roles(mute_role)
            await ctx.respond(
                embed=self.embed.success(
                    f"{member.mention} has been unmuted from sending attachments and embed links."
                )
            )
        except Exception as e:
            await ctx.respond(self.embed.error(f"Failed to unmute member: {e}"))

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
            await ctx.respond(
                embed=self.embed.success(
                    f"Successfully cleared {len(invites)} invites."
                )
            )
        except Exception as e:
            await ctx.respond(self.embed.error(f"Failed to clear invites: {e}"))

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
        role: discord.Option(discord.Role, "Select a role"),
    ):
        # TODO: Implement role info command
        pass

    @_role.command(
        name="add",
        description="Add a role to a member",
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def add(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(discord.Member, "Select a member"),
        role: discord.Option(discord.Role, "Select a role"),
    ):
        try:
            await member.add_roles(role)
            await ctx.respond(
                embed=self.embed.error(
                    f"Successfully added {role.mention} to {member.mention}."
                )
            )
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to add role: {e}"), ephemeral=True
            )

    @_role.command(
        name="remove",
        description="Remove a role from a member",
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def remove(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(discord.Member, "Select a member"),
        role: discord.Option(discord.Role, "Select a role"),
    ):
        try:
            await member.remove_roles(role)
            await ctx.respond(
                embed=self.embed.success(
                    f"Successfully removed {role.mention} from {member.mention}."
                )
            )
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to remove role: {e}"), ephemeral=True
            )

    @_role.command(
        name="color",
        description="Changes a role's color, HEX value must be provided",
    )
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def color(
        self,
        ctx: discord.ApplicationContext,
        role: discord.Option(discord.Role, "Select a role"),
        color: discord.Option(str, "HEX value of the color"),
    ):
        color = color.replace("#", "")
        try:
            await role.edit(color=discord.Color(int(color, 16)))
            await ctx.respond(
                embed=self.embed.success(
                    f"Successfully changed color of {role.mention}."
                )
            )
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to change color: {e}"), ephemeral=True
            )

    @_role.command(
        name="humans",
        description="Add a role to all humans in the guild",
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def humans(
        self,
        ctx: discord.ApplicationContext,
        role: discord.Option(discord.Role, "Select a role"),
    ):
        try:
            for member in ctx.guild.members:
                if member.bot:
                    continue
                await member.add_roles(role)
            await ctx.respond(
                embed=self.embed.success(
                    f"Successfully added {role.mention} to all humans."
                ),
                ephemeral=True,
            )
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to add role: {e}"), ephemeral=True
            )

    @_role.command(
        name="humansremove",
        description="Remove a role from all humans in the guild",
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def humansremove(
        self,
        ctx: discord.ApplicationContext,
        role: discord.Option(discord.Role, "Select a role"),
    ):
        try:
            for member in ctx.guild.members:
                if member.bot:
                    continue
                await member.remove_roles(role)
            await ctx.respond(
                embed=self.embed.success(
                    f"Successfully removed {role.mention} from all humans."
                ),
                ephemeral=True,
            )
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to remove role: {e}"), ephemeral=True
            )

    @_role.command(
        name="delete",
        description="Delete a role from the guild",
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def delete(
        self,
        ctx: discord.ApplicationContext,
        role: discord.Option(discord.Role, "Select a role"),
    ):
        try:
            await role.delete()
            await ctx.respond(
                embed=self.embed.success(f"Successfully deleted {role.mention}.")
            )

        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to delete role: {e}"), ephemeral=True
            )

    @_role.command(
        name="mentionable",
        description="Toggle mentioning a role",
    )
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def mentionable(
        self,
        ctx: discord.ApplicationContext,
        role: discord.Option(discord.Role, "Select a role"),
    ):
        try:
            if role.mentionable:
                await role.edit(mentionable=False)
                await ctx.respond(
                    embed=self.embed.success(
                        f"Successfully disabled mentioning {role.mention}."
                    )
                )
            else:
                await role.edit(mentionable=True)
                await ctx.respond(
                    embed=self.embed.success(
                        f"Successfully enabled mentioning {role.mention}."
                    )
                )
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
        role: discord.Option(discord.Role, "Select a role"),
        icon: discord.Option(discord.Attachment, "Attachment of the icon"),
    ):
        try:
            await role.edit(icon=await icon.read())
            await ctx.respond(
                embed=self.embed.success(f"Successfully set icon for {role.mention}.")
            )
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to set icon: {e}"), ephemeral=True
            )

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
            await ctx.respond(
                f"Successfully purged {len(deleted)} messages from the channel."
            )
        except Exception as e:
            await ctx.respond(
                f"Failed to purge messages: {e}",
                ephemeral=True,
            )

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
            await ctx.respond(
                f"Successfully purged {len(deleted)} messages with embeds."
            )
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to purge messages: {e}"),
                ephemeral=True,
            )

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
            await ctx.respond(
                embed=self.embed.success(
                    f"Successfully purged {len(deleted)} messages with files."
                )
            )
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to purge messages: {e}"),
                ephemeral=True,
            )

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
                image_extensions = [".png", ".jpg", ".jpeg", ".gif", ".webp"]

                for url in urls:
                    if url.lower().endswith(tuple(image_extensions)):
                        return True

            return False

        try:
            deleted = await ctx.channel.purge(limit=amount, check=is_image)
            await ctx.respond(
                embed=self.embed.success(
                    f"Successfully purged {len(deleted)} messages with images."
                )
            )
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to purge messages: {e}"),
                ephemeral=True,
            )

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
                embed=self.embed.success(
                    f"Successfully purged {len(deleted)} messages that contained `{string}`."
                )
            )
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to purge messages: {e}"), ephemeral=True
            )

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
            await ctx.respond(
                embed=self.embed.success(
                    f"Successfully purged {len(deleted)} messages containing links."
                )
            )
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to purge messages: {e}"), ephemeral=True
            )

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
            await ctx.respond(
                embed=self.embed.success(
                    f"Successfully purged {len(deleted)} messages containing mentions."
                )
            )
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to purge messages: {e}"), ephemeral=True
            )

    @discord.slash_command(
        name="nuke",
        description="Nuke (clone) the current channel",
    )
    @commands.has_permissions(manage_channels=True)
    @commands.guild_only()
    async def nuke(self, ctx: discord.ApplicationContext):
        try:
            channel = await ctx.channel.clone()
            await ctx.channel.delete()
            await channel.send(self.config["nuke_image"])
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to nuke channel: {e}"), ephemeral=True
            )

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
            await ctx.respond(
                embed=self.embed.success(
                    f"Successfully set slowmode to {seconds} seconds."
                )
            )
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to set slowmode: {e}"), ephemeral=True
            )

    @discord.slash_command(
        name="rename",
        description="Assigns the selected user a new nickname in the guild",
    )
    @commands.has_permissions(manage_nicknames=True)
    @commands.guild_only()
    async def rename(
        self,
        ctx: discord.ApplicationContext,
        member: discord.Option(discord.Member, "Select a member"),
        nickname: discord.Option(str, "New nickname for the member"),
    ):
        try:
            await member.edit(nick=nickname)
            await ctx.respond(
                embed=self.embed.success(f"Successfully renamed {member.mention}.")
            )
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to rename member: {e}"), ephemeral=True
            )

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
            await ctx.respond(
                embed=self.embed.success(f"Successfully set topic to `{topic}`.")
            )
        except Exception as e:
            await ctx.respond(
                embed=self.embed.error(f"Failed to set topic: {e}"), ephemeral=True
            )


def setup(config: discord.Bot):
    config.add_cog(Moderation(config))
