"""
Yui AI Assistant - Bot de Discord
Modo ligero: solo LLM + memoria + herramientas (sin audio/avatar)
"""

import os
import sys
import json
import logging
import asyncio
import threading
from pathlib import Path
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'backend'))
sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / '.env')

try:
    import discord
except ImportError:
    print("discord.py no esta instalado. Ejecuta: pip install discord.py")
    sys.exit(1)

from message_handler import DiscordMessageHandler

logger = logging.getLogger('Yui.Discord')


def setup_discord_logging(log_dir: Path):
    """Configura logging independiente para el bot de Discord"""
    log_dir.mkdir(parents=True, exist_ok=True)

    disc_logger = logging.getLogger('Yui.Discord')
    disc_logger.setLevel(logging.DEBUG)

    if disc_logger.handlers:
        return disc_logger

    log_file = log_dir / 'discord.log'
    if log_file.exists():
        log_file.unlink()

    file_handler = logging.FileHandler(log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    ))
    disc_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
        datefmt='%H:%M:%S'
    ))
    disc_logger.addHandler(console_handler)

    return disc_logger


class YuiDiscordBot:
    """Bot de Discord para Yui en modo ligero"""

    def __init__(self, llm=None, memory=None):
        """
        Args:
            llm: Instancia de LLM existente (modo integrado) o None (standalone)
            memory: Instancia de MemorySystem existente o None (standalone)
        """
        self.llm = llm
        self.memory = memory
        self._standalone = llm is None
        self._running = False
        self._thread = None
        self._loop = None

        self._load_config()
        setup_discord_logging(PROJECT_ROOT / 'logs')

        intents = discord.Intents.default()
        intents.message_content = True
        activity = discord.CustomActivity(
            name="Hablando con Edakzin 𖹭"
        )
        self.client = discord.Client(
            intents=intents,
            activity=activity,
            status=discord.Status.idle
        )

        self._register_events()
        self.handler = None

    def _load_config(self):
        """Carga configuracion de Discord desde config.json y .env"""
        config_path = PROJECT_ROOT / 'config.json'
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        discord_config = config.get('discord', {})
        self.owner_id = discord_config.get('owner_id', '')
        self.token = os.getenv('DISCORD_BOT_TOKEN', '')

    def _register_events(self):
        """Registra eventos del cliente de Discord"""

        @self.client.event
        async def on_ready():
            logger.info(f"Bot conectado como {self.client.user} (ID: {self.client.user.id})")
            logger.info(f"Servidores: {len(self.client.guilds)}")
            self._running = True
            if self.handler:
                self.handler._discord_loop = asyncio.get_event_loop()

        @self.client.event
        async def on_message(message):
            await self._on_message(message)

    async def _on_message(self, message):
        """Procesa un mensaje entrante"""
        if message.author == self.client.user or message.author.bot:
            return

        # Comando owner para apagar el bot
        if str(message.author.id) == str(self.owner_id) and message.content.strip().lower() == '/apagar':
            await message.channel.send("Entendido, me iré a descansar un rato... 💤 (Apagando bot de Discord)")
            logger.info("Comando /apagar recibido. Apagando el bot de Discord...")
            await self.client.close()
            os._exit(0)
            return

        if not self.handler:
            return

        is_dm = isinstance(message.channel, discord.DMChannel)
        should_reply = is_dm

        if not should_reply and self.client.user in message.mentions:
            should_reply = True

        if not should_reply and message.reference:
            resolved = message.reference.resolved
            if not resolved:
                try:
                    resolved = await message.channel.fetch_message(message.reference.message_id)
                except Exception:
                    resolved = None
            if resolved and resolved.author == self.client.user:
                should_reply = True

        if not should_reply:
            return

        log_content = message.content[:60] + '...' if len(message.content) > 60 else message.content
        logger.info(f"[{message.author.display_name}] {log_content}")

        async with message.channel.typing():
            try:
                loop = asyncio.get_event_loop()
                response = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        self.handler.process_message,
                        message
                    ),
                    timeout=120.0
                )
            except asyncio.TimeoutError:
                logger.error("Timeout generando respuesta (120s)")
                response = "Me tarde mucho pensando, intenta de nuevo."
            except Exception as e:
                logger.error(f"Error procesando mensaje: {e}")
                response = "Tuve un problema, intenta de nuevo."

        for chunk in self._split_message(response):
            await message.channel.send(chunk)

        log_resp = response[:60] + '...' if len(response) > 60 else response
        logger.info(f"[Yui -> {message.author.display_name}] {log_resp}")

    def _split_message(self, text: str, max_len: int = 2000) -> list:
        """Divide mensajes largos respetando el limite de Discord"""
        if len(text) <= max_len:
            return [text]

        chunks = []
        while text:
            if len(text) <= max_len:
                chunks.append(text)
                break

            cut = text.rfind('\n', 0, max_len)
            if cut == -1 or cut < max_len * 0.3:
                cut = text.rfind('. ', 0, max_len)
            if cut == -1 or cut < max_len * 0.3:
                cut = max_len

            chunks.append(text[:cut + 1])
            text = text[cut + 1:].lstrip()

        return chunks

    def _load_standalone_components(self):
        """Carga LLM y memoria para modo standalone"""
        from config import Config

        config = Config.load()

        logger.info("Cargando LLM local (Llama)...")

        # torch debe importarse antes de llama-cpp para que las DLLs de CUDA
        # (cublas, cudart, etc.) se registren en el search path de Windows
        import torch
        from llama_llm import LlamaLLM

        llama_config = config['models']['llama']
        self.llm = LlamaLLM(
            model_path=str(PROJECT_ROOT / config['paths']['llama_model']),
            max_length=llama_config['max_length'],
            temperature=llama_config['temperature'],
            top_p=llama_config['top_p'],
            device=llama_config['device']
        )
        self.llm.load_model()
        logger.info("LLM local cargado")

        logger.info("Cargando sistema de memoria...")
        from memory_system import MemorySystem

        chromadb_path = PROJECT_ROOT / config['paths']['chromadb_path']
        self.memory = MemorySystem(db_path=str(chromadb_path))
        self.memory.load()
        logger.info("Memoria cargada")

    def start_standalone(self):
        """Inicia el bot en modo standalone (bloqueante)"""
        if not self.token:
            logger.error("DISCORD_BOT_TOKEN no configurado en .env")
            return

        logger.info("Modo standalone: cargando componentes...")
        self._load_standalone_components()

        self.handler = DiscordMessageHandler(
            llm=self.llm,
            memory=self.memory,
            owner_id=self.owner_id
        )

        logger.info("Conectando a Discord...")
        self.client.run(self.token, log_handler=None)

    def start_integrated(self, token: str = None):
        """Inicia el bot en modo integrado (no bloqueante, comparte LLM)"""
        token = token or self.token
        if not token:
            logger.error("Token de Discord no proporcionado")
            return False

        self.handler = DiscordMessageHandler(
            llm=self.llm,
            memory=self.memory,
            owner_id=self.owner_id
        )

        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            loop.run_until_complete(self.client.start(token))

        self._thread = threading.Thread(target=_run, daemon=True, name="YuiDiscordBot")
        self._thread.start()
        logger.info("Bot Discord iniciado en modo integrado")
        return True

    def stop(self):
        """Detiene el bot de Discord"""
        if self.client and not self.client.is_closed():
            logger.info("Deteniendo bot de Discord...")
            if self._loop and self._loop.is_running():
                future = asyncio.run_coroutine_threadsafe(self.client.close(), self._loop)
                try:
                    future.result(timeout=10)
                except Exception:
                    pass
            self._running = False
            logger.info("Bot de Discord detenido")

    @property
    def is_running(self) -> bool:
        return self._running and not self.client.is_closed()


def main():
    """Entry point para modo standalone"""
    print("=" * 60)
    print("YUI AI ASSISTANT - DISCORD MODE")
    print("=" * 60)

    bot = YuiDiscordBot()

    try:
        bot.start_standalone()
    except KeyboardInterrupt:
        print("\nCerrando bot...")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
