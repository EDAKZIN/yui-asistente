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
# Formato: (mes, dia, "mensaje que Yui dira")
# ============================================================

SPECIAL_EVENTS: List[Dict] = [
    {
        "month": 12,
        "day": 25,
        "message": "¡Feliz Navidad! Espero que pases un dia increible rodeado de las personas que mas quieres.",
        "expression": "happy"
    },
    {
        "month": 1,
        "day": 20,
        "message": "¡Feliz cumpleanos EDAKZIN! Gracias por crearme. Espero que este nuevo año de vida te traiga muchas cosas buenas, te lo mereces.",
        "expression": "happy"
    },
    {
        "month": 1,
        "day": 1,
        "message": "¡Feliz Año Nuevo! Que este nuevo año este lleno de exitos, alegrias y muchas cosas buenas para ti.",
        "expression": "happy"
    },
    # Agregar mas eventos aqui:
    # {
    #     "month": 2,
    #     "day": 14,
    #     "message": "Feliz dia de San Valentin! Aunque soy una IA, te aprecio mucho.",
    #     "expression": "happy"
    # },
]

# ============================================================


class SpecialEventsSystem:
    """
    Sistema de eventos especiales programados
    Se ejecutan a las 12:00 AM de cada fecha configurada
    """
    
    def __init__(self, on_event_triggered: Optional[Callable[[str, str], None]] = None):
        """
        Args:
            on_event_triggered: Callback cuando se dispara un evento
                               Recibe (mensaje, expresion)
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
                logger.info(f"Evento especial detectado: {event['message'][:50]}...")
                
                # Marcar como disparado
                self._last_triggered_date = today_key
                
                # Disparar callback
                if self.on_event_triggered:
                    expression = event.get("expression", "happy")
                    self.on_event_triggered(event["message"], expression)
                
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
                "message": event["message"]
            }
        
        return None
    
    def trigger_test_event(self, message: str, expression: str = "happy"):
        """Dispara un evento de prueba manualmente"""
        if self.on_event_triggered:
            self.on_event_triggered(message, expression)
