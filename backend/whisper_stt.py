"""
Yui AI Assistant - Módulo STT con Whisper
Speech-to-Text usando OpenAI Whisper
"""

import whisper
import numpy as np
import logging
from pathlib import Path
import tempfile
import soundfile as sf

logger = logging.getLogger('Yui.Whisper')

class WhisperSTT:
    """Conversor de voz a texto usando Whisper"""
    
    def __init__(self, model_size: str = "base", language: str = "es", device: str = None):
        """
        Inicializa Whisper
        
        Args:
            model_size: Tamaño del modelo ('tiny', 'base', 'small', 'medium', 'large')
            language: Código de idioma ('es' para español)
            device: Dispositivo de cómputo ('cuda' o 'cpu', None = auto-detectar)
        """
        self.model_size = model_size
        self.language = language
        self.model = None
        self.device = device
        
        logger.info(f"Inicializando Whisper STT (modelo: {model_size}, idioma: {language})")
    
    def load_model(self):
        """Carga el modelo Whisper en memoria"""
        if self.model is not None:
            logger.warning("Modelo Whisper ya está cargado")
            return
        
        try:
            logger.info(f" Cargando modelo Whisper '{self.model_size}'... (puede tardar unos segundos)")
            self.model = whisper.load_model(self.model_size, device=self.device)
            logger.info(" Modelo Whisper cargado correctamente")
            
        except Exception as e:
            logger.error(f" Error al cargar Whisper: {e}")
            raise
    
    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000) -> str:
        """
        Transcribe audio a texto
        
        Args:
            audio_data: Array numpy con datos de audio
            sample_rate: Frecuencia de muestreo del audio
        
        Returns:
            Texto transcrito
        """
        if self.model is None:
            self.load_model()
        
        logger.info(" Procesando audio con Whisper...")
        
        try:
            # Whisper espera audio en float32 normalizado entre -1 y 1
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # Normalizar si es necesario
            if np.abs(audio_data).max() > 1.0:
                audio_data = audio_data / np.abs(audio_data).max()
            
            # Transcribir con initial_prompt para guiar reconocimiento
            result = self.model.transcribe(
                audio_data,
                language=self.language,
                fp16=False,  # Usar fp32 para compatibilidad
                verbose=False,
                initial_prompt="Yui es una asistente virtual creada por EDAKZIN. El usuario habla con Yui."
            )
            
            text = result["text"].strip()
            
            if text:
                logger.info(f" Transcripción: '{text}'")
            else:
                logger.warning(" No se detectó habla en el audio")
            
            return text
            
        except Exception as e:
            logger.error(f" Error al transcribir audio: {e}")
            raise
    
    def transcribe_file(self, audio_path: str) -> str:
        """
        Transcribe un archivo de audio
        
        Args:
            audio_path: Ruta al archivo de audio
        
        Returns:
            Texto transcrito
        """
        if self.model is None:
            self.load_model()
        
        logger.info(f" Transcribiendo archivo: {audio_path}")
        
        try:
            result = self.model.transcribe(
                audio_path,
                language=self.language,
                fp16=False,
                verbose=False
            )
            
            text = result["text"].strip()
            logger.info(f" Transcripción: '{text}'")
            return text
            
        except Exception as e:
            logger.error(f" Error al transcribir archivo: {e}")
            raise
