import discord
from discord.ext import commands
from discord import app_commands
import math

MEMBERS_PER_PAGE = 15


def build_dashboard_embed(guild: discord.Guild) -> discord.Embed:
    embed = discord.Embed(title=f"🛡️ {guild.name} 관리자 대시보드", color=0xf1c40f)
    embed.add_field(name="서버 인원", value=f"{guild.member_count}명", inline=True)
    embed.add_field(name="텍스트 채널", value=f"{len(guild.text_channels)}개", inline=True)
    embed.add_field(name="음성 채널", value=f"{len(guild.voice_channels)}개", inline=True)
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    embed.set_footer(text="마지막 갱신")
    embed.timestamp = discord.utils.utcnow()
    return embed


class AdminDashboardView(discord.ui.View):
    """상시 관리자 대시보드 패널.
    timeout=None + 고정 custom_id 조합이라 봇이 재시작돼도
    setup()에서 bot.add_view()로 다시 등록해주면 버튼이 계속 동작한다."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="🔄 새로고침", style=discord.ButtonStyle.secondary, custom_id="admdash_refresh")
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = build_dashboard_embed(interaction.guild)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="👥 멤버 목록보기", style=discord.ButtonStyle.primary, custom_id="admdash_memberlist")
    async def member_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        await interaction.response.defer(ephemeral=True)

        # 캐시(guild.members)는 Members Intent/청킹 상태에 따라
        # 음성채널 등 일부만 채워져 있을 수 있어서, API로 전체 멤버를 직접 가져온다.
        try:
            members = [m async for m in guild.fetch_members(limit=None) if not m.bot]
        except discord.Forbidden:
            return await interaction.followup.send(
                "멤버 목록을 가져올 권한이 없습니다. "
                "디스코드 개발자 포털 → Bot → Privileged Gateway Intents 에서 "
                "'Server Members Intent'를 켜주세요.",
                ephemeral=True
            )

        members.sort(key=lambda m: m.display_name.lower())

        if not members:
            return await interaction.followup.send("멤버 정보를 가져올 수 없습니다.", ephemeral=True)

        view = MemberListView(members, interaction.user.id)
        embed = view.build_embed(guild)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class MemberListView(discord.ui.View):
    """멤버 목록 페이지네이션. 요청한 사람만 페이지를 넘길 수 있음."""

    def __init__(self, members: list[discord.Member], author_id: int):
        super().__init__(timeout=120)
        self.members = members
        self.author_id = author_id
        self.page = 0
        self.max_page = max(0, math.ceil(len(members) / MEMBERS_PER_PAGE) - 1)
        self._sync_buttons()

    def _sync_buttons(self):
        self.prev_page.disabled = (self.page <= 0)
        self.next_page.disabled = (self.page >= self.max_page)

    def build_embed(self, guild: discord.Guild) -> discord.Embed:
        start = self.page * MEMBERS_PER_PAGE
        chunk = self.members[start:start + MEMBERS_PER_PAGE]
        lines = [f"{start + i + 1}. {m.mention} ({m.display_name})" for i, m in enumerate(chunk)]

        embed = discord.Embed(
            title=f"👥 {guild.name} 멤버 목록 ({len(self.members)}명)",
            description="\n".join(lines) if lines else "표시할 멤버가 없습니다.",
            color=0x3498db
        )
        embed.set_footer(text=f"{self.page + 1} / {self.max_page + 1} 페이지")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("이 버튼은 요청하신 분만 사용할 수 있습니다.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="◀ 이전", style=discord.ButtonStyle.secondary, custom_id="admdash_ml_prev")
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page -= 1
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.build_embed(interaction.guild), view=self)

    @discord.ui.button(label="다음 ▶", style=discord.ButtonStyle.secondary, custom_id="admdash_ml_next")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.page += 1
        self._sync_buttons()
        await interaction.response.edit_message(embed=self.build_embed(interaction.guild), view=self)


class AdminDashboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="설치-관리자대시보드", description="[관리자] 상시 관리자 대시보드 패널을 이 채널에 설치합니다.")
    @app_commands.default_permissions(administrator=True)
    async def install_dashboard(self, interaction: discord.Interaction):
        embed = build_dashboard_embed(interaction.guild)
        await interaction.response.send_message(embed=embed, view=AdminDashboardView())

    @app_commands.command(name="청소", description="[관리자] 메시지를 삭제합니다.")
    @app_commands.default_permissions(manage_messages=True)
    async def clear_messages(self, interaction: discord.Interaction, amount: int):
        if amount < 1 or amount > 100:
            await interaction.response.send_message("1에서 100 사이의 숫자를 입력해주세요.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 {len(deleted)}개의 메시지를 삭제했습니다.", ephemeral=True)


async def setup(bot):
    bot.add_view(AdminDashboardView())  # 재시작 후에도 버튼 계속 동작하도록 재등록
    await bot.add_cog(AdminDashboardCog(bot))
