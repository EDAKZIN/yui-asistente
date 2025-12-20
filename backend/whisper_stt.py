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
            
            # Transcribir con initial_prompt para guiar reconocimiento de Yui y EDAKZIN
            # El filtro de alucinaciones abajo rechazará si Whisper repite el prompt en silencio
            result = self.model.transcribe(
                audio_data,
                language=self.language,
                fp16=False,  # Usar fp32 para compatibilidad
                verbose=False,
                initial_prompt="Yui es una asistente virtual creada por EDAKZIN. El usuario habla con Yui."
            )
            
            text = result["text"].strip()
            
            # Filtrar alucinaciones conocidas
            text_lower = text.lower()
            
            # Patrón 1: Frases del prompt alucinadas
            prompt_hallucinations = [
                "yui es una asistente virtual",
                "el usuario habla con yui",
                "creada por edakzin",
                "yui es conocido",
                "yui es un trabajador",
                "esfuerzos difíciles",
                "en el compasión",
                "creador de contenidos",
            ]
            
            for phrase in prompt_hallucinations:
                if phrase in text_lower:
                    logger.warning(f" Alucinación detectada, ignorando: '{text[:50]}...'")
                    return ""
            
            # Patrón 2: Caracteres no latinos (Whisper alucina coreano/chino/japonés)
            import re
            if re.search(r'[\u3000-\u9fff\uac00-\ud7af]', text):
                logger.warning(f" Alucinación (caracteres asiáticos): '{text[:30]}...'")
                return ""
            
            # Patrón 3: Repetición excesiva del mismo texto (signo de alucinación)
            words = text_lower.split()
            if len(words) > 5:
                # Si una palabra se repite más de 3 veces en una oración corta
                word_counts = {}
                for word in words:
                    if len(word) > 3:  # Solo palabras significativas
                        word_counts[word] = word_counts.get(word, 0) + 1
                for word, count in word_counts.items():
                    if count > 3:
                        logger.warning(f" Alucinación (repetición): '{text[:40]}...'")
                        return ""
            
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
