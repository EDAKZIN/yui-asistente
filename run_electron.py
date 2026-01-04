"""
Yui AI Assistant - Electron Launcher
Inicia el backend con WebSocket + Desktop Pet de Electron
"""

import os
import sys
import logging
import subprocess
import time
import signal

# Agregar backend al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.gui_api import YuiGUIAPI
from backend.websocket_server import YuiWebSocketServer

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
)
logger = logging.getLogger('Yui.Electron')


def run_with_electron():
    """Ejecuta Yui con Desktop Pet de Electron"""
    logger.info("Iniciando Yui con Electron Desktop Pet...")
    
    electron_process = None
    
    try:
        from backend.yui_assistant import YuiAssistant
        from backend.continuous_listener import ContinuousListener
        from backend.config import Config
        
        # Cargar config
        config = Config.load()
        listening_config = config.get('listening', {})
        
        # Crear instancia de Yui
        logger.info("Cargando modelos de Yui...")
        yui = YuiAssistant()
        yui.load_models()
        
        # Crear listener
        listener = ContinuousListener(
            yui_assistant=yui,
            inactivity_timeout=listening_config.get('inactivity_timeout_seconds', 120.0),
            vad_threshold=listening_config.get('vad_threshold', 0.65),
            proactive_enabled=listening_config.get('proactive_comments_enabled', True),
            max_proactive=listening_config.get('max_proactive_comments', 3)
        )
        
        # Crear API
        api = YuiGUIAPI(yui, listener)
        
        # Crear servidor WebSocket
        ws_server = YuiWebSocketServer(api, host='localhost', port=58765)
        
        # Conectar API de notificaciones
        def setup_ws_notifications():
            """Configura las notificaciones del backend al WebSocket"""
            original_notify_state = api.notify_state_change
            original_notify_transcript = api.notify_transcript
            original_notify_response = api.notify_response
            original_notify_error = api.notify_error
            
            def new_notify_state(new_state: str):
                ws_server.notify_state_change(new_state)
            
            def new_notify_transcript(text: str):
                ws_server.notify_transcript(text)
            
            def new_notify_response(text: str):
                ws_server.notify_response(text)
            
            def new_notify_error(message: str):
                ws_server.notify_error(message)
            
            def new_notify_tts_start(text: str):
                ws_server.notify_tts_start(text)
            
            def new_notify_tts_complete(text: str):
                ws_server.notify_tts_complete(text)
            
            def new_notify_expression(expression_name: str):
                ws_server.notify_expression(expression_name)
            
            api.notify_state_change = new_notify_state
            api.notify_transcript = new_notify_transcript
            api.notify_response = new_notify_response
            api.notify_error = new_notify_error
            api.notify_tts_start = new_notify_tts_start  # CRÍTICO: Conectar callback
            api.notify_expression = new_notify_expression  # Conectar expresiones
            
            # Conectar callbacks de TTS
            yui.tts.set_synthesis_complete_callback(new_notify_tts_complete)
        
        setup_ws_notifications()
        
        # Conectar listener con API
        listener.set_gui_api(api)
        
        # Iniciar WebSocket server en thread
        logger.info("Iniciando servidor WebSocket...")
        print(">>> Iniciando WebSocket server en ws://localhost:58765...")
        ws_thread = ws_server.start_in_thread()
        time.sleep(1.0)  # Esperar que inicie
        print(">>> WebSocket server iniciado")
        
        # Iniciar Electron Desktop Pet
        logger.info("Iniciando Electron Desktop Pet...")
        desktop_pet_path = os.path.join(os.path.dirname(__file__), 'desktop-pet')
        
        # En Windows usar npm.cmd, en otros npm
        npm_cmd = 'npm.cmd' if sys.platform == 'win32' else 'npm'
        
        electron_process = subprocess.Popen(
            [npm_cmd, 'run', 'start'],
            cwd=desktop_pet_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
        )
        
        logger.info("Desktop Pet iniciado")
        
        # Iniciar listener de Yui
        logger.info("Iniciando escucha continua...")
        listener.start()
        
        print("\n" + "=" * 60)
        print("YUI AI ASSISTANT - ELECTRON MODE")
        print("=" * 60)
        print("  • Desktop Pet activo en la bandeja del sistema")
        print("  • WebSocket escuchando en ws://localhost:58765")
        print("  • Presiona Ctrl+C para salir")
        print("=" * 60 + "\n")
        
        # Esperar hasta Ctrl+C o que Electron cierre
        while True:
            # Verificar si Electron sigue corriendo
            if electron_process.poll() is not None:
                logger.info("Electron cerrado, terminando...")
                break
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n¡Hasta luego!")
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup
        logger.info("Cerrando...")
        
        if 'listener' in dir() and listener:
            listener.stop()
        
        if electron_process and electron_process.poll() is None:
            logger.info("Cerrando Electron...")
            if sys.platform == 'win32':
                electron_process.terminate()
            else:
                os.killpg(os.getpgid(electron_process.pid), signal.SIGTERM)
            electron_process.wait(timeout=5)

        logger.info("Proceso terminado limpiamente")
        # Forzar salida inmediata para evitar bloqueos por multiprocessing
        os._exit(0)


if __name__ == '__main__':
    run_with_electron()
