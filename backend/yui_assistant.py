"""
Yui AI Assistant - Pipeline Principal
Integra todos los componentes: STT, LLM, TTS, RVC
"""

import sys
from pathlib import Path

# Agregar backend al path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from logger import YuiLogger
from audio_manager import AudioManager
from whisper_stt import WhisperSTT
from llama_llm import LlamaLLM
from coqui_tts import CoquiTTS
from memory_system import MemorySystem
from commands import command_executor
from diagnostics.memory_monitor import MemoryMonitor
import logging
import re

# Groq LLM para modo rendimiento (lazy load)
groq_llm = None

logger = logging.getLogger('Yui.Assistant')


def should_query_long_term_memory(user_input: str, session_history: list) -> bool:
    """Decide si vale la pena consultar ChromaDB (memoria largo plazo)
    
    Evita latencia innecesaria consultando solo cuando tiene sentido.
    """
    text = user_input.lower()
    
    # 1. Palabras clave que sugieren memoria a largo plazo
    memory_triggers = [
        # Referencias al pasado
        'recuerdas', 'recuerda', 'acordas', 'acuerdas',
        'antes', 'ayer', 'la otra vez', 'hace tiempo',
        'dijiste', 'mencionaste', 'hablamos', 'contaste',
        # Preguntas sobre información personal
        'mi nombre', 'mi cumpleaños', 'mi favorito', 'lo que me gusta',
        'te conté', 'te dije', 'te mencioné',
    ]
    
    if any(trigger in text for trigger in memory_triggers):
        return True
    
    # 3. Preguntas sobre preferencias
    preference_patterns = [
        'qué me gusta', 'cuál es mi', 'qué prefiero',
        'cuáles son mis', 'qué tipo de',
    ]
    if any(pattern in text for pattern in preference_patterns):
        return True
    
    # Por defecto: NO consultar (evita latencia)
    return False

class YuiAssistant:
    """Asistente de voz Yui - Pipeline completo"""
    
    def __init__(self):
        """Inicializa el asistente Yui"""
        print("=" * 70)
        print(" " * 20 + "YUI AI ASSISTANT")
        print("=" * 70)
        
        # Obtener ruta raíz del proyecto (un nivel arriba de backend/)
        self.project_root = Path(__file__).parent.parent
        
        # Cargar configuración
        self.config = Config.load()
        
        # Configurar logging con ruta relativa
        log_dir = self.project_root / self.config['paths']['logs_dir']
        self.logger = YuiLogger.setup(str(log_dir))
        
        self.logger.info("Inicializando Yui AI Assistant...")
        
        # Inicializar componentes
        self._init_components()
        
        self.logger.info(" Yui inicializada correctamente")
        print("=" * 70)
    
    def _init_components(self):
        """Inicializa todos los componentes del pipeline"""
        # Audio Manager
        sample_rate = self.config['audio']['sample_rate']
        channels = self.config['audio']['channels']
        self.audio_manager = AudioManager(sample_rate=sample_rate, channels=channels)
        
        # Whisper STT
        whisper_config = self.config['models']['whisper']
        self.whisper = WhisperSTT(
            model_size=whisper_config['model_size'],
            language=whisper_config['language']
        )
        
        # Llama LLM
        llama_config = self.config['models']['llama']
        llama_path = self.config['paths']['llama_model']
        self.llama = LlamaLLM(
            model_path=llama_path,
            max_length=llama_config['max_length'],
            temperature=llama_config['temperature'],
            top_p=llama_config['top_p'],
            device=llama_config['device']
        )
        
        
        # TTS con Coqui XTTS v2 (usa rutas relativas)
        voice_samples_path = self.project_root / self.config['paths'].get('voice_samples_dir', 'voice_samples')
        self.tts = CoquiTTS(voice_samples_dir=str(voice_samples_path))
        
        # Sistema de Memoria (ruta relativa)
        chromadb_path = self.project_root / self.config['paths']['chromadb_path']
        self.memory = MemorySystem(db_path=str(chromadb_path))
        
        # Modo rendimiento (usa Groq en vez de Llama local)
        self.performance_mode = False
        self.groq = None  # Lazy load
        
        # Sistema de reflexión (lazy load después de memoria)
        self.reflection = None
        
        # Monitor de memoria (VRAM/RAM)
        self._memory_monitor = MemoryMonitor(log_dir=self.project_root / 'logs')
    
    def enable_performance_mode(self) -> str:
        """Activa el modo rendimiento (Groq API en vez de Llama local)"""
        global groq_llm
        
        if self.performance_mode:
            return "Ya estoy en modo rendimiento."
        
        try:
            from groq_llm import GroqLLM
            self.groq = GroqLLM()
            if self.groq.load():
                # Descargar Llama de VRAM
                self.logger.info("Activando modo rendimiento: descargando Llama local...")
                self.llama.unload_model()
                self.performance_mode = True
                self.logger.info("Modo rendimiento activado (usando Groq)")
                return "Modo rendimiento activado. Ahora uso Groq para responder más rápido."
            else:
                return "No pude activar el modo rendimiento. Revisa la API key de Groq."
        except Exception as e:
            self.logger.error(f"Error activando modo rendimiento: {e}")
            return f"Error: {str(e)[:50]}"
    
    def disable_performance_mode(self) -> str:
        """Desactiva el modo rendimiento (vuelve a Llama local)"""
        if not self.performance_mode:
            return "Ya estoy en modo local."
        
        try:
            # Recargar Llama
            self.logger.info("Desactivando modo rendimiento: recargando Llama local...")
            self.llama.load_model()
            self.performance_mode = False
            
            # Liberar Groq
            if self.groq:
                self.groq.unload()
                self.groq = None
            
            self.logger.info("Modo local activado (usando Llama)")
            return "Modo local activado. Vuelvo a usar mi cerebro local."
        except Exception as e:
            self.logger.error(f"Error desactivando modo rendimiento: {e}")
            return f"Error: {str(e)[:50]}"
    
    def get_current_llm(self):
        """Retorna el LLM activo (Groq o Llama)"""
        if self.performance_mode and self.groq:
            return self.groq
        return self.llama
    
    def load_models(self):
        """Carga todos los modelos en memoria"""
        self.logger.info("Cargando modelos...")
        
        # Iniciar monitor de memoria para detectar fugas
        try:
            from diagnostics.memory_monitor import get_monitor
            self._memory_monitor = get_monitor()
            self._memory_monitor.set_baseline()
            self._memory_monitor.start_periodic_logging()
            self.logger.info("Monitor de memoria iniciado")
        except ImportError:
            self._memory_monitor = None
            self.logger.debug("Monitor de memoria no disponible")
        except Exception as e:
            self._memory_monitor = None
            self.logger.warning(f"Error iniciando monitor de memoria: {e}")
        
        print("\n Cargando modelos (esto puede tardar 1-2 minutos)...")
        
        # Cargar Whisper
        print("  [1/4] Cargando Whisper...")
        self.whisper.load_model()
        
        # Cargar Llama
        print("  [2/4] Cargando Llama (esto puede tardar más)...")
        self.llama.load_model()
        
        # Cargar XTTS v2
        print("  [3/4] Cargando XTTS v2 con voz clonada...")
        self.tts.load_model()
        
        # Cargar sistema de memoria
        print("  [4/4] Cargando sistema de memoria...")
        self.memory.load()
        
        # Inicializar sistema de reflexión (después de memoria)
        try:
            from reflection_system import ReflectionSystem
            self.reflection = ReflectionSystem(self.memory, self.llama)
            self.reflection.load()
            self.logger.info("Sistema de reflexión inicializado")
        except Exception as e:
            self.logger.error(f"Error inicializando reflexión: {e}")
            self.reflection = None
        
        # Registrar estado final de carga
        if self._memory_monitor:
            self._memory_monitor.log_event("ALL_MODELS_LOADED")
        
        print(" Todos los modelos cargados\n")
    
    def process_voice_input(self, duration: float = None) -> dict:
        """
        Procesa una entrada de voz completa
        
        Args:
            duration: Duración de grabación en segundos (None = hasta Enter)
        
        Returns:
            Diccionario con 'transcript', 'response', 'audio'
        """
        try:
            # Obtener dispositivo de micrófono seleccionado
            device = getattr(self, 'selected_mic', None)
            
            # 1. Grabar audio del usuario (usando micrófono seleccionado)
            if duration:
                audio_input = self.audio_manager.record(duration=duration, device=device)
            else:
                audio_input = self.audio_manager.record_until_enter(device=device)
            
            if len(audio_input) == 0:
                self.logger.warning("No se grabó audio")
                return {"success": False, "error": "No audio recorded"}
            
            # 2. Transcribir con Whisper
            transcript = self.whisper.transcribe(audio_input)
            
            if not transcript:
                self.logger.warning("No se detectó habla")
                return {"success": False, "error": "No speech detected"}
            
            # 3. Detectar si es un comando o conversación normal
            response_text = self._process_transcript(transcript)
            
            # 4. Sintetizar respuesta
            print(f"\n Yui: {response_text}\n")
            self.tts.synthesize(response_text)
            
            # 5. Guardar conversación en memoria
            self.memory.add_conversation(transcript, response_text)
            
            return {
                "success": True,
                "transcript": transcript,
                "response": response_text
            }
            
        except KeyboardInterrupt:
            self.logger.info("Proceso interrumpido por el usuario")
            return {"success": False, "error": "Interrupted"}
        except Exception as e:
            self.logger.error(f"Error en pipeline: {e}")
            return {"success": False, "error": str(e)}
    
    def _process_transcript(self, transcript: str) -> str:
        """
        Procesa el transcript y detecta si es un comando o conversación
        
        Args:
            transcript: Texto transcrito del usuario
            
        Returns:
            Respuesta (del comando o del LLM)
        """
        text_lower = transcript.lower().strip()
        
        # Verificar si hay una confirmación pendiente (para abrir app)
        if hasattr(self, '_pending_app_confirmation') and self._pending_app_confirmation:
            pending_app = self._pending_app_confirmation
            self._pending_app_confirmation = None  # Limpiar estado
            
            # Verificar si el usuario dijo sí o no
            affirmative = ['sí', 'si', 'yes', 'ok', 'vale', 'dale', 'claro', 'obvio', 'afirmativo', 'correcto', 'eso', 'esa', 'exacto']
            negative = ['no', 'nop', 'nope', 'nel', 'negativo', 'otra', 'otro', 'diferente', 'cancela', 'cancelar']
            
            if any(word in text_lower for word in affirmative):
                # Usuario confirmó - abrir la app
                success, response = command_executor.open_app(pending_app, force=True)
                return response
            elif any(word in text_lower for word in negative):
                return "Entendido, no abriré nada. ¿Cuál aplicación buscabas?"
            else:
                # Respuesta no clara, preguntar de nuevo
                self._pending_app_confirmation = pending_app  # Restaurar
                return f"No entendí, ¿querías abrir {pending_app}? Dime sí o no."
        
        # Detectar comandos de modo rendimiento
        if any(phrase in text_lower for phrase in ['modo rendimiento', 'modo de rendimiento', 'modo rápido', 'modo rapido', 'modo turbo', 'activa groq', 'usa groq']):
            self.logger.info("Comando detectado: activar modo rendimiento")
            return self.enable_performance_mode()
        
        # Detectar comandos de modo local
        if any(phrase in text_lower for phrase in ['modo local', 'modo normal', 'modo lento']):
            self.logger.info("Comando detectado: desactivar modo rendimiento")
            return self.disable_performance_mode()
        
        # Detectar comando "abre X" / "abrir X"
        open_patterns = [
            r'(?:abre|abrir|abrí|abreme|abrirme|ejecuta|ejecutar|inicia|iniciar)\s+(.+)',
            r'(?:pon|poner|ponme)\s+(.+)',
        ]
        
        for pattern in open_patterns:
            match = re.search(pattern, text_lower)
            if match:
                app_name = match.group(1).strip()
                self.logger.info(f"Comando detectado: abrir '{app_name}'")
                success, response = command_executor.open_app(app_name)
                
                # Si success es None, es una sugerencia que necesita confirmación
                if success is None and response.startswith('suggest:'):
                    suggested_app = response.replace('suggest:', '')
                    self._pending_app_confirmation = suggested_app
                    return f"¿Querías abrir {suggested_app}?"
                
                return response
        
        # Detectar "qué hora es"
        if any(phrase in text_lower for phrase in ['qué hora', 'que hora', 'la hora', 'hora es']):
            self.logger.info("Comando detectado: obtener hora")
            _, response = command_executor.execute("get_time")
            return response
        
        # Detectar "qué fecha es" / "qué día es"
        if any(phrase in text_lower for phrase in ['qué fecha', 'que fecha', 'qué día', 'que día', 'que dia']):
            self.logger.info("Comando detectado: obtener fecha")
            _, response = command_executor.execute("get_date")
            return response
        
        # Detectar búsqueda web: "busca X", "qué es X", "quién es X"
        search_patterns = [
            # Variantes de "busca/buscar/busques" (incluye "que busques", "necesito que busques", etc.)
            r'(?:busca|buscas|buscar|busques|búscame|búscar|investiga|investigues)\s+(.+)',
            r'(?:que|necesito que|puedes|podrías)\s+(?:busques|buscar|investigues)\s+(.+)',
            r'(?:dime sobre|háblame de|cuéntame sobre|información sobre)\s+(.+)',
            r'(?:qué|que) (?:es|son|significa|significa)\s+(.+)',
            r'(?:quién|quien) (?:es|fue|era)\s+(.+)',
        ]
        
        for pattern in search_patterns:
            match = re.search(pattern, text_lower)
            if match:
                query = match.group(1).strip().rstrip('.,!?')
                
                # Excluir preguntas sobre Yui, su creador, o el usuario
                # Estas se responden del conocimiento del prompt, no buscar
                exclusion_keywords = ['yui', 'creador', 'creado', 'creaste', 'creó', 'edakzin', 'tú', 'tu']
                if any(kw in query.lower() for kw in exclusion_keywords):
                    self.logger.info(f"Pregunta sobre Yui/creador, no buscar: '{query}'")
                    break  # Salir del loop, dejar que el LLM responda
                
                self.logger.info(f"Comando detectado: buscar '{query}'")
                success, search_results = command_executor.web_search(query)
                
                if success:
                    # Pasar resultados al LLM para una respuesta natural
                    from datetime import datetime
                    fecha_actual = datetime.now().strftime("%d de %B de %Y")
                    
                    # Prompt simple y directo - el contexto viene del historial
                    prompt_with_context = f"""[BÚSQUEDA WEB - {fecha_actual}]
Resultados encontrados:
{search_results}

Responde brevemente usando esta información."""
                    
                    return self.get_current_llm().generate_response(prompt_with_context, use_history=True)
                else:
                    return search_results
        
        
        # Conversación normal - usar LLM con filtrado inteligente de memoria
        long_term_ctx = ""
        if should_query_long_term_memory(transcript, self.memory.session_history):
            long_term_ctx = self.memory.search_relevant_context(transcript, n_results=3)
            if long_term_ctx:
                logger.debug(f"ChromaDB consultado: {len(long_term_ctx)} chars")
        
        # Si hay contexto de largo plazo, incluirlo en el prompt
        if long_term_ctx:
            enriched_prompt = f"[Recuerdos relevantes]:\n{long_term_ctx}\n\n{transcript}"
            return self.get_current_llm().generate_response(enriched_prompt)
        else:
            return self.get_current_llm().generate_response(transcript)
    
    def run_interactive(self):
        """Modo interactivo continuo"""
        print("\n" + "=" * 70)
        print("MODO INTERACTIVO")
        print("=" * 70)
        print("Instrucciones:")
        print("  - Presiona Enter para empezar a grabar")
        print("  - Habla tu mensaje")
        print("  - Presiona Enter nuevamente para detener y procesar")
        print("  - Escribe 'salir' o presiona Ctrl+C para terminar")
        print("=" * 70 + "\n")
        
        while True:
            try:
                # Esperar comando del usuario
                cmd = input("Presiona Enter para hablar (o escribe 'salir' para terminar): ").strip().lower()
                
                if cmd in ['salir', 'exit', 'quit']:
                    print("\n ¡Hasta luego!")
                    break
                
                # Procesar entrada de voz
                result = self.process_voice_input(duration=None)
                
                if not result["success"]:
                    print(f" {result.get('error', 'Error desconocido')}")
                
            except KeyboardInterrupt:
                print("\n\n ¡Hasta luego!")
                break
            except Exception as e:
                self.logger.error(f"Error en modo interactivo: {e}")
                print(f" Error: {e}")
    
    def run_continuous(self):
        """Modo de escucha continua con VAD y wake word"""
        try:
            from continuous_listener import ContinuousListener
            
            # Obtener configuración de escucha
            listen_config = self.config.get('listening', {})
            
            # Crear listener continuo
            listener = ContinuousListener(
                yui_assistant=self,
                inactivity_timeout=listen_config.get('inactivity_timeout_seconds', 120),
                vad_threshold=listen_config.get('vad_threshold', 0.5),
                wake_word=listen_config.get('wake_word', 'hey_jarvis'),
                wake_word_threshold=listen_config.get('wake_word_threshold', 0.5),
                proactive_enabled=listen_config.get('proactive_comments_enabled', True),
                max_proactive=listen_config.get('max_proactive_comments', 3)
            )
            
            # Conectar command_executor para visión proactiva
            listener.command_executor = command_executor
            
            # Ejecutar en modo bloqueante
            listener.run_blocking()
            
        except ImportError as e:
            self.logger.error(f"Error importando módulos de escucha continua: {e}")
            print(f"\nError: Faltan dependencias para escucha continua")
            print(f"   Ejecuta: pip install openwakeword")
        except Exception as e:
            self.logger.error(f"Error en modo continuo: {e}")
            import traceback
            traceback.print_exc()
    
    def test_components(self):
        """Prueba cada componente individualmente"""
        print("\n" + "=" * 70)
        print("MODO PRUEBA DE COMPONENTES")
        print("=" * 70)
        
        # Probar audio
        print("\n[1/4] Probando grabación de audio...")
        input("  Presiona Enter para grabar 3 segundos de audio de prueba...")
        test_audio = self.audio_manager.record(duration=3.0)
        print("   Grabación completada")
        
        # Probar Whisper
        print("\n[2/4] Probando Whisper STT...")
        transcript = self.whisper.transcribe(test_audio)
        print(f"  Transcripción: '{transcript}'")
        
        # Probar Llama
        print("\n[3/4] Probando Llama LLM...")
        test_input = "Hola, ¿cómo estás?"
        response = self.llama.generate_response(test_input)
        print(f"  Respuesta: '{response}'")
        
        # Probar TTS (Coqui XTTS)
        print("\n[4/4] Probando Coqui TTS...")
        print("  Sintetizando respuesta...")
        self.tts.synthesize(response)
        
        print("\n Prueba de componentes completada")
        print("=" * 70)


def main():
    """Función principal"""
    try:
        # Crear asistente
        yui = YuiAssistant()
        
        # Cargar modelos
        yui.load_models()
        
        # Usar micrófono por defecto
        yui.selected_mic = None
        
        # Mostrar menú
        print("\nSelecciona un modo:")
        print("  1. Modo interactivo (presionar Enter para hablar)")
        print("  2. Prueba de componentes")
        print("  3. Una sola interacción")
        print("  4. Escucha continua (VAD + wake word) [NUEVO]")
        
        choice = input("\nOpción (1/2/3/4): ").strip()
        
        if choice == "1":
            yui.run_interactive()
        elif choice == "2":
            yui.test_components()
        elif choice == "3":
            print("\n Una sola interacción:")
            yui.process_voice_input(duration=None)
        elif choice == "4":
            yui.run_continuous()
        else:
            print("Opción no válida")
    
    except KeyboardInterrupt:
        print("\n\n ¡Hasta luego!")
    except Exception as e:
        print(f"\n Error fatal: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
