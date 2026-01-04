"""
Yui AI Assistant - Wake Word Detection
Detecta la palabra de activación "Yui" para despertar del modo reposo
Usa openWakeWord (open source, offline, bajo consumo)
"""

import numpy as np
import logging
import threading
import queue
from typing import Callable, Optional
import sounddevice as sd
from pathlib import Path

logger = logging.getLogger('Yui.WakeWord')


class WakeWordDetector:
    """
    Detector de wake word usando openWakeWord
    Ultra bajo consumo para modo reposo
    """
    
    def __init__(self, 
                 wake_word: str = "hey_jarvis",
                 threshold: float = 0.5,
                 sample_rate: int = 16000):
        """
        Inicializa el detector de wake word
        
        Args:
            wake_word: Nombre del modelo de wake word a usar
                       Opciones: "hey_jarvis", "alexa", "hey_mycroft", etc.
                       Para "Yui" necesitaríamos entrenar modelo custom
            threshold: Umbral de activación (0.0-1.0)
            sample_rate: Frecuencia de muestreo (16000 para openWakeWord)
        """
        self.wake_word = wake_word
        self.threshold = threshold
        self.sample_rate = sample_rate
        
        # Estado
        self.model = None
        self.is_running = False
        
        # Threading
        self._stream = None
        self._audio_queue = queue.Queue()
        self._listen_thread = None
        self._stop_event = threading.Event()
        
        # Callback
        self._on_wake_word: Optional[Callable] = None
        
        logger.info(f"WakeWordDetector inicializado (word='{wake_word}', threshold={threshold})")
    
    def load_model(self):
        """Carga el modelo de wake word"""
        if self.model is not None:
            logger.warning("Modelo wake word ya cargado")
            return
        
        logger.info(f"Cargando modelo openWakeWord '{self.wake_word}'...")
        
        try:
            from openwakeword.model import Model
            
            # Cargar modelo preentrenado
            # openWakeWord viene con varios modelos listos
            self.model = Model(
                wakeword_models=[self.wake_word],
                inference_framework="onnx"  # Más eficiente en CPU
            )
            
            logger.info(f"Modelo wake word cargado correctamente")
            logger.info(f"  Modelos activos: {self.model.models.keys()}")
            
        except ImportError:
            logger.error("openWakeWord no instalado. Ejecuta: pip install openwakeword")
            raise
        except Exception as e:
            logger.error(f"Error cargando modelo wake word: {e}")
            # Fallback: usar detección simple por nombre
            logger.warning("Usando fallback: detección por Whisper")
            self.model = None
    
    def unload_model(self):
        """Descarga el modelo para liberar memoria"""
        if self.model is not None:
            del self.model
            self.model = None
            logger.info("Modelo wake word descargado")
    
    def set_callback(self, on_wake_word: Callable):
        """
        Configura callback para cuando se detecta wake word
        
        Args:
            on_wake_word: Función a llamar cuando se detecta "Yui"
        """
        self._on_wake_word = on_wake_word
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Callback del stream de audio"""
        if status:
            logger.warning(f"Audio status: {status}")
        self._audio_queue.put(indata.copy())
    
    def _listen_loop(self):
        """Loop de escucha para wake word"""
        logger.info("Iniciando loop de escucha wake word")
        
        # Buffer para acumular audio
        audio_buffer = np.array([], dtype=np.float32)
        chunk_size = 1280  # openWakeWord espera chunks de 80ms @ 16kHz
        
        while not self._stop_event.is_set():
            try:
                # Obtener audio
                try:
                    audio_chunk = self._audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # Acumular en buffer
                audio_buffer = np.append(audio_buffer, audio_chunk.flatten())
                
                # Procesar cuando tengamos suficiente audio
                while len(audio_buffer) >= chunk_size:
                    # Extraer chunk
                    chunk = audio_buffer[:chunk_size]
                    audio_buffer = audio_buffer[chunk_size:]
                    
                    # Procesar con modelo
                    if self.model is not None:
                        # Convertir a int16 para openWakeWord
                        chunk_int16 = (chunk * 32767).astype(np.int16)
                        
                        # Predecir
                        prediction = self.model.predict(chunk_int16)
                        
                        # Verificar si se detectó wake word
                        for model_name, scores in prediction.items():
                            if len(scores) > 0:
                                score = scores[-1]  # Último score
                                if score >= self.threshold:
                                    logger.info(f"¡Wake word detectado! ({model_name}: {score:.2f})")
                                    
                                    # Llamar callback
                                    if self._on_wake_word:
                                        self._on_wake_word()
                                    
                                    # Resetear modelo para evitar detecciones múltiples
                                    self.model.reset()
                                    audio_buffer = np.array([], dtype=np.float32)
                                    break
                
            except Exception as e:
                logger.error(f"Error en loop wake word: {e}")
        
        logger.info("Loop de escucha wake word terminado")
    
    def start(self, device: Optional[int] = None):
        """
        Inicia la detección de wake word
        
        Args:
            device: ID del dispositivo de audio
        """
        if self.is_running:
            logger.warning("Wake word detector ya está corriendo")
            return
        
        if self.model is None:
            self.load_model()
        
        logger.info("Iniciando detección de wake word...")
        
        # Limpiar estado
        self._stop_event.clear()
        
        # Vaciar cola
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
        
        # Iniciar stream
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            blocksize=1280,
            callback=self._audio_callback,
            device=device
        )
        self._stream.start()
        
        # Iniciar thread
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()
        
        self.is_running = True
        logger.info("Escuchando wake word...")
    
    def stop(self):
        """Detiene la detección"""
        if not self.is_running:
            return
        
        logger.info("Deteniendo detección wake word...")
        
        self._stop_event.set()
        
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        
        if self._listen_thread:
            self._listen_thread.join(timeout=2.0)
            self._listen_thread = None
        
        self.is_running = False
        logger.info("Wake word detector detenido")


class SimpleNameDetector:
    """
    Detector simple de nombre en texto
    Para verificar si 'Yui' aparece en una transcripcion
    """
    
    def __init__(self, name: str = "yui"):
        """
        Args:
            name: Nombre a detectar (ej: "yui", "hey yui")
        """
        self.name = name.lower()
        self.variations = [
            name.lower(),
            f"hey {name.lower()}",
            f"oye {name.lower()}",
            f"hola {name.lower()}",
            f"ey {name.lower()}",
            f"ei {name.lower()}",
            # Variaciones fonéticas que Whisper realmente produce
            "yui", "yuhi", "yuchi", "yuri", "yuki",
            "llui", "lui", "iui", "yuy", "yuui",
            "yoi", "yue", "yuei", "yuwi", "juhi",
            "juyi", "juli", "guyi",
            # Variaciones vistas en logs reales (solo las distintivas)
            "yoy", "huey", "guey", "güey",
            "yope", "yín", "yuey",
            # Con 'despierta' para wake word (frases completas son seguras)
            "yui despierta", "yoy despierta", "yo y despierta",
            "huey despierta", "joy despierta", "hoy despierta",
        ]
    
    def detect_in_text(self, text: str) -> bool:
        """
        Verifica si el texto contiene el nombre
        
        Args:
            text: Texto transcrito
            
        Returns:
            True si contiene el nombre
        """
        import re
        text_lower = text.lower().strip()
        
        for variation in self.variations:
            # Usar word boundaries para evitar falsos positivos
            # Por ejemplo, no detectar 'joy' en 'enjoyed'
            pattern = r'\b' + re.escape(variation) + r'\b'
            if re.search(pattern, text_lower):
                logger.info(f"Nombre detectado: '{variation}' en '{text[:30]}...'")
                return True
        
        return False


class WhisperWakeWordDetector:
    """
    Detector de wake word usando Whisper tiny
    Usa transcripcion continua para detectar 'Yui'
    Mas preciso que openWakeWord para nombres custom
    """
    
    def __init__(self,
                 name: str = "yui",
                 sample_rate: int = 16000,
                 chunk_duration: float = 2.0):
        """
        Inicializa el detector
        
        Args:
            name: Nombre a detectar
            sample_rate: Frecuencia de muestreo
            chunk_duration: Duracion en segundos de cada chunk a transcribir
        """
        self.name = name.lower()
        self.sample_rate = sample_rate
        self.chunk_duration = chunk_duration
        self.chunk_samples = int(sample_rate * chunk_duration)
        
        # Detector de nombre en texto
        self.name_detector = SimpleNameDetector(name)
        
        # Modelo Whisper
        self.model = None
        
        # Estado
        self.is_running = False
        
        # Threading
        self._stream = None
        self._audio_queue = queue.Queue()
        self._listen_thread = None
        self._stop_event = threading.Event()
        
        # Callback
        self._on_wake_word: Optional[Callable] = None
        
        logger.info(f"WhisperWakeWordDetector inicializado (name='{name}', chunk={chunk_duration}s)")
    
    def load_model(self):
        """Carga Whisper base (OpenAI) para deteccion de wake word"""
        if self.model is not None:
            logger.warning("Modelo Whisper wake word ya cargado")
            return
        
        logger.info("Cargando OpenAI Whisper base para wake word...")
        
        try:
            import whisper
            
            # Usar modelo base de OpenAI Whisper (se puede descargar sin crash)
            self.model = whisper.load_model("base", device="cuda")
            logger.info("OpenAI Whisper base cargado para deteccion de wake word")
            
        except Exception as e:
            logger.error(f"Error cargando OpenAI Whisper base: {e}")
            raise
    
    def unload_model(self):
        """Descarga el modelo de forma segura (OpenAI Whisper soporta esto)"""
        if self.model is None:
            logger.debug("Modelo wake word ya está descargado")
            return
        
        logger.info("Descargando modelo OpenAI Whisper wake word...")
        
        try:
            import gc
            import torch
            
            # Mover modelo a CPU antes de eliminar (más seguro)
            if hasattr(self.model, 'to'):
                self.model.to('cpu')
            
            # Eliminar referencia al modelo
            del self.model
            self.model = None
            
            # Forzar garbage collection
            gc.collect()
            
            # Liberar cache CUDA
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("Modelo OpenAI Whisper wake word descargado")
            
        except Exception as e:
            logger.error(f"Error descargando modelo wake word: {e}")
            self.model = None
    
    def set_callback(self, on_wake_word: Callable):
        """Configura callback para wake word detectado"""
        self._on_wake_word = on_wake_word
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Callback del stream de audio"""
        if status:
            logger.warning(f"Audio status: {status}")
        self._audio_queue.put(indata.copy())
    
    def _is_hallucination(self, text: str) -> bool:
        """Detecta alucinaciones comunes de Whisper en silencio"""
        text_lower = text.lower().strip()
        
        # Textos muy cortos
        if len(text_lower) < 3:
            return True
        
        # Detectar caracteres no-latinos (asiáticos, cirílicos, griegos, etc.)
        for char in text:
            code = ord(char)
            # Fuera del rango latín básico + extendido + símbolos españoles
            if code > 591 and char not in 'áéíóúüñ¿¡ÁÉÍÓÚÜÑ':
                return True
        
        # Frases típicas que Whisper alucina durante silencio
        hallucinations = [
            "gracias por ver",
            "suscríbete",
            "suscribete",
            "hasta la próxima",
            "un abrazo",
            "subtítulos",
            "subtitulos",
            "amara.org",
            "transcripción",
            "traducción",
            "el usuario dice yui",
            "asistente virtual",
            "studying",
            "affected",
            "summer",
            "paradiso",
        ]
        
        for hall in hallucinations:
            if hall in text_lower:
                return True
        
        return False
    
    def _listen_loop(self):
        """Loop de escucha con Whisper"""
        logger.info("Iniciando loop de escucha Whisper wake word")
        
        audio_buffer = np.array([], dtype=np.float32)
        
        while not self._stop_event.is_set():
            try:
                # Obtener audio
                try:
                    audio_chunk = self._audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # Acumular en buffer
                audio_buffer = np.append(audio_buffer, audio_chunk.flatten())
                
                # Transcribir cuando tengamos suficiente audio
                if len(audio_buffer) >= self.chunk_samples:
                    # Extraer chunk para transcribir
                    chunk = audio_buffer[:self.chunk_samples]
                    # Mantener overlap del 50% para no perder palabras
                    audio_buffer = audio_buffer[self.chunk_samples // 2:]
                    
                    # Transcribir usando OpenAI Whisper
                    try:
                        import torch
                        # Convertir a tensor y pasar al modelo
                        audio_tensor = torch.from_numpy(chunk).float()
                        result = self.model.transcribe(
                            audio_tensor,
                            language="es",
                            fp16=torch.cuda.is_available()
                        )
                        transcript = result.get("text", "").strip()
                        
                        # Ignorar alucinaciones comunes de Whisper
                        if transcript and not self._is_hallucination(transcript):
                            logger.debug(f"Wake word check: '{transcript[:50]}'")
                            
                            # Verificar si contiene el nombre
                            if self.name_detector.detect_in_text(transcript):
                                logger.info(f"Wake word 'Yui' detectado en: '{transcript}'")
                                
                                # Llamar callback
                                if self._on_wake_word:
                                    self._on_wake_word()
                                
                                # Limpiar buffer
                                audio_buffer = np.array([], dtype=np.float32)
                                
                    except Exception as e:
                        logger.error(f"Error transcribiendo para wake word: {e}")
                
            except Exception as e:
                logger.error(f"Error en loop Whisper wake word: {e}")
        
        logger.info("Loop de escucha Whisper wake word terminado")
    
    def start(self, device: Optional[int] = None):
        """Inicia la deteccion de wake word"""
        if self.is_running:
            logger.warning("Whisper wake word detector ya corriendo")
            return
        
        if self.model is None:
            self.load_model()
        
        logger.info("Iniciando deteccion Whisper wake word...")
        
        # Limpiar estado
        self._stop_event.clear()
        
        # Vaciar cola
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
        
        # Iniciar stream
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            blocksize=1024,
            callback=self._audio_callback,
            device=device
        )
        self._stream.start()
        
        # Iniciar thread
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()
        
        self.is_running = True
        logger.info("Escuchando wake word 'Yui' con Whisper...")
    
    def stop(self):
        """Detiene la deteccion"""
        if not self.is_running:
            return
        
        logger.info("Deteniendo Whisper wake word detector...")
        
        self._stop_event.set()
        
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.warning(f"Error cerrando stream: {e}")
            self._stream = None
        
        # Solo hacer join si no estamos en el listen thread
        import threading
        if self._listen_thread and threading.current_thread() != self._listen_thread:
            self._listen_thread.join(timeout=2.0)
            self._listen_thread = None
        else:
            # Si estamos en el listen thread, marcamos para limpieza posterior
            logger.debug("Stop llamado desde listen thread, omitiendo join")
        
        self.is_running = False
        logger.info("Whisper wake word detector detenido")

