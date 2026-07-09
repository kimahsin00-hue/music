Python
import discord
from discord.ext import commands
from discord import app_commands

class LoggerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # 임시로 채널 ID를 하드코딩하거나 DB/JSON에서 불러오게 설정 가능합니다.
        self.join_channel_id = 1524346114009075804  # 가입 로그 채널 ID
        self.leave_channel_id = 1524346285933723738 # 탈퇴 로그 채널 ID

    @commands.Cog.listener()
    async def on_member_join(self, member):
        channel = self.bot.get_channel(self.join_channel_id)
        if channel:
            embed = discord.Embed(title="환영합니다!", description=f"{member.mention}님이 서버에 참여하셨습니다.", color=0x2ecc71)
            await channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        channel = self.bot.get_channel(self.leave_channel_id)
        if channel:
            embed = discord.Embed(title="안녕히 가세요", description=f"{member.name}님이 서버를 떠나셨습니다.", color=0xe74c3c)
            await channel.send(embed=embed)

async def setup(bot):
    await bot.add_cog(LoggerCog(bot))