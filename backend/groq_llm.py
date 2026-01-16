"""
Yui AI Assistant - Groq LLM Client
Cliente para usar Groq API como alternativa al LLM local (modo rendimiento)
"""

import os
import logging
from typing import Optional
from dotenv import load_dotenv
from datetime import datetime

logger = logging.getLogger('Yui.Groq')

# Cargar variables de entorno
load_dotenv()


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
            logger.error("Módulo 'groq' no instalado. Ejecuta: pip install groq")
            return False
        except Exception as e:
            logger.error(f"Error cargando cliente Groq: {e}")
            return False
    
    def generate_response(self, user_input: str, context: str = "", use_history: bool = True) -> str:
        """
        Genera respuesta usando Groq API
        
        Args:
            user_input: Mensaje del usuario
            context: Contexto adicional (memoria)
            use_history: No usado (para compatibilidad)
            
        Returns:
            Respuesta generada
        """
        if not self.loaded:
            if not self.load():
                return "No puedo responder ahora, hay un problema con Groq."
        
        try:
            # Inyectar fecha en el system prompt dinámicamente
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
            system_message = f"{self.system_prompt}\n[CONTEXTO TEMPORAL ACTUAL: {current_date}]"
            
            messages = [
                {"role": "system", "content": system_message}
            ]
            
            # Agregar contexto si existe
            if context:
                messages.append({
                    "role": "system", 
                    "content": f"[Contexto/Memoria]: {context}"
                })
            
            messages.append({"role": "user", "content": user_input})
            
            # Truncar log
            log_input = user_input[:60] + "..." if len(user_input) > 60 else user_input
            logger.info(f" Generando respuesta para: '{log_input}'")
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=150,
                temperature=0.7,
                top_p=0.9
            )
            
            result = response.choices[0].message.content.strip()
            
            # Limpiar expresiones entre asteriscos y corchetes
            import re
            result = re.sub(r'\*[^*]+\*\s*', '', result).strip()
            result = re.sub(r'\[[^\]]*expresi[oó]n[^\]]*\]\s*', '', result, flags=re.IGNORECASE).strip()
            
            if not result:
                result = "¿Podrías repetir eso?"
            
            logger.info(f" Respuesta: '{result[:100]}{'...' if len(result) > 100 else ''}'")
            return result
            
        except Exception as e:
            logger.error(f"Error generando respuesta con Groq: {e}")
            return "Tuve un problema conectándome a Groq. ¿Puedes repetir?"
    
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
