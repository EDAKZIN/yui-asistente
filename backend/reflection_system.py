"""
Yui AI Assistant - Sistema de Reflexión Automatizada
Analiza conversaciones y extrae insights sobre el usuario para aprendizaje continuo
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import re

logger = logging.getLogger('Yui.Reflection')


class ReflectionSystem:
    """
    Sistema de reflexión que analiza conversaciones y extrae insights.
    Se ejecuta automáticamente al entrar en modo reposo.
    """
    
    def __init__(self, memory_system, llm):
        """
        Inicializa el sistema de reflexión.
        
        Args:
            memory_system: Instancia de MemorySystem para acceder a conversaciones
            llm: Instancia del LLM para generar reflexiones
        """
        self.memory = memory_system
        self.llm = llm
        self.insights_collection = None
        self.last_reflection = None
        
        logger.info("Sistema de reflexión inicializado")
    
    def load(self):
        """Carga la colección de insights en ChromaDB"""
        if self.memory.client is None:
            logger.warning("Memory system no cargado, reflexión deshabilitada")
            return False
        
        try:
            # Crear colección separada para insights
            self.insights_collection = self.memory.client.get_or_create_collection(
                name="yui_insights",
                metadata={"description": "Insights aprendidos sobre el usuario"}
            )
            logger.info(f"Colección de insights cargada: {self.insights_collection.count()} insights")
            return True
        except Exception as e:
            logger.error(f"Error cargando colección de insights: {e}")
            return False
    
    def get_recent_conversations(self, hours: int = 24) -> List[Dict]:
        """
        Obtiene conversaciones de las últimas N horas.
        
        Args:
            hours: Cuántas horas hacia atrás buscar
            
        Returns:
            Lista de conversaciones recientes
        """
        if self.memory.client is None:
            return []
        
        try:
            cutoff_time = datetime.now() - timedelta(hours=hours)
            cutoff_str = cutoff_time.isoformat()
            
            # Obtener todas las conversaciones con metadata
            all_data = self.memory.collection.get(
                include=["metadatas", "documents"]
            )
            
            if not all_data['ids']:
                return []
            
            recent = []
            for i, metadata in enumerate(all_data['metadatas']):
                timestamp = metadata.get('timestamp', '')
                if timestamp >= cutoff_str:
                    recent.append({
                        'user': metadata.get('user_message', ''),
                        'assistant': metadata.get('assistant_response', ''),
                        'timestamp': timestamp
                    })
            
            # Ordenar por timestamp
            recent.sort(key=lambda x: x['timestamp'])
            
            logger.debug(f"Encontradas {len(recent)} conversaciones en las últimas {hours} horas")
            return recent
            
        except Exception as e:
            logger.error(f"Error obteniendo conversaciones recientes: {e}")
            return []
    
    def reflect_on_session(self) -> List[str]:
        """
        Analiza las conversaciones recientes y extrae insights.
        Llamado automáticamente al entrar en modo reposo.
        
        Returns:
            Lista de insights extraídos
        """
        logger.info("Iniciando reflexión sobre sesión...")
        
        # Obtener conversaciones de las últimas 24 horas
        recent = self.get_recent_conversations(hours=24)
        
        # También incluir historial de sesión actual
        if self.memory.session_history:
            for exchange in self.memory.session_history:
                recent.append({
                    'user': exchange.get('user', ''),
                    'assistant': exchange.get('assistant', ''),
                    'timestamp': datetime.now().isoformat()
                })
        
        if not recent:
            logger.info("No hay conversaciones recientes para reflexionar")
            return []
        
        # Formatear conversaciones para el LLM
        conversations_text = ""
        for conv in recent[-20:]:  # Máximo 20 conversaciones
            conversations_text += f"Usuario: {conv['user']}\n"
            conversations_text += f"Yui: {conv['assistant']}\n\n"
        
        # Prompt de reflexión
        prompt = f"""Analiza estas conversaciones entre el usuario (mi creador) y yo (Yui).
Extrae MÁXIMO 3 insights importantes sobre el usuario.

Tipos de insights válidos:
- PREFERENCIA: Algo que le gusta o no le gusta
- DATO: Información personal (nombre, cumpleaños, trabajo)
- PATRON: Comportamiento frecuente
- RELACION: Cómo me trata o qué espera de mí

Conversaciones:
{conversations_text}

Responde SOLO con los insights, uno por línea, en formato:
[TIPO] Insight concreto

Si no hay insights útiles, responde: NINGUNO"""

        try:
            # Generar reflexión sin usar historial
            insights_text = self.llm.generate_response(prompt, use_history=False)
            
            if "NINGUNO" in insights_text.upper():
                logger.info("Reflexión completada: sin insights nuevos")
                return []
            
            # Parsear insights
            insights = self._parse_insights(insights_text)
            
            # Guardar insights
            for insight in insights:
                self._save_insight(insight)
            
            self.last_reflection = datetime.now()
            logger.info(f"Reflexión completada: {len(insights)} insights guardados")
            
            return insights
            
        except Exception as e:
            logger.error(f"Error durante reflexión: {e}")
            return []
    
    def _parse_insights(self, text: str) -> List[Dict]:
        """Parsea el texto de insights del LLM"""
        insights = []
        
        # Patrón: [TIPO] texto
        pattern = r'\[(\w+)\]\s*(.+)'
        
        for line in text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            
            match = re.match(pattern, line)
            if match:
                insight_type = match.group(1).upper()
                content = match.group(2).strip()
                
                if insight_type in ['PREFERENCIA', 'DATO', 'PATRON', 'RELACION']:
                    insights.append({
                        'type': insight_type,
                        'content': content,
                        'timestamp': datetime.now().isoformat()
                    })
        
        return insights
    
    def _save_insight(self, insight: Dict):
        """Guarda un insight en ChromaDB"""
        if self.insights_collection is None:
            return
        
        try:
            insight_id = f"insight_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            
            # Generar embedding
            full_text = f"[{insight['type']}] {insight['content']}"
            embedding = self.memory.embedder.encode(full_text).tolist()
            
            # Verificar si ya existe un insight similar
            existing = self.insights_collection.query(
                query_embeddings=[embedding],
                n_results=1,
                include=["distances"]
            )
            
            if existing['distances'] and existing['distances'][0]:
                # Si la distancia es muy pequeña, es un duplicado
                if existing['distances'][0][0] < 0.3:
                    logger.debug(f"Insight similar ya existe, ignorando: {insight['content'][:50]}")
                    return
            
            # Guardar
            self.insights_collection.add(
                ids=[insight_id],
                embeddings=[embedding],
                documents=[full_text],
                metadatas=[{
                    'type': insight['type'],
                    'content': insight['content'],
                    'timestamp': insight['timestamp']
                }]
            )
            
            logger.info(f"Insight guardado: [{insight['type']}] {insight['content'][:50]}...")
            
        except Exception as e:
            logger.error(f"Error guardando insight: {e}")
    
    def get_relevant_insights(self, query: str, n_results: int = 3) -> str:
        """
        Obtiene insights relevantes para una consulta.
        
        Args:
            query: Consulta o contexto actual
            n_results: Número de insights a retornar
            
        Returns:
            String con insights relevantes formateados
        """
        if self.insights_collection is None or self.insights_collection.count() == 0:
            return ""
        
        try:
            query_embedding = self.memory.embedder.encode(query).tolist()
            
            results = self.insights_collection.query(
                query_embeddings=[query_embedding],
                n_results=min(n_results, self.insights_collection.count()),
                include=["documents", "metadatas", "distances"]
            )
            
            if not results['documents'] or not results['documents'][0]:
                return ""
            
            insights_text = []
            for doc, meta, distance in zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            ):
                # Solo incluir si es relevante
                relevance = 1 / (1 + distance)
                if relevance >= 0.5:
                    insights_text.append(f"[Recuerdo: {meta.get('content', '')}]")
            
            if insights_text:
                logger.debug(f"Insights relevantes encontrados: {len(insights_text)}")
                return "\n".join(insights_text)
            
            return ""
            
        except Exception as e:
            logger.error(f"Error buscando insights: {e}")
            return ""
    
    def get_stats(self) -> Dict:
        """Obtiene estadísticas del sistema de reflexión"""
        return {
            'enabled': self.insights_collection is not None,
            'total_insights': self.insights_collection.count() if self.insights_collection else 0,
            'last_reflection': self.last_reflection.isoformat() if self.last_reflection else None
        }


# Instancia global (lazy load)
reflection_system: Optional[ReflectionSystem] = None


def get_reflection_system(memory, llm) -> ReflectionSystem:
    """Obtiene la instancia global del sistema de reflexión"""
    global reflection_system
    if reflection_system is None:
        reflection_system = ReflectionSystem(memory, llm)
    return reflection_system
