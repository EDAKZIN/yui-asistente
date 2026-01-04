"""
Yui AI Assistant - Módulo de Comandos
Ejecuta acciones como abrir aplicaciones con filtros de seguridad
"""

from AppOpener import open as app_open
import logging
from datetime import datetime
from typing import Tuple, Optional

from web_search import web_search

# Vision deshabilitada (Gemini removido)

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

# Aliases para nombres comunes de apps (incluyendo errores de Whisper)
APP_ALIASES = {
    # Navegadores
    'opera': 'navegador opera gx',
    'opera gx': 'navegador opera gx',
    'operagx': 'navegador opera gx',
    'gx': 'navegador opera gx',
    'edge': 'microsoft edge',
    'chrome': 'google chrome',
    'firefox': 'mozilla firefox',
    
    # IDEs y editores
    'vs code': 'visual studio code',
    'vscode': 'visual studio code',
    'code': 'visual studio code',
    'visual code': 'visual studio code',
    'android studio': 'android studio',
    
    # Bloc de notas (Windows) - errores comunes de Whisper
    'blog de notas': 'bloc de notas',
    'el blog de notas': 'bloc de notas',
    'el bloc de notas': 'bloc de notas',
    'b, l, o, c de notas': 'bloc de notas',
    'bloc': 'bloc de notas',
    'blog': 'bloc de notas',
    
    # Notepad (editor) - AppOpener lo detecta como 'notepad'
    'notepad++': 'notepad',
    'notepad plus': 'notepad',
    'notepad plus plus': 'notepad',
    'notepad mas mas': 'notepad',
    'notas++': 'notepad',
    
    # Explorador de archivos
    'explorador': 'explorador de archivos',
    'el explorador': 'explorador de archivos',
    'archivos': 'explorador de archivos',
    'carpetas': 'explorador de archivos',
    
    # Juegos
    'roblox': 'roblox player',
    'roblox player': 'roblox player',
    'roblox studio': 'roblox studio',
    'minecraft': 'minecraft launcher',
    'mine': 'minecraft launcher',
    'minecraft launcher': 'minecraft launcher',
    'osu': 'osu',
    
    # Apps de comunicacion
    'spotify': 'spotify',
    'discord': 'discord',
    'steam': 'steam',
    
    # Office
    'word': 'word',
    'excel': 'excel',
    'powerpoint': 'powerpoint',
    'outlook': 'outlook',
    'onenote': 'onenote for windows',
    
    # Utilidades
    'calculadora': 'calculadora',
    'calc': 'calculadora',
    'camara': 'c mara',
    'calendario': 'calendario',
    'reloj': 'reloj',
    'terminal': 'terminal',
    'cmd': 's mbolo del sistema',
    'powershell': 'powershell',
    
    # Apps multimedia
    'obs': 'obs studio bit',
    'vlc': 'vlc media player',
    'fotos': 'fotos',
    'paint': 'paint',
    
    # Launchers
    'epic': 'epic games launcher',
    'epic games': 'epic games launcher',
    
    # Hardware/System
    'cpu z': 'cpu-z',
    'cpuz': 'cpu-z',
    'afterburner': 'msi afterburner',
    'hwmonitor': 'hwmonitor',
    'nvidia': 'nvidia app',
    'nvidia control': 'nvidia control panel',
    
    # Otros
    'github': 'github desktop',
    'git': 'git bash',
    'ollama': 'ollama',
    'rainmeter': 'rainmeter',
}

# Apps del sistema que NO estan en AppOpener (caso de fallback)
SYSTEM_APPS = {
    # Solo como fallback si AppOpener falla
}

# Apps con rutas directas (cuando AppOpener no las encuentra bien)
# Se intentan estas rutas antes de usar AppOpener
DIRECT_APP_PATHS = {
    'roblox': {
        'type': 'uwp',  # Universal Windows Platform app
        'app_id': 'ROBLOXCORPORATION.ROBLOX',
    },
    'minecraft': {
        'type': 'uwp',
        'app_id': 'Microsoft.MinecraftUWP',
    },
}


class CommandExecutor:
    """Ejecuta comandos de voz con filtros de seguridad"""
    
    def __init__(self):
        logger.info("Inicializando modulo de comandos")
        logger.info(f"  Apps bloqueadas: {len(BLOCKED_APPS)}")
        logger.info(f"  Aliases configurados: {len(APP_ALIASES)}")
        
        # Vision deshabilitada
        pass
    
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
    
    def _try_direct_app(self, app_name: str) -> bool:
        """
        Intenta abrir una app usando rutas directas (UWP, shell, etc.)
        
        Args:
            app_name: Nombre de la app (en minúsculas)
            
        Returns:
            True si logró abrirla, False si no está en DIRECT_APP_PATHS
        """
        import subprocess
        
        if app_name not in DIRECT_APP_PATHS:
            return False
        
        config = DIRECT_APP_PATHS[app_name]
        
        try:
            if config['type'] == 'uwp':
                # Abrir app UWP usando PowerShell
                app_id = config['app_id']
                logger.info(f"Abriendo UWP app: {app_id}")
                
                # Buscar la app UWP y obtener su AppUserModelId
                ps_script = f'''
                $app = Get-AppxPackage | Where-Object {{ $_.Name -like "*{app_id}*" }} | Select-Object -First 1
                if ($app) {{
                    $familyName = $app.PackageFamilyName
                    Start-Process "shell:AppsFolder\\$familyName!App"
                    exit 0
                }} else {{
                    exit 1
                }}
                '''
                result = subprocess.run(
                    ['powershell', '-ExecutionPolicy', 'Bypass', '-Command', ps_script],
                    capture_output=True, text=True, timeout=10
                )
                
                if result.returncode == 0:
                    logger.info(f"UWP app abierta: {app_name}")
                    return True
                else:
                    logger.warning(f"UWP app no encontrada: {app_id}")
                    return False
                    
            elif config['type'] == 'exe':
                # Abrir ejecutable directo
                exe_path = config['path']
                if os.path.exists(exe_path):
                    subprocess.Popen([exe_path])
                    logger.info(f"App abierta por ruta directa: {exe_path}")
                    return True
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout abriendo {app_name}")
            return False
        except Exception as e:
            logger.error(f"Error abriendo {app_name} directamente: {e}")
            return False
        
        return False
    
    def open_app(self, app_name: str, force: bool = False) -> Tuple[bool, str]:
        """
        Abre una aplicación si no está bloqueada
        
        Args:
            app_name: Nombre de la aplicación a abrir
            force: Si True, abre sin pedir confirmacion (para cuando usuario ya confirmo)
            
        Returns:
            Tupla (éxito, mensaje)
            - Para sugerencias retorna (None, "suggest:nombre_app")
        """
        import subprocess
        import os
        
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
            # 0. NUEVO: Intentar ruta directa primero para apps problemáticas
            direct_result = self._try_direct_app(app_lower)
            if direct_result:
                return True, f"Listo, abrí {app_name}"
            
            # 1. Verificar si es una app del sistema (se abre con subprocess)
            if resolved_name in SYSTEM_APPS:
                exe_path = SYSTEM_APPS[resolved_name]
                logger.info(f"Abriendo app del sistema: {resolved_name} -> {exe_path}")
                
                # Verificar si el ejecutable existe (solo para rutas absolutas)
                if os.path.isabs(exe_path) and not os.path.exists(exe_path):
                    # Intentar ruta alternativa para Office (x86)
                    alt_path = exe_path.replace('Program Files', 'Program Files (x86)')
                    if os.path.exists(alt_path):
                        exe_path = alt_path
                    else:
                        logger.warning(f"Ejecutable no encontrado: {exe_path}")
                        return False, f"No encontré '{app_name}' instalada"
                
                # Ejecutar
                subprocess.Popen([exe_path], shell=True)
                return True, f"Listo, abrí {app_name}"
            
            # 2. Si no es del sistema, usar AppOpener
            from AppOpener import give_appnames
            available_apps = give_appnames()
            available_apps_lower = [a.lower() for a in available_apps]
            
            # 2a. Buscar coincidencia EXACTA primero
            if resolved_name.lower() in available_apps_lower:
                logger.info(f"Coincidencia exacta: {resolved_name}")
                app_open(resolved_name, match_closest=True, throw_error=False, output=False)
                return True, f"Listo, abrí {app_name}"
            
            # 2b. Buscar coincidencia PARCIAL
            partial_matches = []
            for app in available_apps:
                app_l = app.lower()
                resolved_l = resolved_name.lower()
                # Coincidencia parcial: una contiene a la otra
                if resolved_l in app_l or app_l in resolved_l:
                    partial_matches.append(app)
            
            if partial_matches:
                # Si hay coincidencia parcial y no es forzado, pedir confirmacion
                if not force:
                    best_match = partial_matches[0]  # Tomar la primera
                    logger.info(f"Coincidencia parcial encontrada: '{resolved_name}' -> '{best_match}'")
                    # Retornar sugerencia (None indica que necesita confirmacion)
                    return None, f"suggest:{best_match}"
                else:
                    # Force=True significa que usuario ya confirmo
                    best_match = partial_matches[0]
                    logger.info(f"Abriendo (confirmado): {best_match}")
                    app_open(best_match, match_closest=True, throw_error=False, output=False)
                    return True, f"Listo, abrí {best_match}"
            
            # 3. No hay coincidencia
            logger.warning(f"App no encontrada: {resolved_name}")
            return False, f"No encontré '{app_name}' instalada"
            
        except Exception as e:
            logger.error(f"Error al abrir {app_name}: {e}")
            return False, f"No pude abrir '{app_name}'"
    
    def get_time(self) -> str:
        """Retorna la hora actual en formato 12h"""
        now = datetime.now()
        hour = now.hour
        minute = now.minute
        period = 'de la mañana' if hour < 12 else 'de la tarde' if hour < 19 else 'de la noche'
        hour_12 = hour % 12
        if hour_12 == 0:
            hour_12 = 12
        return f"Son las {hour_12}:{minute:02d} {period}"
    
    def get_date(self) -> str:
        """Retorna la fecha actual"""
        now = datetime.now()
        months = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
                  'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre']
        return f"Hoy es {now.day} de {months[now.month - 1]} de {now.year}"
    
    def web_search(self, query: str) -> Tuple[bool, str]:
        """
        Busca información en internet usando SearxNG
        
        Args:
            query: Consulta de búsqueda
            
        Returns:
            Tupla (éxito, resultados resumidos)
        """
        logger.debug(f"web_search llamado con query: '{query}'")
        return web_search(query)
    
    def describe_screen(self) -> Tuple[bool, str]:
        """
        Describe lo que Yui ve en la pantalla
        NOTA: Visión deshabilitada (Gemini removido)
        
        Returns:
            Tupla (exito, mensaje)
        """
        logger.info("Comando de visión recibido pero está deshabilitado")
        return False, "Lo siento, mi visión no está disponible en este momento."
    
    def execute(self, command_type: str, params: Optional[str] = None) -> Tuple[bool, str]:
        """
        Ejecuta un comando según su tipo
        
        Args:
            command_type: Tipo de comando (open_app, get_time, get_date, web_search)
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
        elif command_type == "web_search":
            return self.web_search(params)
        else:
            return False, "No entendí ese comando"


# Instancia global
command_executor = CommandExecutor()
