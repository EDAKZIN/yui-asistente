"""
Yui AI Assistant - Módulo de Audio
Manejo de grabación y reproducción de audio
"""

import sounddevice as sd
import soundfile as sf
import numpy as np
from pathlib import Path
import tempfile
from typing import Optional
import logging

logger = logging.getLogger('Yui.Audio')

class AudioManager:
    """Gestor de entrada y salida de audio"""
    
    def __init__(self, sample_rate: int = 16000, channels: int = 1):
        """
        Inicializa el gestor de audio
        
        Args:
            sample_rate: Frecuencia de muestreo en Hz (16kHz por defecto para Whisper)
            channels: Número de canales (1=mono, 2=estéreo)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.recording = None
        
        logger.info(f"AudioManager inicializado: {sample_rate}Hz, {channels} canal(es)")
    
    def record(self, duration: float = 5.0, device: Optional[int] = None) -> np.ndarray:
        """
        Graba audio del micrófono
        
        Args:
            duration: Duración de la grabación en segundos
            device: ID del dispositivo de entrada (None = dispositivo por defecto)
        
        Returns:
            Array numpy con los datos de audio
        """
        logger.info(f" Grabando audio durante {duration} segundos...")
        
        try:
            # Grabar audio
            recording = sd.rec(
                int(duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='float32',
                device=device
            )
            sd.wait()  # Esperar a que termine la grabación
            
            self.recording = recording.flatten()  # Convertir a 1D si es necesario
            logger.info(f" Grabación completada: {len(self.recording)} samples")
            
            return self.recording
            
        except Exception as e:
            logger.error(f" Error al grabar audio: {e}")
            raise
    
    def record_until_enter(self, device: Optional[int] = None) -> np.ndarray:
        """
        Graba audio hasta que el usuario presione Enter
        
        Args:
            device: ID del dispositivo de entrada
        
        Returns:
            Array numpy con los datos de audio
        """
        print("\n GRABANDO... Presiona Enter cuando termines de hablar.")
        logger.info("Iniciando grabación con detención manual")
        
        try:
            # Iniciar grabación continua
            recordings = []
            
            def callback(indata, frames, time, status):
                """Callback que captura audio continuamente"""
                if status:
                    logger.warning(f"Estado de audio: {status}")
                recordings.append(indata.copy())
            
            # Abrir stream de audio
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='float32',
                callback=callback,
                device=device
            ):
                input()  # Esperar a que el usuario presione Enter
            
            # Concatenar todas las grabaciones
            if recordings:
                self.recording = np.concatenate(recordings, axis=0).flatten()
                logger.info(f" Grabación completada: {len(self.recording)} samples ({len(self.recording)/self.sample_rate:.2f}s)")
                return self.recording
            else:
                logger.warning("No se grabó audio")
                return np.array([], dtype='float32')
                
        except KeyboardInterrupt:
            logger.info("Grabación cancelada por el usuario")
            return np.array([], dtype='float32')
        except Exception as e:
            logger.error(f" Error al grabar audio: {e}")
            raise
    
    def play(self, audio_data: np.ndarray, sample_rate: Optional[int] = None):
        """
        Reproduce audio
        
        Args:
            audio_data: Array numpy con los datos de audio
            sample_rate: Frecuencia de muestreo (usa self.sample_rate si es None)
        """
        if sample_rate is None:
            sample_rate = self.sample_rate
        
        logger.info(f" Reproduciendo audio: {len(audio_data)} samples a {sample_rate}Hz")
        
        try:
            sd.play(audio_data, sample_rate)
            sd.wait()  # Esperar a que termine la reproducción
            logger.info(" Reproducción completada")
            
        except Exception as e:
            logger.error(f" Error al reproducir audio: {e}")
            raise
    
    def save_wav(self, audio_data: np.ndarray, filepath: str, sample_rate: Optional[int] = None):
        """
        Guarda audio en archivo WAV
        
        Args:
            audio_data: Array numpy con los datos de audio
            filepath: Ruta donde guardar el archivo
            sample_rate: Frecuencia de muestreo
        """
        if sample_rate is None:
            sample_rate = self.sample_rate
        
        logger.info(f" Guardando audio en: {filepath}")
        
        try:
            sf.write(filepath, audio_data, sample_rate)
            logger.info(" Audio guardado correctamente")
            
        except Exception as e:
            logger.error(f" Error al guardar audio: {e}")
            raise
    
    def load_wav(self, filepath: str) -> tuple[np.ndarray, int]:
        """
        Carga audio desde archivo WAV
        
        Args:
            filepath: Ruta del archivo a cargar
        
        Returns:
            Tupla (audio_data, sample_rate)
        """
        logger.info(f" Cargando audio desde: {filepath}")
        
        try:
            audio_data, sample_rate = sf.read(filepath)
            logger.info(f" Audio cargado: {len(audio_data)} samples a {sample_rate}Hz")
            return audio_data, sample_rate
            
        except Exception as e:
            logger.error(f" Error al cargar audio: {e}")
            raise
    
    def get_temp_wav_path(self) -> str:
        """
        Crea un archivo temporal WAV
        
        Returns:
            Ruta al archivo temporal
        """
        temp_file = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
        return temp_file.name
    
    @staticmethod
    def list_devices():
        """Lista todos los dispositivos de audio disponibles"""
        print("\n" + "="*60)
        print("DISPOSITIVOS DE AUDIO DISPONIBLES")
        print("="*60)
        print(sd.query_devices())
        print("="*60 + "\n")
