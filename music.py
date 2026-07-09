import discord
from discord.ext import commands
from discord import app_commands
import wavelink
import sqlite3

DB_PATH = "bdo_data.db"

# DB 함수 (기존과 동일)
def _get_music_channel(guild_id: int):
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT channel_id FROM music_channels WHERE guild_id=?", (guild_id,)).fetchone()
    conn.close()
    return row[0] if row else None

class MusicControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="⏸ 일시정지/재개", style=discord.ButtonStyle.secondary, custom_id="wavelink_pause")
    async def pause_resume(self, interaction: discord.Interaction, button: discord.ui.Button):
        player: wavelink.Player = interaction.guild.voice_client
        if not player:
            return await interaction.response.send_message("재생 중이 아닙니다.", ephemeral=True)
            
        if player.paused:
            await player.pause(False)
            await interaction.response.send_message("▶️ 재개했습니다.", ephemeral=True)
        else:
            await player.pause(True)
            await interaction.response.send_message("⏸ 일시정지했습니다.", ephemeral=True)

    @discord.ui.button(label="⏭ 다음 곡", style=discord.ButtonStyle.primary, custom_id="wavelink_skip")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        player: wavelink.Player = interaction.guild.voice_client
        if player and player.playing:
            await player.skip(force=True)
            await interaction.response.send_message("⏭ 다음 곡으로 넘어갑니다.", ephemeral=True)
        else:
            await interaction.response.send_message("재생 중이 아닙니다.", ephemeral=True)

    @discord.ui.button(label="⏹ 정지", style=discord.ButtonStyle.danger, custom_id="wavelink_stop")
    async def stop(self, interaction: discord.Interaction, button: discord.ui.Button):
        player: wavelink.Player = interaction.guild.voice_client
        if player:
            player.queue.clear()
            await player.disconnect()
        await interaction.response.send_message("⏹ 재생을 종료하고 나갔습니다.", ephemeral=True)

    @discord.ui.button(label="📋 대기열", style=discord.ButtonStyle.secondary, custom_id="wavelink_queue")
    async def show_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        player: wavelink.Player = interaction.guild.voice_client
        if not player or (not player.playing and player.queue.is_empty):
            return await interaction.response.send_message("대기열이 비어있습니다.", ephemeral=True)
            
        lines = []
        if player.current:
            lines.append(f"**현재 재생 중:** {player.current.title}")
            
        for i, track in enumerate(list(player.queue)[:10], 1):
            lines.append(f"{i}. {track.title}")
            
        if len(player.queue) > 10:
            lines.append(f"...외 {len(player.queue)-10}곡")
            
        embed = discord.Embed(title="📋 재생 대기열", description="\n".join(lines), color=0x3498db)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class MusicCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Lavalink 서버 연결 (위에서 설정한 포트와 비밀번호 일치해야 함)
        nodes = [wavelink.Node(uri="http://127.0.0.1:2333", password="youshallnotpass")]
        await wavelink.Pool.connect(nodes=nodes, client=self.bot, cache_capacity=100)

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        print(f"✅ Lavalink 서버 연결 완료: {payload.node.identifier}")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        # 한 곡이 끝나면 큐에서 다음 곡을 꺼내 재생
        player = payload.player
        if not player: return
        
        if player.queue.is_empty:
            await player.disconnect()
        else:
            next_track = player.queue.get()
            await player.play(next_track)
            
            # 다음 곡 UI 전송
            channel = self.bot.get_channel(player.channel.id) # 또는 마지막 명령어 채널
            if channel:
                embed = discord.Embed(
                    title="🎵 지금 재생 중",
                    description=f"**{next_track.title}**",
                    color=0x9b59b6
                )
                await channel.send(embed=embed, view=MusicControlView())

    @commands.Cog.listener()
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
            return await message.channel.send(f"{message.author.mention} 먼저 음성 채널에 입장해주세요!", delete_after=10)

        search_msg = await message.channel.send(f"🔍 **{query}** 검색 중...")

        # Wavelink로 유튜브 검색
        tracks: wavelink.Search = await wavelink.Playable.search(query)
        if not tracks:
            return await search_msg.edit(content=f"❌ **{query}** 검색 결과가 없습니다.")

        track = tracks[0] # 첫 번째 검색 결과
        await search_msg.delete()

        # 음성 채널 접속 및 플레이어 생성
        if not message.guild.voice_client:
            player: wavelink.Player = await message.author.voice.channel.connect(cls=wavelink.Player)
        else:
            player: wavelink.Player = message.guild.voice_client

        # 대기열에 추가
        await player.queue.put_wait(track)

        if not player.playing:
            # 재생 중이 아니면 바로 재생
            next_track = player.queue.get()
            await player.play(next_track)
            
            embed = discord.Embed(
                title="🎵 지금 재생 중",
                description=f"**{next_track.title}**\n요청: {message.author.display_name}",
                color=0x9b59b6
            )
            await message.channel.send(embed=embed, view=MusicControlView())
        else:
            # 이미 재생 중이면 대기열 추가 메시지
            embed = discord.Embed(
                title="📋 대기열 추가",
                description=f"**{track.title}**\n대기열 {len(player.queue)}번째",
                color=0x2ecc71
            )
            await message.channel.send(embed=embed, delete_after=15)

    @app_commands.command(name="음악채널설정", description="[관리자] 노래봇이 사용할 텍스트 채널을 지정합니다")
    @app_commands.default_permissions(administrator=True)
    async def set_music_channel(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT OR REPLACE INTO music_channels (guild_id, channel_id) VALUES (?,?)", (interaction.guild.id, channel.id))
        conn.commit()
        conn.close()
        await interaction.response.send_message(f"✅ 노래봇 채널이 {channel.mention}으로 설정되었습니다.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(MusicCog(bot))