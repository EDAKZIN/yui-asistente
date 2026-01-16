"""
Yui VRAM Profiler - Análisis línea por línea de consumo VRAM

Usa pytorch_memlab para generar un reporte detallado de qué líneas de código
consumen más VRAM en GPU.

Uso:
    python diagnostics/vram_profiler.py

Genera: diagnostics/vram_report.txt
"""

import sys
import os

# Añadir path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import gc
from datetime import datetime

# Intentar importar pytorch_memlab
try:
    from pytorch_memlab import LineProfiler, MemReporter
    HAS_MEMLAB = True
except ImportError:
    HAS_MEMLAB = False
    print("⚠️ pytorch_memlab no instalado. Instalando...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pytorch_memlab"])
    from pytorch_memlab import LineProfiler, MemReporter
    HAS_MEMLAB = True


def get_vram_mb():
    """Obtiene VRAM usada actual en MB"""
    if torch.cuda.is_available():
        return torch.cuda.memory_allocated() / 1024 / 1024
    return 0


def get_vram_reserved_mb():
    """Obtiene VRAM reservada por PyTorch en MB"""
    if torch.cuda.is_available():
        return torch.cuda.memory_reserved() / 1024 / 1024
    return 0


def vram_snapshot(label: str):
    """Imprime snapshot de VRAM con etiqueta"""
    allocated = get_vram_mb()
    reserved = get_vram_reserved_mb()
    try:
        import pynvml
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        total_gpu = mem_info.used / 1024 / 1024
        pynvml.nvmlShutdown()
    except:
        total_gpu = allocated
    
    print(f"[{label}]")
    print(f"  PyTorch Allocated: {allocated:.1f} MB")
    print(f"  PyTorch Reserved:  {reserved:.1f} MB")
    print(f"  GPU Total (nvidia-smi): {total_gpu:.1f} MB")
    print()
    
    return {
        'label': label,
        'allocated': allocated,
        'reserved': reserved,
        'total_gpu': total_gpu
    }


def profile_model_loading():
    """Perfila la carga de todos los modelos de Yui línea por línea"""
    
    report_lines = []
    snapshots = []
    
    def log(msg):
        print(msg)
        report_lines.append(msg)
    
    log("=" * 70)
    log("YUI VRAM PROFILER - REPORTE DETALLADO")
    log(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)
    log("")
    
    # Limpiar GPU
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        gc.collect()
    
    snapshots.append(vram_snapshot("INICIO (GPU limpia)"))
    
    # =========================================================================
    # 1. WHISPER STT
    # =========================================================================
    log("-" * 70)
    log("1. FASTER-WHISPER STT")
    log("-" * 70)
    
    try:
        from faster_whisper import WhisperModel
        
        before = get_vram_mb()
        log(f"   Antes de cargar: {before:.1f} MB")
        
        # Cargar modelo
        model = WhisperModel(
            "medium",
            device="cuda",
            compute_type="int8"
        )
        
        after = get_vram_mb()
        log(f"   Después de cargar: {after:.1f} MB")
        log(f"   ➜ DELTA: +{after - before:.1f} MB")
        
        snapshots.append(vram_snapshot("POST-WHISPER"))
        
        # Limpiar
        del model
        gc.collect()
        torch.cuda.empty_cache()
        
    except Exception as e:
        log(f"   ❌ Error: {e}")
    
    log("")
    
    # =========================================================================
    # 2. LLM (ONNX Runtime GenAI - DirectML)
    # =========================================================================
    log("-" * 70)
    log("2. LLAMA LLM (ONNX Runtime GenAI DirectML)")
    log("-" * 70)
    
    try:
        import onnxruntime_genai as og
        
        before = get_vram_mb()
        log(f"   Antes de cargar: {before:.1f} MB")
        
        model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "models", "llm-local", "Llama-3.2-3B-ONNX-INT4"
        )
        
        if os.path.exists(model_path):
            log(f"   Cargando modelo desde: {model_path}")
            llm_model = og.Model(model_path)
            tokenizer = og.Tokenizer(llm_model)
            
            after = get_vram_mb()
            log(f"   Después de cargar: {after:.1f} MB")
            log(f"   ➜ DELTA PyTorch: +{after - before:.1f} MB")
            log(f"   ⚠️ NOTA: DirectML usa VRAM separada de PyTorch CUDA")
            
            snapshots.append(vram_snapshot("POST-LLM"))
            
            # Limpiar
            del tokenizer
            del llm_model
            gc.collect()
        else:
            log(f"   ⚠️ Modelo no encontrado en: {model_path}")
        
    except Exception as e:
        log(f"   ❌ Error: {e}")
    
    log("")
    
    # =========================================================================
    # 3. SENTENCE TRANSFORMER (Embeddings)
    # =========================================================================
    log("-" * 70)
    log("3. SENTENCE TRANSFORMER (Embeddings)")
    log("-" * 70)
    
    try:
        from sentence_transformers import SentenceTransformer
        
        before = get_vram_mb()
        log(f"   Antes de cargar: {before:.1f} MB")
        
        embedder = SentenceTransformer('all-MiniLM-L6-v2')
        
        after = get_vram_mb()
        log(f"   Después de cargar: {after:.1f} MB")
        log(f"   ➜ DELTA: +{after - before:.1f} MB")
        
        snapshots.append(vram_snapshot("POST-EMBEDDINGS"))
        
        # Limpiar
        del embedder
        gc.collect()
        torch.cuda.empty_cache()
        
    except Exception as e:
        log(f"   ❌ Error: {e}")
    
    log("")
    
    # =========================================================================
    # 4. SILERO VAD
    # =========================================================================
    log("-" * 70)
    log("4. SILERO VAD")
    log("-" * 70)
    
    try:
        before = get_vram_mb()
        log(f"   Antes de cargar: {before:.1f} MB")
        
        vad_model, utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            onnx=False
        )
        vad_model = vad_model.cuda()
        
        after = get_vram_mb()
        log(f"   Después de cargar: {after:.1f} MB")
        log(f"   ➜ DELTA: +{after - before:.1f} MB")
        
        snapshots.append(vram_snapshot("POST-VAD"))
        
        # Limpiar
        del vad_model
        gc.collect()
        torch.cuda.empty_cache()
        
    except Exception as e:
        log(f"   ❌ Error: {e}")
    
    log("")
    
    # =========================================================================
    # 5. EMOTION DETECTOR
    # =========================================================================
    log("-" * 70)
    log("5. EMOTION DETECTOR (pysentimiento)")
    log("-" * 70)
    
    try:
        from pysentimiento import create_analyzer
        
        before = get_vram_mb()
        log(f"   Antes de cargar: {before:.1f} MB")
        
        emotion_analyzer = create_analyzer(
            task="emotion",
            lang="es"
        )
        
        after = get_vram_mb()
        log(f"   Después de cargar: {after:.1f} MB")
        log(f"   ➜ DELTA: +{after - before:.1f} MB")
        
        snapshots.append(vram_snapshot("POST-EMOTION"))
        
        # Limpiar
        del emotion_analyzer
        gc.collect()
        torch.cuda.empty_cache()
        
    except Exception as e:
        log(f"   ❌ Error: {e}")
    
    log("")
    
    # =========================================================================
    # 6. OPENAI WHISPER BASE (Wake Word)
    # =========================================================================
    log("-" * 70)
    log("6. OPENAI WHISPER BASE (Wake Word)")
    log("-" * 70)
    
    try:
        import whisper
        
        before = get_vram_mb()
        log(f"   Antes de cargar: {before:.1f} MB")
        
        wake_model = whisper.load_model("base", device="cuda")
        
        after = get_vram_mb()
        log(f"   Después de cargar: {after:.1f} MB")
        log(f"   ➜ DELTA: +{after - before:.1f} MB")
        
        snapshots.append(vram_snapshot("POST-WAKEWORD"))
        
        # Limpiar
        del wake_model
        gc.collect()
        torch.cuda.empty_cache()
        
    except Exception as e:
        log(f"   ❌ Error: {e}")
    
    log("")
    
    # =========================================================================
    # RESUMEN FINAL
    # =========================================================================
    log("=" * 70)
    log("RESUMEN DE SNAPSHOTS")
    log("=" * 70)
    
    for snap in snapshots:
        log(f"  {snap['label']:30} | GPU: {snap['total_gpu']:8.1f} MB | PyTorch: {snap['allocated']:8.1f} MB")
    
    log("")
    log("=" * 70)
    log("NOTAS IMPORTANTES:")
    log("=" * 70)
    log("• PyTorch CUDA solo trackea tensores de PyTorch")
    log("• DirectML (ONNX LLM) usa memoria GPU separada")
    log("• TTS (proceso separado) no se incluye aquí")
    log("• Para ver TTS, usar nvidia-smi mientras TTS está corriendo")
    log("")
    
    # Guardar reporte
    report_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "vram_report.txt"
    )
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    
    log(f"Reporte guardado en: {report_path}")
    
    return snapshots


def profile_with_memlab():
    """Usa pytorch_memlab para análisis más detallado"""
    
    print("\n" + "=" * 70)
    print("PYTORCH MEMLAB - ANÁLISIS DE TENSORES EN MEMORIA")
    print("=" * 70 + "\n")
    
    # Cargar un modelo de ejemplo para análisis
    from faster_whisper import WhisperModel
    
    model = WhisperModel("medium", device="cuda", compute_type="int8")
    
    # Crear reporter
    reporter = MemReporter(model)
    reporter.report()
    
    # Limpiar
    del model
    gc.collect()
    torch.cuda.empty_cache()


if __name__ == "__main__":
    print("\n🔍 Iniciando VRAM Profiler para Yui...\n")
    
    # Verificar CUDA
    if not torch.cuda.is_available():
        print("❌ CUDA no disponible. Este profiler requiere GPU NVIDIA.")
        sys.exit(1)
    
    print(f"GPU detectada: {torch.cuda.get_device_name(0)}")
    print(f"VRAM total: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    print()
    
    # Ejecutar profiling
    snapshots = profile_model_loading()
    
    print("\n✅ Profiling completado!")
