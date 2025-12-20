"""
Yui AI Assistant - GUI Backend API
Expone funciones al frontend via pywebview
"""

import os
import json
import logging
import threading
from typing import Optional

logger = logging.getLogger('Yui.GUI')


class YuiGUIAPI:
    """
    API que se expone al frontend JavaScript via pywebview
    Todas las funciones aquí son llamables desde JS: window.pywebview.api.<function>()
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
        """Establece la referencia a la ventana pywebview"""
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
                if self._is_muted:
                    # Pausar VAD
                    if hasattr(self.listener, 'vad'):
                        self.listener.vad.stop()
                        logger.debug("VAD detenido por mute")
                    logger.info("Micrófono muteado desde GUI")
                else:
                    # Reanudar VAD
                    if hasattr(self.listener, 'vad'):
                        self.listener.vad.start()
                        logger.debug("VAD iniciado por unmute")
                    logger.info("Micrófono desmuteado desde GUI")
            except Exception as e:
                logger.error(f"Error en toggle_mute: {e}")
                import traceback
                logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        return {'muted': self._is_muted}
    
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
    
    def notify_state_change(self, new_state: str):
        """Notifica al frontend un cambio de estado"""
        if self.window:
            self.window.evaluate_js(f"window.yuiCallbacks.onStateChange('{new_state}')")
    
    def notify_transcript(self, text: str):
        """Notifica al frontend una nueva transcripción"""
        if self.window:
            # Escapar comillas para JS
            safe_text = text.replace("'", "\\'").replace('"', '\\"')
            self.window.evaluate_js(f"window.yuiCallbacks.onTranscript('{safe_text}')")
    
    def notify_response(self, text: str):
        """Notifica al frontend una respuesta de Yui"""
        if self.window:
            safe_text = text.replace("'", "\\'").replace('"', '\\"')
            self.window.evaluate_js(f"window.yuiCallbacks.onResponse('{safe_text}')")
    
    def notify_error(self, message: str):
        """Notifica al frontend un error"""
        if self.window:
            safe_msg = message.replace("'", "\\'").replace('"', '\\"')
            self.window.evaluate_js(f"window.yuiCallbacks.onError('{safe_msg}')")
