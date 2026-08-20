"""
TTS Microservice Server - Yui AI Assistant
WebSocket server para sintesis de voz con RealtimeTTS + DeepSpeed
Aislado en su propio proceso y venv para evitar conflictos de dependencias
"""

import asyncio
import json
import logging
import os
import glob
import sys
from pathlib import Path

# Paths relativos al directorio padre (yui-asistente)
BASE_DIR = Path(__file__).parent.parent
VOICE_SAMPLES_DIR = BASE_DIR / "voice_samples"
MODELS_DIR = BASE_DIR / "models"
LOGS_DIR = BASE_DIR / "logs"

# IMPORTANTE: Cambiar al directorio base para que TTS descargue modelos ahi
os.chdir(BASE_DIR)

# Configurar variables de entorno para que Coqui TTS use nuestro directorio de modelos
# Esto evita que descargue el modelo duplicado en tts-service/models/
os.environ['COQUI_TOS_AGREED'] = '1'  # Aceptar TOS automaticamente

# Crear directorio de logs si no existe
LOGS_DIR.mkdir(exist_ok=True)

# Configurar logging
LOG_FORMAT = '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
LOG_DATE_FORMAT = '%H:%M:%S'

# Logger principal
logger = logging.getLogger('Yui.TTSServer')
logger.setLevel(logging.DEBUG)
logger.propagate = False  # Evitar logs duplicados

# Handler para archivo (logs/tts.log)
file_handler = logging.FileHandler(LOGS_DIR / "tts.log", mode='w', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
logger.addHandler(file_handler)

# Handler para consola con colores si esta disponible
try:
    import colorlog
    console_handler = colorlog.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(colorlog.ColoredFormatter(
        '%(log_color)s' + LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT
    ))
    logger.addHandler(console_handler)
except ImportError:
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
    logger.addHandler(console_handler)

# Puerto del servidor (51001 = puerto poco comun para evitar conflictos)
TTS_PORT = 51001


class TTSEngine:
    """Motor de síntesis de voz con RealtimeTTS + DeepSpeed"""
    
    def __init__(self):
        self.engine = None
        self.stream = None
        self.voice_samples = []
        self.device = "cuda"
        self._is_playing = False
        self._is_loaded = False
        
    def find_voice_samples(self):
        """Busca muestras de voz WAV en la carpeta"""
        pattern = str(VOICE_SAMPLES_DIR / '*.wav')
        samples = glob.glob(pattern)
        
        if samples:
            logger.info(f"Encontradas {len(samples)} muestras de voz")
        else:
            logger.warning(f"No se encontraron muestras en {VOICE_SAMPLES_DIR}")
        
        return samples


    
    def load(self):
        """Carga el modelo XTTS v2 con RealtimeTTS (CUDA nativo)"""
        if self._is_loaded:
            logger.warning("TTS ya está cargado")
            return True
        
        try:
            import torch
            logger.info("Cargando RealtimeTTS con CUDA...")
            logger.info(f"  PyTorch: {torch.__version__}")
            logger.info(f"  CUDA disponible: {torch.cuda.is_available()}")
            if torch.cuda.is_available():
                logger.info(f"  GPU: {torch.cuda.get_device_name(0)}")
            
            from RealtimeTTS import TextToAudioStream, CoquiEngine
            
            # Buscar muestras de voz
            self.voice_samples = self.find_voice_samples()
            
            if not self.voice_samples:
                logger.error("No hay muestras de voz disponibles")
                return False
            
            # Mostrar info de muestras
            logger.info(f"  Usando {len(self.voice_samples)} muestras de voz para clonación")
            
            # Verificar si hay modelo local
            local_model = MODELS_DIR / "v2.0.2"
            if local_model.exists():
                logger.info(f"  Modelo local detectado: {local_model}")
            
            # Crear engine CON DeepSpeed (instalado en venv compartido)
            self.engine = CoquiEngine(
                model_name="tts_models/multilingual/multi-dataset/xtts_v2",
                voice=self.voice_samples,
                language="es",
                use_deepspeed=True,  # DeepSpeed habilitado
                device=self.device,
                speed=1.0,
                temperature=0.75,
                full_sentences=True,
                level=logging.WARNING
            )
            
            self.stream = TextToAudioStream(self.engine)
            self._is_loaded = True
            
            logger.info("RealtimeTTS + DeepSpeed cargado correctamente")
            logger.info("  Modo: CUDA + DeepSpeed")
            return True
            
        except Exception as e:
            logger.error(f"Error al cargar TTS: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._load_fallback()
    
    def _load_fallback(self):
        """Intenta cargar sin DeepSpeed"""
        try:
            logger.warning("Intentando sin DeepSpeed...")
            from RealtimeTTS import TextToAudioStream, CoquiEngine
            
            self.engine = CoquiEngine(
                model_name="tts_models/multilingual/multi-dataset/xtts_v2",
                voice=self.voice_samples,
                language="es",
                use_deepspeed=False,
                device=self.device,
                speed=1.0,
                full_sentences=True,
                level=logging.WARNING
            )
            
            self.stream = TextToAudioStream(self.engine)
            self._is_loaded = True
            logger.info("Fallback sin DeepSpeed cargado")
            return True
            
        except Exception as e:
            logger.error(f"Fallback también falló: {e}")
            return False
    
    def synthesize(self, text: str, language: str = "es"):
        """Sintetiza texto a voz con streaming"""
        if not self._is_loaded:
            if not self.load():
                raise RuntimeError("TTS no pudo cargarse")
        
        log_text = text[:50] + "..." if len(text) > 50 else text
        logger.info(f"Sintetizando: '{log_text}'")
        
        try:
            # Detener cualquier reproduccion previa para limpiar buffer
            if self._is_playing:
                logger.info("  Deteniendo sintesis previa antes de nueva...")
                self.stream.stop()
            
            self._is_playing = True
            self.stream.feed(text)
            self.stream.play(
                fast_sentence_fragment=False,
                language=language
            )
            
            self._is_playing = False
            logger.info("  Síntesis completada")
            return True
            
        except Exception as e:
            self._is_playing = False
            logger.error(f"Error al sintetizar: {e}")
            raise
    
    def stop(self):
        """Detiene la reproducción actual y limpia el buffer"""
        if self.stream:
            try:
                self.stream.stop()
                self._is_playing = False
                logger.info("Reproducción detenida")
            except Exception as e:
                logger.warning(f"Error al detener stream: {e}")
                self._is_playing = False
    
    def shutdown(self):
        """Libera recursos"""
        self.unload()
    
    def unload(self):
        """Descarga el modelo TTS y libera VRAM"""
        if not self._is_loaded:
            logger.info("TTS ya está descargado")
            return True
        
        logger.info("Descargando modelo TTS para liberar VRAM...")
        
        # Detener stream si está activo
        if self.stream:
            try:
                self.stream.stop()
            except:
                pass
            self.stream = None
        
        # Shutdown del engine
        if self.engine:
            try:
                if hasattr(self.engine, 'shutdown'):
                    self.engine.shutdown()
            except:
                pass
            del self.engine
            self.engine = None
        
        self._is_loaded = False
        
        # Limpiar CUDA agresivamente
        try:
            import gc
            import torch
            gc.collect()
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                vram = torch.cuda.memory_allocated(0) / 1024**3
                logger.info(f"  VRAM después de descargar TTS: {vram:.2f}GB")
        except Exception as e:
            logger.error(f"Error limpiando CUDA: {e}")
        
        logger.info("Modelo TTS descargado - VRAM liberada")
        return True
    
    @property
    def is_playing(self):
        return self._is_playing
    
    @property
    def is_loaded(self):
        return self._is_loaded


# Instancia global del engine
tts_engine = TTSEngine()


async def handle_client(websocket):
    """Maneja conexiones WebSocket de clientes"""
    client_addr = websocket.remote_address
    logger.info(f"Cliente conectado: {client_addr}")
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                action = data.get('action', '')
                
                if action == 'synthesize':
                    text = data.get('text', '')
                    language = data.get('language', 'es')
                    
                    if not text:
                        await websocket.send(json.dumps({
                            'status': 'error',
                            'message': 'No text provided'
                        }))
                        continue
                    
                    # Notificar que empezamos
                    await websocket.send(json.dumps({
                        'status': 'playing',
                        'text': text
                    }))
                    
                    # Sintetizar (bloqueante, reproduce audio localmente)
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None, 
                        lambda: tts_engine.synthesize(text, language)
                    )
                    
                    # Notificar que terminamos
                    await websocket.send(json.dumps({
                        'status': 'done',
                        'text': text
                    }))
                
                elif action == 'stop':
                    tts_engine.stop()
                    await websocket.send(json.dumps({
                        'status': 'stopped'
                    }))
                
                elif action == 'health':
                    await websocket.send(json.dumps({
                        'status': 'ok',
                        'loaded': tts_engine.is_loaded,
                        'playing': tts_engine.is_playing
                    }))
                
                elif action == 'load':
                    loop = asyncio.get_event_loop()
                    success = await loop.run_in_executor(None, tts_engine.load)
                    await websocket.send(json.dumps({
                        'status': 'loaded' if success else 'error',
                        'loaded': tts_engine.is_loaded
                    }))
                
                elif action == 'unload':
                    # Descargar modelo para liberar VRAM
                    loop = asyncio.get_event_loop()
                    success = await loop.run_in_executor(None, tts_engine.unload)
                    await websocket.send(json.dumps({
                        'status': 'unloaded' if success else 'error',
                        'loaded': tts_engine.is_loaded
                    }))
                
                else:
                    await websocket.send(json.dumps({
                        'status': 'error',
                        'message': f'Unknown action: {action}'
                    }))
                    
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    'status': 'error',
                    'message': 'Invalid JSON'
                }))
            except Exception as e:
                logger.error(f"Error procesando mensaje: {e}")
                await websocket.send(json.dumps({
                    'status': 'error',
                    'message': str(e)
                }))
                
    except Exception as e:
        logger.info(f"Cliente desconectado: {client_addr} ({e})")
    finally:
        logger.info(f"Conexión cerrada: {client_addr}")


async def main():
    """Punto de entrada principal del servidor"""
    import websockets
    
    logger.info("=" * 60)
    logger.info("TTS Microservice - Yui AI Assistant")
    logger.info("=" * 60)
    logger.info(f"Puerto: {TTS_PORT}")
    logger.info(f"Voice samples: {VOICE_SAMPLES_DIR}")
    logger.info(f"Models: {MODELS_DIR}")
    
    # Pre-cargar el modelo
    logger.info("Pre-cargando modelo TTS...")
    if tts_engine.load():
        logger.info("Modelo listo")
    else:
        logger.warning("Modelo no pudo pre-cargarse, se cargará bajo demanda")
    
    logger.info(f"Servidor WebSocket iniciando en ws://localhost:{TTS_PORT}")
    
    async with websockets.serve(handle_client, "localhost", TTS_PORT):
        logger.info("Servidor TTS listo y escuchando")
        await asyncio.Future()  # Correr indefinidamente


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Servidor detenido por usuario")
        tts_engine.shutdown()
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        sys.exit(1)
