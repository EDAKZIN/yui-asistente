"""
Yui AI Assistant - Modo de Escucha Continua
Integra VAD, wake word, y máquina de estados para escucha activa
"""

import time
import threading
import logging
import random
from typing import Optional
import numpy as np

from state_machine import YuiStateMachine, YuiState
from vad_listener import VADListener
from wake_word import WhisperWakeWordDetector, SimpleNameDetector
from reminders import ReminderSystem
from emotion_detector import EmotionDetector
from special_events import SpecialEventsSystem
from vrm_config import VRMConfig

logger = logging.getLogger('Yui.Continuous')


class ContinuousListener:
    """
    Controlador de escucha continua
    Maneja la transición entre modos activo/reposo
    """
    
    def __init__(self, 
                 yui_assistant,
                 inactivity_timeout: float = 120.0,
                 vad_threshold: float = 0.5,
                 wake_word: str = "hey_jarvis",
                 wake_word_threshold: float = 0.5,
                 proactive_enabled: bool = True,
                 max_proactive: int = 3):
        """
        Inicializa el listener continuo
        
        Args:
            yui_assistant: Referencia al YuiAssistant principal
            inactivity_timeout: Segundos antes de comentario proactivo
            vad_threshold: Umbral de detección de voz
            wake_word: Palabra de activación
            wake_word_threshold: Umbral para wake word
            proactive_enabled: Si hacer comentarios proactivos
            max_proactive: Máximo de comentarios proactivos
        """
        self.yui = yui_assistant
        self.proactive_enabled = proactive_enabled
        
        # Máquina de estados
        self.state_machine = YuiStateMachine(inactivity_timeout=inactivity_timeout)
        self.state_machine.max_proactive_comments = max_proactive
        self.state_machine.set_callbacks(
            on_state_change=self._on_state_change,
            on_sleep=self._on_sleep,
            on_wake=self._on_wake
        )
        
        # VAD Listener
        self.vad = VADListener(
            threshold=vad_threshold,
            min_speech_duration=0.3,
            min_silence_duration=0.8
        )
        self.vad.set_callbacks(
            on_speech_start=self._on_speech_start,
            on_speech_end=self._on_speech_end
        )
        
        # Wake Word Detector (usa Whisper tiny para detectar 'Yui')
        self.wake_detector = WhisperWakeWordDetector(
            name="yui",
            chunk_duration=2.0
        )
        self.wake_detector.set_callback(self._on_wake_word_detected)
        
        # Detector simple de nombre (fallback)
        self.name_detector = SimpleNameDetector(name="yui")
        
        # Estado
        self.is_running = False
        self._proactive_thread = None
        self._stop_event = threading.Event()
        self._is_waking = False  # Flag para indicar que estamos en proceso de despertar
        
        # Referencia a command_executor (se setea después)
        self.command_executor = None
        
        # Audio del habla actual
        self._current_speech_audio: Optional[np.ndarray] = None
        
        # Sistema de recordatorios
        self.reminders = ReminderSystem(on_reminder_triggered=self._on_reminder_triggered)
        
        # Detector de emociones para expresiones del modelo
        self.emotion_detector = EmotionDetector()
        
        # Configuracion VRM centralizada (lee model-config.json)
        self.vrm_config = VRMConfig.get_instance()
        
        # Sistema de eventos especiales (Navidad, cumpleanos, etc.)
        self.special_events = SpecialEventsSystem(on_event_triggered=self._on_special_event)
        
        # Referencia al GUI API (para enviar actualizaciones al frontend)
        self.gui_api = None
        
        # Estadísticas de sesión
        self._start_time = time.time()
        self.conversation_count = 0
        
        logger.info("ContinuousListener inicializado")
    
    def set_gui_api(self, gui_api):
        """Establece la referencia al GUI API para actualizaciones en tiempo real"""
        self.gui_api = gui_api
        logger.info("GUI API conectado a ContinuousListener")
        
        # Conectar callback del TTS para subtitulos sincronizados
        # El callback se llama justo antes de reproducir el audio
        if hasattr(self.yui, 'tts'):
            def on_tts_ready(text):
                self._notify_gui('notify_tts_start', text)
            self.yui.tts.set_synthesis_complete_callback(on_tts_ready)
            logger.info("Callback TTS conectado para subtitulos sincronizados")
    
    def _notify_gui(self, method: str, *args):
        """Envía notificación al GUI si está conectado"""
        if self.gui_api:
            try:
                func = getattr(self.gui_api, method, None)
                if func:
                    func(*args)
            except Exception as e:
                logger.debug(f"Error notificando GUI: {e}")
    
    def _detect_and_apply_expression(self, response_text: str):
        """Detecta emocion en la respuesta y aplica expresion al modelo"""
        try:
            # Detectar emocion
            emotion = self.emotion_detector.detect(response_text)
            
            # Mapear a expresion del modelo (desde model-config.json)
            expression = self.vrm_config.get_expression(emotion)
            
            logger.info(f"Emocion detectada: {emotion} -> expresion: {expression}")
            
            # Enviar al frontend
            self._notify_gui('notify_expression', expression)
            
        except Exception as e:
            logger.warning(f"Error detectando/aplicando expresion: {e}")
            # En caso de error, aplicar neutral
            self._notify_gui('notify_expression', 'neutral')
    
    def _on_state_change(self, old_state: YuiState, new_state: YuiState):
        """Callback cuando cambia el estado"""
        logger.info(f"Estado cambiado: {old_state.value} → {new_state.value}")
        # Notificar a la GUI
        self._notify_gui('notify_state_change', new_state.value)
    
    def _on_sleep(self):
        """Callback al entrar en modo reposo"""
        logger.info("Entrando en modo REPOSO - liberando recursos...")
        
        
        # Log VRAM inicial
        try:
            import torch
            if torch.cuda.is_available():
                vram_inicial = torch.cuda.memory_allocated(0) / 1024**3
                logger.info(f"  VRAM al inicio de reposo: {vram_inicial:.2f}GB")
        except:
            pass
        
        # Ejecutar reflexión ANTES de descargar el LLM
        try:
            if hasattr(self.yui, 'reflection') and self.yui.reflection:
                logger.info("  Ejecutando reflexión antes de dormir...")
                insights = self.yui.reflection.reflect_on_session()
                if insights:
                    logger.info(f"  Reflexión completada: {len(insights)} insights guardados")
        except Exception as e:
            logger.error(f"Error en reflexión: {e}")
        
        # Detener VAD
        self.vad.stop()
        
        # Descargar modelos pesados para liberar VRAM/RAM
        import torch
        import gc
        
        try:
            # 1. Descargar LLM (Llama o Groq)
            if hasattr(self.yui, 'groq') and self.yui.groq is not None and hasattr(self.yui.groq, 'unload'):
                logger.info("  Descargando cliente Groq...")
                self.yui.groq.unload()
            
            if hasattr(self.yui, 'llama') and self.yui.llama is not None and self.yui.llama.model is not None:
                logger.info("  Descargando modelo LLM local...")
                self.yui.llama.unload_model()
                gc.collect()
                torch.cuda.empty_cache()
                vram_post_llm = torch.cuda.memory_allocated(0) / 1024**3
                logger.info(f"  VRAM después de descargar LLM: {vram_post_llm:.2f}GB")

            # 2. Detener proceso TTS (libera toda la VRAM del TTS)
            if hasattr(self.yui, 'tts') and self.yui.tts is not None:
                logger.info("  Deteniendo proceso TTS...")
                self.yui.tts.shutdown()
                gc.collect()
                torch.cuda.empty_cache()
                vram_post_tts = torch.cuda.memory_allocated(0) / 1024**3
                logger.info(f"  VRAM después de detener TTS: {vram_post_tts:.2f}GB")
            
            # 3. Descargar Whisper STT (libera ~1.5GB VRAM)
            if hasattr(self.yui, 'whisper') and self.yui.whisper is not None:
                logger.info("  Descargando modelo Whisper STT...")
                self.yui.whisper.unload_model()
                gc.collect()
                torch.cuda.empty_cache()
                vram_post_whisper = torch.cuda.memory_allocated(0) / 1024**3
                logger.info(f"  VRAM después de descargar Whisper: {vram_post_whisper:.2f}GB")
            
            # Limpiar cache CUDA agresivamente
            gc.collect()
            gc.collect()  # Doble collect
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                vram_final = torch.cuda.memory_allocated(0) / 1024**3
                vram_reserved = torch.cuda.memory_reserved(0) / 1024**3
                logger.info(f"  VRAM final: {vram_final:.2f}GB (reservada por PyTorch: {vram_reserved:.2f}GB)")
            
        except Exception as e:
            logger.error(f"Error descargando modelos: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # Iniciar wake word detector (carga Whisper base ~1GB)
        # Solo si no estamos muteados
        if self.gui_api and self.gui_api._is_muted:
            logger.info("  Modo muteado activo - wake detector NO iniciado")
        else:
            logger.info("  Iniciando wake word detector...")
            self.wake_detector.start()
        
        # Log VRAM con wake detector
        try:
            if torch.cuda.is_available():
                vram_con_wake = torch.cuda.memory_allocated(0) / 1024**3
                logger.info(f"  VRAM con wake detector: {vram_con_wake:.2f}GB")
        except:
            pass
        
        logger.info("Modo REPOSO activo - solo escuchando wake word")
    
    def _on_wake(self):
        """Callback al despertar del modo reposo"""
        logger.info("Despertando del modo REPOSO...")
        print("\n[DESPERTANDO...]")
        
        # CRÍTICO: Bloquear comentarios proactivos mientras recargamos modelos
        self._is_waking = True
        
        # Notificar GUI que estamos despertando
        self._notify_gui('notify_state_change', 'waking')
        
        # Detener wake word detector
        logger.info("  Deteniendo wake word detector...")
        try:
            self.wake_detector.stop()
            logger.debug("  Wake word detector detenido correctamente")
        except Exception as e:
            logger.error(f"  Error deteniendo wake word detector: {e}")
        
        # Descargar modelo wake word para liberar VRAM (ahora usa OpenAI Whisper, no crash)
        logger.info("  Descargando modelo Whisper base (wake word)...")
        try:
            self.wake_detector.unload_model()
            logger.info("  Modelo wake word descargado correctamente")
        except Exception as e:
            logger.error(f"  Error descargando modelo wake word: {e}")
        
        # Recargar modelos principales según el modo previo
        try:
            logger.info("  Recargando modelo Whisper medium (STT)...")
            print("  Recargando Whisper...")
            self.yui.whisper.load_model()
            
            # RESTAURAR ESTADO EXACTO (Local o Groq)
            if self.yui.performance_mode:
                logger.info("  Despertando en MODO RENDIMIENTO (Groq)...")
                print("  Conectando a Groq (Modo Rendimiento)...")
                # Asegurar que la instancia de Groq exista
                if self.yui.groq is None:
                    try:
                        from groq_llm import GroqLLM
                        self.yui.groq = GroqLLM()
                    except ImportError as e:
                        logger.error(f"No se pudo importar GroqLLM: {e}")
                        self.yui.performance_mode = False
                
                if self.yui.groq.load():
                    logger.info("  Groq recargado correctamente")
                else:
                    logger.warning("  Fallo al recargar Groq, volviendo a local...")
                    self.yui.performance_mode = False
                    self.yui.llama.load_model()
            else:
                logger.info("  Despertando en MODO LOCAL (Llama)...")
                print("  Recargando LLM Local...")
                self.yui.llama.load_model()
                logger.debug("  LLM recargado correctamente")
            
            logger.info("  Recargando modelo TTS...")
            print("  Recargando TTS...")
            self.yui.tts.load_model()
            logger.debug("  TTS recargado correctamente")
            
        except Exception as e:
            logger.error(f"Error recargando modelos: {e}")
            import traceback
            logger.error(f"Traceback completo:\n{traceback.format_exc()}")
        
        # Reiniciar VAD solo si no esta muteado
        logger.info("  Reiniciando VAD...")
        try:
            # Verificar si el usuario tiene mute activado
            is_muted = False
            if self.gui_api and hasattr(self.gui_api, '_is_muted'):
                is_muted = self.gui_api._is_muted
            
            if is_muted:
                logger.info("  VAD NO reiniciado (usuario está muteado)")
            else:
                self.vad.start()
                logger.debug("  VAD reiniciado correctamente")
        except Exception as e:
            logger.error(f"  Error reiniciando VAD: {e}")
            import traceback
            logger.error(f"Traceback:\n{traceback.format_exc()}")
        
        # Liberar flag - modelos cargados, listo para comentarios proactivos
        self._is_waking = False
        
        logger.info("Modo ACTIVO restaurado")
        print("[ACTIVO - Listo para escuchar]\n")
    
    def _on_speech_start(self):
        """Callback cuando inicia el habla"""
        if self.state_machine.is_sleeping:
            return
        
        logger.debug("Inicio de habla detectado")
        self.state_machine.transition_to(YuiState.LISTENING)
        print("\n[ESCUCHANDO...]")
    
    def _on_reminder_triggered(self, reminder):
        """Callback cuando un recordatorio se activa"""
        logger.info(f"Recordatorio activado: {reminder.message}")
        
        # Esperar a que el sistema esté libre (no procesando, no hablando TTS)
        max_wait = 30  # Máximo 30 segundos de espera
        waited = 0
        while waited < max_wait:
            is_busy = (
                self.state_machine.state != YuiState.ACTIVE or
                (hasattr(self.yui, 'tts') and self.yui.tts._is_playing)
            )
            if not is_busy:
                break
            logger.debug(f"Sistema ocupado, esperando para recordatorio... ({waited}s)")
            time.sleep(1)
            waited += 1
        
        if waited >= max_wait:
            logger.warning("Timeout esperando sistema libre, lanzando recordatorio de todas formas")
        
        # Generar respuesta natural usando el LLM si está disponible
        try:
            if hasattr(self.yui.llama, 'model') and self.yui.llama.model:
                # Prompt claro para que el LLM entienda que es un ANUNCIO, no crear uno nuevo
                prompt = f"""El usuario te pidió que le recordaras "{reminder.message}". 
Ya pasó el tiempo y ahora debes AVISARLE que es momento de hacerlo.
Responde de forma amigable y breve (1-2 oraciones) recordándole que debe: {reminder.message}
NO ofrezcas poner otro recordatorio. Solo avísale que ya es hora."""
                response = self.yui.get_current_llm().generate_response(prompt)
                
                # Verificar que no sea una respuesta confusa
                if 'minutos' in response.lower() and 'recordar' in response.lower():
                    # El LLM se confundió, usar fallback
                    response = f"¡Oye! Ya es hora de {reminder.message}"
            else:
                # Fallback si el LLM no está cargado
                response = f"¡Hey! Es hora de {reminder.message}"
        except Exception as e:
            logger.warning(f"Error generando recordatorio natural: {e}")
            response = f"¡Hey! Recuerda: {reminder.message}"
        
        print(f"\n[RECORDATORIO] Yui: {response}")
        self._notify_gui('notify_response', response)
        
        # Sintetizar con TTS
        logger.info(f"Recordatorio - intentando sintetizar: '{response[:50]}...'")
        try:
            # Cliente TTS WebSocket
            if self.yui.tts:
                logger.debug("TTS disponible, sintetizando...")
                self.yui.tts.synthesize(response)
                logger.info("Recordatorio sintetizado correctamente")
            else:
                logger.warning("TTS no disponible para recordatorio")
        except Exception as e:
            logger.error(f"Error sintetizando recordatorio: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
    def _on_special_event(self, event_type: str, prompt_hint: str, expression: str):
        """Callback cuando se dispara un evento especial (Navidad, cumpleanos, etc.)
        
        Ahora genera el mensaje dinamicamente usando el LLM con el prompt_hint
        """
        logger.info(f"Evento especial activado: {event_type}")
        
        # Generar mensaje dinamico con LLM
        try:
            # Usar el LLM activo (local o Groq) para generar el mensaje
            llm = self.yui.groq if self.yui.performance_mode and self.yui.groq else self.yui.llama
            
            # Prompt para que el LLM genere un mensaje de evento especial
            event_prompt = f"""[EVENTO ESPECIAL: {event_type}]
{prompt_hint}
Genera un mensaje corto y emotivo (2-3 oraciones maximo). 
Habla directamente a EDAKZIN en segunda persona.
No uses asteriscos ni descripciones de acciones."""
            
            message = llm.generate_response(event_prompt)
            
            if not message or len(message.strip()) < 5:
                # Fallback si el LLM falla
                message = f"¡Hola! Hoy es un dia especial: {event_type}."
                logger.warning(f"LLM no genero mensaje para evento, usando fallback")
            
            logger.info(f"Mensaje generado para {event_type}: {message[:50]}...")
            
        except Exception as e:
            logger.error(f"Error generando mensaje de evento con LLM: {e}")
            message = f"¡Hola! Hoy es un dia especial."
        
        print(f"\n[EVENTO ESPECIAL] Yui: {message}")
        self._notify_gui('notify_response', message)
        
        # Aplicar expresion correspondiente
        expr_name = self.vrm_config.get_expression(expression)
        self._notify_gui('notify_expression', expr_name)
        
        # Sintetizar con TTS
        try:
            if self.yui.tts:
                self.yui.tts.synthesize(message)
                logger.info("Evento especial sintetizado correctamente")
            else:
                logger.warning("TTS no disponible para evento especial")
        except Exception as e:
            logger.error(f"Error sintetizando evento especial: {e}")
    
    def _on_speech_end(self, audio: np.ndarray):
        """Callback cuando termina el habla"""
        if self.state_machine.is_sleeping:
            return
        
        logger.info(f"Habla completada: {len(audio)} samples ({len(audio)/16000:.2f}s)")
        
        # Cambiar a estado PROCESSING
        self.state_machine.transition_to(YuiState.PROCESSING)
        
        # Procesar audio en thread separado para no bloquear
        threading.Thread(target=self._process_speech, args=(audio,), daemon=True).start()
    
    def _process_speech(self, audio: np.ndarray):
        """Procesa el audio capturado"""
        try:
            # 1. Transcribir
            transcript = self.yui.whisper.transcribe(audio)
            
            if not transcript or len(transcript.strip()) < 2:
                logger.debug("Transcripcion vacia o muy corta")
                self.state_machine.transition_to(YuiState.ACTIVE)
                return
            
            text_lower = transcript.lower().strip()
            
            # 2. Verificar si es para Yui (mencion o comando directo)
            is_for_yui = self._is_message_for_yui(text_lower)
            
            if not is_for_yui:
                # No es para Yui, ignorar
                logger.debug(f"Ignorando (no es para Yui): '{transcript[:40]}...'")
                self.state_machine.transition_to(YuiState.ACTIVE)
                return
            
            print(f"\nTu: {transcript}")
            # Notificar transcripción a la GUI
            self._notify_gui('notify_transcript', transcript)
            
            # 3. Verificar si es comando de reposo
            if self.state_machine.check_sleep_trigger(transcript):
                # Obtener respuesta de despedida
                response = self.state_machine.get_sleep_response()
                print(f"\nYui: {response}")
                self._notify_gui('notify_response', response)
                self.yui.tts.synthesize(response)
                
                # Entrar en reposo
                self.state_machine.transition_to(YuiState.SLEEPING)
                return
            
            # 3.5 Verificar si es un recordatorio
            reminder_data = self.reminders.parse_reminder(text_lower)
            if reminder_data:
                try:
                    # Es un recordatorio
                    delay = reminder_data['delay_seconds']
                    message = reminder_data['message']
                    
                    if message and len(message) >= 2 and message != "algo":
                        reminder = self.reminders.add_reminder(message, delay)
                        time_str = self.reminders.format_time_remaining(delay)
                        
                        # Respuesta de confirmación
                        response = f"Entendido, te recordaré {message} en {time_str}."
                    else:
                        # No se pudo extraer el mensaje claramente
                        response = "Perdón, no entendí bien qué quieres que te recuerde. ¿Puedes repetirlo de otra forma?"
                        logger.warning(f"Recordatorio con mensaje vacío o genérico: '{message}'")
                    
                    print(f"\nYui: {response}")
                    self._notify_gui('notify_response', response)
                    self.yui.tts.synthesize(response)
                    
                except Exception as e:
                    logger.error(f"Error creando recordatorio: {e}")
                    response = "Ups, tuve un problema al poner el recordatorio. ¿Puedes intentarlo de nuevo?"
                    print(f"\nYui: {response}")
                    self._notify_gui('notify_response', response)
                    self.yui.tts.synthesize(response)
                
                # Volver a estado activo
                self.state_machine.reset_activity()
                self.state_machine.transition_to(YuiState.ACTIVE)
                return
            
            # 4. Procesar normalmente
            response = self.yui._process_transcript(transcript)
            
            # Sintetizar respuesta
            print(f"\nYui: {response}")
            logger.info(f"Respuesta de Yui: '{response[:50]}...'")
            
            self._notify_gui('notify_response', response)
            
            # Detectar emocion y aplicar expresion al modelo
            self._detect_and_apply_expression(response)
            
            self.yui.tts.synthesize(response)
            
            # 6. Auto-limpiar memoria si respuesta es repetitiva
            self.yui.memory.auto_clean_if_repetitive(response)
            
            # 7. Guardar en memoria de CORTO PLAZO (sesión) para continuidad
            self.yui.memory.add_to_session(transcript, response)
            
            
            # 7.6 Incrementar contador de conversaciones
            self.conversation_count += 1
            
            # 8. Guardar en memoria de LARGO PLAZO (ChromaDB) si es relevante
            self.yui.memory.add_conversation(transcript, response)
            
            # 9. Actualizar contexto de conversación para detección de continuidad
            response_keywords = self._extract_keywords(response.lower())
            if hasattr(self, '_last_conversation_keywords'):
                self._last_conversation_keywords.update(response_keywords)
            else:
                self._last_conversation_keywords = response_keywords
            self._last_yui_mention_time = time.time()  # Renovar tiempo de conversación
            
            # 10. Volver a estado activo
            self.state_machine.reset_activity()
            self.state_machine.transition_to(YuiState.ACTIVE)
            
        except Exception as e:
            logger.error(f"Error procesando habla: {e}")
            self.state_machine.transition_to(YuiState.ACTIVE)
    
    def _extract_keywords(self, text: str) -> set:
        """Extrae palabras clave significativas de un texto"""
        # Palabras comunes a ignorar
        stop_words = {
            "el", "la", "los", "las", "un", "una", "unos", "unas",
            "de", "del", "en", "con", "por", "para", "que", "qué",
            "es", "son", "está", "están", "ser", "estar", "hay",
            "y", "o", "pero", "si", "no", "sí", "muy", "más",
            "me", "te", "se", "nos", "lo", "le", "les",
            "yui", "oye", "hey", "hola", "gracias", "ok", "vale",
            "cuánto", "cuánta", "cuántos", "cuántas", "cómo", "dónde",
            "uy", "a", "al", "como", "donde", "cuando",
        }
        
        # Extraer palabras significativas (4+ caracteres, no stop words)
        words = set()
        for word in text.lower().split():
            # Limpiar puntuación
            word = ''.join(c for c in word if c.isalnum())
            if len(word) >= 4 and word not in stop_words:
                words.add(word)
        
        return words
    
    def _is_related_to_conversation(self, text: str) -> bool:
        """Verifica si el texto está relacionado con la conversación anterior"""
        if not hasattr(self, '_last_conversation_keywords') or not self._last_conversation_keywords:
            return True  # Sin contexto previo, aceptar
        
        # NUEVO: Si Yui hizo una pregunta en su última respuesta, aceptar cualquier respuesta
        try:
            last_exchange = self.yui.memory.get_last_exchange()
            if last_exchange:
                last_yui_response = last_exchange.get('assistant', '').lower()
                # Si la última respuesta fue una pregunta, aceptar la respuesta del usuario
                if '?' in last_yui_response:
                    logger.debug("Aceptando respuesta porque Yui hizo una pregunta")
                    return True
        except:
            pass  # Sin memoria de sesión, continuar con lógica normal
        
        current_keywords = self._extract_keywords(text)
        
        # Verificar si comparten al menos una palabra clave
        shared = current_keywords & self._last_conversation_keywords
        if shared:
            logger.debug(f"Palabras compartidas: {shared}")
            return True
        
        # Frases de continuación que siempre son válidas (respuestas a preguntas, etc.)
        continuation_phrases = [
            # Conectores
            "y ", "pero ", "entonces ", "además ", "también ",
            # Confirmaciones
            "gracias", "ok", "vale", "entendido", "perfecto",
            "sí", "no", "claro", "bien", "bueno", "ajá", "aja",
            # Repetición
            "repite", "otra vez", "de nuevo", "qué dijiste",
            # Respuestas a opciones (como "A o B?")
            "el primero", "el segundo", "la primera", "la segunda",
            "uno", "dos", "tres", "ninguno", "ambos", "todos",
            "ese", "esa", "eso", "esto", "aquel", "aquella",
            # Respuestas cortas típicas
            "como ", "así ", "del ", "de la ", "en el ", "en la ",
            "lo que ", "eso que ", "lo de ", "la de ", "el de ",
        ]
        
        for phrase in continuation_phrases:
            if phrase in text.lower():
                return True
        
        return False
    
    def _is_message_for_yui(self, text_lower: str) -> bool:
        """
        Verifica si el mensaje es para Yui
        
        Returns:
            True si menciona a Yui o es un comando directo
        """
        # Variaciones del nombre (incluyendo errores comunes de Whisper vistos en logs)
        name_mentions = [
            "yui", "oye yui", "hey yui", "hola yui", "ey yui",
            # Errores comunes de Whisper
            "uy,", "uy ", "uy?", "uy!",  # 'Uy' es muy común
            "yuhi", "yuchi", "llui", "lui", "yuei",
            "joey", "jui", "yoy", "y hoy ",  # Joey apareció en logs
            "yo ya ",  # 'Yo ya abre' en vez de 'Yui abre'
        ]
        
        # Verificar mencion del nombre
        for name in name_mentions:
            if name in text_lower:
                logger.debug(f"Mencion detectada: '{name}'")
                # Marcar que estamos en modo conversación
                self._last_yui_mention_time = time.time()
                self._last_conversation_keywords = self._extract_keywords(text_lower)
                return True
        
        # Modo conversación: si mencionaron a Yui recientemente (30s), verificar contexto
        if hasattr(self, '_last_yui_mention_time'):
            time_since_mention = time.time() - self._last_yui_mention_time
            if time_since_mention < 30.0:
                # Verificar si el mensaje está relacionado con el tema anterior
                if self._is_related_to_conversation(text_lower):
                    logger.debug(f"Modo conversación activo ({time_since_mention:.1f}s, tema relacionado)")
                    self._last_yui_mention_time = time.time()  # Renovar tiempo
                    self._last_conversation_keywords = self._extract_keywords(text_lower)
                    return True
                else:
                    logger.debug(f"Mensaje ignorado (tema no relacionado con conversación)")
                    return False
        
        # Patrones de comandos directos (sin necesidad de mencionar nombre)
        command_patterns = [
            # Abrir apps
            "abre ", "abrir ", "abrí ", "abreme ", "ejecuta ", "inicia ",
            "pon ", "poner ", "ponme ",
            # Hora/Fecha
            "qué hora", "que hora", "la hora",
            "qué fecha", "que fecha", "qué día", "que día", "que dia",
            # Busqueda
            "busca ", "búscame ", "investiga ", "dime sobre ",
            "qué es ", "que es ", "quién es ", "quien es ",
            # Reposo
            "descansa", "no te necesito", "duerme", "reposo",
        ]
        
        for pattern in command_patterns:
            if pattern in text_lower:
                logger.debug(f"Comando directo detectado: '{pattern}'")
                return True
        
        return False
    
    def _on_wake_word_detected(self):
        """Callback cuando se detecta wake word"""
        logger.info("¡Wake word detectado!")
        
        # CRÍTICO: Ejecutar en thread separado para no bloquear el wake detector
        # Esto evita conflictos al descargar el modelo mientras estamos en su callback
        def _wake_async():
            try:
                # Obtener respuesta de despertar
                response = self.state_machine.get_wake_response()
                
                # Despertar (esto recarga los modelos)
                self.state_machine.transition_to(YuiState.ACTIVE)
                
                # Responder (ahora TTS está cargado)
                print(f"\nYui: {response}")
                self.yui.tts.synthesize(response)
            except Exception as e:
                logger.error(f"Error en despertar async: {e}")
                import traceback
                logger.error(traceback.format_exc())
        
        wake_thread = threading.Thread(target=_wake_async, daemon=True)
        wake_thread.start()
    
    def _proactive_loop(self):
        """Loop para comentarios proactivos GENERADOS por LLM"""
        logger.info("Iniciando loop de comentarios proactivos (LLM)")
        
        while not self._stop_event.is_set():
            try:
                # Esperar un poco (interrumpible)
                if self._stop_event.wait(timeout=10):
                    break
                
                # NO hacer comentarios si estamos despertando (modelos no cargados aún)
                if self._is_waking:
                    continue
                
                # Verificar si debe hacer comentario proactivo
                if self.proactive_enabled and self.state_machine.should_make_proactive_comment():
                    # Cambiar a estado PROACTIVE
                    self.state_machine.transition_to(YuiState.PROACTIVE)
                    
                    # Obtener contexto de memoria para "estado emocional"
                    # Usa get_smart_context que PRIORIZA la sesión actual sobre memoria antigua
                    memory_context = ""
                    try:
                        memory_context = self.yui.memory.get_smart_context(
                            "conversación actual con el usuario", min_relevance=0.7
                        )
                    except:
                        pass
                    
                    # Generar comentario dinámico usando LLM con Ghost Prompting
                    # Esto mantiene la personalidad completa de Yui sin contaminar historial
                    try:
                        llm = self.yui.get_current_llm()
                        
                        # Verificar si es LLM local (tiene generate_proactive)
                        if hasattr(llm, 'generate_proactive'):
                            comment = llm.generate_proactive(
                                task_instruction="Genera un comentario casual para llamar la atención del usuario",
                                memory_context=memory_context
                            )
                        else:
                            # Fallback para Groq u otros LLMs
                            prompt = f"""Eres Yui. El usuario no te ha hablado en un rato.
{f"[Recuerdos]: {memory_context}" if memory_context else ""}
Genera UN comentario corto (máximo 10 palabras) casual."""
                            comment = llm.generate_response(prompt, use_history=False)
                        
                        if comment:
                            self.state_machine.proactive_comment_count += 1
                            print(f"\nYui: {comment}")
                            self.yui.tts.synthesize(comment)
                    except Exception as e:
                        logger.error(f"Error generando comentario proactivo: {e}")
                    
                    # Resetear timer
                    self.state_machine.last_activity_time = time.time()
                    
                    # Volver a activo
                    self.state_machine.transition_to(YuiState.ACTIVE)
                
            except Exception as e:
                logger.error(f"Error en loop proactivo: {e}")
        
        logger.info("Loop proactivo terminado")
    

    
    def start(self):
        """Inicia el modo de escucha continua"""
        if self.is_running:
            logger.warning("ContinuousListener ya está corriendo")
            return
        
        logger.info("Iniciando escucha continua...")
        
        # Cargar modelos VAD
        self.vad.load_model()
        
        # Configurar estado inicial
        self.state_machine.transition_to(YuiState.ACTIVE)
        self._stop_event.clear()
        
        
        # Iniciar VAD
        self.vad.start()
        
        # Iniciar thread proactivo
        if self.proactive_enabled:
            self._proactive_thread = threading.Thread(
                target=self._proactive_loop, 
                daemon=True
            )
            self._proactive_thread.start()
        

        
        # Iniciar sistema de recordatorios
        self.reminders.start()
        
        # Iniciar sistema de eventos especiales (Navidad, cumpleanos, etc.)
        self.special_events.start()
        
        self.is_running = True
        
        print("\n" + "=" * 60)
        print("MODO ESCUCHA CONTINUA ACTIVO")
        print("=" * 60)
        print("  • Habla cuando quieras, Yui te escucha automáticamente")
        print("  • Di 'descansa' o 'no te necesito' para modo reposo")
        print("  • Di 'Yui' para despertarla del reposo")
        print("  • Presiona Ctrl+C para salir")
        print("=" * 60 + "\n")
        
        logger.info("Escucha continua iniciada")
    
    def stop(self):
        """Detiene el modo de escucha continua"""
        if not self.is_running:
            return
        
        logger.info("Deteniendo escucha continua...")
        
        # Señalar stop
        self._stop_event.set()
        
        # Detener componentes
        self.vad.stop()
        self.wake_detector.stop()
        
        # Esperar thread proactivo
        if self._proactive_thread:
            self._proactive_thread.join(timeout=2.0)
            self._proactive_thread = None
        
        # Detener sistema de recordatorios
        self.reminders.stop()
        
        # Detener sistema de eventos especiales
        self.special_events.stop()
        
        # Detener TTS completamente (libera threads de audio)
        if hasattr(self.yui, 'tts'):
            self.yui.tts.shutdown()
        
        self.is_running = False
        logger.info("Escucha continua detenida")
    
    def run_blocking(self):
        """Ejecuta el modo continuo bloqueando hasta Ctrl+C"""
        self.start()
        
        try:
            while self.is_running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n\nHasta luego!")
        finally:
            self.stop()
