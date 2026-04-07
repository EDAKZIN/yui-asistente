"""
Yui AI Assistant - WebSocket Server
Expone la API de Yui para comunicación con Electron
"""

import asyncio
import json
import logging
from typing import Optional, Set
import websockets
from websockets.server import WebSocketServerProtocol

logger = logging.getLogger('Yui.WebSocket')


class YuiWebSocketServer:
    """
    Servidor WebSocket que expone la API de Yui
    Permite comunicación bidireccional con Electron
    """
    
    def __init__(self, gui_api, host: str = 'localhost', port: int = 58765):
        """
        Args:
            gui_api: Instancia de YuiGUIAPI
            host: Host del servidor
            port: Puerto del servidor
        """
        self.gui_api = gui_api
        self.host = host
        self.port = port
        self.clients: Set[WebSocketServerProtocol] = set()
        self.server = None
        self._loop = None
        
        logger.info(f"WebSocket server configurado en ws://{host}:{port}")
    
    async def register(self, websocket: WebSocketServerProtocol):
        """Registra un nuevo cliente"""
        self.clients.add(websocket)
        logger.info(f"Cliente conectado. Total: {len(self.clients)}")
        
        # Enviar estado inicial al nuevo cliente
        try:
            initial_state = self.gui_api.get_initial_state()
            await websocket.send(json.dumps({
                'type': 'initial_state',
                'data': initial_state
            }))
        except Exception as e:
            logger.error(f"Error enviando estado inicial: {e}")
    
    async def unregister(self, websocket: WebSocketServerProtocol):
        """Desregistra un cliente"""
        self.clients.discard(websocket)
        logger.info(f"Cliente desconectado. Total: {len(self.clients)}")
    
    async def broadcast(self, message: dict):
        """Envía mensaje a todos los clientes conectados"""
        if not self.clients:
            return
        
        message_json = json.dumps(message)
        await asyncio.gather(
            *[client.send(message_json) for client in self.clients],
            return_exceptions=True
        )
    
    async def handle_message(self, websocket: WebSocketServerProtocol, message: str):
        """Procesa un mensaje del cliente"""
        try:
            data = json.loads(message)
            action = data.get('action')
            params = data.get('params', {})
            
            logger.debug(f"Acción recibida: {action}")
            
            # Mapear acciones a métodos de la API
            result = None
            
            if action == 'get_initial_state':
                result = self.gui_api.get_initial_state()
            
            elif action == 'get_state':
                result = self.gui_api.get_state()
            
            elif action == 'toggle_mute':
                result = self.gui_api.toggle_mute()
                # Notificar a todos los clientes
                await self.broadcast({'type': 'mute_changed', 'data': result})
            
            elif action == 'toggle_sleep':
                result = self.gui_api.toggle_sleep()
                # Notificar a todos los clientes
                await self.broadcast({'type': 'sleep_changed', 'data': result})
            
            elif action == 'toggle_performance':
                result = self.gui_api.toggle_performance()
                # Notificar a todos los clientes
                await self.broadcast({'type': 'performance_changed', 'data': result})
            
            elif action == 'set_mute_key':
                key = params.get('key', 'F1')
                result = self.gui_api.set_mute_key(key)
            
            elif action == 'set_vad_threshold':
                threshold = params.get('threshold', 0.65)
                result = self.gui_api.set_vad_threshold(threshold)
            
            elif action == 'set_proactive_enabled':
                enabled = params.get('enabled', True)
                result = self.gui_api.set_proactive_enabled(enabled)
            
            elif action == 'set_memory_monitoring':
                enabled = params.get('enabled', False)
                result = self.gui_api.set_memory_monitoring(enabled)
            
            elif action == 'set_detailed_logging':
                enabled = params.get('enabled', False)
                result = self.gui_api.set_detailed_logging(enabled)
            
            elif action == 'get_session_stats':
                result = self.gui_api.get_session_stats()
            
            elif action == 'toggle_discord_bot':
                result = self.gui_api.toggle_discord_bot()
                await self.broadcast({'type': 'discord_changed', 'data': result})
            
            elif action == 'toggle_console':
                result = self.gui_api.toggle_console()
            
            elif action == 'shutdown':
                # Reiniciar todo el sistema
                logger.info("Comando de reinicio recibido - reiniciando Yui...")
                result = {'status': 'restarting'}
                await websocket.send(json.dumps({
                    'type': 'response',
                    'action': action,
                    'data': result
                }))
                # Dar un momento para que el mensaje se envíe
                import asyncio
                await asyncio.sleep(0.3)
                # Reiniciar: lanzar nuevo proceso y cerrar este
                import sys
                import os
                import subprocess
                # Obtener el path del script principal
                script_path = os.path.abspath(sys.argv[0])
                python = sys.executable
                
                # Limpiar recursos antes de reiniciar!
                if self.gui_api:
                    self.gui_api.cleanup()
                
                # Lanzar nuevo proceso (detached)
                subprocess.Popen(
                    [python, script_path],
                    cwd=os.path.dirname(script_path),
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
                # Cerrar este proceso
                os._exit(0)
            
            else:
                result = {'error': f'Acción desconocida: {action}'}
            
            # Enviar respuesta
            await websocket.send(json.dumps({
                'type': 'response',
                'action': action,
                'data': result
            }))
            
        except json.JSONDecodeError:
            logger.error(f"JSON inválido: {message}")
            await websocket.send(json.dumps({
                'type': 'error',
                'message': 'JSON inválido'
            }))
        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}")
            await websocket.send(json.dumps({
                'type': 'error',
                'message': str(e)
            }))
    
    async def handler(self, websocket):
        """Handler principal de conexiones WebSocket"""
        await self.register(websocket)
        try:
            async for message in websocket:
                await self.handle_message(websocket, message)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister(websocket)
    
    # === Métodos para notificar desde el backend ===
    
    def notify_state_change(self, new_state: str):
        """Notifica cambio de estado a todos los clientes"""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast({'type': 'state_change', 'data': {'state': new_state}}),
                self._loop
            )
    
    def notify_transcript(self, text: str):
        """Notifica nueva transcripción"""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast({'type': 'transcript', 'data': {'text': text}}),
                self._loop
            )
    
    def notify_response(self, text: str):
        """Notifica respuesta de Yui"""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast({'type': 'response', 'data': {'text': text}}),
                self._loop
            )
    
    def notify_error(self, message: str):
        """Notifica error"""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast({'type': 'error', 'data': {'message': message}}),
                self._loop
            )
    
    def notify_tts_start(self, text: str):
        """Notifica que TTS va a iniciar síntesis (para mostrar subtítulo)"""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast({
                    'type': 'tts_start',
                    'data': {'text': text}
                }),
                self._loop
            )
    
    def notify_tts_complete(self, text: str):
        """Notifica que TTS completó síntesis (para ocultar subtítulo)"""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast({'type': 'tts_complete', 'data': {'text': text}}),
                self._loop
            )
    
    def notify_expression(self, expression_name: str):
        """Notifica al frontend que cambie la expresion del modelo Live2D"""
        if self._loop:
            asyncio.run_coroutine_threadsafe(
                self.broadcast({
                    'type': 'set_expression',
                    'data': {'name': expression_name}
                }),
                self._loop
            )
    
    async def start_async(self):
        """Inicia el servidor WebSocket (async)"""
        self._loop = asyncio.get_event_loop()
        self.server = await websockets.serve(
            self.handler,
            self.host,
            self.port
        )
        logger.info(f"WebSocket server iniciado en ws://{self.host}:{self.port}")
        return self.server
    
    def start_in_thread(self):
        """Inicia el servidor en un thread separado"""
        import threading
        
        async def run_server():
            try:
                print(f"[WebSocket] Iniciando servidor en ws://{self.host}:{self.port}...")
                self._loop = asyncio.get_running_loop()
                
                async with websockets.serve(self.handler, self.host, self.port) as server:
                    print(f"[WebSocket] Servidor ACTIVO en ws://{self.host}:{self.port}")
                    logger.info(f"WebSocket server iniciado en ws://{self.host}:{self.port}")
                    await asyncio.Future()  # Correr indefinidamente
            except Exception as e:
                print(f"[WebSocket] ERROR iniciando servidor: {e}")
                import traceback
                traceback.print_exc()
        
        def thread_target():
            asyncio.run(run_server())
        
        thread = threading.Thread(target=thread_target, daemon=True)
        thread.start()
        return thread
    
    async def stop(self):
        """Detiene el servidor"""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("WebSocket server detenido")
