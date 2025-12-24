"""
Yui AI Assistant - Modo de Escucha Continua
Integra VAD, wake word, y máquina de estados para escucha activa
"""

import time
import threading
import logging
from typing import Optional
import numpy as np

from state_machine import YuiStateMachine, YuiState
from vad_listener import VADListener
from wake_word import WhisperWakeWordDetector, SimpleNameDetector
from reminders import ReminderSystem

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
        
        # Audio del habla actual
        self._current_speech_audio: Optional[np.ndarray] = None
        
        # Sistema de recordatorios
        self.reminders = ReminderSystem(on_reminder_triggered=self._on_reminder_triggered)
        
        # Referencia al GUI API (para enviar actualizaciones al frontend)
        self.gui_api = None
        
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
    
    def _on_state_change(self, old_state: YuiState, new_state: YuiState):
        """Callback cuando cambia el estado"""
        logger.info(f"Estado cambiado: {old_state.value} → {new_state.value}")
        # Notificar a la GUI
        self._notify_gui('notify_state_change', new_state.value)
    
    def _on_sleep(self):
        """Callback al entrar en modo reposo"""
        logger.info("Entrando en modo REPOSO - liberando recursos...")
        
        # Detener VAD
        self.vad.stop()
        
        # Descargar modelos pesados para liberar VRAM
        try:
            # Descargar LLM
            if hasattr(self.yui, 'llama') and self.yui.llama.model is not None:
                logger.info("  Descargando modelo LLM...")
                del self.yui.llama.model
                self.yui.llama.model = None
                if hasattr(self.yui.llama, 'tokenizer'):
                    del self.yui.llama.tokenizer
                    self.yui.llama.tokenizer = None
                
            # Descargar TTS (CoquiTTS usa 'tts' no 'model')
            if hasattr(self.yui, 'tts') and hasattr(self.yui.tts, 'tts') and self.yui.tts.tts is not None:
                logger.info("  Descargando modelo TTS...")
                del self.yui.tts.tts
                self.yui.tts.tts = None
            
            # Limpiar cache CUDA
            import torch
            import gc
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
                torch.cuda.synchronize()
                logger.info("  Cache CUDA liberada")
            
        except Exception as e:
            logger.error(f"Error descargando modelos: {e}")
        
        # Iniciar wake word detector
        self.wake_detector.start()
        
        logger.info("Modo REPOSO activo - solo escuchando wake word")
    
    def _on_wake(self):
        """Callback al despertar del modo reposo"""
        logger.info("Despertando del modo REPOSO...")
        print("\n[DESPERTANDO...]")
        
        # Notificar GUI que estamos despertando
        self._notify_gui('notify_state_change', 'waking')
        
        # Detener wake word detector
        logger.info("  Deteniendo wake word detector...")
        try:
            self.wake_detector.stop()
            logger.debug("  Wake word detector detenido correctamente")
        except Exception as e:
            logger.error(f"  Error deteniendo wake word detector: {e}")
        
        # Descargar modelo wake word para liberar VRAM
        logger.info("  Descargando modelo Whisper base (wake word)...")
        try:
            self.wake_detector.unload_model()
            logger.debug("  Modelo wake word descargado correctamente")
        except Exception as e:
            logger.error(f"  Error descargando modelo wake word: {e}")
        
        # Recargar modelos principales
        try:
            logger.info("  Recargando modelo Whisper medium (STT)...")
            print("  Recargando Whisper...")
            self.yui.whisper.load_model()
            logger.debug("  Whisper recargado correctamente")
            
            logger.info("  Recargando modelo LLM...")
            print("  Recargando LLM...")
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
        
        # Generar respuesta natural usando el LLM si está disponible
        try:
            if hasattr(self.yui.llama, 'model') and self.yui.llama.model:
                # Prompt claro para que el LLM entienda que es un ANUNCIO, no crear uno nuevo
                prompt = f"""El usuario te pidió que le recordaras "{reminder.message}". 
Ya pasó el tiempo y ahora debes AVISARLE que es momento de hacerlo.
Responde de forma amigable y breve (1-2 oraciones) recordándole que debe: {reminder.message}
NO ofrezcas poner otro recordatorio. Solo avísale que ya es hora."""
                response = self.yui.llama.generate_response(prompt)
                
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
            # CoquiTTS usa 'tts' no 'model'
            if self.yui.tts.tts:
                logger.debug("TTS disponible, sintetizando...")
                self.yui.tts.synthesize(response)
                logger.info("Recordatorio sintetizado correctamente")
            else:
                logger.warning("TTS no disponible para recordatorio")
        except Exception as e:
            logger.error(f"Error sintetizando recordatorio: {e}")
            import traceback
            logger.error(traceback.format_exc())
    
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
            
            self.yui.tts.synthesize(response)
            
            # 6. Auto-limpiar memoria si respuesta es repetitiva
            self.yui.memory.auto_clean_if_repetitive(response)
            
            # 7. Guardar en memoria
            self.yui.memory.add_conversation(transcript, response)
            
            # 7. Volver a estado activo
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
        
        current_keywords = self._extract_keywords(text)
        
        # Verificar si comparten al menos una palabra clave
        shared = current_keywords & self._last_conversation_keywords
        if shared:
            logger.debug(f"Palabras compartidas: {shared}")
            return True
        
        # Frases de continuación que siempre son válidas
        continuation_phrases = [
            "y ", "pero ", "entonces ", "además ", "también ",
            "gracias", "ok", "vale", "entendido", "perfecto",
            "sí", "no", "claro", "bien", "bueno",
            "repite", "otra vez", "de nuevo", "qué dijiste",
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
        
        # Obtener respuesta de despertar
        response = self.state_machine.get_wake_response()
        
        # Despertar
        self.state_machine.transition_to(YuiState.ACTIVE)
        
        # Responder
        print(f"\nYui: {response}")
        self.yui.tts.synthesize(response)
    
    def _proactive_loop(self):
        """Loop para comentarios proactivos"""
        logger.info("Iniciando loop de comentarios proactivos")
        
        while not self._stop_event.is_set():
            try:
                # Esperar un poco
                time.sleep(10)  # Verificar cada 10 segundos
                
                # Verificar si debe hacer comentario proactivo
                if self.proactive_enabled and self.state_machine.should_make_proactive_comment():
                    # Cambiar a estado PROACTIVE
                    self.state_machine.transition_to(YuiState.PROACTIVE)
                    
                # Generar comentario proactivo
                    comment = self.state_machine.get_proactive_comment()
                    if comment:
                        print(f"\nYui (proactivo): {comment}")
                        self.yui.tts.synthesize(comment)
                    
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
