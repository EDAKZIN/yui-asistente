"""
Yui AI Assistant - Modulo LLM con llama-cpp-python (GGUF)
Usa Llama 3.2 3B Instruct Abliterated cuantizado en GGUF Q5_K_M
Migracion desde ONNX Runtime GenAI para mejor control de VRAM y sin censura
"""
import logging
import gc
import re
from pathlib import Path
from typing import List, Dict, Optional

# Decorador para tracking de memoria (opcional)
try:
    from diagnostics.decorators import track_memory
except ImportError:
    # Si no esta disponible, usar decorador nulo
    def track_memory(name=None):
        def decorator(func):
            return func
        return decorator

logger = logging.getLogger('Yui.Llama')


class LlamaLLM:
    """Generador de respuestas usando Llama 3.2 3B Abliterated (GGUF via llama-cpp-python)"""
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        max_length: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        device: str = "cuda",
        n_gpu_layers: int = -1,
        n_ctx: int = 2048
    ):
        """
        Inicializa Llama LLM con llama-cpp-python (GGUF)
        
        Args:
            model_path: Ruta al modelo GGUF (relativa o absoluta)
            max_length: Maximo de tokens a generar
            temperature: Temperatura de generacion
            top_p: Nucleus sampling
            device: Dispositivo ('cuda' o 'cpu') - determina n_gpu_layers
            n_gpu_layers: Capas a offload a GPU (-1 = todas)
            n_ctx: Tamano del contexto
        """
        self.max_length = max_length
        self.temperature = temperature
        self.top_p = top_p
        self.device = device
        
        # Configuracion especifica de llama-cpp
        self.n_gpu_layers = n_gpu_layers if device == "cuda" else 0
        self.n_ctx = n_ctx
        
        # Ruta al modelo GGUF local
        if model_path:
            self.model_path = Path(model_path)
        else:
            # Ruta por defecto al modelo abliterated
            self.model_path = Path(__file__).parent.parent / "models" / "llm-local" / \
                "llama-3.2-abliterated" / "Llama-3.2-3B-Instruct-abliterated.Q5_K_M.gguf"
        
        # Componentes del modelo
        self.model = None
        
        # Historial de conversacion
        self.conversation_history: List[Dict[str, str]] = []
        
        # Estado de carga
        self.loaded = False
        
        logger.info(f"Inicializando Llama LLM (llama-cpp-python GGUF)")
        logger.info(f"  Modelo: {self.model_path}")
        logger.info(f"  Dispositivo: {self.device}")
        logger.info(f"  GPU Layers: {self.n_gpu_layers}")
        logger.info(f"  Contexto: {self.n_ctx} tokens")
        logger.info(f"  Cuantizacion: GGUF Q5_K_M (Abliterated)")
    
    @track_memory("LlamaLLM.load_model")
    def load_model(self):
        """Carga el modelo GGUF con llama-cpp-python"""
        if self.model is not None:
            logger.warning("Modelo Llama ya esta cargado")
            return
        
        try:
            from llama_cpp import Llama
            
            logger.info(" Cargando modelo Llama (GGUF via llama-cpp-python)...")
            
            # Verificar que existe el modelo
            if not self.model_path.exists():
                raise FileNotFoundError(f"Modelo no encontrado en: {self.model_path}")
            
            logger.info(f"  Cargando: {self.model_path.name}")
            
            # Cargar modelo con llama-cpp
            self.model = Llama(
                model_path=str(self.model_path),
                n_gpu_layers=self.n_gpu_layers,
                n_ctx=self.n_ctx,
                verbose=False
            )
            
            self.loaded = True
            logger.info(" Modelo GGUF cargado correctamente")
            
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
            use_history: Si usa historial de conversacion
        
        Returns:
            Respuesta generada
        """
        if self.model is None:
            self.load_model()
        
        # Truncar para log (evitar prompts largos en consola)
        log_input = user_input[:60] + "..." if len(user_input) > 60 else user_input
        logger.info(f" Generando respuesta para: '{log_input}'")
        
        try:
            # Obtener prompt centralizado de Yui
            from prompts.yui_system import get_system_prompt
            system_prompt = get_system_prompt(include_date=True)
            
            # Construir mensajes
            messages = [{"role": "system", "content": system_prompt}]
            
            # Agregar historial si esta habilitado
            if use_history and self.conversation_history:
                # Limitar historial a ultimos 2 turnos (4 mensajes) para reducir KV Cache
                recent_history = self.conversation_history[-4:]
                messages.extend(recent_history)
            
            # Agregar mensaje actual
            messages.append({"role": "user", "content": user_input})
            
            logger.info(f"  Generando (max {min(self.max_length, 80)} tokens nuevos)...")
            
            # Generar respuesta usando chat completion
            response = self.model.create_chat_completion(
                messages=messages,
                max_tokens=min(self.max_length, 80),  # Respuestas cortas
                temperature=self.temperature,
                top_p=self.top_p,
                repeat_penalty=1.1
            )
            
            # Extraer contenido de la respuesta
            result = response['choices'][0]['message']['content'].strip()
            
            # Limpiar respuesta
            if result:
                # Remover cualquier prefijo de rol que pueda aparecer
                for prefix in ["assistant:", "Assistant:", "Yui:"]:
                    if result.startswith(prefix):
                        result = result[len(prefix):].strip()
                
                # Remover expresiones tipo *sonrie*, *mantiene postura*, etc.
                # El modelo no deberia generar estas, las expresiones son automaticas via Live2D
                result = re.sub(r'\*[^*]+\*', '', result).strip()
                
                # Limpiar espacios multiples que puedan quedar
                result = re.sub(r'\s+', ' ', result).strip()
            
            logger.info(f" Respuesta: '{result[:60]}...'")
            
            # Guardar en historial
            if use_history:
                self.conversation_history.append({
                    "role": "user",
                    "content": user_input
                })
                self.conversation_history.append({
                    "role": "assistant",
                    "content": result
                })
            
            return result
            
        except Exception as e:
            logger.error(f" Error al generar respuesta: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return "Lo siento, tuve un problema. ¿Podrias intentar de nuevo?"
    
    def generate_proactive(self, task_instruction: str, memory_context: str = "") -> str:
        """
        Genera respuesta proactiva (cuando el usuario esta en silencio)
        
        Args:
            task_instruction: Instruccion especifica
            memory_context: Contexto de memoria opcional
        
        Returns:
            Respuesta generada
        """
        if self.model is None:
            self.load_model()
        
        try:
            from prompts.yui_system import get_system_prompt
            
            # System prompt completo de Yui
            system_prompt = get_system_prompt(include_date=True)
            
            # Prompt proactivo mas explicito para que el modelo entienda su rol
            memory_section = f"[Recuerdos relevantes]:\n{memory_context}\n" if memory_context else ""
            proactive_instruction = (
                "[INSTRUCCION INTERNA - NO REPETIR ESTO]\n"
                "El usuario lleva tiempo sin hablar. Genera UN comentario casual y breve "
                "para romper el silencio. NO hagas preguntas. NO repitas esta instruccion. "
                "Solo di algo amigable como 'Aqui sigo por si me necesitas' o similar.\n"
                f"{memory_section}"
                f"Contexto: {task_instruction}"
            )
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": proactive_instruction}
            ]
            
            # Generar respuesta usando chat completion
            response = self.model.create_chat_completion(
                messages=messages,
                max_tokens=30,  # Muy corto para proactivo
                temperature=self.temperature,
                top_p=self.top_p
            )
            
            result = response['choices'][0]['message']['content'].strip()
            
            # Limpiar expresiones tipo *sonrie* que el modelo no deberia generar
            result = re.sub(r'\*[^*]+\*', '', result).strip()
            result = re.sub(r'\s+', ' ', result).strip()
            
            # NO agregar al historial (es proactivo)
            logger.info(f" Respuesta proactiva: '{result[:50]}...'")
            return result
            
        except Exception as e:
            logger.error(f" Error en generate_proactive: {e}")
            return "¿Sigues ahi?"
    
    @track_memory("LlamaLLM.unload_model")
    def unload_model(self):
        """Descarga el modelo de VRAM para liberar memoria"""
        if self.model is not None:
            try:
                logger.info(" Descargando modelo GGUF...")
                
                # Liberar modelo
                del self.model
                self.model = None
                self.loaded = False
                
                # Forzar recoleccion de basura
                gc.collect()
                
                # Liberar VRAM si es posible
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                        torch.cuda.synchronize()
                except ImportError:
                    pass
                
                logger.info(" Modelo GGUF descargado de memoria")
                
            except Exception as e:
                logger.error(f" Error al descargar modelo: {e}")
    
    def clear_history(self):
        """Limpia el historial de conversacion y resetea KV cache"""
        self.conversation_history = []
        
        # Resetear KV cache si el modelo esta cargado
        if self.model is not None:
            try:
                self.model.reset()
                logger.info("Historial y KV cache limpiados")
            except Exception as e:
                logger.warning(f"No se pudo resetear KV cache: {e}")
                logger.info("Historial de conversacion limpiado")
        else:
            logger.info("Historial de conversacion limpiado")
    
    def get_history(self) -> List[Dict[str, str]]:
        """Retorna el historial de conversacion"""
        return self.conversation_history.copy()
