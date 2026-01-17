"""
Yui AI Assistant - Sistema de Eventos Especiales
Maneja eventos programados para fechas especificas (Navidad, cumpleanos, etc.)
"""

import logging
import threading
from datetime import datetime, time
from typing import Callable, Optional, List, Dict

logger = logging.getLogger('Yui.Events')


# ============================================================
# CONFIGURACION DE EVENTOS ESPECIALES
# Agregar o modificar eventos aqui es muy facil:
# Formato: (mes, dia, prompt_hint para generar mensaje)
# ============================================================

SPECIAL_EVENTS: List[Dict] = [
    {
        "month": 12,
        "day": 25,
        "event_type": "navidad",
        "prompt_hint": "Es Navidad (25 de diciembre). Felicita a EDAKZIN de forma calida y personal.",
        "expression": "happy"
    },
    {
        "month": 1,
        "day": 20,
        "event_type": "cumpleanos_creador",
        "prompt_hint": "Hoy es el cumpleanos de EDAKZIN (tu creador). Felicitalo con cariño y agradecimiento por haberte creado.",
        "expression": "happy"
    },
    {
        "month": 1,
        "day": 1,
        "event_type": "ano_nuevo",
        "prompt_hint": "Es Año Nuevo (1 de enero). Desea un feliz año nuevo a EDAKZIN con buenos deseos.",
        "expression": "happy"
    },
]

# ============================================================


class SpecialEventsSystem:
    """
    Sistema de eventos especiales programados
    Se ejecutan a las 12:00 AM de cada fecha configurada
    """
    
    def __init__(self, on_event_triggered: Optional[Callable[[str, str, str], None]] = None):
        """
        Args:
            on_event_triggered: Callback cuando se dispara un evento
                               Recibe (event_type, prompt_hint, expresion)
        """
        self.on_event_triggered = on_event_triggered
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_triggered_date: Optional[str] = None  # Evitar duplicados
        
        logger.info(f"Sistema de eventos especiales inicializado ({len(SPECIAL_EVENTS)} eventos configurados)")
    
    def start(self):
        """Inicia el loop de verificacion de eventos"""
        if self._running:
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()
        logger.info("Loop de eventos especiales iniciado")
    
    def stop(self):
        """Detiene el loop de verificacion"""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        
        logger.info("Loop de eventos especiales detenido")
    
    def _check_loop(self):
        """Loop principal que verifica eventos cada minuto"""
        logger.info("Iniciando loop de verificacion de eventos especiales")
        
        while not self._stop_event.is_set():
            try:
                self._check_events()
            except Exception as e:
                logger.error(f"Error verificando eventos: {e}")
            
            # Esperar 30 segundos antes de volver a verificar
            self._stop_event.wait(30)
    
    def _check_events(self):
        """Verifica si hay un evento para la fecha/hora actual"""
        now = datetime.now()
        
        # Solo activar eventos a las 12:00 AM (entre 00:00 y 00:01)
        if now.hour != 0 or now.minute > 1:
            return
        
        # Clave unica para la fecha de hoy
        today_key = f"{now.month}-{now.day}"
        
        # Ya se disparo un evento hoy?
        if self._last_triggered_date == today_key:
            return
        
        # Buscar evento para hoy
        for event in SPECIAL_EVENTS:
            if event["month"] == now.month and event["day"] == now.day:
                event_type = event.get("event_type", "evento")
                prompt_hint = event.get("prompt_hint", "")
                logger.info(f"Evento especial detectado: {event_type}")
                
                # Marcar como disparado
                self._last_triggered_date = today_key
                
                # Disparar callback con event_type, prompt_hint y expression
                if self.on_event_triggered:
                    expression = event.get("expression", "happy")
                    self.on_event_triggered(event_type, prompt_hint, expression)
                
                break
    
    def get_next_event(self) -> Optional[Dict]:
        """Retorna el proximo evento programado (para debug)"""
        now = datetime.now()
        
        for event in SPECIAL_EVENTS:
            event_date = datetime(now.year, event["month"], event["day"])
            if event_date < now:
                event_date = datetime(now.year + 1, event["month"], event["day"])
            
            return {
                "date": event_date,
                "event_type": event.get("event_type", "evento"),
                "prompt_hint": event.get("prompt_hint", "")
            }
        
        return None

