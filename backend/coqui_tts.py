"""
Yui AI Assistant - Cliente TTS (WebSocket + Gestión de Proceso)
Conecta al microservicio TTS aislado para síntesis de voz
Gestiona el ciclo de vida del proceso TTS (start/stop)
NO importa torch, DeepSpeed ni RealtimeTTS (esas dependencias están en el microservicio)
"""

import asyncio
import json
import logging
import threading
import subprocess
import sys
import os
import time
from typing import Callable, Optional
from pathlib import Path

# Funcion para registrar eventos de memoria (opcional)
try:
    from diagnostics.decorators import log_memory_event
except ImportError:
    def log_memory_event(event: str):
        pass  # No-op si diagnostics no esta disponible

logger = logging.getLogger('Yui.Coqui')

# Puerto del servidor TTS (51001 = puerto poco comun)
TTS_SERVICE_PORT = 51001
TTS_SERVICE_URL = f"ws://localhost:{TTS_SERVICE_PORT}"

# Timeout de conexión y síntesis
CONNECTION_TIMEOUT = 10
SYNTHESIS_TIMEOUT = 120  # 2 minutos

# Rutas del microservicio TTS
BACKEND_DIR = Path(__file__).parent
PROJECT_DIR = BACKEND_DIR.parent
TTS_SERVICE_DIR = PROJECT_DIR / "tts-service"
TTS_SERVER_SCRIPT = TTS_SERVICE_DIR / "tts_server.py"
TTS_PYTHON_EXE = TTS_SERVICE_DIR / "venv_tts" / "Scripts" / "python.exe"


class CoquiTTS:
    """Cliente WebSocket para el microservicio TTS con gestión de proceso"""
    
    def __init__(self, voice_samples_dir: str = "voice_samples"):
        """
        Inicializa el cliente TTS
        
        Args:
            voice_samples_dir: Carpeta con muestras de voz (usado por el servidor)
        """
        self.voice_samples_dir = voice_samples_dir
        self._is_playing = False
        self._is_connected = False
        self._cancel_synthesis = False  # Flag para cancelar síntesis en progreso
        self._on_synthesis_complete: Optional[Callable] = None
        self._lock = threading.Lock()
        
        # Gestión de proceso TTS
        self._tts_process: Optional[subprocess.Popen] = None
        self._process_lock = threading.Lock()
        
        logger.info("Inicializando cliente TTS (WebSocket + Gestión Proceso)")
        logger.info(f"  Servidor TTS: {TTS_SERVICE_URL}")
        logger.info(f"  Script: {TTS_SERVER_SCRIPT}")
        logger.info(f"  Python: {TTS_PYTHON_EXE}")
    
    def set_synthesis_complete_callback(self, callback: Callable):
        """Configura callback para cuando TTS completa síntesis"""
        self._on_synthesis_complete = callback
    
    # ==================== GESTIÓN DE PROCESO ====================
    
    def _start_tts_process(self) -> bool:
        """
        Inicia el proceso del microservicio TTS
        
        Returns:
            True si el proceso se inició correctamente
        """
        with self._process_lock:
            # Verificar si ya está corriendo
            if self._tts_process is not None and self._tts_process.poll() is None:
                logger.debug("Proceso TTS ya está corriendo")
                return True
            
            # Verificar que los archivos existen
            if not TTS_PYTHON_EXE.exists():
                logger.error(f"No existe el Python del TTS: {TTS_PYTHON_EXE}")
                logger.error("Ejecuta: cd tts-service && py -3.11 -m venv venv_tts")
                return False
            
            if not TTS_SERVER_SCRIPT.exists():
                logger.error(f"No existe el script TTS: {TTS_SERVER_SCRIPT}")
                return False
            
            logger.info("Iniciando proceso TTS...")
            
            try:
                # Iniciar proceso con output redirigido a logs
                log_file = PROJECT_DIR / "logs" / "tts_process.log"
                log_file.parent.mkdir(exist_ok=True)
                
                self._tts_process = subprocess.Popen(
                    [str(TTS_PYTHON_EXE), str(TTS_SERVER_SCRIPT)],
                    cwd=str(TTS_SERVICE_DIR),
                    stdout=open(log_file, 'w'),
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                
                logger.info(f"  Proceso TTS iniciado (PID: {self._tts_process.pid})")
                return True
                
            except Exception as e:
                logger.error(f"Error iniciando proceso TTS: {e}")
                self._tts_process = None
                return False
    
    def _stop_tts_process(self) -> bool:
        """
        Detiene el proceso del microservicio TTS
        
        Returns:
            True si se detuvo correctamente
        """
        with self._process_lock:
            if self._tts_process is None:
                logger.debug("No hay proceso TTS que detener")
                return True
            
            if self._tts_process.poll() is not None:
                logger.debug("Proceso TTS ya terminó")
                self._tts_process = None
                return True
            
            logger.info(f"Deteniendo proceso TTS (PID: {self._tts_process.pid})...")
            
            try:
                self._tts_process.terminate()
                try:
                    self._tts_process.wait(timeout=10)
                    logger.info("  Proceso TTS terminado limpiamente")
                except subprocess.TimeoutExpired:
                    logger.warning("  Timeout esperando TTS, forzando kill...")
                    self._tts_process.kill()
                    self._tts_process.wait(timeout=5)
                    logger.info("  Proceso TTS forzado a terminar")
                
                self._tts_process = None
                self._is_connected = False
                return True
                
            except Exception as e:
                logger.error(f"Error deteniendo proceso TTS: {e}")
                self._tts_process = None
                return False
    
    def _is_process_running(self) -> bool:
        """Verifica si el proceso TTS está corriendo"""
        with self._process_lock:
            return self._tts_process is not None and self._tts_process.poll() is None
    
    def _wait_for_server_ready(self, max_attempts: int = 30, delay: float = 2.0) -> bool:
        """
        Espera a que el servidor TTS esté listo para aceptar conexiones
        
        Args:
            max_attempts: Número máximo de intentos
            delay: Segundos entre intentos
            
        Returns:
            True si el servidor está listo
        """
        logger.info("  Esperando a que el servidor TTS esté listo...")
        
        for attempt in range(max_attempts):
            try:
                # Intentar conexión de prueba
                import socket
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                result = sock.connect_ex(('localhost', TTS_SERVICE_PORT))
                sock.close()
                
                if result == 0:
                    logger.info(f"  Servidor TTS listo después de {(attempt + 1) * delay:.1f}s")
                    return True
                    
            except Exception:
                pass
            
            # Verificar que el proceso sigue vivo
            if not self._is_process_running():
                logger.error("  Proceso TTS murió mientras esperaba")
                return False
            
            time.sleep(delay)
        
        logger.error(f"  Timeout esperando servidor TTS ({max_attempts * delay}s)")
        return False
    
    # ==================== CONEXIÓN WEBSOCKET ====================
    
    async def _connect(self):
        """Conecta al servidor TTS (conexión fresca cada vez)"""
        try:
            import websockets
            ws = await asyncio.wait_for(
                websockets.connect(TTS_SERVICE_URL),
                timeout=CONNECTION_TIMEOUT
            )
            self._is_connected = True
            logger.info("Conectado al servidor TTS")
            return ws
        except asyncio.TimeoutError:
            logger.error(f"Timeout conectando a TTS server ({CONNECTION_TIMEOUT}s)")
            return None
        except Exception as e:
            logger.error(f"Error conectando a TTS server: {e}")
            return None
    
    async def _send_message(self, data: dict) -> Optional[dict]:
        """Envía mensaje al servidor y espera respuesta"""
        ws = await self._connect()
        if ws is None:
            return None
        
        try:
            await ws.send(json.dumps(data))
            response = await asyncio.wait_for(
                ws.recv(),
                timeout=SYNTHESIS_TIMEOUT
            )
            return json.loads(response)
        except Exception as e:
            logger.error(f"Error comunicándose con TTS server: {e}")
            return None
        finally:
            await ws.close()
    
    async def _send_stop_command(self):
        """Envía comando de stop al servidor TTS para interrumpir síntesis actual"""
        try:
            import websockets
            ws = await asyncio.wait_for(
                websockets.connect(TTS_SERVICE_URL),
                timeout=2.0
            )
            await ws.send(json.dumps({'action': 'stop'}))
            self._is_playing = False
            await ws.close()
            logger.info("  Síntesis anterior interrumpida")
        except Exception as e:
            logger.warning(f"Error enviando stop: {e}")
    
    # ==================== SÍNTESIS ====================
    
    async def _synthesize_async(self, text: str, language: str = "es"):
        """Versión async de synthesize"""
        if not text:
            return
        
        # Resetear flag de cancelación
        self._cancel_synthesis = False
        
        # Si ya está hablando, interrumpir síntesis actual
        if self._is_playing:
            logger.info("Interrumpiendo síntesis actual para nueva...")
            await self._send_stop_command()
        
        log_text = text[:50] + "..." if len(text) > 50 else text
        logger.info(f" Sintetizando (streaming): '{log_text}'")
        
        # Notificar GUI inmediatamente
        if self._on_synthesis_complete is not None:
            self._on_synthesis_complete(text)
        
        self._is_playing = True
        ws = None
        
        try:
            # Asegurar que el proceso está corriendo
            if not self._is_process_running():
                logger.warning("Proceso TTS no está corriendo, iniciando...")
                if not self._start_tts_process():
                    raise ConnectionError("No se pudo iniciar el proceso TTS")
                if not self._wait_for_server_ready():
                    raise ConnectionError("Servidor TTS no respondió a tiempo")
            
            # Crear conexión fresca para esta síntesis
            ws = await self._connect()
            if ws is None:
                raise ConnectionError("No se pudo conectar al servidor TTS")
            
            # Enviar solicitud de síntesis
            await ws.send(json.dumps({
                'action': 'synthesize',
                'text': text,
                'language': language
            }))
            
            # Esperar respuestas (playing -> done)
            while True:
                # Verificar si se canceló la síntesis
                if self._cancel_synthesis:
                    logger.info("  Síntesis cancelada por interrupción")
                    await self._send_stop_command()
                    break
                
                try:
                    response = await asyncio.wait_for(
                        ws.recv(),
                        timeout=SYNTHESIS_TIMEOUT
                    )
                    data = json.loads(response)
                    status = data.get('status', '')
                    
                    if status == 'playing':
                        pass
                    elif status == 'done':
                        logger.info("  Síntesis streaming completada")
                        break
                    elif status == 'stopped':
                        logger.info("  Síntesis detenida por comando stop")
                        break
                    elif status == 'error':
                        raise RuntimeError(data.get('message', 'Error desconocido'))
                    
                except asyncio.TimeoutError:
                    logger.warning("Timeout esperando respuesta del TTS")
                    break
                    
        except Exception as e:
            logger.error(f" Error al sintetizar: {e}")
            raise
        finally:
            self._is_playing = False
            if ws:
                await ws.close()
    
    def synthesize(self, text: str, language: str = "es"):
        """
        Sintetiza texto a voz (bloqueante)
        
        Args:
            text: Texto a sintetizar
            language: Código de idioma (es, en, fr, de, it, pt, etc.)
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        if loop.is_running():
            future = asyncio.run_coroutine_threadsafe(
                self._synthesize_async(text, language),
                loop
            )
            future.result(timeout=SYNTHESIS_TIMEOUT)
        else:
            loop.run_until_complete(self._synthesize_async(text, language))
    
    def synthesize_async(self, text: str, language: str = "es"):
        """Sintetiza texto a voz en un hilo separado (no bloqueante)"""
        def run_sync():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self._synthesize_async(text, language))
            finally:
                loop.close()
        
        thread = threading.Thread(target=run_sync, daemon=True)
        thread.start()
        return thread
    
    # ==================== CICLO DE VIDA ====================
    
    def load_model(self) -> bool:
        """
        Inicia el proceso TTS y carga el modelo
        
        Returns:
            True si el modelo se cargó correctamente
        """
        logger.info("Cargando modelo TTS (iniciando proceso)...")
        log_memory_event("CoquiTTS.load_model:START")
        
        # Iniciar proceso si no está corriendo
        if not self._start_tts_process():
            return False
        
        # Esperar a que el servidor esté listo
        if not self._wait_for_server_ready():
            self._stop_tts_process()
            return False
        
        # Enviar comando load al servidor
        async def _load():
            response = await self._send_message({'action': 'load'})
            if response and response.get('status') == 'loaded':
                logger.info(" Modelo TTS cargado correctamente")
                log_memory_event("CoquiTTS.load_model:END")
                return True
            else:
                logger.error(" Error cargando modelo TTS")
                return False
        
        import concurrent.futures
        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(lambda: asyncio.run(_load()))
                return future.result(timeout=180)  # 3 minutos para cargar modelo
        except Exception as e:
            logger.error(f"Error cargando TTS: {e}")
            return False
    
    def unload_model(self) -> bool:
        """
        Detiene el proceso TTS completamente (libera toda la VRAM)
        
        Returns:
            True si se detuvo correctamente
        """
        logger.info("Descargando modelo TTS (deteniendo proceso)...")
        result = self._stop_tts_process()
        if result:
            logger.info(" Proceso TTS detenido - VRAM liberada")
            log_memory_event("CoquiTTS.unload_model:END")
        return result
    
    def shutdown(self):
        """Detiene el proceso TTS para liberar VRAM"""
        logger.info("Shutdown TTS...")
        self._stop_tts_process()
        self._is_playing = False
        self._is_connected = False
    
    def stop(self):
        """Detiene la reproducción actual y envía comando stop al servidor TTS"""
        logger.info("  Deteniendo reproducción...")
        
        # Marcar para cancelar síntesis en progreso
        self._cancel_synthesis = True
        self._is_playing = False
        
        # Enviar comando stop al servidor TTS (conexión rápida)
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self._send_stop_command())
            loop.close()
            logger.info("  Reproducción detenida correctamente")
        except Exception as e:
            logger.warning(f"  Error enviando stop al servidor: {e}")
    
    def is_playing(self) -> bool:
        """Retorna True si hay audio reproduciéndose"""
        return self._is_playing
    
    def is_ready(self) -> bool:
        """Retorna True si el TTS está listo para sintetizar"""
        return self._is_process_running()
    
    def change_voice(self, new_samples_dir: str):
        """
        Cambia la voz a usar
        Nota: Requiere reiniciar el servidor TTS con nuevas muestras
        """
        logger.warning("change_voice requiere reiniciar el servidor TTS")
    
    def list_available_voices(self) -> list:
        """Lista las muestras de voz disponibles"""
        return []
