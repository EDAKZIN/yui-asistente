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

logger = logging.getLogger('Yui.Memory')

class MemorySystem:
    """Sistema de memoria a largo plazo usando ChromaDB"""
    
    def __init__(self, db_path: str):
        """
        Inicializa el sistema de memoria
        
        Args:
            db_path: Ruta donde guardar la base de datos
        """
        self.db_path = db_path
        self.client = None
        self.collection = None
        self.embedder = None
        
        logger.info(f"Inicializando sistema de memoria")
        logger.info(f"  DB: {db_path}")
    
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
            self.embedder = SentenceTransformer('all-MiniLM-L6-v2')  # ~80MB, rápido
            
            logger.info(" Sistema de memoria listo")
            logger.info(f"  Conversaciones almacenadas: {self.collection.count()}")
            
        except Exception as e:
            logger.error(f" Error al cargar sistema de memoria: {e}")
            logger.error("  Memoria deshabilitada, continuando sin ella")
            self.client = None
    
    def add_conversation(self, user_message: str, assistant_response: str):
        """
        Almacena una conversación
        
        Args:
            user_message: Mensaje del usuario
            assistant_response: Respuesta del asistente
        """
        if self.client is None:
            return  # Memoria deshabilitada
        
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
            
            logger.debug(f" Conversación guardada: {conversation_id}")
            
        except Exception as e:
            logger.error(f" Error al guardar conversación: {e}")
    
    def search_relevant_context(self, query: str, n_results: int = 3) -> str:
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
            
            # Construir contexto
            context_parts = []
            for doc, metadata in zip(results['documents'][0], results['metadatas'][0]):
                context_parts.append(f"[Conversación previa: {doc}]")
            
            context = "\n".join(context_parts)
            logger.debug(f" Contexto recuperado: {len(context_parts)} conversaciones")
            
            return context
            
        except Exception as e:
            logger.error(f" Error al buscar contexto: {e}")
            return ""
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas de la memoria"""
        if self.client is None:
            return {"enabled": False}
        
        return {
            "enabled": True,
            "total_conversations": self.collection.count(),
            "db_path": self.db_path
        }
