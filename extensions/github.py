import discord
import aiosqlite
import yaml
import aiohttp

from discord.ext import commands
from helpers.utils import iso_to_discord_timestamp
from helpers.constants import file_emoji_dict


def load_config():
    with open("config.yml", "r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    return config


def get_file_emoji(file_name):
    for extension, emoji in file_emoji_dict.items():
        if file_name.endswith(extension) or file_name == extension:
            return emoji
    return file_emoji_dict["file"]


config = load_config()


class CommitSelectMenu(discord.ui.Select):
    def __init__(self, commits, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commits = commits

    async def get_commit(self, url: str):
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return "Invalid commit."

                commit_info = await resp.json()

        return commit_info

    async def callback(self, interaction: discord.Interaction):
        if selected_commit := next(
            (
                commit
                for commit in self.commits
                if commit["sha"].startswith(self.values[0])
            ),
            None,
        ):
            commit_message = selected_commit["commit"]["message"].split("\n")[0]

            embed = discord.Embed(
                title=commit_message,
                color=config["COLORS"]["DEFAULT"],
            )
            embed.add_field(
                name="Commit message:",
                value=selected_commit["commit"]["message"],
                inline=False,
            )

            comit_ts = iso_to_discord_timestamp(
                selected_commit["commit"]["author"]["date"]
            )

            embed.add_field(
                name="Info:",
                value=(
                    f"Committed by  [`{selected_commit['commit']['author']['name']}`]({selected_commit['author']['html_url']}) - "
                    f"{comit_ts}\n"
                ),
                inline=False,
            )

            stats = await self.get_commit(selected_commit["url"])
            stats = stats["stats"]

            embed.add_field(
                name="Changes:",
                value=(
                    f"{stats['total']} changes: "
                    f"✨ {stats['additions']} additions & "
                    f"🗑️ {stats['deletions']}  deletions"
                ),
                inline=False,
            )
            embed.set_footer(text=f"SHA: {selected_commit['sha']}")
            embed.set_author(
                name=selected_commit["author"]["login"],
                icon_url=selected_commit["author"]["avatar_url"],
                url=selected_commit["author"]["html_url"],
            )

            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(
                    label="View diff",
                    url=selected_commit["html_url"],
                )
            )

            await interaction.response.send_message(
                embed=embed, view=view, ephemeral=True
            )


class Github(commands.Cog):
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

    _git = discord.commands.SlashCommandGroup(
        name="git",
        description="GitHub related commands.",
    )

    @_git.command(
        name="pr",
        description="Get information about a pull request.",
    )
    async def _pr(
        self,
        ctx: discord.ApplicationContext,
        repo: discord.Option(
            str,
            "The repository to get the pull request from. (e.g. uni-bot/uni)",
            required=True,
        ),
        pr_number: discord.Option(int, "The pull request number.", required=True),
    ):
        if (parts := repo.count("/")) != 1:
            await ctx.respond(
                "Invalid repository format. The format should be **owner/repo**."
            )
            return

        pr_info = await self.get_pr_info(repo, pr_number)
        color = config["COLORS"]["DEFAULT"]
        embed = discord.Embed(
            title=f"<:propen:1189443196003045418> {pr_info['title']}",
            url=pr_info["html_url"],
            color=color,
        )

        body_text = (
            f"{pr_info['body'][:400]}{'...' if len(pr_info['body']) > 400 else ''}"
        )
        assignee_text = (
            ", ".join(
                f"[{assignee['login']}]({assignee['html_url']})"
                for assignee in pr_info["assignees"]
            )
            or "No assignees"
        )

        embed.description = f"{body_text}\n\nThis pull request has a total of 💬 **{pr_info['comments']}** comments, 📝 **{pr_info['commits']}** commits, 🟢 **{pr_info['additions']}** additions, 🔴 **{pr_info['deletions']}** deletions, and 📄 **{pr_info['changed_files']}** changed files."
        embed.add_field(
            name="Author",
            value=f"[{pr_info['user']['login']}]({pr_info['user']['html_url']})",
        )
        embed.add_field(name="Assignees", value=assignee_text)
        embed.add_field(
            name="Created",
            value=f"{iso_to_discord_timestamp(pr_info['created_at'])}",
        )

        for field_name, key in [("Merged", "merged_at"), ("Closed", "closed_at")]:
            if date := pr_info.get(key):
                embed.add_field(
                    name=field_name, value=f"{iso_to_discord_timestamp(date)}"
                )

        embed.set_author(
            name=pr_info["head"]["repo"]["full_name"],
            url=pr_info["head"]["repo"]["html_url"],
            icon_url=pr_info["head"]["repo"]["owner"]["avatar_url"],
        )

        await ctx.respond(embed=embed)

    @_git.command(
        name="issue",
        description="Get information about an issue.",
    )
    async def _issue(
        self,
        ctx: discord.ApplicationContext,
        repo: discord.Option(
            str,
            "The repository to get the issue from. (e.g. uni-bot/uni)",
            required=True,
        ),
        issue_number: discord.Option(int, "The issue number.", required=True),
    ):
        if (parts := repo.count("/")) != 1:
            await ctx.respond(
                "Invalid repository format. The format should be **owner/repo**."
            )
            return

        issue_info = await self.get_issue_info(repo, issue_number)
        color = config["COLORS"]["DEFAULT"]
        embed = discord.Embed(
            title=f"<:issue:1189452390433292370> {issue_info['title']}",
            url=issue_info["html_url"],
            color=color,
        )

        body_text = f"{issue_info['body'][:400]}{'...' if len(issue_info['body']) > 400 else ''}"
        assignee_text = (
            ", ".join(
                f"[{assignee['login']}]({assignee['html_url']})"
                for assignee in issue_info["assignees"]
            )
            or "No assignees"
        )

        embed.description = f"{body_text}\n\nThis issue has a total of 💬 **{issue_info['comments']}** comments."
        embed.add_field(
            name="Author",
            value=f"[{issue_info['user']['login']}]({issue_info['user']['html_url']})",
        )
        embed.add_field(name="Assignees", value=assignee_text)
        embed.add_field(
            name="Created",
            value=f"{iso_to_discord_timestamp(issue_info['created_at'])}",
        )

        for field_name, key in [("Closed", "closed_at")]:
            if date := issue_info.get(key):
                embed.add_field(
                    name=field_name, value=f"{iso_to_discord_timestamp(date)}"
                )

        embed.set_author(
            name=issue_info["repository_url"].split("/")[-1],
            url=issue_info["repository_url"],
            icon_url=issue_info["user"]["avatar_url"],
        )

        await ctx.respond(embed=embed)

    @_git.command(
        name="repo",
        description="Get information about a repository.",
    )
    async def _repo(
        self,
        ctx: discord.ApplicationContext,
        repo: discord.Option(
            str,
            "The repository to get information about. (e.g. uni-bot/uni)",
            required=True,
        ),
    ):
        if (parts := repo.count("/")) != 1:
            await ctx.respond(
                "Invalid repository format. The format should be **owner/repo**."
            )
            return

        repo_info = await self.get_repo_info(repo)
        color = config["COLORS"]["DEFAULT"]
        embed = discord.Embed(
            title=f"<:repo:1189453310906880041> {repo_info['name']}",
            url=repo_info["html_url"],
            color=color,
        )

        embed.description = f"{repo_info['description']}\n\nThis repository has a total of 🌟 **{repo_info['stargazers_count']}** stars, 🍴 **{repo_info['forks_count']}** forks, and 📂 **{repo_info['size']}** KB."
        embed.add_field(
            name="Owner",
            value=f"[{repo_info['owner']['login']}]({repo_info['owner']['html_url']})",
        )
        embed.add_field(
            name="Created",
            value=f"{iso_to_discord_timestamp(repo_info['created_at'])}",
        )

        await ctx.respond(embed=embed)

    @_git.command(
        name="user",
        description="Get information about a user.",
    )
    async def _user(
        self,
        ctx: discord.ApplicationContext,
        user: discord.Option(
            str,
            "The user to get information about. (e.g. uni-bot)",
            required=True,
        ),
    ):
        user_info = await self.get_user_info(user)
        color = config["COLORS"]["DEFAULT"]
        embed = discord.Embed(
            title=f"👤 {user_info['login']}",
            url=user_info["html_url"],
            color=color,
        )

        bio = user_info["bio"] or "No bio."

        embed.description = f"{bio}\n\nThis user has a total of 🌟 **{user_info['public_repos']}** public repositories, 🍴 **{user_info['public_gists']}** public gists, and 💬 **{user_info['followers']}** followers."
        embed.add_field(
            name="Created",
            value=f"{iso_to_discord_timestamp(user_info['created_at'])}",
        )

        if user_info["avatar_url"]:
            embed.set_thumbnail(url=user_info["avatar_url"])

        await ctx.respond(embed=embed)

    @_git.command(
        name="commits",
        description="Get the latest commits for a repository.",
    )
    async def _commits(
        self,
        ctx: discord.ApplicationContext,
        repo: discord.Option(
            str,
            "The repository to get the latest commits for. (e.g. uni-bot/uni)",
            required=True,
        ),
    ):
        if repo.count("/") != 1:
            return await ctx.respond(
                "Invalid repository format. The format should be **owner/repo**."
            )

        commit_info = await self.get_latest_commit_info(repo)
        if isinstance(commit_info, str):
            return await ctx.respond(commit_info)

        check_mark = "<:checkmark:1189457685171687538>"

        description = []

        for commit in commit_info:
            sha = commit["sha"][:7]  # Short SHA
            message = commit["commit"]["message"].split("\n")[0]

            if len(message) > 50:
                message = f"{message[:50]}..."
            description.append(
                f"{check_mark} [`{sha}`]({commit['html_url']}) {message.replace('`', '')}"
            )

        embed = discord.Embed(
            title=f"<:github:1189461200841482400> Latest commits in `{repo}`",
            description="\n".join(description),
            color=config["COLORS"]["DEFAULT"],
            url=f"https://github.com/{repo}",
        )

        select_menu = CommitSelectMenu(
            commit_info,
            placeholder="Select a commit to view more information.",
            min_values=1,
            max_values=1,
        )

        for commit in commit_info:
            sha = commit["sha"][:7]
            select_menu.add_option(
                label=f"{sha} - {commit['commit']['author']['name']}",
                value=sha,
                description=commit["commit"]["message"].split("\n")[0][:100],
            )

        view = discord.ui.View()
        view.add_item(select_menu)

        await ctx.respond(
            embed=embed,
            view=view,
        )

    @_git.command(
        name="loc",
        description="Line of code breakdown for a repository.",
    )
    async def _loc(
        self,
        ctx: discord.ApplicationContext,
        repo: discord.Option(
            str,
            "The repository to get the line of code breakdown for. (e.g. uni-bot/uni)",
            required=True,
        ),
    ):
        if repo.count("/") != 1:
            return await ctx.respond(
                "Invalid repository format. The format should be **owner/repo**."
            )

        await ctx.defer()

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.codetabs.com/v1/loc?github={repo}"
            ) as resp:
                if resp.status != 200:
                    return await ctx.respond("Invalid repository.")

                data = await resp.json()

            embed = discord.Embed(
                title=f"Lines of Code in `{repo}`",
                color=config["COLORS"]["DEFAULT"],
                url=f"https://github.com/{repo}",
            )

            total_lines = sum(item["lines"] for item in data)
            total_files = sum(item["files"] for item in data)
            code_breakdown = "\n".join(
                f"{item['language']}: {item['linesOfCode']}"
                for item in data
                if item["language"] != "Total"
            )
            embed.description = f"A total of **{total_lines}** lines of code in **{total_files}** files."
            embed.add_field(
                name="More information:",
                value=f"```{code_breakdown}```",
                inline=False,
            )

            await ctx.respond(embed=embed)

    @_git.command(
        name="files",
        description="Get the files of a repository.",
    )
    async def _files(
        self,
        ctx: discord.ApplicationContext,
        repo: discord.Option(
            str,
            "The repository to get the files for. (e.g. uni-bot/uni)",
            required=True,
        ),
    ):
        if repo.count("/") != 1:
            return await ctx.respond(
                "Invalid repository format. The format should be **owner/repo**."
            )

        await ctx.defer()

        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.github.com/repos/{repo}/contents"
            ) as resp:
                if resp.status != 200:
                    return await ctx.respond("Invalid repository.")

                data = await resp.json()

            embed = discord.Embed(
                title=f"`{repo}`",
                color=config["COLORS"]["DEFAULT"],
                url=f"https://github.com/{repo}",
            )

            description_lines = []
            for item in data:
                if item["type"] == "dir":
                    icon = file_emoji_dict["dir"]
                else:
                    icon = get_file_emoji(item["name"])
                description_lines.append(
                    f"{icon} [`{item['name']}`]({item['html_url']})"
                )
            embed.description = "\n".join(description_lines)

            view = discord.ui.View()
            view.add_item(
                discord.ui.Button(
                    label="View on GitHub", url=f"https://github.com/{repo}"
                )
            )

            await ctx.respond(embed=embed, view=view)

    async def get_pr_info(self, repo, pr_number):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.github.com/repos/{repo}/pulls/{pr_number}"
            ) as resp:
                if resp.status != 200:
                    return "Invalid repository or pull request number."

                pr_info = await resp.json()

        return pr_info

    async def get_issue_info(self, repo, issue_number):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.github.com/repos/{repo}/issues/{issue_number}"
            ) as resp:
                if resp.status != 200:
                    return "Invalid repository or issue number."

                issue_info = await resp.json()

        return issue_info

    async def get_repo_info(self, repo):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.github.com/repos/{repo}") as resp:
                if resp.status != 200:
                    return "Invalid repository."

                repo_info = await resp.json()

        return repo_info

    async def get_user_info(self, user):
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.github.com/users/{user}") as resp:
                if resp.status != 200:
                    return "Invalid user."

                user_info = await resp.json()

        return user_info

    async def get_latest_commit_info(self, repo):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.github.com/repos/{repo}/commits"
            ) as resp:
                if resp.status != 200:
                    return "Invalid repository."

                data = await resp.json()
                return data[:10]


def setup(bot_: discord.Bot):
    bot_.add_cog(Github(bot_))
