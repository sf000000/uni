import discord
import yaml
from discord.ext import commands


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class Tags(commands.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        self.db = bot.db

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
        try:
            await self.db.tags.insert_one(
                {
                    "guild_id": ctx.guild.id,
                    "name": name,
                    "content": content,
                    "author_id": ctx.author.id,
                }
            )
            await ctx.respond(f"Tag '{name}' added successfully!", ephemeral=True)
        except discord.errors.DuplicateEntry:
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
        tag = await self.db.tags.find_one({"guild_id": ctx.guild.id, "name": name})
        if tag:
            if tag["author_id"] == ctx.author.id:
                await self.db.tags.delete_one({"guild_id": ctx.guild.id, "name": name})
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
        tag = await self.db.tags.find_one({"guild_id": ctx.guild.id, "name": name})
        if tag:
            try:
                tag_author = await self.bot.fetch_user(tag["author_id"])
            except discord.NotFound:
                await ctx.respond(
                    f"Author of tag '{name}' not found on Discord.", ephemeral=True
                )
                return

            embed = discord.Embed(
                title=f"Tag: {name}",
                description=f"Author: {tag_author.mention} ({tag['author_id']})",
                color=self.config["colors"]["default"],
            )
            embed.set_thumbnail(url=tag_author.avatar.url)

            tag_count = await self.db.tags.count_documents(
                {"guild_id": ctx.guild.id, "author_id": tag["author_id"]}
            )
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
        tag = await self.db.tags.find_one({"guild_id": ctx.guild.id, "name": name})
        if tag:
            if tag["author_id"] == ctx.author.id:
                await self.db.tags.update_one(
                    {"guild_id": ctx.guild.id, "name": name},
                    {"$set": {"name": new_name}},
                )
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
        tag = await self.db.tags.find_one({"guild_id": ctx.guild.id, "name": name})
        if tag:
            if tag["author_id"] == ctx.author.id:
                await self.db.tags.update_one(
                    {"guild_id": ctx.guild.id, "name": name},
                    {"$set": {"content": new_content}},
                )
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
        tags = await self.db.tags.find(
            {
                "guild_id": ctx.guild.id,
                "name": {"$regex": f".*{keyword}.*", "$options": "i"},
            }
        ).to_list(length=None)

        if tags:
            tag_names = [tag["name"] for tag in tags]
            tag_names_str = "\n".join(tag_names)
            embed = discord.Embed(
                title=f"Tags matching '{keyword}'",
                description=tag_names_str,
                color=self.config["colors"]["default"],
            )
            await ctx.respond(embed=embed)
        else:
            await ctx.respond(f"No tags found matching '{keyword}'.", ephemeral=True)

    @_tags.command(
        name="reset",
        description="Removes all tags for the current guild.",
    )
    async def _reset(
        self,
        ctx: discord.ApplicationContext,
    ):
        await self.db.tags.delete_many({"guild_id": ctx.guild.id})
        await ctx.respond("Tags reset successfully.", ephemeral=True)

    @_tags.command(
        name="random",
        description="Shows a random tag.",
    )
    async def _random(
        self,
        ctx: discord.ApplicationContext,
    ):
        tag = await self.db.tags.aggregate(
            [{"$match": {"guild_id": ctx.guild.id}}, {"$sample": {"size": 1}}]
        ).to_list(length=1)

        if tag:
            embed = discord.Embed(
                description=tag[0]["content"],
                color=self.config["colors"]["default"],
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
        tag = await self.db.tags.find_one({"guild_id": ctx.guild.id, "name": name})
        if tag:
            embed = discord.Embed(
                description=tag["content"],
                color=self.config["colors"]["default"],
            )
            await ctx.respond(embed=embed)
        else:
            await ctx.respond(f"Tag '{name}' not found.", ephemeral=True)


def setup(bot: discord.Bot):
    bot.add_cog(Tags(bot))
