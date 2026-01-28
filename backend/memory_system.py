"""
Yui AI Assistant - Sistema de Memoria con ChromaDB
Almacena y recupera conversaciones para contexto a largo plazo
"""

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
import logging
from typing import List, Dict
from datetime import datetime
import os

# Decorador para tracking de memoria (opcional)
try:
    from diagnostics.decorators import track_memory
except ImportError:
    def track_memory(name=None):
        def decorator(func):
            return func
        return decorator

logger = logging.getLogger('Yui.Memory')

class MemorySystem:
    """Sistema de memoria a largo plazo usando ChromaDB"""
    
    def __init__(self, db_path: str, max_session_history: int = 25):
        """
        Inicializa el sistema de memoria
        
        Args:
            db_path: Ruta donde guardar la base de datos (largo plazo)
            max_session_history: Máximo de mensajes en memoria de corto plazo
        """
        self.db_path = db_path
        self.client = None
        self.collection = None
        self.embedder = None
        
        # Memoria de corto plazo (sesión actual)
        # Se limpia automáticamente al cerrar/reiniciar
        self.session_history: List[Dict] = []
        self.max_session_history = max_session_history
        
        logger.info(f"Inicializando sistema de memoria")
        logger.info(f"  DB: {db_path}")
        logger.info(f"  Historial de sesión: máx {max_session_history} mensajes")
    
    @track_memory("MemorySystem.load")
    def load(self):
        """Carga el sistema de memoria"""
        if self.client is not None:
            logger.warning("Sistema de memoria ya está cargado")
            return
        
        try:
            logger.info(" Cargando sistema de memoria...")
            
            # Crear directorio si no existe
            os.makedirs(self.db_path, exist_ok=True)
            
            # Inicializar ChromaDB
            logger.info("  Inicializando ChromaDB...")
            self.client = chromadb.PersistentClient(
                path=self.db_path,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            
            # Crear o cargar colección
            self.collection = self.client.get_or_create_collection(
                name="yui_conversations",
                metadata={"description": "Historial de conversaciones de Yui"}
            )
            
            logger.info(f"  Colección cargada: {self.collection.count()} conversaciones")
            
            # Cargar modelo de embeddings (pequeño y rápido)
            logger.info("  Cargando modelo de embeddings...")
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')  # CPU para ahorrar VRAM (~100 MB)
            
            logger.info(" Sistema de memoria listo")
            logger.info(f"  Conversaciones almacenadas: {self.collection.count()}")
            
        except Exception as e:
            logger.error(f" Error al cargar sistema de memoria: {e}")
            logger.error("  Memoria deshabilitada, continuando sin ella")
            self.client = None
    
    # =========================================================================
    # MEMORIA DE CORTO PLAZO (Sesión actual)
    # =========================================================================
    
    def add_to_session(self, user_message: str, assistant_response: str):
        """
        Agrega un intercambio a la memoria de corto plazo (sesión)
        
        Args:
            user_message: Mensaje del usuario
            assistant_response: Respuesta de Yui
        """
        self.session_history.append({
            "user": user_message,
            "assistant": assistant_response
        })
        
        # Mantener solo los últimos N intercambios
        if len(self.session_history) > self.max_session_history:
            self.session_history = self.session_history[-self.max_session_history:]
        
        logger.debug(f"Sesión: {len(self.session_history)} intercambios en memoria")
    
    def get_session_context(self, n_last: int = 5) -> str:
        """
        Obtiene el contexto de la sesión actual para el LLM
        
        Args:
            n_last: Cuántos intercambios recientes incluir
            
        Returns:
            String con el historial de la sesión
        """
        if not self.session_history:
            return ""
        
        recent = self.session_history[-n_last:]
        context_parts = []
        
        for exchange in recent:
            context_parts.append(f"Usuario: {exchange['user']}")
            context_parts.append(f"Yui: {exchange['assistant']}")
        
        return "\n".join(context_parts)
    
    def clear_session(self):
        """Limpia la memoria de corto plazo (se llama al reiniciar)"""
        self.session_history.clear()
        logger.info("Memoria de sesión limpiada")
    
    def get_last_exchange(self) -> Dict:
        """Obtiene el último intercambio de la sesión"""
        if self.session_history:
            return self.session_history[-1]
        return {}
    
    # =========================================================================
    # MEMORIA DE LARGO PLAZO (ChromaDB - persistente)
    # =========================================================================
    
    def should_save(self, user_message: str, assistant_response: str) -> bool:
        """
        Decide si una conversación vale la pena guardar
        
        Args:
            user_message: Mensaje del usuario
            assistant_response: Respuesta del asistente
            
        Returns:
            True si debe guardarse
        """
        user_lower = user_message.lower().strip()
        
        # No guardar mensajes muy cortos (probablemente ruido)
        if len(user_message) < 10:
            return False
        
        # No guardar comandos simples
        command_patterns = ['abre ', 'abrir ', 'qué hora', 'que hora', 'qué fecha', 'que fecha']
        for pattern in command_patterns:
            if pattern in user_lower:
                return False
        
        # No guardar si parece basura/ruido de ASR
        words = user_lower.split()
        if len(words) < 2:
            return False
        
        # No guardar si la respuesta es "no te entendí"
        if "no te entendí" in assistant_response.lower() or "puedes repetir" in assistant_response.lower():
            return False
        
        return True
    
    def add_conversation(self, user_message: str, assistant_response: str):
        """
        Almacena una conversación si es relevante
        
        Args:
            user_message: Mensaje del usuario
            assistant_response: Respuesta del asistente
        """
        if self.client is None:
            return  # Memoria deshabilitada
        
        # Filtrar conversaciones no relevantes
        if not self.should_save(user_message, assistant_response):
            logger.debug(f"Conversación no guardada (no relevante): '{user_message[:30]}...'")
            return
        
        try:
            # Crear ID único basado en timestamp
            conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            
            # Texto combinado para embedding
            full_text = f"Usuario: {user_message}\nYui: {assistant_response}"
            
            # Generar embedding
            embedding = self.embedder.encode(full_text).tolist()
            
            # Almacenar en ChromaDB
            self.collection.add(
                ids=[conversation_id],
                embeddings=[embedding],
                documents=[full_text],
                metadatas=[{
                    "timestamp": datetime.now().isoformat(),
                    "user_message": user_message,
                    "assistant_response": assistant_response
                }]
            )
            
            logger.info(f" Conversación guardada: {conversation_id}")
            
        except Exception as e:
            logger.error(f" Error al guardar conversación: {e}")
    
    def search_relevant_context(self, query: str, n_results: int = 10) -> str:
        """
        Busca conversaciones relevantes para un query
        
        Args:
            query: Consulta del usuario
            n_results: Número de resultados a retornar
        
        Returns:
            String con contexto relevante
        """
        if self.client is None or self.collection.count() == 0:
            return ""  # Sin memoria o vacía
        
        try:
            # Generar embedding del query
            query_embedding = self.embedder.encode(query).tolist()
            
            # Buscar similares
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=min(n_results, self.collection.count())
            )
            
            if not results['documents'] or not results['documents'][0]:
                return ""
            
            # Filtrar por relevancia (distancia < 0.7 = relevante)
            # ChromaDB usa distancia coseno: 0 = idéntico, 2 = opuesto
            distances = results.get('distances', [[]])[0]
            if distances and distances[0] > 0.7:
                logger.debug(f"Contexto descartado: distancia {distances[0]:.2f} > 0.7")
                return ""
            
            # Construir contexto solo con resultados relevantes
            context_parts = []
            for i, (doc, metadata) in enumerate(zip(results['documents'][0], results['metadatas'][0])):
                if i < len(distances) and distances[i] <= 0.7:
                    context_parts.append(f"[Conversación previa: {doc}]")
            
            if not context_parts:
                return ""
            
            context = "\n".join(context_parts)
            logger.debug(f"Contexto recuperado: {len(context_parts)} conversaciones relevantes")
            
            return context
            
        except Exception as e:
            logger.error(f" Error al buscar contexto: {e}")
            return ""
    
    def get_smart_context(self, query: str, min_relevance: float = 0.6) -> str:
        """
        Obtiene contexto inteligente combinando sesión + largo plazo con filtrado.
        
        Args:
            query: Consulta o descripción actual
            min_relevance: Umbral mínimo de relevancia (0-1, mayor = más estricto)
        
        Returns:
            String con contexto relevante (prioriza sesión, luego largo plazo filtrado)
        """
        context_parts = []
        
        # 1. SIEMPRE incluir contexto de sesión reciente si existe (es lo más relevante)
        session_ctx = self.get_session_context(n_last=2)
        if session_ctx:
            context_parts.append(f"[Conversación actual]:\n{session_ctx}")
        
        # 2. Buscar en largo plazo SOLO si hay alta relevancia
        if self.client is not None and self.collection.count() > 0:
            try:
                query_embedding = self.embedder.encode(query).tolist()
                
                # Buscar con distancias para poder filtrar
                # Buscar más resultados para tener más contexto
                results = self.collection.query(
                    query_embeddings=[query_embedding],
                    n_results=10,  # Más resultados para mejor contexto
                    include=["documents", "metadatas", "distances"]
                )
                
                if results['documents'] and results['documents'][0]:
                    for doc, meta, distance in zip(
                        results['documents'][0], 
                        results['metadatas'][0],
                        results['distances'][0]
                    ):
                        # ChromaDB usa L2 distance - menor es mejor
                        # Convertir a score de relevancia (0-1)
                        relevance = 1 / (1 + distance)
                        
                        if relevance >= min_relevance:
                            # Filtrar memorias genéricas/inútiles
                            response = meta.get('assistant_response', '').lower()
                            if any(phrase in response for phrase in [
                                "no te entendí", "puedes repetir", "claro, dime",
                                "en qué puedo ayudarte", "listo, abrí"
                            ]):
                                continue  # Skip respuestas genéricas
                            
                            context_parts.append(f"[Recuerdo relevante ({relevance:.0%})]: {doc}")
                            logger.debug(f"Memoria largo plazo incluida (relevancia: {relevance:.0%})")
                        else:
                            logger.debug(f"Memoria descartada (relevancia: {relevance:.0%} < {min_relevance:.0%})")
                            
            except Exception as e:
                logger.debug(f"Error buscando largo plazo: {e}")
        
        return "\n".join(context_parts) if context_parts else ""
    
    def clean_repetitive_memories(self, phrase: str, max_occurrences: int = 2) -> int:
        """
        Limpia memorias que contienen una frase repetitiva
        
        Args:
            phrase: Frase a buscar en las memorias
            max_occurrences: Cuántas ocurrencias permitir (elimina el resto)
        
        Returns:
            Número de memorias eliminadas
        """
        if self.client is None:
            return 0
        
        try:
            # Obtener todas las memorias
            all_data = self.collection.get(include=["metadatas", "documents"])
            
            if not all_data['ids']:
                return 0
            
            phrase_lower = phrase.lower()
            matching_ids = []
            
            # Encontrar memorias que contienen la frase
            for i, metadata in enumerate(all_data['metadatas']):
                response = metadata.get('assistant_response', '').lower()
                if phrase_lower in response:
                    matching_ids.append((all_data['ids'][i], metadata.get('timestamp', '')))
            
            # Si hay más de max_occurrences, eliminar las más antiguas
            if len(matching_ids) > max_occurrences:
                # Ordenar por timestamp (más antiguos primero)
                matching_ids.sort(key=lambda x: x[1])
                
                # IDs a eliminar (todos excepto los últimos max_occurrences)
                ids_to_delete = [id for id, _ in matching_ids[:-max_occurrences]]
                
                # Eliminar de ChromaDB
                self.collection.delete(ids=ids_to_delete)
                
                logger.info(f" Limpiadas {len(ids_to_delete)} memorias repetitivas con '{phrase[:30]}...'")
                return len(ids_to_delete)
            
            return 0
            
        except Exception as e:
            logger.error(f" Error limpiando memorias repetitivas: {e}")
            return 0
    
    def _is_informative_response(self, response: str) -> bool:
        """
        Verifica si una respuesta contiene información valiosa que no debe perderse
        
        Args:
            response: Respuesta del asistente
            
        Returns:
            True si contiene información importante
        """
        response_lower = response.lower()
        
        # Palabras que indican información importante
        protected_keywords = [
            # Fechas y tiempo
            "enero", "febrero", "marzo", "abril", "mayo", "junio",
            "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
            "lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo",
            "navidad", "año nuevo", "cumpleaños", "aniversario", "feriado", "festividad",
            # Números específicos (indica respuesta calculada)
            "son ", "es ", "resultado", "total", "suma", "resta",
            # Datos personales/preferencias
            "tu nombre", "te llamas", "te gusta", "prefieres", "favorito",
            "recuerdo", "mencionaste", "dijiste",
            # Información factual
            "significa", "definición", "explicación", "porque",
            "historia", "origen", "creador", "inventor",
        ]
        
        for keyword in protected_keywords:
            if keyword in response_lower:
                return True
        
        # Si tiene números específicos (ej: "84", "100", "2025"), es informativa
        import re
        if re.search(r'\b\d{2,}\b', response):  # Números de 2+ dígitos
            return True
        
        return False
    
    def auto_clean_if_repetitive(self, assistant_response: str):
        """
        Verifica si una respuesta es repetitiva y limpia automáticamente la memoria
        SOLO limpia respuestas genéricas, NO información importante
        
        Args:
            assistant_response: Respuesta del asistente a verificar
        """
        # Primero verificar si es una respuesta informativa (NO limpiar)
        if self._is_informative_response(assistant_response):
            logger.debug(f" Respuesta informativa protegida: '{assistant_response[:40]}...'")
            return
        
        # Frases genéricas que si se repiten mucho, deben limpiarse
        repetitive_phrases = [
            "estoy cansada",
            "estoy cansado", 
            "no estoy segura de eso",
            "no estoy seguro de eso",
            "podrías repetir",
            "dime qué necesitas",
            "en qué puedo ayudarte",
            "claro, dime",
        ]
        
        response_lower = assistant_response.lower()
        
        # Solo limpiar si la respuesta es corta Y genérica
        # Respuestas largas probablemente tienen información útil
        if len(assistant_response) > 100:
            return
        
        for phrase in repetitive_phrases:
            if phrase in response_lower:
                cleaned = self.clean_repetitive_memories(phrase, max_occurrences=1)
                if cleaned > 0:
                    logger.info(f" Auto-limpieza: eliminadas {cleaned} memorias genéricas con '{phrase}'")
                break
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas de la memoria"""
        if self.client is None:
            return {"enabled": False}
        
        return {
            "enabled": True,
            "total_conversations": self.collection.count(),
            "db_path": self.db_path
        }
