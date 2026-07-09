import discord
from discord.ext import commands
from discord import app_commands

class RoomNameModal(discord.ui.Modal, title="음성 채널 생성"):
    room_name = discord.ui.TextInput(
        label="채널 이름",
        style=discord.TextStyle.short,
        placeholder="생성할 채널 이름을 입력하세요.",
        required=True
    )

    def __init__(self, limit: int):
        super().__init__()
        self.limit = limit

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        category = interaction.channel.category # 명령어를 친 카테고리에 생성
        
        # 권한 설정: 생성자는 모든 권한, 나머지는 기본 권한
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=True),
            interaction.user: discord.PermissionOverwrite(manage_channels=True, connect=True)
        }

        try:
            vc = await guild.create_voice_channel(
                name=self.room_name.value,
                category=category,
                user_limit=self.limit,
                overwrites=overwrites
            )
            await interaction.response.send_message(f"✅ {vc.mention} 채널이 생성되었습니다!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ 채널 생성 실패: {e}", ephemeral=True)


class VoiceCreatorView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="👥 3인방 생성", style=discord.ButtonStyle.primary, custom_id="vc_3")
    async def create_3(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RoomNameModal(limit=3))

    @discord.ui.button(label="👥 5인방 생성", style=discord.ButtonStyle.success, custom_id="vc_5")
    async def create_5(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RoomNameModal(limit=5))

    @discord.ui.button(label="👥 20인방 생성", style=discord.ButtonStyle.danger, custom_id="vc_20")
    async def create_20(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(RoomNameModal(limit=20))


class VoiceCreatorCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="음성방패널", description="음성방 생성 패널을 띄웁니다.")
    @app_commands.default_permissions(administrator=True)
    async def setup_voice_panel(self, interaction: discord.Interaction):
        embed = discord.Embed(title="맞춤형 음성 채널 생성기", description="아래 버튼을 눌러 원하는 인원수의 음성 채널을 만드세요.\n(방장 권한이 부여되어 자유롭게 관리할 수 있습니다.)", color=0x3498db)
        await interaction.response.send_message(embed=embed, view=VoiceCreatorView())

async def setup(bot):
    await bot.add_cog(VoiceCreatorCog(bot))
    # 봇 재시작 시에도 뷰가 유지되도록 메인 파일 setup_hook에 self.add_view(VoiceCreatorView()) 추가 권장