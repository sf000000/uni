import discord
import aiosqlite
import yaml
import openai
import os

from discord.ext import commands
from helpers.utils import is_premium


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


config = load_config()


class AI(commands.Cog):
    def __init__(self, bot_: discord.Bot):
        self.bot = bot_
        self.db_path = "kino.db"
        self.bot.loop.create_task(self.setup_db())
        self.open_ai = openai.AsyncOpenAI(api_key=config["OPENAI_API_KEY"])
        self.conversation_history = {}

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

    async def dalle_generate_image(self, prompt: str) -> str:
        response = await self.open_ai.images.generate(
            model="dall-e-3", prompt=prompt, n=1, size="1024x1024"
        )
        return response.data[0].url

    _ai = discord.commands.SlashCommandGroup(
        name="ai", description="Commands for interacting with the AI."
    )

    @_ai.command(name="draw", description="Draws an image based on a prompt.")
    async def _draw(
        self,
        ctx: discord.ApplicationContext,
        prompt: discord.Option(
            str, description="The prompt to use for the AI to draw.", required=True
        ),
    ):
        if not await is_premium(
            ctx.author,
            self.conn,
        ):
            return await ctx.respond(
                embed=discord.Embed(
                    description=config["MESSAGES"]["PREMIUM_ONLY"],
                    color=config["COLORS"]["ERROR"],
                )
            )

        embed = discord.Embed(
            color=config["COLORS"]["DEFAULT"],
        )
        embed.add_field(
            name="Drawing...",
            value="Grab a cup of coffee, this might take a while.",
        )
        await ctx.defer()
        await ctx.respond(embed=embed)

        image_url = await self.dalle_generate_image(prompt)

        await ctx.interaction.edit_original_response(
            embed=discord.Embed(
                color=config["COLORS"]["SUCCESS"],
            ).set_image(url=image_url)
        )

    @_ai.command(name="chat", description="Chat with Uni.")
    @commands.guild_only()
    async def chat(
        self,
        ctx: discord.ApplicationContext,
        message: discord.Option(str, "The message to send to Uni.", required=True),
    ):
        if not await is_premium(
            ctx.author,
            self.conn,
        ):
            return await ctx.respond(
                embed=discord.Embed(
                    description=config["MESSAGES"]["PREMIUM_ONLY"],
                    color=config["COLORS"]["ERROR"],
                )
            )

        await ctx.defer()

        user_id = ctx.author.id
        user_history = self.conversation_history.setdefault(user_id, [])
        user_history.append({"role": "user", "content": message})

        prompt = f"Q: {message}\nA:"
        chat_response = await self.open_ai.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=user_history + [{"role": "system", "content": prompt}],
        )

        bot_response = chat_response.choices[0].message.content.strip()

        user_history.append({"role": "assistant", "content": bot_response})
        history_length = len(user_history) // 2

        clear_history_button = discord.ui.Button(
            style=discord.ButtonStyle.danger,
            label=f"Clear History ({history_length})",
            custom_id="clear_message_history",
        )
        clear_history_button.callback = self._clear_message_history_callback

        get_chatlog_button = discord.ui.Button(
            style=discord.ButtonStyle.secondary,
            label="Chatlog",
            custom_id="get_chatlog",
        )
        get_chatlog_button.callback = self.generate_chat_history_file

        view = discord.ui.View(clear_history_button, get_chatlog_button)

        await ctx.respond(bot_response, view=view)

    async def _clear_message_history_callback(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        self.conversation_history[user_id] = []
        await interaction.response.edit_message(
            content="Message history cleared.", view=None
        )

    async def generate_chat_history_file(self, interaction: discord.Interaction):
        user_history = self.conversation_history.setdefault(interaction.user.id, [])

        history_text = "Chat History with Uni\n\n"
        for message in user_history:
            speaker = "Uni" if message["role"] == "assistant" else "You"
            history_text += f"{speaker}: {message['content']}\n"

        with open(
            f"{interaction.user.id}_chat_history.txt", "w", encoding="utf-8"
        ) as file:
            file.write(history_text)

        await interaction.response.send_message(
            file=discord.File(f"{interaction.user.id}_chat_history.txt"),
            content="Here's your chat history with Uni.",
        )
        os.remove(f"{interaction.user.id}_chat_history.txt")


def setup(bot_: discord.Bot):
    bot_.add_cog(AI(bot_))
