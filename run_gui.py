"""
Yui AI Assistant - GUI Launcher
Inicia la interfaz gráfica con pywebview
"""

import os
import sys
import logging
import threading
import webview

# Agregar backend al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.gui_api import YuiGUIAPI

# Configurar logging básico para standalone
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
)
logger = logging.getLogger('Yui.GUI')


def create_gui(yui_assistant=None, continuous_listener=None, debug=False):
    """
    Crea y retorna la ventana de la GUI
    
    Args:
        yui_assistant: Instancia de YuiAssistant (opcional)
        continuous_listener: Instancia de ContinuousListener (opcional)
        debug: Habilitar herramientas de desarrollo
    
    Returns:
        webview.Window
    """
    # Crear API
    api = YuiGUIAPI(yui_assistant, continuous_listener)
    
    # Ruta al HTML
    ui_path = os.path.join(os.path.dirname(__file__), 'ui', 'index.html')
    
    # Crear ventana
    window = webview.create_window(
        title='Yui - AI Assistant',
        url=ui_path,
        js_api=api,
        width=450,
        height=700,
        resizable=True,
        min_size=(350, 500),
        background_color='#1a1a1a',
        text_select=False
    )
    
    # Dar referencia de la ventana al API
    api.set_window(window)
    
    return window, api


def run_gui_standalone():
    """Ejecuta la GUI en modo standalone (sin backend de Yui)"""
    logger.info("Iniciando GUI en modo standalone...")
    
    window, api = create_gui(debug=True)
    
    # Iniciar webview
    webview.start(debug=True)


def run_gui_with_yui():
    """Ejecuta la GUI con el backend completo de Yui"""
    logger.info("Iniciando GUI con backend de Yui...")
    
    # Importar componentes de Yui
    try:
        from backend.yui_assistant import YuiAssistant
        from backend.continuous_listener import ContinuousListener
        from backend.config import Config
        
        # Cargar config
        config = Config.load()
        listening_config = config.get('listening', {})
        
        # Crear instancia de Yui
        yui = YuiAssistant()
        yui.load_models()
        
        # Crear listener con config
        listener = ContinuousListener(
            yui_assistant=yui,
            inactivity_timeout=listening_config.get('inactivity_timeout_seconds', 120.0),
            vad_threshold=listening_config.get('vad_threshold', 0.65),
            proactive_enabled=listening_config.get('proactive_comments_enabled', True),
            max_proactive=listening_config.get('max_proactive_comments', 3)
        )
        
        # Crear GUI con referencias
        window, api = create_gui(yui, listener, debug=False)
        
        # Conectar GUI API con listener
        listener.set_gui_api(api)
        
        # Iniciar listener en thread separado
        def start_listener():
            listener.start()
        
        listener_thread = threading.Thread(target=start_listener, daemon=True)
        
        # Callback cuando la GUI está lista
        def on_loaded():
            logger.info("GUI cargada, iniciando listener...")
            listener_thread.start()
        
        window.events.loaded += on_loaded
        
        # Iniciar webview (bloquea hasta cerrar)
        webview.start()
        
        # Cleanup al cerrar
        logger.info("Cerrando GUI, deteniendo listener...")
        listener.stop()
        
    except ImportError as e:
        logger.error(f"Error importando módulos de Yui: {e}")
        logger.info("Ejecutando en modo standalone...")
        run_gui_standalone()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Yui AI Assistant GUI')
    parser.add_argument('--standalone', action='store_true', 
                        help='Ejecutar solo la GUI sin backend')
    parser.add_argument('--debug', action='store_true',
                        help='Habilitar herramientas de desarrollo')
    
    args = parser.parse_args()
    
    if args.standalone:
        run_gui_standalone()
    else:
        run_gui_with_yui()
