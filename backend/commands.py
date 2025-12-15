"""
Yui AI Assistant - Módulo de Comandos
Ejecuta acciones como abrir aplicaciones con filtros de seguridad
"""

from AppOpener import open as app_open
import logging
from datetime import datetime
from typing import Tuple, Optional

logger = logging.getLogger('Yui.Commands')

# Lista negra de aplicaciones potencialmente peligrosas
BLOCKED_APPS = {
    # Terminales - ejecución arbitraria de comandos
    'cmd', 'command', 'command prompt', 'símbolo del sistema',
    'powershell', 'windows powershell', 'pwsh',
    'terminal', 'windows terminal', 'wt',
    'bash', 'wsl', 'ubuntu',
    
    # Editores de sistema - modificar configuración crítica
    'regedit', 'registry', 'registro', 'editor de registro',
    'gpedit', 'group policy', 'directiva de grupo',
    'msconfig', 'system configuration', 'configuración del sistema',
    'secpol', 'local security policy',
    
    # Gestión de procesos/servicios
    'taskmgr', 'task manager', 'administrador de tareas',
    'services', 'services.msc', 'servicios',
    'devmgmt', 'device manager', 'administrador de dispositivos',
    
    # Utilidades de disco - potencialmente destructivas
    'diskpart', 'disk management', 'administración de discos',
    'format', 'chkdsk',
    'diskperf',
    
    # Panel de control y configuración avanzada
    'control', 'control panel', 'panel de control',
    'sysdm', 'system properties',
    'netplwiz', 'user accounts',
    
    # Otros potencialmente peligrosos
    'taskkill', 'shutdown', 'restart',
    'bcdedit', 'boot configuration',
}

# Aliases para nombres comunes de apps
APP_ALIASES = {
    'opera': 'navegador opera gx',
    'opera gx': 'navegador opera gx',
    'operagx': 'navegador opera gx',
    'gx': 'navegador opera gx',
    'edge': 'microsoft edge',
    'vs code': 'visual studio code',
    'vscode': 'visual studio code',
    'code': 'visual studio code',
}


class CommandExecutor:
    """Ejecuta comandos de voz con filtros de seguridad"""
    
    def __init__(self):
        logger.info("Inicializando módulo de comandos")
        logger.info(f"  Apps bloqueadas: {len(BLOCKED_APPS)}")
        logger.info(f"  Aliases configurados: {len(APP_ALIASES)}")
    
    def is_blocked(self, app_name: str) -> bool:
        """
        Verifica si una aplicación está bloqueada
        
        Args:
            app_name: Nombre de la aplicación
            
        Returns:
            True si está bloqueada
        """
        app_lower = app_name.lower().strip()
        
        # Verificar coincidencia directa o parcial
        for blocked in BLOCKED_APPS:
            if blocked in app_lower or app_lower in blocked:
                return True
        
        return False
    
    def open_app(self, app_name: str) -> Tuple[bool, str]:
        """
        Abre una aplicación si no está bloqueada
        
        Args:
            app_name: Nombre de la aplicación a abrir
            
        Returns:
            Tupla (éxito, mensaje)
        """
        if not app_name:
            return False, "No especificaste qué aplicación abrir"
        
        # Resolver alias (ej: "opera" -> "navegador opera gx")
        # Limpiar puntuación y espacios
        app_lower = app_name.lower().strip().rstrip('.,!?;:')
        resolved_name = APP_ALIASES.get(app_lower, app_name.strip().rstrip('.,!?;:'))
        if resolved_name != app_name.strip().rstrip('.,!?;:'):
            logger.info(f"Alias resuelto: '{app_name}' -> '{resolved_name}'")
        
        # Verificar lista negra
        if self.is_blocked(resolved_name):
            logger.warning(f"Intento de abrir app bloqueada: {resolved_name}")
            return False, f"No puedo abrir '{app_name}' por seguridad"
        
        try:
            # Primero verificar si la app existe en el sistema
            from AppOpener import give_appnames
            available_apps = [a.lower() for a in give_appnames()]
            
            # Buscar coincidencia
            found = False
            for app in available_apps:
                if resolved_name.lower() in app or app in resolved_name.lower():
                    found = True
                    break
            
            if not found:
                logger.warning(f"App no encontrada: {resolved_name}")
                return False, f"No encontré '{app_name}' instalada"
            
            logger.info(f"Abriendo aplicación: {resolved_name}")
            # output=False evita que AppOpener cree archivos/carpetas
            app_open(resolved_name, match_closest=True, throw_error=False, output=False)
            return True, f"Listo, abrí {app_name}"
            
        except Exception as e:
            logger.error(f"Error al abrir {app_name}: {e}")
            return False, f"No pude abrir '{app_name}'"
    
    def get_time(self) -> str:
        """Retorna la hora actual"""
        now = datetime.now()
        return f"Son las {now.strftime('%H:%M')}"
    
    def get_date(self) -> str:
        """Retorna la fecha actual"""
        now = datetime.now()
        months = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        return f"Hoy es {now.day} de {months[now.month - 1]} de {now.year}"
    
    def execute(self, command_type: str, params: Optional[str] = None) -> Tuple[bool, str]:
        """
        Ejecuta un comando según su tipo
        
        Args:
            command_type: Tipo de comando (open_app, get_time, get_date)
            params: Parámetros del comando
            
        Returns:
            Tupla (éxito, mensaje de respuesta)
        """
        if command_type == "open_app":
            return self.open_app(params)
        elif command_type == "get_time":
            return True, self.get_time()
        elif command_type == "get_date":
            return True, self.get_date()
        else:
            return False, "No entendí ese comando"


# Instancia global
command_executor = CommandExecutor()
