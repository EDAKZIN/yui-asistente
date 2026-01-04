"""
Yui AI Assistant - Máquina de Estados
Controla los modos de operación: Activo, Escuchando, Procesando, Reposo
"""

from enum import Enum
from typing import Callable, Optional
import logging
import time
import random

logger = logging.getLogger('Yui.StateMachine')


class YuiState(Enum):
    """Estados posibles de Yui"""
    LOADING = "loading"        # Cargando modelos
    ACTIVE = "active"          # Escuchando activamente, esperando voz
    LISTENING = "listening"    # VAD detectó voz, grabando
    PROCESSING = "processing"  # Procesando respuesta
    PROACTIVE = "proactive"    # Haciendo comentario proactivo
    SLEEPING = "sleeping"      # Modo reposo (bajo recursos)


# NOTA: Comentarios proactivos ahora se generan dinámicamente con LLM en continuous_listener.py

# Frases para entrar en reposo
SLEEP_TRIGGERS = [
    "descansa", "descanso", "no te necesito", "duerme", "reposo",
    "estoy ocupado", "estoy ocupada", "déjame solo", "déjame sola",
    "silencio", "cállate", "no hables", "modo reposo", "modo de descanso",
    "vuelve luego", "hasta luego", "nos vemos", "a dormir", "vete a dormir"
]

# Frases para despertar
WAKE_PHRASES = [
    "Estoy de vuelta, ¿en qué puedo ayudarte?",
    "¡Aquí estoy! ¿Qué necesitas?",
    "Desperté, ¿qué pasa?",
    "Ya estoy lista, dime.",
]

# Frases al entrar en reposo
SLEEP_RESPONSES = [
    "Está bien, estaré aquí cuando me necesites. Solo di 'Yui'.",
    "Entendido, entraré en reposo. Llámame cuando quieras.",
    "De acuerdo, descansaré. Di 'Yui' para despertarme.",
    "Ok, me voy a dormir. Solo di mi nombre si me necesitas.",
]


class YuiStateMachine:
    """Máquina de estados para controlar el comportamiento de Yui"""
    
    def __init__(self, inactivity_timeout: float = 120.0):
        """
        Inicializa la máquina de estados
        
        Args:
            inactivity_timeout: Segundos de inactividad antes de comentario proactivo
        """
        self.state = YuiState.LOADING
        self.previous_state = None
        self.inactivity_timeout = inactivity_timeout
        self.last_activity_time = time.time()
        self.proactive_comment_count = 0
        self.max_proactive_comments = 3  # Máximo antes de callarse
        
        # Callbacks
        self._on_state_change: Optional[Callable] = None
        self._on_sleep: Optional[Callable] = None
        self._on_wake: Optional[Callable] = None
        
        logger.info(f"StateMachine inicializada (timeout: {inactivity_timeout}s)")
    
    def set_callbacks(self, 
                      on_state_change: Callable = None,
                      on_sleep: Callable = None,
                      on_wake: Callable = None):
        """Configura los callbacks para eventos de estado"""
        self._on_state_change = on_state_change
        self._on_sleep = on_sleep
        self._on_wake = on_wake
    
    def transition_to(self, new_state: YuiState):
        """
        Realiza transición a nuevo estado
        
        Args:
            new_state: Estado destino
        """
        if new_state == self.state:
            return
        
        self.previous_state = self.state
        old_state = self.state
        self.state = new_state
        
        logger.info(f"Estado: {old_state.value} → {new_state.value}")
        
        # Resetear contador de inactividad en transiciones relevantes
        if new_state in [YuiState.LISTENING, YuiState.PROCESSING]:
            self.reset_activity()
        
        # Callbacks específicos
        if new_state == YuiState.SLEEPING and self._on_sleep:
            self._on_sleep()
        elif old_state == YuiState.SLEEPING and self._on_wake:
            self._on_wake()
        
        # Callback general
        if self._on_state_change:
            self._on_state_change(old_state, new_state)
    
    def reset_activity(self):
        """Resetea el timer de inactividad"""
        self.last_activity_time = time.time()
        self.proactive_comment_count = 0
    
    def get_inactivity_duration(self) -> float:
        """Retorna segundos desde última actividad"""
        return time.time() - self.last_activity_time
    
    def should_make_proactive_comment(self) -> bool:
        """Verifica si debe hacer un comentario proactivo"""
        if self.state != YuiState.ACTIVE:
            return False
        
        if self.proactive_comment_count >= self.max_proactive_comments:
            return False
        
        return self.get_inactivity_duration() >= self.inactivity_timeout
    
    # NOTA: get_proactive_comment() eliminado - ahora se genera dinámicamente con LLM en continuous_listener.py
    
    def check_sleep_trigger(self, text: str) -> bool:
        """
        Verifica si el texto contiene una frase para entrar en reposo
        
        Args:
            text: Texto transcrito del usuario
            
        Returns:
            True si debe entrar en reposo
        """
        text_lower = text.lower().strip()
        
        for trigger in SLEEP_TRIGGERS:
            if trigger in text_lower:
                logger.info(f"Sleep trigger detectado: '{trigger}' en '{text[:30]}...'")
                return True
        
        return False
    
    def get_sleep_response(self) -> str:
        """Obtiene una frase de despedida para entrar en reposo"""
        return random.choice(SLEEP_RESPONSES)
    
    def get_wake_response(self) -> str:
        """Obtiene una frase de bienvenida al despertar"""
        return random.choice(WAKE_PHRASES)
    
    @property
    def is_active(self) -> bool:
        """Verifica si está en modo activo (no en reposo)"""
        return self.state != YuiState.SLEEPING
    
    @property
    def is_sleeping(self) -> bool:
        """Verifica si está en modo reposo"""
        return self.state == YuiState.SLEEPING
    
    @property
    def is_processing(self) -> bool:
        """Verifica si está procesando una respuesta"""
        return self.state == YuiState.PROCESSING
