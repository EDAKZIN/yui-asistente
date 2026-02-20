"""
Configuracion VRM centralizada.
Lee model-config.json del frontend como fuente unica de verdad
para expresiones, posturas y demas parametros del modelo VRM.
"""

import json
import os
import logging

logger = logging.getLogger('Yui.VRMConfig')


class VRMConfig:
    """Singleton que carga y expone la configuracion de model-config.json"""
    
    _instance = None
    _config = None
    
    # Mapeo adicional para emociones que no estan en el config
    # (emociones del detector que no tienen equivalente directo en VRM)
    EXTRA_EMOTION_MAP = {
        'shy': 'happy',
        'excited': 'happy',
        'confused': 'surprised'
    }
    
    @classmethod
    def get_instance(cls):
        """Retorna la instancia unica de VRMConfig"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def __init__(self):
        self._config_path = os.path.join(
            os.path.dirname(__file__),
            '..', 'desktop-pet', 'model-config.json'
        )
        self.reload()
    
    def reload(self):
        """Recarga la configuracion desde el archivo"""
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            logger.info(f"Configuracion VRM cargada desde {self._config_path}")
        except FileNotFoundError:
            logger.warning(f"model-config.json no encontrado en {self._config_path}, usando defaults")
            self._config = {}
        except json.JSONDecodeError as e:
            logger.error(f"Error parseando model-config.json: {e}")
            self._config = {}
    
    @property
    def expressions(self) -> dict:
        """Mapeo emocion -> expresion VRM desde el config"""
        return self._config.get('expressions', {
            'happy': 'happy',
            'sad': 'sad',
            'angry': 'angry',
            'fear': 'surprised',
            'disgust': 'angry',
            'surprise': 'surprised',
            'neutral': 'neutral'
        })
    
    @property
    def posture_presets(self) -> dict:
        """Presets de postura corporal por emocion"""
        return self._config.get('posturePresets', {})
    
    @property
    def lip_sync(self) -> list:
        """Morfos de lip-sync disponibles"""
        return self._config.get('lipSync', ['aa', 'ih', 'ou', 'ee', 'oh'])
    
    def get_expression(self, emotion: str) -> str:
        """
        Obtiene la expresion VRM para una emocion detectada.
        Busca primero en el config, luego en el mapeo extra,
        y finalmente retorna 'neutral' como fallback.
        """
        # Primero buscar en el config (model-config.json)
        expr = self.expressions.get(emotion)
        if expr:
            return expr
        
        # Luego en el mapeo extra (emociones sin equivalente directo)
        return self.EXTRA_EMOTION_MAP.get(emotion, 'neutral')
