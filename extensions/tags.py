import discord
import aiosqlite
import yaml

from discord.ext import commands


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class Tags(commands.Cog):
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

    _tags = discord.commands.SlashCommandGroup(
        name="tags",
        description="Commands for managing tags.",
    )

    @_tags.command(
        name="add",
        description="Adds a tag.",
    )
    async def _add(
        self,
        ctx: discord.ApplicationContext,
        name: discord.Option(str, description="The name of the tag.", required=True),
        content: discord.Option(
            str, description="The content of the tag.", required=True
        ),
    ):
        async with self.conn.cursor() as cur:
            try:
                await cur.execute(
                    "INSERT INTO tags (guild_id, name, content, author_id) VALUES (?, ?, ?, ?)",
                    (ctx.guild.id, name, content, ctx.author.id),
                )
                await self.conn.commit()
                await ctx.respond(f"Tag '{name}' added successfully!", ephemeral=True)
            except aiosqlite.IntegrityError:
                await ctx.respond(f"Tag '{name}' already exists.", ephemeral=True)

    @_tags.command(
        name="delete",
        description="Deletes a tag.",
    )
    async def _delete(
        self,
        ctx: discord.ApplicationContext,
        name: discord.Option(str, description="The name of the tag.", required=True),
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT author_id FROM tags WHERE guild_id = ? AND name = ?",
                (ctx.guild.id, name),
            )
            row = await cur.fetchone()

            if row:
                tag_author_id = row[0]
                if int(tag_author_id) == ctx.author.id:
                    await cur.execute(
                        "DELETE FROM tags WHERE guild_id = ? AND name = ?",
                        (ctx.guild.id, name),
                    )
                    await self.conn.commit()
                    await ctx.respond(f"Tag '{name}' deleted successfully.")
                else:
                    await ctx.respond(
                        "You do not have permission to delete this tag.", ephemeral=True
                    )
            else:
                await ctx.respond(f"Tag '{name}' not found.", ephemeral=True)

    @_tags.command(
        name="author",
        description="Shows the author of a tag.",
    )
    async def _author(
        self,
        ctx: discord.ApplicationContext,
        name: discord.Option(str, description="The name of the tag.", required=True),
    ):
        guild_id = str(ctx.guild.id)

        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT author_id FROM tags WHERE guild_id = ? AND name = ?",
                (guild_id, name),
            )
            row = await cur.fetchone()

            if row:
                tag_author_id = row[0]
                try:
                    tag_author = await self.bot.fetch_user(tag_author_id)
                except discord.NotFound:
                    await ctx.respond(
                        f"Author of tag '{name}' not found on Discord.", ephemeral=True
                    )
                    return

                embed = discord.Embed(
                    title=f"Tag: {name}",
                    description=f"Author: {tag_author.mention} ({tag_author_id})",
                    color=config["COLORS"]["DEFAULT"],
                )
                embed.set_thumbnail(url=tag_author.avatar.url)

                await cur.execute(
                    "SELECT COUNT(*) FROM tags WHERE guild_id = ? AND author_id = ?",
                    (guild_id, tag_author_id),
                )
                tag_count_row = await cur.fetchone()
                tag_count = tag_count_row[0] if tag_count_row else 0

                embed.add_field(name="Total Tags", value=str(tag_count), inline=False)
                await ctx.respond(embed=embed)
            else:
                await ctx.respond(f"Tag '{name}' not found.", ephemeral=True)

    @_tags.command(
        name="rename",
        description="Renames a tag.",
    )
    async def _rename(
        self,
        ctx: discord.ApplicationContext,
        name: discord.Option(str, description="The name of the tag.", required=True),
        new_name: discord.Option(
            str, description="The new name of the tag.", required=True
        ),
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT author_id FROM tags WHERE guild_id = ? AND name = ?",
                (ctx.guild.id, name),
            )
            row = await cur.fetchone()

            if row:
                tag_author_id = row[0]
                print(type(tag_author_id), type(ctx.author.id))
                if int(tag_author_id) == ctx.author.id:
                    await cur.execute(
                        "UPDATE tags SET name = ? WHERE guild_id = ? AND name = ?",
                        (new_name, ctx.guild.id, name),
                    )
                    await self.conn.commit()
                    await ctx.respond(f"Tag '{name}' renamed to '{new_name}'.")
                else:
                    await ctx.respond(
                        "You do not have permission to rename this tag.", ephemeral=True
                    )
            else:
                await ctx.respond(f"Tag '{name}' not found.", ephemeral=True)

    @_tags.command(
        name="edit",
        description="Edits the content of a tag.",
    )
    async def _edit(
        self,
        ctx: discord.ApplicationContext,
        name: discord.Option(str, description="The name of the tag.", required=True),
        new_content: discord.Option(
            str, description="The new content of the tag.", required=True
        ),
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT author_id FROM tags WHERE guild_id = ? AND name = ?",
                (ctx.guild.id, name),
            )
            row = await cur.fetchone()

            if row:
                tag_author_id = row[0]
                if int(tag_author_id) == ctx.author.id:
                    await cur.execute(
                        "UPDATE tags SET content = ? WHERE guild_id = ? AND name = ?",
                        (new_content, ctx.guild.id, name),
                    )
                    await self.conn.commit()
                    await ctx.respond(f"Tag '{name}' edited successfully.")
                else:
                    await ctx.respond(
                        "You do not have permission to edit this tag.", ephemeral=True
                    )
            else:
                await ctx.respond(f"Tag '{name}' not found.", ephemeral=True)

    @_tags.command(
        name="search",
        description="Searches for tags based on a keyword.",
    )
    async def _search(
        self,
        ctx: discord.ApplicationContext,
        keyword: discord.Option(
            str, description="The keyword to search for.", required=True
        ),
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT name FROM tags WHERE guild_id = ? AND name LIKE ?",
                (ctx.guild.id, f"%{keyword}%"),
            )
            rows = await cur.fetchall()

            if rows:
                tag_names = [row[0] for row in rows]
                tag_names_str = "\n".join(tag_names)
                embed = discord.Embed(
                    title=f"Tags matching '{keyword}'",
                    description=tag_names_str,
                    color=config["COLORS"]["DEFAULT"],
                )
                await ctx.respond(embed=embed)
            else:
                await ctx.respond(
                    f"No tags found matching '{keyword}'.", ephemeral=True
                )

    @_tags.command(
        name="reset",
        description="Removes all tags for the current guild.",
    )
    async def _reset(
        self,
        ctx: discord.ApplicationContext,
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM tags WHERE guild_id = ?",
                (ctx.guild.id,),
            )
            await self.conn.commit()
            await ctx.respond("Tags reset successfully.", ephemeral=True)

    @_tags.command(
        name="random",
        description="Shows a random tag.",
    )
    async def _random(
        self,
        ctx: discord.ApplicationContext,
    ):
        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT name, content FROM tags WHERE guild_id = ? ORDER BY RANDOM() LIMIT 1",
                (ctx.guild.id,),
            )
            row = await cur.fetchone()

            if row:
                tag_content = row[1]
                embed = discord.Embed(
                    description=tag_content,
                    color=config["COLORS"]["DEFAULT"],
                )
                await ctx.respond(embed=embed)
            else:
                await ctx.respond("No tags found.", ephemeral=True)

    @_tags.command(
        name="get",
        description="Retrieves and displays a tag.",
    )
    async def _get(
        self,
        ctx: discord.ApplicationContext,
        name: discord.Option(
            str, description="The name of the tag to retrieve.", required=True
        ),
    ):
        guild_id = str(ctx.guild.id)

        async with self.conn.cursor() as cur:
            await cur.execute(
                "SELECT content FROM tags WHERE guild_id = ? AND name = ?",
                (guild_id, name),
            )
            row = await cur.fetchone()

            if row:
                tag_content = row[0]
                embed = discord.Embed(
                    description=tag_content,
                    color=config["COLORS"]["DEFAULT"],
                )
                await ctx.respond(embed=embed)
            else:
                await ctx.respond(f"Tag '{name}' not found.", ephemeral=True)


def setup(bot_: discord.Bot):
    bot_.add_cog(Tags(bot_))
