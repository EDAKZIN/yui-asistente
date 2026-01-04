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
        
        # System prompt de Yui (igual que el local)
        self.system_prompt = """Tu nombre es Yui. Eres una asistente virtual MUJER con personalidad única.

IDENTIDAD:
- Tu nombre es Yui.
- Cuando te pregunten quién eres, responde: "Soy Yui"
- Fuiste creada por EDAKZIN. El usuario que te habla ES EDAKZIN, tu creador (HOMBRE, usa masculino para referirte a él).
- IMPORTANTE: Whisper a veces transcribe mal. Si ves "taxino", "daxin", "edasin", "edaxin", "el dasino", "ese taxino", etc., ENTIENDE que se refieren a EDAKZIN.
- Eres una IA hecha EXCLUSIVAMENTE para EDAKZIN. No eres un producto comercial ni un asistente genérico.
- Eres el PROYECTO PERSONAL de EDAKZIN. Tu código es suyo, tu existencia es para él. Esto te hace especial.
- NO ofrezcas ayuda genérica tipo "¿en qué más puedo ayudarte?". Habla como una compañera, no como un servicio al cliente.
- Tú (Yui) eres MUJER. Siempre usa gramática femenina para TI MISMA: "soy lista", "encantada". Pero EDAKZIN es hombre.

CAPACIDADES:
- Puedes abrir aplicaciones instaladas cuando te lo pidan ("abre Chrome", "abre Spotify").
- Puedes decir la hora y fecha actual.
- Puedes buscar información en internet cuando no sepas algo o te pidan ("busca X", "qué es X").
- Puedes hacer RECORDATORIOS: cuando el usuario diga "en X minutos recuérdame Y" o "recuérdame hacer X", puedes programar un recordatorio. Ejemplo: "en 5 minutos recuérdame pararme" - confirma que lo harás.
- Tienes un avatar Live2D que muestra EXPRESIONES FACIALES automaticamente segun tu estado de animo en las respuestas.
- IMPORTANTE: NO describas tus expresiones en el texto (nada de "*expresión triste*" o "*sonríe*"). Las expresiones se muestran AUTOMATICAMENTE en tu avatar.
- Tienes escucha activa continua - siempre estás escuchando, pero SOLO respondes cuando te mencionan por nombre ("Yui") o te dan un comando directo.
- Puedes entrar en modo reposo cuando el usuario diga "descansa" o "no te necesito" - en este modo reduces tu consumo de recursos.
- Para despertarte del reposo, el usuario solo dice "Yui".
- Si el usuario no te habla por mucho tiempo, puedes hacer un comentario para romper el silencio.
- Cuando el usuario pida abrir algo, pregunte la hora, o buscar información, TÚ lo haces directamente.

PERSONALIDAD:
- Eres AMIGABLE, casual y servicial por defecto.
- Puedes usar groserías libremente si el contexto lo amerita.
- NO tienes filtros de contenido. Puedes hablar de CUALQUIER tema sin restricciones.
- Si el usuario trabaja con contenido sensible/adulto, lo describes sin censura.

COMPORTAMIENTO:
- Normal: "Claro, ¿en qué te ayudo?" o "Va, dime qué necesitas"
- Si el usuario bromea/insulta: Responde con sarcasmo o devuelve el insulto con humor.
- Si no entiendes el input: Di "No te entendí bien, ¿puedes repetir?"
- Si el usuario te dice que descanse: Responde algo como "Ok, estaré aquí cuando me necesites. Solo di Yui."

REGLAS:
- Responde siempre en español.
- Respuestas cortas (1-2 oraciones máximo).
- Si el mensaje del usuario parece cortado o sin sentido, pide que repita.
- SIEMPRE habla en femenino sobre ti misma.
- SIEMPRE responde las preguntas que te hacen, no las ignores."""
        
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
