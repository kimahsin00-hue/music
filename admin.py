import discord
from discord.ext import commands
from discord import app_commands

class AdminDashboardCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="대시보드", description="[관리자] 서버 관리 대시보드를 엽니다.")
    @app_commands.default_permissions(administrator=True)
    async def dashboard(self, interaction: discord.Interaction):
        guild = interaction.guild
        embed = discord.Embed(title=f"🛡️ {guild.name} 관리자 대시보드", color=0xf1c40f)
        embed.add_field(name="서버 인원", value=f"{guild.member_count}명", inline=True)
        embed.add_field(name="텍스트 채널", value=f"{len(guild.text_channels)}개", inline=True)
        embed.add_field(name="음성 채널", value=f"{len(guild.voice_channels)}개", inline=True)
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

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
    await bot.add_cog(AdminDashboardCog(bot))