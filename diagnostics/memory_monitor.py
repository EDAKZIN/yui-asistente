"""
Yui AI Assistant - Memory Monitor
Sistema robusto de monitoreo y deteccion de fugas de memoria (VRAM y RAM)
"""

import logging
import threading
import time
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from collections import deque

logger = logging.getLogger('Yui.Memory')


@dataclass
class MemorySnapshot:
    """Captura de estado de memoria en un momento dado"""
    timestamp: str
    vram_total_mb: float      # VRAM total GPU (nvidia-smi) - TODO lo que usa la GPU
    vram_torch_mb: float      # VRAM PyTorch CUDA - Whisper, VAD, Emociones, Embeddings
    vram_other_mb: float      # VRAM no-PyTorch - LLM (DirectML), TTS (proceso separado)
    ram_process_mb: float     # RAM del proceso Yui principal
    ram_system_percent: float # RAM total sistema en %
    event: str = ""           # Evento asociado (ej: "LLM.load_model")
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    def to_log_line(self) -> str:
        event_str = f" | {self.event}" if self.event else ""
        # Formato claro:
        # GPU_TOTAL = Todo lo que nvidia-smi reporta
        # CUDA = PyTorch (Whisper, VAD, Emociones, Embeddings)
        # DML+TTS = DirectML (LLM ONNX) + TTS (proceso separado) + otros
        return (
            f"{self.timestamp} | "
            f"GPU_TOTAL:{self.vram_total_mb:.0f}MB "
            f"[CUDA:{self.vram_torch_mb:.0f} DML+TTS:{self.vram_other_mb:.0f}] | "
            f"RAM_YUI:{self.ram_process_mb:.0f}MB | "
            f"RAM_SYS:{self.ram_system_percent:.1f}%"
            f"{event_str}"
        )


class MemoryMonitor:
    """
    Monitor central de memoria para detectar fugas.
    
    Funcionalidades:
    - Captura de snapshots de VRAM (pynvml) y RAM (psutil)
    - Logging periodico automatico
    - Medicion antes/despues de operaciones
    - Analisis de tendencias para detectar fugas
    """
    
    def __init__(self, log_dir: Optional[Path] = None, log_interval: int = 2):
        """
        Args:
            log_dir: Directorio para guardar logs (default: logs/)
            log_interval: Intervalo en segundos para logging periodico
        """
        self.log_dir = log_dir or Path(__file__).parent.parent / "logs"
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / "memory.log"
        self.log_interval = log_interval
        
        # Estado del monitor
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Historial de snapshots en memoria (ultimos 100)
        self._history: deque = deque(maxlen=100)
        
        # Baseline para comparaciones
        self._baseline: Optional[MemorySnapshot] = None
        
        # Callbacks para alertas
        self._alert_callbacks: List[Callable] = []
        
        # Inicializar dependencias
        self._init_pynvml()
        self._init_psutil()
        
        logger.info(f"MemoryMonitor inicializado (log: {self.log_file})")
    
    def _init_pynvml(self):
        """Inicializa pynvml (nvidia-ml-py) para VRAM"""
        self._pynvml_available = False
        try:
            import pynvml
            pynvml.nvmlInit()
            self._pynvml = pynvml
            self._gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            self._pynvml_available = True
            logger.debug("pynvml inicializado correctamente")
        except ImportError:
            logger.warning("pynvml no disponible - instala nvidia-ml-py")
        except Exception as e:
            logger.warning(f"Error inicializando pynvml: {e}")
    
    def _init_psutil(self):
        """Inicializa psutil para RAM"""
        self._psutil_available = False
        try:
            import psutil
            self._psutil = psutil
            self._process = psutil.Process(os.getpid())
            self._psutil_available = True
            logger.debug("psutil inicializado correctamente")
        except ImportError:
            logger.warning("psutil no disponible - instala psutil")
        except Exception as e:
            logger.warning(f"Error inicializando psutil: {e}")
    
    def get_vram_nvidia(self) -> float:
        """Obtiene VRAM total usada via nvidia-smi (MB)"""
        if not self._pynvml_available:
            return 0.0
        try:
            info = self._pynvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
            return info.used / (1024 * 1024)  # Bytes a MB
        except Exception as e:
            logger.error(f"Error obteniendo VRAM nvidia: {e}")
            return 0.0
    
    def get_vram_torch(self) -> float:
        """Obtiene VRAM usada por PyTorch CUDA (MB)"""
        try:
            import torch
            if torch.cuda.is_available():
                return torch.cuda.memory_allocated(0) / (1024 * 1024)
        except ImportError:
            pass
        except Exception as e:
            logger.error(f"Error obteniendo VRAM torch: {e}")
        return 0.0
    
    def get_ram_process(self) -> float:
        """Obtiene RAM usada por el proceso actual (MB)"""
        if not self._psutil_available:
            return 0.0
        try:
            return self._process.memory_info().rss / (1024 * 1024)
        except Exception as e:
            logger.error(f"Error obteniendo RAM proceso: {e}")
            return 0.0
    
    def get_ram_system_percent(self) -> float:
        """Obtiene porcentaje de RAM del sistema usado"""
        if not self._psutil_available:
            return 0.0
        try:
            return self._psutil.virtual_memory().percent
        except Exception as e:
            logger.error(f"Error obteniendo RAM sistema: {e}")
            return 0.0
    
    def take_snapshot(self, event: str = "") -> MemorySnapshot:
        """
        Captura snapshot actual de memoria
        
        Args:
            event: Descripcion del evento (ej: "LLM.load_model")
        """
        vram_total = self.get_vram_nvidia()
        vram_torch = self.get_vram_torch()
        vram_other = max(0, vram_total - vram_torch)
        
        snapshot = MemorySnapshot(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            vram_total_mb=vram_total,
            vram_torch_mb=vram_torch,
            vram_other_mb=vram_other,
            ram_process_mb=self.get_ram_process(),
            ram_system_percent=self.get_ram_system_percent(),
            event=event
        )
        
        self._history.append(snapshot)
        return snapshot
    
    def log_snapshot(self, snapshot: MemorySnapshot):
        """Escribe snapshot al archivo de log"""
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(snapshot.to_log_line() + '\n')
        except Exception as e:
            logger.error(f"Error escribiendo log de memoria: {e}")
    
    def log_event(self, event: str):
        """Registra un evento con snapshot"""
        snapshot = self.take_snapshot(event)
        self.log_snapshot(snapshot)
        logger.info(f"[MEMORY] {event} | VRAM: {snapshot.vram_total_mb:.0f}MB")
        return snapshot
    
    def set_baseline(self):
        """Establece el baseline actual para comparaciones"""
        # Escribir header con leyenda al inicio del log
        try:
            with open(self.log_file, 'w', encoding='utf-8') as f:
                f.write("=" * 80 + "\n")
                f.write("YUI MEMORY MONITOR LOG\n")
                f.write("=" * 80 + "\n")
                f.write("LEYENDA:\n")
                f.write("  GPU_TOTAL  = VRAM total usada (nvidia-smi)\n")
                f.write("  CUDA       = PyTorch CUDA (Whisper, VAD, Emociones, Embeddings)\n")
                f.write("  DML+TTS    = DirectML (LLM ONNX) + TTS (proceso separado) + otros\n")
                f.write("  RAM_YUI    = RAM del proceso principal de Yui\n")
                f.write("  RAM_SYS    = RAM total del sistema (%)\n")
                f.write("=" * 80 + "\n\n")
        except Exception as e:
            logger.error(f"Error escribiendo header de log: {e}")
        
        self._baseline = self.take_snapshot("BASELINE")
        self.log_snapshot(self._baseline)
        logger.info(f"[MEMORY] Baseline establecido: GPU={self._baseline.vram_total_mb:.0f}MB, RAM={self._baseline.ram_process_mb:.0f}MB")
    
    def compare_to_baseline(self) -> Dict:
        """Compara estado actual con baseline"""
        if not self._baseline:
            return {"error": "No hay baseline establecido"}
        
        current = self.take_snapshot()
        
        return {
            "vram_delta_mb": current.vram_total_mb - self._baseline.vram_total_mb,
            "ram_delta_mb": current.ram_process_mb - self._baseline.ram_process_mb,
            "baseline": self._baseline.to_dict(),
            "current": current.to_dict()
        }
    
    @contextmanager
    def track_operation(self, name: str):
        """
        Context manager para medir memoria antes/despues de una operacion
        
        Uso:
            with monitor.track_operation("LLM.load_model"):
                llm.load_model()
        """
        before = self.take_snapshot(f"{name}:START")
        start_time = time.time()
        
        try:
            yield
        finally:
            elapsed = time.time() - start_time
            after = self.take_snapshot(f"{name}:END")
            
            vram_delta = after.vram_total_mb - before.vram_total_mb
            ram_delta = after.ram_process_mb - before.ram_process_mb
            
            # Registrar resultado
            result_line = (
                f"{after.timestamp} | OPERATION | {name} | "
                f"VRAM: {vram_delta:+.0f}MB | RAM: {ram_delta:+.0f}MB | "
                f"Time: {elapsed:.2f}s"
            )
            
            try:
                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(result_line + '\n')
            except:
                pass
            
            logger.info(f"[MEMORY] {name} | VRAM: {vram_delta:+.0f}MB | RAM: {ram_delta:+.0f}MB | {elapsed:.2f}s")
    
    def _periodic_loop(self):
        """Loop de logging periodico"""
        logger.info(f"Iniciando logging periodico cada {self.log_interval}s")
        
        while not self._stop_event.is_set():
            snapshot = self.take_snapshot("PERIODIC")
            self.log_snapshot(snapshot)
            
            # Detectar alertas
            self._check_alerts(snapshot)
            
            # Esperar intervalo
            self._stop_event.wait(self.log_interval)
        
        logger.info("Logging periodico detenido")
    
    def _check_alerts(self, snapshot: MemorySnapshot):
        """Verifica condiciones de alerta"""
        # Alerta si VRAM > 95% del total disponible
        if self._pynvml_available:
            try:
                info = self._pynvml.nvmlDeviceGetMemoryInfo(self._gpu_handle)
                total_mb = info.total / (1024 * 1024)
                usage_percent = (snapshot.vram_total_mb / total_mb) * 100
                
                if usage_percent > 95:
                    alert = f"ALERT: VRAM al {usage_percent:.1f}%!"
                    logger.warning(f"[MEMORY] {alert}")
                    try:
                        with open(self.log_file, 'a', encoding='utf-8') as f:
                            f.write(f"{snapshot.timestamp} | {alert}\n")
                    except:
                        pass
            except:
                pass
        
        # Alerta si RAM del proceso > 8GB
        if snapshot.ram_process_mb > 8000:
            alert = f"ALERT: RAM proceso > 8GB ({snapshot.ram_process_mb:.0f}MB)"
            logger.warning(f"[MEMORY] {alert}")
    
    def start_periodic_logging(self):
        """Inicia el logging periodico en background"""
        if self._running:
            logger.warning("Logging periodico ya esta corriendo")
            return
        
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._periodic_loop, daemon=True)
        self._thread.start()
        self._running = True
        
        logger.info("Logging periodico de memoria iniciado")
    
    def stop_periodic_logging(self):
        """Detiene el logging periodico"""
        if not self._running:
            return
        
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._running = False
        
        logger.info("Logging periodico de memoria detenido")
    
    def analyze_log(self, log_path: Optional[Path] = None) -> Dict:
        """
        Analiza el log de memoria para detectar fugas
        
        Returns:
            Dict con resultados del analisis
        """
        log_path = log_path or self.log_file
        
        if not log_path.exists():
            return {"error": "Log no encontrado", "path": str(log_path)}
        
        snapshots = []
        operations = []
        alerts = []
        
        try:
            with open(log_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    if "| PERIODIC |" in line or "VRAM:" in line:
                        # Parsear snapshot
                        parts = line.split("|")
                        if len(parts) >= 2:
                            timestamp = parts[0].strip()
                            # Extraer VRAM total
                            for part in parts:
                                if "VRAM:" in part:
                                    try:
                                        vram_str = part.split("VRAM:")[1].strip().split()[0]
                                        vram = float(vram_str.replace("MB", ""))
                                        snapshots.append({
                                            "timestamp": timestamp,
                                            "vram_mb": vram
                                        })
                                    except:
                                        pass
                                    break
                    
                    if "| OPERATION |" in line:
                        operations.append(line)
                    
                    if "ALERT" in line:
                        alerts.append(line)
        
        except Exception as e:
            return {"error": f"Error leyendo log: {e}"}
        
        # Analisis
        result = {
            "total_snapshots": len(snapshots),
            "total_operations": len(operations),
            "total_alerts": len(alerts),
            "alerts": alerts[-10:] if alerts else [],  # Ultimas 10 alertas
            "leak_detected": False,
            "leak_suspects": [],
            "summary": {}
        }
        
        if len(snapshots) >= 10:
            # Calcular tendencia de VRAM
            first_10 = [s["vram_mb"] for s in snapshots[:10]]
            last_10 = [s["vram_mb"] for s in snapshots[-10:]]
            
            avg_first = sum(first_10) / len(first_10)
            avg_last = sum(last_10) / len(last_10)
            
            growth = avg_last - avg_first
            
            result["summary"] = {
                "vram_start_avg_mb": round(avg_first, 1),
                "vram_end_avg_mb": round(avg_last, 1),
                "vram_growth_mb": round(growth, 1),
                "vram_peak_mb": max(s["vram_mb"] for s in snapshots),
                "vram_min_mb": min(s["vram_mb"] for s in snapshots)
            }
            
            # Detectar fuga si hay crecimiento > 500MB sin operaciones recientes
            if growth > 500:
                result["leak_detected"] = True
                result["leak_suspects"].append(
                    f"VRAM crecio {growth:.0f}MB durante la sesion"
                )
        
        # Analizar operaciones de descarga
        for op in operations:
            if "unload" in op.lower():
                # Verificar si el delta es positivo (no libero memoria)
                if "+0" in op or any(f"+{i}" in op for i in range(1, 1000)):
                    result["leak_detected"] = True
                    result["leak_suspects"].append(f"Descarga incompleta: {op[:100]}")
        
        return result
    
    def get_summary(self) -> str:
        """Retorna resumen del estado actual"""
        snapshot = self.take_snapshot()
        
        summary = [
            "=" * 50,
            "MEMORY MONITOR SUMMARY",
            "=" * 50,
            f"VRAM Total:     {snapshot.vram_total_mb:.0f} MB",
            f"  - PyTorch:    {snapshot.vram_torch_mb:.0f} MB",
            f"  - Other:      {snapshot.vram_other_mb:.0f} MB",
            f"RAM Proceso:    {snapshot.ram_process_mb:.0f} MB",
            f"RAM Sistema:    {snapshot.ram_system_percent:.1f}%",
        ]
        
        if self._baseline:
            vram_delta = snapshot.vram_total_mb - self._baseline.vram_total_mb
            ram_delta = snapshot.ram_process_mb - self._baseline.ram_process_mb
            summary.extend([
                "-" * 50,
                f"Delta vs Baseline:",
                f"  VRAM: {vram_delta:+.0f} MB",
                f"  RAM:  {ram_delta:+.0f} MB",
            ])
        
        summary.append("=" * 50)
        return "\n".join(summary)
    
    def shutdown(self):
        """Limpieza al cerrar"""
        self.stop_periodic_logging()
        
        if self._pynvml_available:
            try:
                self._pynvml.nvmlShutdown()
            except:
                pass
        
        logger.info("MemoryMonitor cerrado")


# Instancia global (singleton)
_monitor: Optional[MemoryMonitor] = None


def get_monitor() -> MemoryMonitor:
    """Obtiene la instancia global del monitor"""
    global _monitor
    if _monitor is None:
        _monitor = MemoryMonitor()
    return _monitor


def init_monitor(log_dir: Optional[Path] = None, log_interval: int = 30) -> MemoryMonitor:
    """Inicializa el monitor global con configuracion custom"""
    global _monitor
    _monitor = MemoryMonitor(log_dir=log_dir, log_interval=log_interval)
    return _monitor
