import asyncio
import sqlite3
import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import yt_dlp

load_dotenv()

# ==========================================
# [독립 실행형 음악 봇]
# 기존 cogs/music.py 의 MusicCog 로직을 그대로 가져와
# 별도 프로세스 / 별도 봇 토큰으로 실행할 수 있게 만든 파일입니다.
# ==========================================

YDL_SEARCH_OPTS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch1",
    "extract_flat": False,
    "noplaylist": True,
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

DB_PATH = "bdo_data.db"  # 기존 봇과 같은 DB 파일을 공유합니다 (같은 폴더에서 실행 시)


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS music_channels (
            guild_id INTEGER PRIMARY KEY,
            channel_id INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def _get_music_channel(guild_id: int):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute(
        "SELECT channel_id FROM music_channels WHERE guild_id=?", (guild_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


def _set_music_channel(guild_id: int, channel_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        "INSERT OR REPLACE INTO music_channels (guild_id, channel_id) VALUES (?,?)",
        (guild_id, channel_id),
    )
    conn.commit()
    conn.close()


class MusicControlView(discord.ui.View):
    def __init__(self, bot: "MusicBot", guild_id: int):
        super().__init__(timeout=None)
        self.bot = bot
        self.guild_id = guild_id

    @discord.ui.button(label="⏸ 일시정지/재개", style=discord.ButtonStyle.secondary, custom_id="music_pause")
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if not vc:
            await interaction.response.send_message("재생 중이 아닙니다.", ephemeral=True); return
        if vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ 재개했습니다.", ephemeral=True)
        elif vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸ 일시정지했습니다.", ephemeral=True)
        else:
            await interaction.response.send_message("재생 중이 아닙니다.", ephemeral=True)

    @discord.ui.button(label="⏭ 다음 곡", style=discord.ButtonStyle.primary, custom_id="music_skip")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc and (vc.is_playing() or vc.is_paused()):
            vc.stop()
            await interaction.response.send_message("⏭ 다음 곡으로 넘어갑니다.", ephemeral=True)
        else:
            await interaction.response.send_message("재생 중이 아닙니다.", ephemeral=True)

    @discord.ui.button(label="⏹ 정지", style=discord.ButtonStyle.danger, custom_id="music_stop")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.bot.get_state(self.guild_id)
        state["queue"].clear()
        vc = interaction.guild.voice_client
        if vc:
            await vc.disconnect()
        await interaction.response.send_message("⏹ 재생을 종료하고 음성 채널에서 나갔습니다.", ephemeral=True)

    @discord.ui.button(label=" 현재 대기열", style=discord.ButtonStyle.secondary, custom_id="music_queue")
    async def show_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        state = self.bot.get_state(self.guild_id)
        current = state.get("current")
        queue = state.get("queue", [])
        if not current and not queue:
            await interaction.response.send_message("대기열이 비어있습니다.", ephemeral=True); return
        lines = []
        if current:
            lines.append(f" **현재 재생 중:** {current['title']}")
        for i, item in enumerate(queue[:10], 1):
            lines.append(f"{i}. {item['title']}")
        if len(queue) > 10:
            lines.append(f"...외 {len(queue)-10}곡")
        embed = discord.Embed(title="📋 재생 대기열", description="\n".join(lines), color=0x3498db)
        await interaction.response.send_message(embed=embed, ephemeral=True)


def _search_youtube(query: str) -> dict | None:
    with yt_dlp.YoutubeDL(YDL_SEARCH_OPTS) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if not info or "entries" not in info or not info["entries"]:
                return None
            entry = info["entries"][0]
            formats = entry.get("formats", [])
            audio_url = None
            for f in formats:
                if f.get("acodec") != "none" and f.get("vcodec") == "none":
                    audio_url = f["url"]
                    break
            if not audio_url:
                audio_url = entry.get("url")
            return {
                "title": entry.get("title", "알 수 없음"),
                "url": audio_url,
                "duration": entry.get("duration", 0),
            }
        except Exception as e:
            raise RuntimeError(f"yt-dlp 오류: {e}")


class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.guilds = True
        super().__init__(command_prefix="!!음악!!", intents=intents)  # 프리픽스 명령 안 쓸 거라 충돌 방지용으로 임의 문자열
        self._states: dict[int, dict] = {}
        _init_db()

    def get_state(self, guild_id: int) -> dict:
        if guild_id not in self._states:
            self._states[guild_id] = {"queue": [], "current": None, "control_msg": None}
        return self._states[guild_id]

    async def setup_hook(self):
        # 영구 View 등록 (버튼이 재시작 후에도 동작하도록)
        self.add_view(MusicControlView(self, 0))
        await self.tree.sync()
        print("🎵 음악봇 슬래시 명령 동기화 완료")

    async def on_ready(self):
        print(f"✅ 음악봇 로그인 완료: {self.user} ({self.user.id})")

    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        music_ch = _get_music_channel(message.guild.id)
        if not music_ch or message.channel.id != music_ch:
            return

        query = message.content.strip()
        if not query:
            return

        if not message.author.voice or not message.author.voice.channel:
            await message.channel.send(
                f"{message.author.mention} 먼저 음성 채널에 입장해주세요!", delete_after=10
            )
            return

        search_msg = await message.channel.send(f"🔍 **{query}** 검색 중...")

        try:
            info = await asyncio.get_event_loop().run_in_executor(
                None, lambda: _search_youtube(query)
            )
        except Exception as e:
            await search_msg.edit(content=f"❌ 검색 실패: {e}")
            return

        if not info:
            await search_msg.edit(content=f"❌ **{query}** 검색 결과가 없습니다.")
            return

        state = self.get_state(message.guild.id)
        state["queue"].append({
            "title": info["title"],
            "url": info["url"],
            "duration": info.get("duration", 0),
            "requester": message.author.display_name,
        })

        await search_msg.delete()

        vc = message.guild.voice_client
        if not vc or not vc.is_connected():
            vc = await message.author.voice.channel.connect()
            await self._play_next(message.guild, message.channel)
        elif not vc.is_playing() and not vc.is_paused():
            await self._play_next(message.guild, message.channel)
        else:
            embed = discord.Embed(
                title="📋 대기열 추가",
                description=f"**{info['title']}**\n대기열 {len(state['queue'])}번째",
                color=0x2ecc71
            )
            await message.channel.send(embed=embed, delete_after=15)

    async def _play_next(self, guild: discord.Guild, channel: discord.TextChannel):
        state = self.get_state(guild.id)
        vc = guild.voice_client

        if not state["queue"] or not vc:
            state["current"] = None
            if vc:
                await asyncio.sleep(60)
                if vc.is_connected() and not vc.is_playing():
                    await vc.disconnect()
            return

        item = state["queue"].pop(0)
        state["current"] = item

        if state.get("control_msg"):
            try:
                await state["control_msg"].delete()
            except Exception:
                pass

        dur = f"{item['duration']//60}:{item['duration']%60:02d}" if item["duration"] else "알 수 없음"
        embed = discord.Embed(
            title="🎵 지금 재생 중",
            description=f"**{item['title']}**\n⏱ {dur} | 요청: {item['requester']}",
            color=0x9b59b6
        )
        view = MusicControlView(self, guild.id)
        control_msg = await channel.send(embed=embed, view=view)
        state["control_msg"] = control_msg

        def after_playing(error):
            if error:
                print(f"⚠️ 재생 오류: {error}")
            asyncio.run_coroutine_threadsafe(
                self._play_next(guild, channel), self.loop
            )

        try:
            source = discord.FFmpegPCMAudio(item["url"], **FFMPEG_OPTIONS)
            source = discord.PCMVolumeTransformer(source, volume=0.5)
            vc.play(source, after=after_playing)
        except Exception as e:
            await channel.send(f"❌ 재생 오류: {e}", delete_after=15)
            await self._play_next(guild, channel)


bot = MusicBot()


@bot.tree.command(name="음악채널설정", description="[관리자] 노래봇이 사용할 텍스트 채널을 지정합니다")
@app_commands.default_permissions(administrator=True)
async def set_music_channel(interaction: discord.Interaction, channel: discord.VoiceChannel):
    _set_music_channel(interaction.guild.id, channel.id)
    await interaction.response.send_message(
        f"✅ 노래봇 채널이 {channel.mention}으로 설정되었습니다.\n"
        "해당 채널에 가수명이나 노래 제목을 입력하면 자동으로 재생됩니다.",
        ephemeral=True
    )


if __name__ == "__main__":
    token = os.getenv("MUSIC_BOT_TOKEN")
    if not token:
        print("❌ 오류: .env 파일에서 MUSIC_BOT_TOKEN을 찾을 수 없습니다!")
        print("   (기존 DISCORD_TOKEN과는 별개의 새 봇 토큰을 발급받아 .env에 추가하세요)")
        raise SystemExit(1)
    bot.run(token)
