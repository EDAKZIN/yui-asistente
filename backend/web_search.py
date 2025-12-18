"""
Yui AI Assistant - Módulo de Búsqueda Web con Brave Search API
Motor de búsqueda de alta calidad usando la API oficial de Brave
"""

import os
import requests
import logging
from typing import Tuple
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

logger = logging.getLogger('Yui.WebSearch')


class BraveSearch:
    """Motor de búsqueda usando Brave Search API"""
    
    # Endpoint oficial de Brave Search API
    API_URL = "https://api.search.brave.com/res/v1/web/search"
    
    def __init__(self):
        self.api_key = os.getenv("BRAVE_API_KEY", "").strip()
        
        if self.api_key:
            logger.info("Brave Search API inicializada correctamente")
        else:
            logger.warning("BRAVE_API_KEY no configurada - las búsquedas fallarán")
    
    def is_configured(self) -> bool:
        """Verifica si la API key está configurada"""
        return bool(self.api_key)
    
    def search(self, query: str, max_results: int = 5) -> Tuple[bool, str]:
        """
        Busca en internet usando Brave Search API
        
        Args:
            query: Consulta de búsqueda
            max_results: Número máximo de resultados (1-20)
            
        Returns:
            Tupla (éxito, resultados resumidos o mensaje de error)
        """
        if not query:
            return False, "No especificaste qué buscar"
        
        if not self.api_key:
            logger.error("Intento de búsqueda sin API key configurada")
            return False, "La búsqueda web no está configurada. Falta BRAVE_API_KEY en .env"
        
        # Limpiar y validar query
        clean_query = query.strip()
        if len(clean_query) < 2:
            return False, "La búsqueda es muy corta"
        
        logger.info(f"Buscando: '{clean_query}'")
        
        try:
            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": self.api_key
            }
            
            params = {
                "q": clean_query,
                "count": min(max_results, 20),  # Brave permite máximo 20
                "search_lang": "es",  # Español
                "text_decorations": "false",
                "spellcheck": "true"
            }
            
            response = requests.get(
                self.API_URL,
                headers=headers,
                params=params,
                timeout=10
            )
            
            # Manejar errores de API
            if response.status_code == 401:
                logger.error("API key de Brave inválida o expirada")
                return False, "La API key de Brave es inválida"
            
            if response.status_code == 429:
                logger.error("Límite de cuota de Brave alcanzado")
                return False, "Se alcanzó el límite de búsquedas. Intenta más tarde"
            
            if response.status_code != 200:
                logger.error(f"Error de Brave API: {response.status_code} - {response.text[:200]}")
                return False, "Error al buscar en internet"
            
            data = response.json()
            
            # Extraer resultados web
            web_results = data.get("web", {}).get("results", [])
            
            if not web_results:
                logger.info("Búsqueda sin resultados")
                return False, f"No encontré resultados para '{clean_query}'"
            
            # Construir resumen de resultados
            summary_parts = []
            
            for result in web_results[:max_results]:
                # Priorizar descripción, luego extracto
                content = result.get("description", "") or result.get("extra_snippets", [""])[0] if result.get("extra_snippets") else ""
                title = result.get("title", "")
                
                if content and len(content) > 20:
                    # Limpiar y truncar contenido
                    clean_content = content.strip()
                    if len(clean_content) > 300:
                        clean_content = clean_content[:300] + "..."
                    summary_parts.append(clean_content)
                elif title:
                    summary_parts.append(title)
            
            if summary_parts:
                summary = " ".join(summary_parts)
                logger.info(f"Búsqueda exitosa: {len(web_results)} resultados")
                return True, summary
            else:
                return False, "Los resultados no tenían contenido útil"
                
        except requests.exceptions.Timeout:
            logger.error("Timeout en búsqueda de Brave")
            return False, "La búsqueda tardó demasiado"
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de conexión: {e}")
            return False, "No pude conectar con el servicio de búsqueda"
        
        except Exception as e:
            logger.error(f"Error inesperado en búsqueda: {e}")
            return False, "Ocurrió un error al buscar"


# Instancia global
brave_search = BraveSearch()


def web_search(query: str) -> Tuple[bool, str]:
    """
    Función de conveniencia para búsqueda web
    
    Args:
        query: Consulta de búsqueda
        
    Returns:
        Tupla (éxito, resultados)
    """
    return brave_search.search(query)
