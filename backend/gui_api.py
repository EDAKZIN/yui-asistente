"""
Yui AI Assistant - GUI Backend API
Expone funciones al frontend via WebSocket
"""

import os
import json
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
        
        # Referencia a la ventana (se setea después)
        self.window = None
        
        logger.info("GUI API inicializada")
    
    def set_window(self, window):
        """Establece la referencia a la ventana (legacy, no usado en Electron)"""
        self.window = window
    
    # ==================== Estado ====================
    
    def get_initial_state(self) -> dict:
        """Retorna el estado inicial para el frontend"""
        logger.info(">>> get_initial_state() llamado desde frontend")
        
        current_state = 'active'
        if self.listener and hasattr(self.listener, 'state_machine'):
            current_state = self.listener.state_machine.state.value
        
        result = {
            'state': current_state,
            'muted': self._is_muted,
            'mute_key': self._mute_key,
            'vad_threshold': 0.65,
            'proactive_enabled': True
        }
        
        logger.info(f">>> Retornando: mute_key='{self._mute_key}', state='{current_state}'")
        return result
    
    def get_state(self) -> dict:
        """Retorna el estado actual"""
        current_state = 'active'
        if self.listener and hasattr(self.listener, 'state_machine'):
            current_state = self.listener.state_machine.state.value
        
        return {
            'state': current_state,
            'muted': self._is_muted
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
    
    # ==================== Callbacks desde backend ====================
    # Estas funciones son sobreescritas en run_electron.py para usar WebSocket
    
    def notify_state_change(self, new_state: str):
        """Notifica cambio de estado - sobreescrita por run_electron.py"""
        pass
    
    def notify_transcript(self, text: str):
        """Notifica nueva transcripcion - sobreescrita por run_electron.py"""
        pass
    
    def notify_response(self, text: str):
        """Notifica respuesta de Yui - sobreescrita por run_electron.py"""
        pass
    
    def notify_error(self, message: str):
        """Notifica error - sobreescrita por run_electron.py"""
        pass
