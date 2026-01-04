"""
Yui AI Assistant - Módulo STT con faster-whisper
Speech-to-Text usando faster-whisper (CTranslate2, optimizado para menos VRAM)
"""

from faster_whisper import WhisperModel
import numpy as np
import logging
import re

logger = logging.getLogger('Yui.Whisper')


class WhisperSTT:
    """Conversor de voz a texto usando faster-whisper (optimizado)"""
    
    def __init__(self, model_size: str = "medium", language: str = "es", device: str = "cuda"):
        """
        Inicializa faster-whisper
        
        Args:
            model_size: Tamaño del modelo ('tiny', 'base', 'small', 'medium', 'large-v2')
            language: Código de idioma ('es' para español)
            device: Dispositivo ('cuda' o 'cpu')
        """
        self.model_size = model_size
        self.language = language
        self.device = device
        self.model = None
        
        # Usar INT8 para menor VRAM (misma precision, ~50% menos memoria)
        self.compute_type = "int8" if device == "cuda" else "int8"
        
        logger.info(f"Inicializando faster-whisper STT (modelo: {model_size}, idioma: {language})")
        logger.info(f"  Compute type: {self.compute_type} (optimizado para menor VRAM)")
    
    def load_model(self):
        """Carga el modelo faster-whisper en memoria"""
        if self.model is not None:
            logger.warning("Modelo Whisper ya está cargado")
            return
        
        try:
            logger.info(f" Cargando modelo faster-whisper '{self.model_size}'... (puede tardar unos segundos)")
            
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
            
            logger.info(" Modelo faster-whisper cargado correctamente")
            logger.info(f"  Dispositivo: {self.device.upper()}")
            logger.info(f"  Cuantizacion: {self.compute_type}")
            
        except Exception as e:
            logger.error(f" Error al cargar faster-whisper: {e}")
            raise
    
    def unload_model(self):
        """Descarga el modelo de VRAM para liberar memoria"""
        if self.model is not None:
            import gc
            import torch
            
            del self.model
            self.model = None
            
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info(" Modelo Whisper descargado de VRAM")
    
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
        
        logger.info(" Procesando audio con faster-whisper...")
        
        try:
            # Faster-whisper espera audio en float32 normalizado entre -1 y 1
            if audio_data.dtype != np.float32:
                audio_data = audio_data.astype(np.float32)
            
            # Normalizar si es necesario
            if np.abs(audio_data).max() > 1.0:
                audio_data = audio_data / np.abs(audio_data).max()
            
            # Transcribir con parámetros anti-alucinación
            segments, info = self.model.transcribe(
                audio_data,
                language=self.language,
                initial_prompt="Vocabulario: Yui, EDAKZIN.",
                
                # Filtrar silencios (el modelo alucina en silencio)
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500),
                
                # Romper la cadena - evita que errores se repitan en bucle
                condition_on_previous_text=False,
                
                # Más estricto con repeticiones (default 2.4)
                compression_ratio_threshold=2.0,
                
                # Más estricto con confianza (default -1.0)
                log_prob_threshold=-0.5,
                
                # Temperatura fría para menos creatividad
                temperature=0.0
            )
            
            # Unir todos los segmentos
            text = " ".join([segment.text.strip() for segment in segments]).strip()
            
            # Filtrar alucinaciones conocidas
            text = self._filter_hallucinations(text)
            
            if text:
                logger.info(f" Transcripción: '{text}'")
            else:
                logger.warning(" No se detectó habla en el audio")
            
            return text
            
        except Exception as e:
            logger.error(f" Error al transcribir audio: {e}")
            raise
    
    def _filter_hallucinations(self, text: str) -> str:
        """Filtra alucinaciones comunes de Whisper"""
        if not text:
            return ""
        
        text_lower = text.lower()
        
        # Patrón 1: Frases del prompt alucinadas
        prompt_hallucinations = [
            "yui es una asistente virtual",
            "el usuario habla con yui",
            "el usuario habla con edakzin",  # Nueva alucinación detectada
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
        if re.search(r'[\u3000-\u9fff\uac00-\ud7af]', text):
            logger.warning(f" Alucinación (caracteres asiáticos): '{text[:30]}...'")
            return ""
        
        # Patrón 3: Repetición excesiva del mismo texto
        words = text_lower.split()
        if len(words) > 5:
            word_counts = {}
            for word in words:
                if len(word) > 3:
                    word_counts[word] = word_counts.get(word, 0) + 1
            for word, count in word_counts.items():
                if count > 3:
                    logger.warning(f" Alucinación (repetición): '{text[:40]}...'")
                    return ""
        
        return text
    
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
            segments, info = self.model.transcribe(
                audio_path,
                language=self.language,
                vad_filter=True
            )
            
            text = " ".join([segment.text.strip() for segment in segments]).strip()
            logger.info(f" Transcripción: '{text}'")
            return text
            
        except Exception as e:
            logger.error(f" Error al transcribir archivo: {e}")
            raise
