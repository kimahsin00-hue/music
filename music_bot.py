import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
from cogs.music import MusicControlView # 뷰 영구 유지를 위해 import

load_dotenv()

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        super().__init__(command_prefix="!!", intents=intents)

    async def setup_hook(self):
        # 음악 컨트롤 뷰 영구 등록 (재시작해도 버튼 작동)
        self.add_view(MusicControlView())
        
        # cogs 폴더에서 기능 불러오기
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
                print(f"✅ {filename} 로드 완료")
                
        await self.tree.sync()
        print("🎵 슬래시 명령 동기화 완료")

    async def on_ready(self):
        print(f"✅ 봇 로그인 완료: {self.user}")

bot = MyBot()

if __name__ == "__main__":
    bot.run(os.getenv("BOT_TOKEN"))