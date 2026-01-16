"""
Yui AI Assistant - Memory Decorators
Decoradores para tracking automatico de memoria en funciones
"""

import functools
import logging
from typing import Optional

logger = logging.getLogger('Yui.Memory')


def track_memory(operation_name: Optional[str] = None):
    """
    Decorador para trackear memoria antes/despues de una funcion
    
    Uso:
        @track_memory("LLM.load_model")
        def load_model(self):
            ...
        
        # O sin nombre (usa el nombre de la funcion)
        @track_memory()
        def load_model(self):
            ...
    
    El decorador:
    1. Toma snapshot antes de ejecutar
    2. Ejecuta la funcion
    3. Toma snapshot despues
    4. Registra el delta en el log de memoria
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Determinar nombre de la operacion
            name = operation_name
            if not name:
                # Intentar obtener nombre de clase + metodo
                if args and hasattr(args[0], '__class__'):
                    class_name = args[0].__class__.__name__
                    name = f"{class_name}.{func.__name__}"
                else:
                    name = func.__name__
            
            # Obtener monitor (lazy import para evitar circular)
            try:
                from diagnostics.memory_monitor import get_monitor
                monitor = get_monitor()
                
                with monitor.track_operation(name):
                    return func(*args, **kwargs)
                    
            except ImportError:
                # Si el modulo no esta disponible, ejecutar sin tracking
                logger.debug(f"Memory tracking no disponible para {name}")
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Error en memory tracking para {name}: {e}")
                return func(*args, **kwargs)
        
        return wrapper
    return decorator


def log_memory_event(event: str):
    """
    Registra un evento de memoria manualmente
    
    Args:
        event: Descripcion del evento
    
    Uso:
        log_memory_event("Modelo TTS descargado")
    """
    try:
        from diagnostics.memory_monitor import get_monitor
        monitor = get_monitor()
        monitor.log_event(event)
    except ImportError:
        logger.debug(f"Memory monitor no disponible para evento: {event}")
    except Exception as e:
        logger.warning(f"Error registrando evento de memoria: {e}")


def get_memory_snapshot() -> dict:
    """
    Obtiene snapshot actual de memoria
    
    Returns:
        Dict con VRAM y RAM actuales
    """
    try:
        from diagnostics.memory_monitor import get_monitor
        monitor = get_monitor()
        snapshot = monitor.take_snapshot()
        return snapshot.to_dict()
    except ImportError:
        return {"error": "Memory monitor no disponible"}
    except Exception as e:
        return {"error": str(e)}


def print_memory_summary():
    """Imprime resumen de memoria a consola"""
    try:
        from diagnostics.memory_monitor import get_monitor
        monitor = get_monitor()
        print(monitor.get_summary())
    except ImportError:
        print("Memory monitor no disponible")
    except Exception as e:
        print(f"Error: {e}")
