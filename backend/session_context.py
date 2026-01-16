"""
Yui AI Assistant - Contexto de Sesión con Archivo .md
Maneja la memoria de corto plazo usando un archivo markdown temporal
para reducir el KV Cache del LLM.
"""

import logging
import os
from datetime import datetime
from typing import Optional
from pathlib import Path

logger = logging.getLogger('Yui.SessionContext')


class SessionContext:
    """
    Maneja el contexto de sesión usando un archivo .md temporal.
    Esto reduce el KV Cache al no enviar todo el historial en el prompt.
    """
    
    def __init__(self, logs_dir: str = "logs"):
        self.logs_dir = Path(logs_dir)
        self.context_file = self.logs_dir / "yui_session_context.md"
        self.session_start = None
        self.current_topic = "Conversación general"
        self.current_emotion = "neutral"
        self.exchange_count = 0
        self.last_exchanges = []  # Últimos 3 intercambios para el .md
        self.max_exchanges_in_file = 3
        
        logger.info("SessionContext inicializado")
    
    def start_session(self):
        """Inicia una nueva sesión creando el archivo .md"""
        self.session_start = datetime.now()
        self.exchange_count = 0
        self.last_exchanges = []
        self.current_topic = "Conversación general"
        self.current_emotion = "neutral"
        
        # Crear directorio si no existe
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Crear archivo inicial
        self._write_context_file()
        logger.info(f"Sesión iniciada: {self.context_file}")
    
    def add_exchange(self, user_message: str, assistant_response: str, emotion: str = "neutral"):
        """
        Agrega un intercambio al contexto de sesión.
        
        Args:
            user_message: Lo que dijo el usuario
            assistant_response: Lo que respondió Yui
            emotion: Emoción detectada (opcional)
        """
        self.exchange_count += 1
        self.current_emotion = emotion
        
        # Actualizar tema si el mensaje es suficientemente largo
        if len(user_message) > 20:
            # Extraer primeras palabras como tema aproximado
            words = user_message.split()[:5]
            self.current_topic = " ".join(words) + "..."
        
        # Agregar a últimos intercambios (mantener solo los últimos N)
        self.last_exchanges.append({
            "user": self._truncate(user_message, 100),
            "assistant": self._truncate(assistant_response, 150)
        })
        
        if len(self.last_exchanges) > self.max_exchanges_in_file:
            self.last_exchanges = self.last_exchanges[-self.max_exchanges_in_file:]
        
        # Actualizar archivo
        self._write_context_file()
        logger.debug(f"Intercambio #{self.exchange_count} agregado al contexto")
    
    def get_context_for_llm(self) -> str:
        """
        Obtiene el contexto formateado para incluir en el prompt del LLM.
        Este es un resumen compacto, NO el historial completo.
        
        Returns:
            String con contexto resumido para el LLM
        """
        if not self.last_exchanges:
            return ""
        
        lines = []
        lines.append("## Contexto de sesión actual")
        lines.append(f"- Tema: {self.current_topic}")
        lines.append(f"- Estado: {self.current_emotion}")
        lines.append(f"- Intercambios: {self.exchange_count}")
        lines.append("")
        lines.append("### Últimos intercambios:")
        
        for ex in self.last_exchanges:
            lines.append(f"- Usuario: {ex['user']}")
            lines.append(f"- Yui: {ex['assistant']}")
        
        return "\n".join(lines)
    
    def get_summary(self) -> str:
        """
        Obtiene un resumen de la sesión para guardar en memoria largo plazo.
        
        Returns:
            Resumen de la sesión
        """
        if self.exchange_count == 0:
            return ""
        
        duration = ""
        if self.session_start:
            delta = datetime.now() - self.session_start
            minutes = int(delta.total_seconds() / 60)
            duration = f" ({minutes} min)"
        
        summary = f"Sesión{duration}: {self.exchange_count} intercambios sobre '{self.current_topic}'"
        return summary
    
    def clear(self):
        """Limpia el contexto de sesión (llamar en modo reposo o cierre)"""
        self.last_exchanges = []
        self.exchange_count = 0
        self.current_topic = "Conversación general"
        self.current_emotion = "neutral"
        
        # Borrar archivo
        if self.context_file.exists():
            self.context_file.unlink()
            logger.info("Archivo de contexto eliminado")
    
    def _write_context_file(self):
        """Escribe el archivo .md con el contexto actual"""
        lines = []
        lines.append("# Yui - Contexto de Sesión")
        lines.append("")
        
        if self.session_start:
            lines.append(f"**Inicio**: {self.session_start.strftime('%Y-%m-%d %H:%M')}")
        
        lines.append(f"**Tema actual**: {self.current_topic}")
        lines.append(f"**Estado emocional**: {self.current_emotion}")
        lines.append(f"**Intercambios**: {self.exchange_count}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## Últimos intercambios")
        lines.append("")
        
        for i, ex in enumerate(self.last_exchanges, 1):
            lines.append(f"### #{i}")
            lines.append(f"**Usuario**: {ex['user']}")
            lines.append(f"**Yui**: {ex['assistant']}")
            lines.append("")
        
        try:
            self.context_file.write_text("\n".join(lines), encoding='utf-8')
        except Exception as e:
            logger.error(f"Error escribiendo contexto: {e}")
    
    def _truncate(self, text: str, max_len: int) -> str:
        """Trunca texto si es muy largo"""
        if len(text) <= max_len:
            return text
        return text[:max_len-3] + "..."
