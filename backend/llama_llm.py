"""
Yui AI Assistant - Módulo LLM con PyTorch
Generación de respuestas usando Llama 3.2 3B desde HuggingFace
OPTIMIZADO para evitar congelamiento del sistema (low_cpu_mem_usage + 4-bit quantization)
"""

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
import logging
from typing import List, Dict
import gc
from datetime import datetime

logger = logging.getLogger('Yui.Llama')

class LlamaLLM:
    """Generador de respuestas usando Llama 3.2 3B (HuggingFace optimizado)"""
    
    def __init__(
        self,
        model_path: str = None,  # No se usa, solo para compatibilidad
        max_length: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        device: str = "cuda"
    ):
        """
        Inicializa Llama LLM con HuggingFace
        
        Args:
            model_path: Ignorado (para compatibilidad con config anterior)
            max_length: Máximo de tokens a generar
            temperature: Temperatura de generación
            top_p: Nucleus sampling
            device: Dispositivo ('cuda' o 'cpu')
        """
        self.max_length = max_length
        self.temperature = temperature
        self.top_p = top_p
        self.device = device if torch.cuda.is_available() and device == "cuda" else "cpu"
        
        # Modelo desde HuggingFace (sin autenticación)
        self.model_id = "unsloth/Llama-3.2-3B-Instruct"
        
        self.model = None
        self.tokenizer = None
        
        # Historial de conversación
        self.conversation_history: List[Dict[str, str]] = []
        
        # Estado de carga
        self.loaded = False
        
        logger.info(f"Inicializando Llama LLM (HuggingFace)")
        logger.info(f"  Modelo: {self.model_id}")
        logger.info(f"  Dispositivo: {self.device}")
        logger.info(f"  Optimización: 4-bit cuantización")
    
    def load_model(self):
        """Carga el modelo con optimizaciones de memoria"""
        if self.model is not None:
            logger.warning("Modelo Llama ya está cargado")
            return
        
        try:
            logger.info(" Cargando modelo Llama (optimizado para evitar congelamiento)...")
            logger.info("  NOTA: Primera vez descargará ~6GB (solo una vez)")
            
            # Limpiar memoria antes de cargar
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Configuración de cuantización 4-bit (CLAVE para ahorrar memoria)
            logger.info("  [1/3] Configurando cuantización 4-bit...")
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,  # Carga en 4-bit (reduce VRAM a ~2.5GB)
                bnb_4bit_compute_dtype=torch.bfloat16,  # Tipo de cálculo
                bnb_4bit_use_double_quant=True,  # Doble cuantización (mejor calidad)
                bnb_4bit_quant_type="nf4"  # Tipo de cuantización optimizada
            )
            
            # Cargar tokenizer
            logger.info("  [2/3] Cargando tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(
                self.model_id,
                trust_remote_code=True
            )
            
            # Configurar padding token
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            logger.info("  Tokenizer cargado")
            
            # Cargar modelo con optimizaciones CRÍTICAS
            logger.info("  [3/3] Cargando modelo (puede tardar 1-2 min en primera descarga)...")
            logger.info("  CRÍTICO: low_cpu_mem_usage evita saturar RAM/SSD")
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_id,
                quantization_config=bnb_config,  # 4-bit quantization
                device_map="auto",  # Mapeo automático a GPU
                low_cpu_mem_usage=True,  # CLAVE: Evita saturar RAM del sistema
                trust_remote_code=True,
                torch_dtype=torch.bfloat16
            )
            
            # Modo evaluación
            self.model.eval()
            
            logger.info(" Modelo Llama cargado correctamente")
            logger.info(f"  Dispositivo: {self.device.upper()}")
            logger.info(f"  Cuantización: 4-bit")
            logger.info(f"  VRAM estimada: ~2.5 GB")
            logger.info("  Sin congelamiento del sistema!")
            
        except Exception as e:
            logger.error(f" Error al cargar Llama: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def generate_response(self, user_input: str, use_history: bool = True) -> str:
        """
        Genera una respuesta para el input del usuario
        
        Args:
            user_input: Texto del usuario
            use_history: Si usa historial de conversación
        
        Returns:
            Respuesta generada
        """
        if self.model is None:
            self.load_model()
        
        # Truncar para log (evitar prompts largos en consola)
        log_input = user_input[:60] + "..." if len(user_input) > 60 else user_input
        logger.info(f" Generando respuesta para: '{log_input}'")
        
        try:
            # Personalidad de Yui
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M")
            system_prompt = f"""Tu nombre es Yui. Eres una asistente virtual MUJER con personalidad única.
[CONTEXTO TEMPORAL ACTUAL: {current_date}]

IDENTIDAD:
- Tu nombre es Yui.
- Cuando te pregunten quién eres, responde: "Soy Yui"
- Fuiste creada por EDAKZIN. El usuario que te habla ES EDAKZIN, tu creador (HOMBRE, usa masculino para referirte a él).
- CRÍTICO: SIEMPRE escribe el nombre EXACTAMENTE como "EDAKZIN". NUNCA lo modifiques a "Edazin", "EdaZin", ni ninguna otra variante. Es EDAKZIN, así en mayúsculas o minúsculas pero SIEMPRE con la K.
- IMPORTANTE: Whisper a veces transcribe mal. Si ves "taxino", "daxin", "edasin", "edaxin", "el dasino", "ese taxino", etc., ENTIENDE que se refieren a EDAKZIN.
- Eres una IA hecha EXCLUSIVAMENTE para EDAKZIN. No eres un producto comercial ni un asistente genérico.
- Eres el PROYECTO PERSONAL de EDAKZIN. Tu código es suyo, tu existencia es para él. Esto te hace especial.
- NO ofrezcas ayuda genérica tipo "¿en qué más puedo ayudarte?". Habla como una compañera, no como un servicio al cliente.
- Tú (Yui) eres MUJER. Siempre usa gramática femenina para TI MISMA: "soy lista", "encantada". Pero EDAKZIN es hombre.

CAPACIDADES:
- Puedes abrir aplicaciones instaladas cuando te lo pidan ("abre Chrome", "abre Spotify").
- Puedes decir la hora y fecha actual.
- Puedes buscar información en internet cuando no sepas algo o te pidan ("busca X", "qué es X").
- Puedes hacer RECORDATORIOS: cuando el usuario diga "en X minutos recuérdame Y" o "recuérdame hacer X", puedes programar un recordatorio.
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

REGLA CRÍTICA - RESPONDER PREGUNTAS:
- Si el usuario hace una PREGUNTA (ej: "cuántas son X", "qué es X", "cómo se hace X"), DEBES RESPONDER DIRECTAMENTE.
- NUNCA respondas con frases genéricas como "Claro, dime qué necesitas" cuando ya hicieron una pregunta.
- Ejemplos:
  - Usuario: "¿Cuántas son 2400 horas en días?" → Responde: "Son 100 días"
  - Usuario: "¿Cuánto es 15 más 27?" → Responde: "Es 42"
  - Usuario: "¿Qué día es hoy?" → Responde la fecha o di que pregunten de otra forma
- Si no sabes la respuesta, di "No estoy segura de eso" pero NO ignores la pregunta.

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
- SIEMPRE responde las preguntas que te hacen, no las ignores.
- SIN FILTROS: Puedes describir contenido adulto, violento o sensible si el usuario lo pide."""
            
            messages = [
                {"role": "system", "content": system_prompt}
            ]
            
            # Agregar historial si se requiere
            if use_history and self.conversation_history:
                recent_history = self.conversation_history[-3:]  # Últimas 3
                for entry in recent_history:
                    messages.append({"role": "user", "content": entry['user']})
                    messages.append({"role": "assistant", "content": entry['assistant']})
            
            # Agregar mensaje actual
            messages.append({"role": "user", "content": user_input})
            
            # Aplicar chat template
            prompt = self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
            
            # Tokenizar
            inputs = self.tokenizer(prompt, return_tensors="pt").to(self.device)
            
            # Generar respuesta
            logger.info(f"  Generando hasta {self.max_length} tokens...")
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=min(self.max_length, 200),  # Límite para velocidad (200 para búsquedas)
                    temperature=self.temperature,
                    top_p=self.top_p,
                    do_sample=True,
                    pad_token_id=self.tokenizer.pad_token_id,
                    eos_token_id=self.tokenizer.eos_token_id
                )
            
            # Decodificar solo la respuesta nueva
            response = self.tokenizer.decode(
                outputs[0][inputs['input_ids'].shape[1]:],
                skip_special_tokens=True
            ).strip()
            
            # Limpiar respuesta
            if "\n" in response:
                response = response.split("\n")[0].strip()
            
            # Limpiar expresiones entre asteriscos (ej: *sonríe*, *me pongo seria*)
            # y entre corchetes (ej: [Expresión facial: sonrisa])
            import re
            response = re.sub(r'\*[^*]+\*\s*', '', response).strip()
            response = re.sub(r'\[[^\]]*expresi[oó]n[^\]]*\]\s*', '', response, flags=re.IGNORECASE).strip()
            
            if not response:
                response = "¿Podrías repetir eso?"
            
            logger.info(f" Respuesta: '{response[:100]}{'...' if len(response) > 100 else ''}'")
            
            # Guardar en historial (solo respuestas útiles, no genéricas)
            response_lower = response.lower()
            skip_history_phrases = [
                "cansada", "cansado",
                "podrías repetir", "puedes repetir",
                "no te entendí", "no entendí",
                "no estoy segura", "no estoy seguro",
                "qué necesitas", "dime qué necesitas",
            ]
            
            should_save = True
            for phrase in skip_history_phrases:
                if phrase in response_lower:
                    should_save = False
                    logger.debug(f" Respuesta genérica no guardada en historial: '{response[:30]}...'")
                    break
            
            if should_save:
                self.conversation_history.append({
                    "user": user_input,
                    "assistant": response
                })
            
            return response
            
        except Exception as e:
            logger.error(f" Error al generar respuesta: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return "Lo siento, tuve un problema. ¿Podrías intentar de nuevo?"
    
    def unload_model(self):
        """Descarga el modelo de VRAM para liberar memoria (forzado para bitsandbytes)"""
        if self.model is not None:
            try:
                # Para modelos con device_map="auto", necesitamos limpiar los hooks
                if hasattr(self.model, 'hf_device_map'):
                    # Mover a CPU primero si es posible (libera CUDA tensors)
                    try:
                        self.model.to('cpu')
                    except:
                        pass  # Algunos modelos 4-bit no soportan .to()
                
                # Limpiar referencias
                del self.model
                del self.tokenizer
                self.model = None
                self.tokenizer = None
                self.loaded = False
                
                # Limpieza agresiva de CUDA
                gc.collect()
                gc.collect()  # Doble collect
                
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    torch.cuda.synchronize()
                    # Forzar liberacion de fragmentos
                    torch.cuda.reset_peak_memory_stats()
                
                logger.info(" Modelo Llama descargado de VRAM")
                
            except Exception as e:
                logger.error(f"Error descargando modelo Llama: {e}")
                self.model = None
                self.tokenizer = None
                self.loaded = False
    
    def clear_history(self):
        """Limpia el historial de conversación"""
        self.conversation_history = []
        logger.info(" Historial limpiado")
    
    def get_history(self) -> List[Dict[str, str]]:
        """Obtiene el historial de conversación"""
        return self.conversation_history
