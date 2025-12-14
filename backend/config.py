"""
Yui AI Assistant - Gestor de Configuración
Carga y proporciona acceso a la configuración desde config.json
"""

import json
from pathlib import Path
from typing import Any, Dict

class Config:
    """Gestor de configuración centralizado"""
    
    _config: Dict = None
    _config_path: str = None
    
    @classmethod
    def load(cls, config_path: str = None) -> Dict:
        """
        Carga la configuración desde archivo JSON
        
        Args:
            config_path: Ruta al archivo de configuración. Si es None, busca config.json en la raíz del proyecto
        
        Returns:
            Diccionario con la configuración completa
        """
        if config_path is None:
            # Buscar config.json en la raíz del proyecto (un nivel arriba de backend/)
            config_path = Path(__file__).parent.parent / "config.json"
        
        cls._config_path = str(config_path)
        
        with open(config_path, 'r', encoding='utf-8') as f:
            cls._config = json.load(f)
        
        return cls._config
    
    @classmethod
    def get(cls, key_path: str, default: Any = None) -> Any:
        """
        Obtiene un valor de configuración usando notación de punto
        
        Args:
            key_path: Ruta al valor usando punto como separador (ej: 'models.whisper.model_size')
            default: Valor por defecto si no se encuentra la clave
        
        Returns:
            Valor de configuración o default si no existe
        
        Ejemplo:
            >>> Config.get('models.whisper.language')
            'es'
        """
        if cls._config is None:
            cls.load()
        
        keys = key_path.split('.')
        value = cls._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    @classmethod
    def reload(cls):
        """Recarga la configuración desde el archivo"""
        if cls._config_path:
            cls.load(cls._config_path)
