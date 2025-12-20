"""
Yui AI Assistant - VAD Listener (Voice Activity Detection)
Detecta automáticamente cuando el usuario empieza/termina de hablar
Usa Silero VAD para detección precisa con soporte GPU
"""

import numpy as np
import torch
import logging
import threading
import queue
from typing import Callable, Optional
import sounddevice as sd

logger = logging.getLogger('Yui.VAD')


class VADListener:
    """
    Detector de actividad de voz usando Silero VAD
    Escucha continuamente y dispara callbacks al detectar voz
    """
    
    def __init__(self, 
                 sample_rate: int = 16000,
                 threshold: float = 0.5,
                 min_speech_duration: float = 0.3,
                 min_silence_duration: float = 0.8,
                 speech_pad_ms: int = 300):
        """
        Inicializa el detector de voz
        
        Args:
            sample_rate: Frecuencia de muestreo (16000 requerido para Silero)
            threshold: Umbral de detección (0.0-1.0, más alto = más estricto)
            min_speech_duration: Duración mínima de habla para considerar válida
            min_silence_duration: Duración de silencio para considerar fin de habla
            speech_pad_ms: Padding en ms antes/después del habla
        """
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.min_speech_duration = min_speech_duration
        self.min_silence_duration = min_silence_duration
        self.speech_pad_ms = speech_pad_ms
        
        # Estado
        self.model = None
        self.is_running = False
        self.is_speaking = False
        self.speech_start_time = None
        self.silence_start_time = None
        
        # Threading
        self._stream = None
        self._audio_queue = queue.Queue()
        self._listen_thread = None
        self._stop_event = threading.Event()
        
        # Callbacks
        self._on_speech_start: Optional[Callable] = None
        self._on_speech_end: Optional[Callable[[np.ndarray], None]] = None
        
        # Buffer de audio del habla actual
        self._speech_buffer = []
        
        logger.info(f"VADListener inicializado (threshold={threshold}, sample_rate={sample_rate}Hz)")
    
    def load_model(self):
        """Carga el modelo Silero VAD"""
        if self.model is not None:
            logger.warning("Modelo VAD ya cargado")
            return
        
        logger.info("Cargando modelo Silero VAD...")
        
        try:
            # Cargar modelo desde torch hub
            self.model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                onnx=False
            )
            
            # Usar GPU si está disponible
            if torch.cuda.is_available():
                self.model = self.model.cuda()
                logger.info("  VAD usando GPU (CUDA)")
            else:
                logger.info("  VAD usando CPU")
            
            logger.info("Modelo Silero VAD cargado correctamente")
            
        except Exception as e:
            logger.error(f"Error cargando Silero VAD: {e}")
            raise
    
    def unload_model(self):
        """Descarga el modelo para liberar memoria"""
        if self.model is not None:
            del self.model
            self.model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("Modelo VAD descargado")
    
    def set_callbacks(self,
                      on_speech_start: Callable = None,
                      on_speech_end: Callable[[np.ndarray], None] = None):
        """
        Configura callbacks para eventos de voz
        
        Args:
            on_speech_start: Se llama cuando inicia el habla
            on_speech_end: Se llama cuando termina el habla (recibe audio grabado)
        """
        self._on_speech_start = on_speech_start
        self._on_speech_end = on_speech_end
    
    def _audio_callback(self, indata, frames, time_info, status):
        """Callback del stream de audio"""
        if status:
            logger.warning(f"Audio status: {status}")
        # Copiar datos a la cola
        self._audio_queue.put(indata.copy())
    
    def _process_audio(self, audio_chunk: np.ndarray) -> float:
        """
        Procesa un chunk de audio y retorna probabilidad de voz
        
        Args:
            audio_chunk: Array de audio
            
        Returns:
            Probabilidad de voz (0.0-1.0)
        """
        if self.model is None:
            return 0.0
        
        try:
            # Convertir a tensor
            audio_tensor = torch.from_numpy(audio_chunk).float()
            
            # Mover a GPU si corresponde
            if next(self.model.parameters()).is_cuda:
                audio_tensor = audio_tensor.cuda()
            
            # Obtener probabilidad de voz
            with torch.no_grad():
                speech_prob = self.model(audio_tensor, self.sample_rate).item()
            
            return speech_prob
            
        except Exception as e:
            logger.error(f"Error procesando audio: {e}")
            return 0.0
    
    def _listen_loop(self):
        """Loop principal de escucha (corre en thread separado)"""
        import time
        
        logger.info("Iniciando loop de escucha VAD")
        
        # Tamaño del chunk: 512 samples = 32ms @ 16kHz
        chunk_size = 512
        
        while not self._stop_event.is_set():
            try:
                # Obtener audio de la cola (timeout para poder verificar stop_event)
                try:
                    audio_chunk = self._audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue
                
                # Flatten y procesar
                audio_flat = audio_chunk.flatten()
                
                # Agregar al buffer si estamos grabando
                if self.is_speaking:
                    self._speech_buffer.append(audio_flat)
                
                # Obtener probabilidad de voz
                speech_prob = self._process_audio(audio_flat)
                
                # Lógica de detección
                if speech_prob >= self.threshold:
                    # Voz detectada
                    if not self.is_speaking:
                        # Inicio de habla
                        self.is_speaking = True
                        self.speech_start_time = time.time()
                        self.silence_start_time = None
                        self._speech_buffer = [audio_flat]
                        
                        logger.debug(f"Voz detectada (prob={speech_prob:.2f})")
                        
                        if self._on_speech_start:
                            self._on_speech_start()
                    else:
                        # Continúa hablando
                        self.silence_start_time = None
                else:
                    # Silencio detectado
                    if self.is_speaking:
                        if self.silence_start_time is None:
                            self.silence_start_time = time.time()
                        
                        # Verificar si el silencio es suficientemente largo
                        silence_duration = time.time() - self.silence_start_time
                        
                        if silence_duration >= self.min_silence_duration:
                            # Fin de habla
                            speech_duration = time.time() - self.speech_start_time - silence_duration
                            
                            if speech_duration >= self.min_speech_duration:
                                # Habla válida
                                logger.debug(f"Fin de habla (duración={speech_duration:.2f}s)")
                                
                                # Compilar audio
                                if self._speech_buffer:
                                    full_audio = np.concatenate(self._speech_buffer)
                                    
                                    if self._on_speech_end:
                                        self._on_speech_end(full_audio)
                            else:
                                logger.debug(f"Habla muy corta ignorada ({speech_duration:.2f}s)")
                            
                            # Resetear estado
                            self.is_speaking = False
                            self.speech_start_time = None
                            self.silence_start_time = None
                            self._speech_buffer = []
                
            except Exception as e:
                logger.error(f"Error en loop VAD: {e}")
        
        logger.info("Loop de escucha VAD terminado")
    
    def start(self, device: Optional[int] = None):
        """
        Inicia la escucha continua
        
        Args:
            device: ID del dispositivo de audio (None = default)
        """
        if self.is_running:
            logger.warning("VAD ya está corriendo")
            return
        
        if self.model is None:
            self.load_model()
        
        logger.info("Iniciando escucha continua VAD...")
        
        # Limpiar estado
        self._stop_event.clear()
        self.is_speaking = False
        self._speech_buffer = []
        
        # Vaciar cola
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break
        
        # Iniciar stream de audio
        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=1,
            dtype='float32',
            blocksize=512,
            callback=self._audio_callback,
            device=device
        )
        self._stream.start()
        
        # Iniciar thread de procesamiento
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()
        
        self.is_running = True
        logger.info("VAD escuchando activamente")
    
    def stop(self):
        """Detiene la escucha"""
        if not self.is_running:
            return
        
        logger.info("Deteniendo escucha VAD...")
        
        # Señalar stop
        self._stop_event.set()
        
        # Detener stream
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        
        # Esperar thread
        if self._listen_thread:
            self._listen_thread.join(timeout=2.0)
            self._listen_thread = None
        
        self.is_running = False
        logger.info("VAD detenido")
    
    def pause(self):
        """Pausa temporalmente la detección (sin cerrar stream)"""
        self._stop_event.set()
        logger.debug("VAD pausado")
    
    def resume(self):
        """Resume la detección después de una pausa"""
        if not self.is_running:
            return
        
        self._stop_event.clear()
        
        # Reiniciar thread si no está corriendo
        if self._listen_thread is None or not self._listen_thread.is_alive():
            self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._listen_thread.start()
        
        logger.debug("VAD resumido")
