"""
Yui AI Assistant - Discord Message Handler
Procesamiento de mensajes de Discord con historial por canal
"""

import re
import logging
import threading
from typing import Dict, List
from datetime import datetime

logger = logging.getLogger('Yui.Discord')

SUMMARY_THRESHOLD = 40
KEEP_RECENT = 10
MAX_DISCORD_LENGTH = 2000


def _clean_response(text: str) -> str:
    """Limpia la respuesta del LLM para Discord"""
    if not text:
        return "Tuve un problema, intenta de nuevo."

    for prefix in ["assistant:", "Assistant:", "Yui:"]:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()

    text = re.sub(r'\*[^*]+\*', '', text).strip()
    text = re.sub(r'\s+', ' ', text).strip()

    if not text:
        return "Tuve un problema, intenta de nuevo."

    if text[-1] in '.!?)"\'':
        return text

    last_period = max(text.rfind('.'), text.rfind('!'), text.rfind('?'))
    if last_period > len(text) * 0.3:
        return text[:last_period + 1]

    return text + "..."


class DiscordMessageHandler:
    """Procesa mensajes de Discord y genera respuestas con el LLM de Yui"""

    def __init__(self, llm, memory, owner_id: str):
        """
        Args:
            llm: Instancia de LlamaLLM o GroqLLM
            memory: Instancia de MemorySystem (puede ser None)
            owner_id: ID de Discord del creador (EDAKZIN)
        """
        self.llm = llm
        self.memory = memory
        self.owner_id = str(owner_id)
        self.channel_histories: Dict[str, List[Dict[str, str]]] = {}
        self._llm_lock = threading.Lock()
        self._discord_loop = None

    def process_message(self, message) -> str:
        """Procesa un mensaje de Discord y genera respuesta"""
        user_name = message.author.display_name
        is_owner = str(message.author.id) == self.owner_id

        if is_owner:
            user_name = "EDAKZIN"

        clean_content = message.clean_content

        # Comandos solo disponibles para el owner
        if is_owner:
            cmd_response = self._check_owner_commands(clean_content, message)
            if cmd_response:
                self._save_to_history_and_memory(
                    str(message.channel.id), user_name,
                    clean_content, cmd_response
                )
                return cmd_response

        formatted_input = f"[usuario: {user_name}] {clean_content}"

        search_ctx = self._check_web_search(clean_content) if is_owner else ""
        if search_ctx:
            formatted_input += f"\n\n{search_ctx}"

        channel_id = str(message.channel.id)
        if channel_id not in self.channel_histories:
            self.channel_histories[channel_id] = []

        history = self.channel_histories[channel_id]

        from prompts.yui_system import get_system_prompt
        system_prompt = get_system_prompt(include_date=True, context_mode="discord")

        messages = [{"role": "system", "content": system_prompt}]

        memory_ctx = self._get_memory_context(clean_content)
        if memory_ctx:
            messages.append({"role": "system", "content": f"[Recuerdos relevantes]:\n{memory_ctx}"})

        messages.extend(history)
        messages.append({"role": "user", "content": formatted_input})

        logger.info(f"Generando respuesta para {user_name} ({len(messages)} msgs en historial)...")
        response_text = self._generate(messages)

        history.append({"role": "user", "content": formatted_input})
        history.append({"role": "assistant", "content": response_text})

        if len(history) >= SUMMARY_THRESHOLD:
            self._summarize_channel_history(channel_id)

        if self.memory:
            try:
                self.memory.add_conversation(
                    f"[Discord - {user_name}] {clean_content}",
                    response_text
                )
            except Exception as e:
                logger.warning(f"Error guardando en memoria: {e}")


        return response_text

    def _generate(self, messages: list) -> str:
        """Genera respuesta del LLM con thread safety"""
        with self._llm_lock:
            try:
                from llama_llm import LlamaLLM

                if isinstance(self.llm, LlamaLLM):
                    if self.llm.model is None:
                        self.llm.load_model()

                    total_chars = sum(len(m["content"]) for m in messages)
                    logger.info(f"Llamando LLM local ({len(messages)} msgs, ~{total_chars} chars)...")

                    response = self.llm.model.create_chat_completion(
                        messages=messages,
                        max_tokens=500,
                        temperature=0.7,
                        top_p=0.9,
                        repeat_penalty=1.1
                    )
                    raw = response['choices'][0]['message']['content'].strip()
                    logger.info(f"LLM respondio: '{raw[:60]}...'")
                else:
                    from groq_llm import GroqLLM
                    if isinstance(self.llm, GroqLLM) and self.llm.client:
                        logger.info(f"Llamando Groq ({len(messages)} msgs)...")
                        response = self.llm.client.chat.completions.create(
                            model=self.llm.model,
                            messages=messages,
                            max_tokens=500,
                            temperature=0.7,
                            top_p=0.9
                        )
                        raw = response.choices[0].message.content.strip()
                        logger.info(f"Groq respondio: '{raw[:60]}...'")
                    else:
                        return "No tengo mi cerebro disponible ahora mismo."

                return _clean_response(raw)

            except Exception as e:
                logger.error(f"Error generando respuesta: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return "Tuve un problema generando la respuesta."

    def _summarize_channel_history(self, channel_id: str):
        """Resume el historial de un canal cuando crece demasiado"""
        history = self.channel_histories.get(channel_id, [])
        if len(history) < SUMMARY_THRESHOLD:
            return

        old_messages = history[:-KEEP_RECENT]
        recent_messages = history[-KEEP_RECENT:]

        history_text = ""
        for msg in old_messages:
            role = "Usuario" if msg["role"] == "user" else "Yui"
            content = msg["content"]
            if msg["role"] == "system":
                continue
            history_text += f"{role}: {content}\n"

        try:
            summary_msgs = [{
                "role": "system",
                "content": (
                    "Resume la siguiente conversacion en maximo 3 oraciones. "
                    "Captura los temas principales, datos importantes y el tono general. "
                    "Responde SOLO con el resumen, sin introducciones."
                )
            }, {
                "role": "user",
                "content": history_text
            }]

            from llama_llm import LlamaLLM
            if isinstance(self.llm, LlamaLLM) and self.llm.model:
                response = self.llm.model.create_chat_completion(
                    messages=summary_msgs,
                    max_tokens=200,
                    temperature=0.3
                )
                summary = response['choices'][0]['message']['content'].strip()
            else:
                from groq_llm import GroqLLM
                if isinstance(self.llm, GroqLLM) and self.llm.client:
                    response = self.llm.client.chat.completions.create(
                        model=self.llm.model,
                        messages=summary_msgs,
                        max_tokens=200,
                        temperature=0.3
                    )
                    summary = response.choices[0].message.content.strip()
                else:
                    self.channel_histories[channel_id] = recent_messages
                    return

            self.channel_histories[channel_id] = [
                {"role": "system", "content": f"[Resumen de conversacion anterior]: {summary}"}
            ] + recent_messages

            logger.info(
                f"Historial canal {channel_id[:8]} resumido: "
                f"{len(old_messages)} msgs -> 1 resumen + {len(recent_messages)} recientes"
            )

        except Exception as e:
            logger.warning(f"Error resumiendo historial: {e}")
            self.channel_histories[channel_id] = recent_messages

    def _save_to_history_and_memory(self, channel_id: str, user_name: str,
                                     user_text: str, response: str):
        """Guarda un intercambio en historial y memoria"""
        if channel_id not in self.channel_histories:
            self.channel_histories[channel_id] = []

        history = self.channel_histories[channel_id]
        history.append({"role": "user", "content": f"[usuario: {user_name}] {user_text}"})
        history.append({"role": "assistant", "content": response})

        if self.memory:
            try:
                self.memory.add_conversation(
                    f"[Discord - {user_name}] {user_text}", response
                )
            except Exception:
                pass

    def _check_owner_commands(self, text: str, message) -> str:
        """Detecta y ejecuta comandos, solo para el owner"""
        text_lower = text.lower().strip()

        # Hora
        if any(p in text_lower for p in ['qué hora', 'que hora', 'la hora', 'hora es']):
            try:
                from commands import command_executor
                _, response = command_executor.execute("get_time")
                logger.info(f"[HERRAMIENTA] Hora -> {response}")
                return response
            except Exception as e:
                logger.warning(f"Error ejecutando hora: {e}")

        # Fecha
        if any(p in text_lower for p in ['qué fecha', 'que fecha', 'qué día', 'que día', 'que dia']):
            try:
                from commands import command_executor
                _, response = command_executor.execute("get_date")
                logger.info(f"[HERRAMIENTA] Fecha -> {response}")
                return response
            except Exception as e:
                logger.warning(f"Error ejecutando fecha: {e}")

        # Recordatorios
        reminder_result = self._check_reminder(text, message)
        if reminder_result:
            return reminder_result

        return ""

    def _check_reminder(self, text: str, message) -> str:
        """Detecta y programa recordatorios via Discord"""
        try:
            from reminders import ReminderSystem

            if not hasattr(self, '_reminder_system'):
                self._reminder_channels = {}
                self._reminder_system = ReminderSystem(
                    on_reminder_triggered=self._on_reminder
                )
                self._reminder_system.start()

            parsed = self._reminder_system.parse_reminder(text)
            if not parsed:
                return ""

            reminder = self._reminder_system.add_reminder(
                parsed['message'], parsed['delay_seconds']
            )

            self._reminder_channels[reminder.id] = message.channel

            minutes = parsed['delay_seconds'] // 60
            seconds = parsed['delay_seconds'] % 60
            time_str = f"{minutes} minutos" if minutes else f"{seconds} segundos"
            if minutes and seconds:
                time_str = f"{minutes}m {seconds}s"

            logger.info(f"[HERRAMIENTA] Recordatorio programado: '{parsed['message']}' en {time_str}")
            return f"Listo, te recuerdo en {time_str}: {parsed['message']}"

        except Exception as e:
            logger.warning(f"Error con recordatorio: {e}")
            return ""

    def _on_reminder(self, reminder):
        """Callback cuando un recordatorio se activa"""
        import asyncio
        try:
            channel = self._reminder_channels.pop(reminder.id, None)
            if not channel:
                logger.warning(f"No se encontro canal para recordatorio {reminder.id}")
                return

            msg = f"Oye EDAKZIN, me pediste que te recordara: **{reminder.message}**"
            logger.info(f"[HERRAMIENTA] Recordatorio activado: '{reminder.message}'")

            if self._discord_loop and self._discord_loop.is_running():
                asyncio.run_coroutine_threadsafe(channel.send(msg), self._discord_loop)
            else:
                logger.warning("No hay event loop de Discord para enviar recordatorio")
        except Exception as e:
            logger.error(f"Error enviando recordatorio: {e}")


    def _check_web_search(self, text: str) -> str:
        """Detecta y ejecuta busquedas web si el mensaje lo requiere"""
        text_lower = text.lower().strip()

        search_patterns = [
            r'(?:busca|buscas|buscar|busques|investiga|investigues)\s+(.+)',
            r'(?:dime sobre|háblame de|cuéntame sobre|información sobre)\s+(.+)',
            r'(?:qué|que) (?:es|son|significa)\s+(.+)',
            r'(?:quién|quien) (?:es|fue|era)\s+(.+)',
        ]

        for pattern in search_patterns:
            match = re.search(pattern, text_lower)
            if match:
                query = match.group(1).strip().rstrip('.,!?')
                exclusions = ['yui', 'creador', 'edakzin', 'tú', 'tu']
                if any(kw in query.lower() for kw in exclusions):
                    return ""

                try:
                    from commands import command_executor
                    logger.info(f"[HERRAMIENTA] Busqueda web: '{query}'")
                    success, results = command_executor.web_search(query)
                    if success:
                        logger.info(f"[HERRAMIENTA] Resultados web obtenidos ({len(results)} chars)")
                        fecha = datetime.now().strftime("%d de %B de %Y")
                        return f"[BUSQUEDA WEB - {fecha}]\nResultados:\n{results}\nResponde usando esta informacion."
                except Exception as e:
                    logger.warning(f"Error en busqueda web: {e}")
                return ""

        return ""

    def _get_memory_context(self, text: str) -> str:
        """Consulta memoria a largo plazo si el mensaje lo amerita"""
        if not self.memory:
            return ""

        triggers = [
            'recuerdas', 'recuerda', 'acordas', 'acuerdas',
            'antes', 'la otra vez', 'dijiste', 'mencionaste',
            'hablamos', 'contaste', 'te conté', 'te dije',
            'sabes de mi', 'sabes sobre', 'conoces',
            'que sabes', 'qué sabes',
        ]

        text_lower = text.lower()
        if not any(t in text_lower for t in triggers):
            return ""

        try:
            ctx = self.memory.search_relevant_context(text, n_results=5)
            if ctx:
                logger.info(f"[HERRAMIENTA] Memoria consultada ({len(ctx)} chars)")
            return ctx
        except Exception as e:
            logger.warning(f"Error consultando memoria: {e}")
            return ""
