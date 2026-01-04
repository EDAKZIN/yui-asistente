"""
Yui AI Assistant - Detector de Emociones
Usa transformers con pysentimiento para detectar emociones en español
"""

import logging
from typing import Optional

logger = logging.getLogger('Yui.Emotion')


class EmotionDetector:
    """Detecta emociones en texto usando RoBERTuito (español)"""
    
    # Mapeo de emociones del modelo a categorias simplificadas
    EMOTION_MAP = {
        'joy': 'happy',
        'sadness': 'sad',
        'anger': 'angry',
        'fear': 'fear',
        'surprise': 'surprise',
        'disgust': 'angry',  # Disgust -> angry para simplificar
        'others': 'neutral',
        'neutral': 'neutral'
    }
    
    def __init__(self):
        self.classifier = None
        self._loaded = False
        logger.info("EmotionDetector inicializado (carga lazy)")
    
    def load(self):
        """Carga el modelo de emociones"""
        if self._loaded:
            return
        
        try:
            from transformers import pipeline
            import torch
            
            device = 0 if torch.cuda.is_available() else -1
            logger.info("Cargando modelo de emociones (pysentimiento/robertuito)...")
            
            self.classifier = pipeline(
                "text-classification",
                model="pysentimiento/robertuito-emotion-analysis",
                device=device,
                top_k=1
            )
            
            self._loaded = True
            logger.info("Modelo de emociones cargado correctamente")
            
        except Exception as e:
            logger.error(f"Error cargando modelo de emociones: {e}")
            self.classifier = None
    
    def detect(self, text: str) -> str:
        """
        Detecta la emocion principal del texto
        
        Args:
            text: Texto a analizar (respuesta de Yui)
            
        Returns:
            Emocion simplificada: happy, sad, angry, fear, surprise, neutral
        """
        if not text or len(text.strip()) < 3:
            return 'neutral'
        
        # Cargar modelo si no esta cargado
        if not self._loaded:
            self.load()
        
        if self.classifier is None:
            logger.warning("Clasificador no disponible, retornando neutral")
            return 'neutral'
        
        try:
            # Truncar texto muy largo
            text_truncated = text[:512]
            
            result = self.classifier(text_truncated)
            
            # Extraer emocion del resultado
            if result and len(result) > 0:
                # pipeline con top_k=1 retorna [[{label, score}]]
                emotion_raw = result[0][0]['label'] if isinstance(result[0], list) else result[0]['label']
                emotion = self.EMOTION_MAP.get(emotion_raw.lower(), 'neutral')
                
                logger.debug(f"Emocion detectada: {emotion_raw} -> {emotion}")
                return emotion
            
            return 'neutral'
            
        except Exception as e:
            logger.error(f"Error detectando emocion: {e}")
            return 'neutral'
    
    def unload(self):
        """Descarga el modelo para liberar memoria"""
        if self.classifier is not None:
            del self.classifier
            self.classifier = None
            self._loaded = False
            
            import torch
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info("Modelo de emociones descargado")
