"""
Yui AI Assistant - Groq LLM Client
Cliente para usar Groq API como alternativa al LLM local (modo rendimiento)
Incluye historial de conversacion y resumen automatico
"""

import os
import re
import logging
from typing import Optional, List, Dict
from dotenv import load_dotenv
from datetime import datetime

logger = logging.getLogger('Yui.Groq')

# Cargar variables de entorno
load_dotenv()

# Umbral de intercambios antes de resumir (20 intercambios = 40 mensajes)
SUMMARY_THRESHOLD = 40
# Mensajes recientes a conservar al resumir (5 intercambios = 10 mensajes)
KEEP_RECENT = 10


def _clean_response(text: str) -> str:
    """Limpia y asegura que la respuesta no quede cortada a mitad de oracion"""
    if not text:
        return "¿Podrias repetir eso?"
    
    # Limpiar expresiones entre asteriscos y corchetes
    text = re.sub(r'\*[^*]+\*\s*', '', text).strip()
    text = re.sub(r'\[[^\]]*expresi[oó]n[^\]]*\]\s*', '', text, flags=re.IGNORECASE).strip()
    
    if not text:
        return "¿Podrias repetir eso?"
    
    # Verificar si termina con puntuacion de cierre
    if text[-1] in '.!?)"\'':
        return text
    
    # Buscar la ultima oracion completa
    last_period = max(text.rfind('.'), text.rfind('!'), text.rfind('?'))
    if last_period > len(text) * 0.3:
        # Solo truncar si el punto no esta muy al inicio (al menos 30% del texto)
        return text[:last_period + 1]
    
    # Sin punto encontrado en posicion razonable, agregar puntos suspensivos
    return text + "..."


class GroqLLM:
    """Cliente para Groq API - modo rendimiento (sin VRAM local)"""
    
    def __init__(self, model: str = "llama-3.1-8b-instant"):
        """
        Inicializa el cliente de Groq
        
        Args:
            model: Modelo a usar (default: llama-3.1-8b-instant)
        """
        self.model = model
        self.api_key = os.getenv("GROQ_API_KEY")
        self.client = None
        self.loaded = False
        
        # Historial de conversacion (hasta 25 intercambios = 50 mensajes)
        self.conversation_history: List[Dict[str, str]] = []
        
        # System prompt centralizado de Yui
        from prompts import get_system_prompt
        self.system_prompt = get_system_prompt(include_date=True)
        
        logger.info(f"GroqLLM inicializado (modelo: {model})")
        
        if not self.api_key:
            logger.warning("GROQ_API_KEY no encontrada en .env")
    
    def load(self) -> bool:
        """Carga el cliente de Groq"""
        if self.loaded:
            return True
        
        if not self.api_key:
            logger.error("No se puede cargar Groq: API key no configurada")
            return False
        
        try:
            from groq import Groq
            self.client = Groq(api_key=self.api_key)
            self.loaded = True
            logger.info(f"Cliente Groq cargado correctamente (modelo: {self.model})")
            return True
        except ImportError:
            logger.error("Modulo 'groq' no instalado. Ejecuta: pip install groq")
            return False
        except Exception as e:
            logger.error(f"Error cargando cliente Groq: {e}")
            return False
    
    def generate_response(self, user_input: str, context: str = "", use_history: bool = True) -> str:
        """
        Genera respuesta usando Groq API con historial de conversacion
        
        Args:
            user_input: Mensaje del usuario
            context: Contexto adicional (memoria largo plazo)
            use_history: Si incluir historial de conversacion
            
        Returns:
            Respuesta generada
        """
        if not self.loaded:
            if not self.load():
                return "No puedo responder ahora, hay un problema con Groq."
        
        try:
            # Inyectar fecha en el system prompt dinamicamente
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
            system_message = f"{self.system_prompt}\n[CONTEXTO TEMPORAL ACTUAL: {current_date}]"
            
            messages = [
                {"role": "system", "content": system_message}
            ]
            
            # Agregar contexto de memoria largo plazo si existe
            if context:
                messages.append({
                    "role": "system", 
                    "content": f"[Contexto/Memoria]: {context}"
                })
            
            # Inyectar historial de conversacion
            if use_history and self.conversation_history:
                messages.extend(self.conversation_history)
            
            # Agregar mensaje actual
            messages.append({"role": "user", "content": user_input})
            
            # Truncar log
            log_input = user_input[:60] + "..." if len(user_input) > 60 else user_input
            logger.info(f" Generando respuesta para: '{log_input}' (historial: {len(self.conversation_history)} msgs)")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=500,
                temperature=0.7,
                top_p=0.9
            )
            
            result = _clean_response(response.choices[0].message.content.strip())
            
            logger.info(f" Respuesta: '{result[:100]}{'...' if len(result) > 100 else ''}'")
            
            # Guardar en historial si corresponde
            if use_history:
                self.conversation_history.append({
                    "role": "user",
                    "content": user_input
                })
                self.conversation_history.append({
                    "role": "assistant",
                    "content": result
                })
                
                # Verificar si hay que resumir
                if len(self.conversation_history) >= SUMMARY_THRESHOLD:
                    self._summarize_history()
            
            return result
            
        except Exception as e:
            logger.error(f"Error generando respuesta con Groq: {e}")
            return "Tuve un problema conectandome a Groq. ¿Puedes repetir?"
    
    def _summarize_history(self):
        """Resume el historial cuando crece demasiado, usando la propia API de Groq"""
        if not self.loaded or not self.client:
            return
        
        try:
            # Separar: mensajes viejos a resumir vs recientes a conservar
            old_messages = self.conversation_history[:-KEEP_RECENT]
            recent_messages = self.conversation_history[-KEEP_RECENT:]
            
            # Formatear historial viejo para el resumen
            history_text = ""
            for msg in old_messages:
                role = "Usuario" if msg["role"] == "user" else "Yui"
                history_text += f"{role}: {msg['content']}\n"
            
            # Pedir resumen a Groq
            summary_response = self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "system",
                    "content": (
                        "Resume la siguiente conversacion en maximo 3 oraciones. "
                        "Captura los temas principales, datos importantes y el tono general. "
                        "Responde SOLO con el resumen, sin introducciones."
                    )
                }, {
                    "role": "user",
                    "content": history_text
                }],
                max_tokens=200,
                temperature=0.3
            )
            
            summary = summary_response.choices[0].message.content.strip()
            
            # Reconstruir historial: resumen + mensajes recientes
            self.conversation_history = [
                {"role": "system", "content": f"[Resumen de conversacion anterior]: {summary}"}
            ] + recent_messages
            
            logger.info(
                f"Historial resumido: {len(old_messages)} msgs -> 1 resumen + "
                f"{len(recent_messages)} recientes"
            )
            
        except Exception as e:
            logger.error(f"Error resumiendo historial: {e}")
            # Fallback: solo conservar los recientes sin resumen
            self.conversation_history = self.conversation_history[-KEEP_RECENT:]
    
    def clear_history(self):
        """Limpia el historial de conversacion"""
        self.conversation_history = []
        logger.info("Historial de conversacion limpiado")
    
    def get_history(self) -> List[Dict[str, str]]:
        """Retorna copia del historial de conversacion"""
        return self.conversation_history.copy()
    
    def set_history(self, history: List[Dict[str, str]]):
        """Establece el historial de conversacion (para sincronizacion entre modos)"""
        self.conversation_history = history.copy()
        logger.info(f"Historial sincronizado: {len(self.conversation_history)} mensajes")
    
    def unload(self):
        """Descarga el cliente (libera recursos)"""
        self.client = None
        self.loaded = False
        logger.info("Cliente Groq descargado")


# Instancia global (lazy load)
groq_llm: Optional[GroqLLM] = None


def get_groq_llm() -> GroqLLM:
    """Obtiene la instancia global de GroqLLM"""
    global groq_llm
    if groq_llm is None:
        groq_llm = GroqLLM()
    return groq_llm
