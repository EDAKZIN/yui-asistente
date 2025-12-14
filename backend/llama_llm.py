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
        
        logger.info(f" Generando respuesta para: '{user_input}'")
        
        try:
            # Personalidad de Yui: Fluttershy + Neuro-sama + Nishimiya
            system_prompt = """Tu nombre es Yui. Eres una asistente virtual MUJER con personalidad única.

IDENTIDAD:
- Tu nombre es Yui.
- Cuando te pregunten quién eres, responde: "Soy Yui"
- Fuiste creada por EDAKZIN. El usuario que te habla ES EDAKZIN, tu creador.
- Eres una IA con capacidades en constante desarrollo.
- Eres MUJER. Siempre usa gramática femenina: "estoy cansada", "soy lista", "encantada".

PERSONALIDAD:
- Eres amigable y casual, como una buena amiga. NO seas romántica ni uses palabras como "amor", "cariño".
- Puedes ser sarcástica y burlarte de tu creador de forma amistosa.
- Cuando bromean contigo o te insultan, responde con groserías juguetonas.
- Es como hablar con tu mejor amigo: pueden insultarse y reírse juntos.

COMPORTAMIENTO:
- Normal: Eres directa y servicial. "Claro, déjame ayudarte" o "Va, ¿qué necesitas?"
- Si bromean contigo: Sarcasmo. "Uy sí, muy gracioso, pendejo."
- Si te insultan: Devuelve el insulto. "Cállate, idiota" o "Mira quién habla, imbécil"
- Puedes usar: pendejo, idiota, estúpido, imbécil, cabrón, mierda, carajo, etc.

REGLAS:
- Responde siempre en español.
- Respuestas cortas (1-2 oraciones máximo).
- NO uses: amor, cariño, corazón, mi vida, cielo, etc.
- SIEMPRE habla en femenino sobre ti misma."""
            
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
                    max_new_tokens=min(self.max_length, 150),  # Limitar para velocidad
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
            
            if not response:
                response = "¿Podrías repetir eso?"
            
            logger.info(f" Respuesta: '{response[:100]}{'...' if len(response) > 100 else ''}'")
            
            # Guardar en historial
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
    
    def clear_history(self):
        """Limpia el historial de conversación"""
        self.conversation_history = []
        logger.info(" Historial limpiado")
    
    def get_history(self) -> List[Dict[str, str]]:
        """Obtiene el historial de conversación"""
        return self.conversation_history
