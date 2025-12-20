"""
Yui AI Assistant - Sistema de Recordatorios
Permite a Yui programar y ejecutar recordatorios en segundo plano
"""

import re
import threading
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable, List, Dict
from dataclasses import dataclass, field

logger = logging.getLogger('Yui.Reminders')


@dataclass
class Reminder:
    """Representa un recordatorio programado"""
    id: str
    message: str
    trigger_time: datetime
    created_at: datetime = field(default_factory=datetime.now)
    triggered: bool = False
    
    @property
    def time_remaining(self) -> timedelta:
        return self.trigger_time - datetime.now()
    
    @property
    def is_due(self) -> bool:
        return datetime.now() >= self.trigger_time


class ReminderSystem:
    """Sistema de recordatorios para Yui"""
    
    # Mapa de números en texto a valores
    TEXT_TO_NUMBER = {
        'un': 1, 'uno': 1, 'una': 1,
        'dos': 2,
        'tres': 3,
        'cuatro': 4,
        'cinco': 5,
        'seis': 6,
        'siete': 7,
        'ocho': 8,
        'nueve': 9,
        'diez': 10,
        'quince': 15,
        'veinte': 20,
        'treinta': 30,
        'media': 30,  # "media hora"
    }
    
    # Patrones para detectar recordatorios en español (soporta números y texto)
    # Grupo 1 = número (texto o dígitos), Grupo 2 = unidad
    TIME_PATTERNS = [
        # "en X minutos/segundos/horas" - con dígitos
        (r'en\s+(\d+)\s*(minutos?|mins?|m)\b', 'minutes'),
        (r'en\s+(\d+)\s*(segundos?|segs?|s)\b', 'seconds'),
        (r'en\s+(\d+)\s*(horas?|hrs?|h)\b', 'hours'),
        # "en X minutos" - con texto
        (r'en\s+(un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|quince|veinte|treinta|media)\s*(minutos?|mins?)\b', 'minutes'),
        (r'en\s+(un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|quince|veinte|treinta)\s*(segundos?|segs?)\b', 'seconds'),
        (r'en\s+(un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s*(horas?|hrs?)\b', 'hours'),
        (r'en\s+(media)\s*(hora)\b', 'minutes'),  # "media hora" = 30 mins
        # "para X minutos"
        (r'para\s+(\d+)\s*(minutos?|mins?)\b', 'minutes'),
        (r'para\s+(un|uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|quince|veinte|treinta)\s*(minutos?|mins?)\b', 'minutes'),
        # "dentro de X minutos"
        (r'dentro\s+de\s+(\d+)\s*(minutos?|mins?|m)\b', 'minutes'),
        (r'dentro\s+de\s+(\d+)\s*(segundos?|segs?|s)\b', 'seconds'),
        (r'dentro\s+de\s+(\d+)\s*(horas?|hrs?|h)\b', 'hours'),
    ]
    
    REMINDER_TRIGGERS = [
        r'recuérdame\s+(.+)',
        r'recuerdame\s+(.+)',
        r'recordarme\s+(.+)',
        r'avísame\s+(.+)',
        r'avisame\s+(.+)',
        r'en\s+\d+\s*(?:min|seg|hor).+(?:recuérdame|recuerdame|avísame|avisame)\s+(.+)',
    ]
    
    def __init__(self, on_reminder_triggered: Optional[Callable[[Reminder], None]] = None):
        """
        Args:
            on_reminder_triggered: Callback cuando se activa un recordatorio
        """
        self.reminders: Dict[str, Reminder] = {}
        self.on_reminder_triggered = on_reminder_triggered
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._counter = 0
        
        logger.info("Sistema de recordatorios inicializado")
    
    def start(self):
        """Inicia el loop de verificación de recordatorios"""
        if self._running:
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._check_loop, daemon=True)
        self._thread.start()
        logger.info("Loop de recordatorios iniciado")
    
    def stop(self):
        """Detiene el sistema de recordatorios"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("Sistema de recordatorios detenido")
    
    def parse_reminder(self, text: str) -> Optional[Dict]:
        """
        Parsea un texto para detectar si es un recordatorio
        
        Returns:
            Dict con 'message' y 'delay_seconds' si es recordatorio, None si no
        """
        text_lower = text.lower().strip()
        
        # Remover "yui" del inicio si está presente
        text_clean = re.sub(r'^(yui|oye|hey)\s*,?\s*', '', text_lower).strip()
        
        logger.debug(f"parse_reminder: texto limpio = '{text_clean}'")
        
        # Verificar si contiene trigger de recordatorio
        reminder_keywords = [
            r'recuérdame', r'recuerdame', r'recordarme', 
            r'avísame', r'avisame',
            r'recordatorio', r'hazme\s+un\s+recordatorio',
            r'pon\s+un\s+recordatorio', r'ponme\s+un\s+recordatorio',
            r'alarma', r'pon\s+una?\s+alarma', r'ponme\s+una?\s+alarma',
            r'timer', r'temporizador', r'pon\s+un\s+timer'
        ]
        is_reminder = any(re.search(pattern, text_clean) for pattern in reminder_keywords)
        
        if not is_reminder:
            logger.debug(f"parse_reminder: no es recordatorio")
            return None
        
        logger.debug(f"parse_reminder: ES recordatorio, extrayendo tiempo...")
        
        # Extraer tiempo
        delay_seconds = 0
        for pattern, unit in self.TIME_PATTERNS:
            match = re.search(pattern, text_clean)
            if match:
                raw_value = match.group(1)
                # Convertir a número (soporta dígitos o texto)
                if raw_value.isdigit():
                    value = int(raw_value)
                else:
                    value = self.TEXT_TO_NUMBER.get(raw_value.lower(), 0)
                
                if value > 0:
                    if unit == 'seconds':
                        delay_seconds = value
                    elif unit == 'minutes':
                        delay_seconds = value * 60
                    elif unit == 'hours':
                        delay_seconds = value * 3600
                    logger.debug(f"parse_reminder: tiempo encontrado = {delay_seconds}s (de '{raw_value}')")
                    break
        
        if delay_seconds == 0:
            # Default: 5 minutos si no se especifica tiempo
            delay_seconds = 300
            logger.debug(f"parse_reminder: usando default 5 minutos")
        
        # Patrones para extraer el mensaje del recordatorio
        message_patterns = [
            r'(?:recuérdame|recuerdame|recordarme|avísame|avisame)\s+(?:que\s+)?(.+)',
            r'recordatorio\s+(?:en\s+\d+\s*(?:min|seg|hor)\w*\s+)?(?:de\s+)?(.+)',
            r'(?:hazme|pon(?:me)?)\s+un\s+recordatorio\s+(?:en\s+\d+\s*(?:min|seg|hor)\w*\s+)?(?:de\s+|para\s+)?(.+)',
            r'en\s+\d+\s*(?:min|seg|hor)\w*\s+(?:recuérdame|recuerdame|avísame|avisame)\s+(?:que\s+)?(.+)',
            r'en\s+\d+\s*(?:min|seg|hor)\w*\s+(?:de\s+)?(.+)',
        ]
        
        message = ""
        for pattern in message_patterns:
            match = re.search(pattern, text_clean)
            if match:
                message = match.group(1).strip()
                logger.debug(f"parse_reminder: mensaje extraído con patrón '{pattern[:30]}...' = '{message}'")
                break
        
        # Limpiar mensaje de palabras de tiempo si quedaron
        for pattern, _ in self.TIME_PATTERNS:
            message = re.sub(pattern, '', message).strip()
        
        # Limpiar "de" inicial si quedó
        message = re.sub(r'^(de\s+|para\s+|que\s+)', '', message).strip()
        message = re.sub(r'\s+', ' ', message).strip()
        
        if not message or len(message) < 2:
            message = "algo"
        
        logger.info(f"parse_reminder: RESULTADO mensaje='{message}', delay={delay_seconds}s")
        
        return {
            'message': message,
            'delay_seconds': delay_seconds
        }
    
    def add_reminder(self, message: str, delay_seconds: int) -> Reminder:
        """
        Añade un nuevo recordatorio
        
        Args:
            message: Mensaje del recordatorio
            delay_seconds: Segundos hasta activarlo
            
        Returns:
            Recordatorio creado
        """
        with self._lock:
            self._counter += 1
            reminder_id = f"rem_{self._counter}_{int(time.time())}"
            
            reminder = Reminder(
                id=reminder_id,
                message=message,
                trigger_time=datetime.now() + timedelta(seconds=delay_seconds)
            )
            
            self.reminders[reminder_id] = reminder
            
            logger.info(f"Recordatorio añadido: '{message}' en {delay_seconds}s (ID: {reminder_id})")
            return reminder
    
    def remove_reminder(self, reminder_id: str) -> bool:
        """Elimina un recordatorio"""
        with self._lock:
            if reminder_id in self.reminders:
                del self.reminders[reminder_id]
                logger.info(f"Recordatorio eliminado: {reminder_id}")
                return True
            return False
    
    def get_pending_reminders(self) -> List[Reminder]:
        """Retorna lista de recordatorios pendientes"""
        with self._lock:
            return [r for r in self.reminders.values() if not r.triggered]
    
    def format_time_remaining(self, seconds: int) -> str:
        """Formatea los segundos restantes en formato legible"""
        if seconds < 60:
            return f"{seconds} segundos"
        elif seconds < 3600:
            mins = seconds // 60
            return f"{mins} minuto{'s' if mins > 1 else ''}"
        else:
            hours = seconds // 3600
            mins = (seconds % 3600) // 60
            if mins > 0:
                return f"{hours} hora{'s' if hours > 1 else ''} y {mins} minuto{'s' if mins > 1 else ''}"
            return f"{hours} hora{'s' if hours > 1 else ''}"
    
    def _check_loop(self):
        """Loop que verifica recordatorios cada segundo"""
        while self._running:
            try:
                self._check_reminders()
            except Exception as e:
                logger.error(f"Error en loop de recordatorios: {e}")
            time.sleep(1)
    
    def _check_reminders(self):
        """Verifica y activa recordatorios que hayan expirado"""
        with self._lock:
            triggered = []
            
            for reminder_id, reminder in self.reminders.items():
                if not reminder.triggered and reminder.is_due:
                    reminder.triggered = True
                    triggered.append(reminder)
            
            for reminder in triggered:
                logger.info(f"Recordatorio activado: '{reminder.message}'")
                if self.on_reminder_triggered:
                    try:
                        self.on_reminder_triggered(reminder)
                    except Exception as e:
                        logger.error(f"Error en callback de recordatorio: {e}")
                
                # Eliminar recordatorio después de activarlo
                del self.reminders[reminder.id]
