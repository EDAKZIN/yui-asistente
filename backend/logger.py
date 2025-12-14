"""
Yui AI Assistant - Sistema de Logging
Configuración de logs con colores y rotación de archivos
"""

import logging
import colorlog
from pathlib import Path
from datetime import datetime

class YuiLogger:
    """Gestor de logging para Yui con colores en consola y archivos rotativos"""
    
    _initialized = False
    logger = None
    
    @classmethod
    def setup(cls, log_dir: str, name: str = 'Yui', level=logging.DEBUG):
        """
        Configura el sistema de logging
        
        Args:
            log_dir: Directorio donde guardar los logs
            name: Nombre del logger
            level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        if cls._initialized:
            return cls.logger
        
        # Crear directorio de logs si no existe
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)
        
        # Crear logger principal
        cls.logger = logging.getLogger(name)
        cls.logger.setLevel(level)
        
        # Handler para consola con colores
        console_handler = colorlog.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = colorlog.ColoredFormatter(
            '%(log_color)s%(asctime)s | %(levelname)-8s%(reset)s | %(cyan)s%(name)s%(reset)s | %(message)s',
            datefmt='%H:%M:%S',
            log_colors={
                'DEBUG': 'white',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
        console_handler.setFormatter(console_formatter)
        cls.logger.addHandler(console_handler)
        
        # Handler para archivo - LIMPIO en cada inicio
        log_file_path = log_path / 'yui.log'
        
        # Limpiar log anterior al iniciar nueva sesión
        if log_file_path.exists():
            log_file_path.unlink()  # Eliminar log anterior
        
        file_handler = logging.FileHandler(
            log_file_path,
            mode='w',  # Modo escritura (sobrescribe)
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        cls.logger.addHandler(file_handler)
        
        cls._initialized = True
        cls.logger.info("=" * 60)
        cls.logger.info("Sistema de logging inicializado")
        cls.logger.info(f"Logs guardados en: {log_path}")
        cls.logger.info("=" * 60)
        
        return cls.logger
    
    @classmethod
    def get_logger(cls) -> logging.Logger:
        """Obtiene el logger configurado"""
        if not cls._initialized:
            raise RuntimeError("Logger no inicializado. Llama a YuiLogger.setup() primero")
        return cls.logger
