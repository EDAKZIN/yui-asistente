"""
Yui AI Assistant - GUI Backend API
Expone funciones al frontend via WebSocket
"""

import os
import sys
import json
import ctypes
import logging
import threading
from typing import Optional

logger = logging.getLogger('Yui.GUI')


class YuiGUIAPI:
    """
    API que se expone al frontend via WebSocket
    Las funciones son llamadas desde el websocket_server
    """
    
    def __init__(self, yui_assistant=None, continuous_listener=None):
        """
        Args:
            yui_assistant: Instancia de YuiAssistant
            continuous_listener: Instancia de ContinuousListener
        """
        self.yui = yui_assistant
        self.listener = continuous_listener
        
        # Estado local
        self._is_muted = False
        self._mute_key = 'F1'
        self._console_visible = not getattr(sys, 'frozen', False)  # Visible solo en desarrollo
        
        # Cargar mute_key guardada
        try:
            from pathlib import Path
            config_path = Path(__file__).parent.parent / 'config.json'
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            self._mute_key = config.get('gui', {}).get('mute_key', 'F1')
            logger.info(f"Mute key cargada desde config: '{self._mute_key}'")
        except Exception as e:
            logger.warning(f"No se pudo cargar mute_key: {e}")
        
        # Referencia a la ventana (se setea despues)
        self.window = None
        
        # Bot de Discord (modo integrado)
        self._discord_bot = None
        
        logger.info("GUI API inicializada")
    
    def set_window(self, window):
        """Establece la referencia a la ventana (legacy, no usado en Electron)"""
        self.window = window
    
    # ==================== Estado ====================
    
    def get_initial_state(self) -> dict:
        """Retorna el estado inicial para el frontend"""
        logger.info(">>> get_initial_state() llamado desde frontend")
        
        current_state = 'active'
        is_sleeping = False
        if self.listener and hasattr(self.listener, 'state_machine'):
            current_state = self.listener.state_machine.state.value
            from state_machine import YuiState
            is_sleeping = self.listener.state_machine.state == YuiState.SLEEPING
        # Verificar si el modo rendimiento está activo
        is_performance_mode = False
        if self.yui and hasattr(self.yui, 'performance_mode'):
            is_performance_mode = self.yui.performance_mode
        
        result = {
            'state': current_state,
            'is_muted': self._is_muted,
            'is_sleeping': is_sleeping,
            'is_performance_mode': is_performance_mode,
            'mute_key': self._mute_key,
            'vad_threshold': 0.65,
            'proactive_enabled': getattr(self.listener, 'proactive_enabled', True) if self.listener else True,
            # Estados de "Más Opciones"
            'options': {
                'memory_monitoring': getattr(self, '_memory_monitoring_enabled', False),
                'detailed_logs': getattr(self, '_detailed_logs_enabled', False),
                'console_visible': self._console_visible,
                'discord_active': self._discord_bot is not None and self._discord_bot.is_running
            }
        }
        
        logger.info(f">>> Retornando: state='{current_state}', is_muted={self._is_muted}, options={result['options']}")
        return result
    
    def get_state(self) -> dict:
        """Retorna el estado actual"""
        current_state = 'active'
        if self.listener and hasattr(self.listener, 'state_machine'):
            current_state = self.listener.state_machine.state.value
        
        return {
            'state': current_state,
            'is_muted': self._is_muted  # CORREGIDO: era 'muted'
        }
    
    # ==================== Controles ====================
    
    def toggle_mute(self) -> dict:
        """Alterna el estado de mute"""
        self._is_muted = not self._is_muted
        logger.debug(f"toggle_mute llamado, nuevo estado: {self._is_muted}")
        
        if self.listener:
            try:
                # Verificar si estamos en modo reposo
                is_sleeping = False
                if hasattr(self.listener, 'state_machine'):
                    from state_machine import YuiState
                    is_sleeping = self.listener.state_machine.state == YuiState.SLEEPING
                
                if self._is_muted:
                    # Pausar segun el modo actual
                    if is_sleeping:
                        # En reposo, detener wake word detector
                        if hasattr(self.listener, 'wake_detector'):
                            self.listener.wake_detector.stop()
                            logger.debug("Wake detector detenido por mute")
                    else:
                        # En activo, detener VAD
                        if hasattr(self.listener, 'vad'):
                            self.listener.vad.stop()
                            logger.debug("VAD detenido por mute")
                    logger.info("Micrófono muteado desde GUI")
                else:
                    # Reanudar segun el modo actual
                    if is_sleeping:
                        # En reposo, reanudar wake word detector
                        if hasattr(self.listener, 'wake_detector'):
                            self.listener.wake_detector.start()
                            logger.debug("Wake detector iniciado por unmute")
                    else:
                        # En activo, reanudar VAD
                        if hasattr(self.listener, 'vad'):
                            self.listener.vad.start()
                            logger.debug("VAD iniciado por unmute")
                    logger.info("Micrófono desmuteado desde GUI")
            except Exception as e:
                logger.error(f"Error en toggle_mute: {e}")
                import traceback
                logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        return {'is_muted': self._is_muted}
    
    def toggle_sleep(self) -> dict:
        """Alterna modo reposo"""
        logger.debug("toggle_sleep llamado")
        
        if not self.listener or not hasattr(self.listener, 'state_machine'):
            logger.warning("toggle_sleep: No hay listener disponible")
            return {'sleeping': False, 'error': 'No listener available'}
        
        try:
            from state_machine import YuiState
            
            is_sleeping = self.listener.state_machine.state == YuiState.SLEEPING
            logger.debug(f"Estado actual: {'sleeping' if is_sleeping else 'active'}")
            
            if is_sleeping:
                # Despertar
                logger.info("Despertando desde GUI...")
                self.listener.state_machine.transition_to(YuiState.ACTIVE)
            else:
                # Dormir
                logger.info("Entrando en reposo desde GUI...")
                self.listener.state_machine.transition_to(YuiState.SLEEPING)
            
            return {'sleeping': not is_sleeping}
        except Exception as e:
            logger.error(f"Error en toggle_sleep: {e}")
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            return {'sleeping': False, 'error': str(e)}
    
    def toggle_performance(self) -> dict:
        """Alterna modo rendimiento (Groq API vs Llama local)"""
        logger.debug("toggle_performance llamado")
        
        if not self.yui:
            logger.warning("toggle_performance: No hay YuiAssistant disponible")
            return {'is_performance_mode': False, 'error': 'No YuiAssistant available'}
        
        try:
            is_performance = getattr(self.yui, 'performance_mode', False)
            logger.debug(f"Estado actual: {'performance' if is_performance else 'normal'}")
            
            if is_performance:
                # Desactivar modo rendimiento
                logger.info("Desactivando modo rendimiento desde GUI...")
                self.yui.disable_performance_mode()
            else:
                # Activar modo rendimiento
                logger.info("Activando modo rendimiento desde GUI...")
                self.yui.enable_performance_mode()
            
            new_state = getattr(self.yui, 'performance_mode', False)
            return {'is_performance_mode': new_state}
        except Exception as e:
            logger.error(f"Error en toggle_performance: {e}")
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")
            return {'is_performance_mode': False, 'error': str(e)}
    
    # ==================== Configuración ====================
    
    def set_mute_key(self, key: str) -> dict:
        """Cambia la tecla de mute y guarda en config"""
        self._mute_key = key
        logger.info(f"Tecla de mute cambiada a: {key}")
        
        # Guardar en config.json
        try:
            from pathlib import Path
            config_path = Path(__file__).parent.parent / 'config.json'
            
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            
            # Añadir sección gui si no existe
            if 'gui' not in config:
                config['gui'] = {}
            config['gui']['mute_key'] = key
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            
            logger.info(f"Mute key guardada en config.json: {key}")
        except Exception as e:
            logger.error(f"Error guardando mute key: {e}")
        
        return {'mute_key': key}
    
    def set_vad_threshold(self, threshold: float) -> dict:
        """Cambia el umbral de VAD"""
        if self.listener and hasattr(self.listener, 'vad'):
            self.listener.vad.threshold = threshold
            logger.info(f"Umbral VAD cambiado a: {threshold}")
        return {'vad_threshold': threshold}
    
    def set_proactive_enabled(self, enabled: bool) -> dict:
        """Activa/desactiva comentarios proactivos"""
        if self.listener:
            self.listener.proactive_enabled = enabled
            logger.info(f"Comentarios proactivos: {'habilitados' if enabled else 'deshabilitados'}")
        return {'proactive_enabled': enabled}
    
    def cleanup(self):
        """Limpia recursos antes de cerrar/reiniciar"""
        logger.info("Limpiando recursos desde GUI API...")
        if self.listener:
            try:
                self.listener.stop()
            except Exception as e:
                logger.error(f"Error deteniendo listener en cleanup: {e}")
    
    # ==================== Monitoreo y Estadísticas ====================
    
    def set_memory_monitoring(self, enabled: bool) -> dict:
        """Activa/desactiva el monitor periódico de VRAM/RAM"""
        try:
            if self.yui and hasattr(self.yui, '_memory_monitor') and self.yui._memory_monitor:
                if enabled:
                    self.yui._memory_monitor.start_periodic_logging()
                    logger.info("Monitor de memoria ACTIVADO")
                else:
                    self.yui._memory_monitor.stop_periodic_logging()
                    logger.info("Monitor de memoria DESACTIVADO")
                return {'memory_monitoring': enabled}
            else:
                logger.warning("Monitor de memoria no disponible")
                return {'memory_monitoring': False, 'error': 'Monitor no disponible'}
        except Exception as e:
            logger.error(f"Error en set_memory_monitoring: {e}")
            return {'memory_monitoring': False, 'error': str(e)}
    
    def set_detailed_logging(self, enabled: bool) -> dict:
        """Activa/desactiva logs detallados (DEBUG) a archivo"""
        try:
            from logger import YuiLogger
            YuiLogger.set_debug_enabled(enabled)
            return {'detailed_logging': enabled}
        except Exception as e:
            logger.error(f"Error en set_detailed_logging: {e}")
            return {'detailed_logging': False, 'error': str(e)}
    
    def get_session_stats(self) -> dict:
        """Retorna estadísticas de la sesión actual (on-demand, lazy)"""
        import time
        
        stats = {
            'uptime_seconds': 0,
            'conversation_count': 0,
            'vram_mb': None
        }
        
        try:
            # Uptime desde inicio del listener
            if self.listener and hasattr(self.listener, '_start_time'):
                stats['uptime_seconds'] = int(time.time() - self.listener._start_time)
            
            # Contador de conversaciones
            if self.listener and hasattr(self.listener, 'conversation_count'):
                stats['conversation_count'] = self.listener.conversation_count
            
            # VRAM solo si monitor está disponible
            if self.yui and hasattr(self.yui, '_memory_monitor') and self.yui._memory_monitor:
                stats['vram_mb'] = round(self.yui._memory_monitor.get_vram_nvidia(), 0)
        except Exception as e:
            logger.error(f"Error obteniendo stats: {e}")
        
        return stats
    
    def toggle_console(self) -> dict:
        """
        Muestra u oculta la ventana de consola (solo Windows)
        
        Returns:
            dict con estado actual de la consola
        """
        if sys.platform != 'win32':
            return {'visible': True, 'error': 'Solo disponible en Windows'}
        
        try:
            kernel32 = ctypes.WinDLL('kernel32')
            user32 = ctypes.WinDLL('user32')
            
            hwnd = kernel32.GetConsoleWindow()
            if not hwnd:
                return {'visible': False, 'error': 'No hay ventana de consola'}
            
            SW_HIDE = 0
            SW_SHOW = 5
            
            if self._console_visible:
                user32.ShowWindow(hwnd, SW_HIDE)
                self._console_visible = False
                logger.info("Consola oculta")
            else:
                user32.ShowWindow(hwnd, SW_SHOW)
                self._console_visible = True
                logger.info("Consola visible")
            
            return {'visible': self._console_visible}
            
        except Exception as e:
            logger.error(f"Error toggle consola: {e}")
            return {'visible': self._console_visible, 'error': str(e)}
    
    # ==================== Callbacks desde backend ====================
    # Estas funciones son sobreescritas en run_electron.py para usar WebSocket
    
    def notify_state_change(self, new_state: str):
        """Notifica cambio de estado - sobreescrita por run_electron.py"""
        pass
    
    def notify_transcript(self, text: str):
        """Notifica transcript detectado (override en subclase)"""
        pass
    
    def notify_response(self, text: str):
        """Notifica respuesta de Yui (override en subclase)"""
        pass
    
    def notify_tts_start(self, text: str):
        """Notifica inicio de síntesis TTS (override en subclase)"""
        pass
    
    def notify_error(self, message: str):
        """Notifica error (override en subclase)"""
        pass
    
    def notify_expression(self, expression_name: str):
        """Notifica cambio de expresion del modelo (override en subclase)"""
        pass
    
    # ==================== Discord ====================
    
    def toggle_discord_bot(self) -> dict:
        """Inicia o detiene el bot de Discord en modo integrado"""
        if self._discord_bot and self._discord_bot.is_running:
            self._discord_bot.stop()
            self._discord_bot = None
            logger.info("Bot de Discord detenido desde GUI")
            return {'discord_active': False}
        
        try:
            from pathlib import Path
            import sys as _sys
            discord_path = str(Path(__file__).parent.parent / 'integraciones' / 'discord')
            if discord_path not in _sys.path:
                _sys.path.insert(0, discord_path)
            
            from bot import YuiDiscordBot
            
            llm = self.yui.get_current_llm() if self.yui else None
            memory = self.yui.memory if self.yui else None
            
            self._discord_bot = YuiDiscordBot(llm=llm, memory=memory)
            success = self._discord_bot.start_integrated()
            
            if success:
                logger.info("Bot de Discord iniciado desde GUI (modo integrado)")
            
            return {'discord_active': success}
        except ImportError as e:
            logger.error(f"discord.py no instalado: {e}")
            return {'discord_active': False, 'error': 'discord.py no instalado'}
        except Exception as e:
            logger.error(f"Error iniciando bot Discord: {e}")
            return {'discord_active': False, 'error': str(e)}
