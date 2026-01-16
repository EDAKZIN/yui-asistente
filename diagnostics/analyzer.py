"""
Yui AI Assistant - Memory Analyzer CLI
Herramienta de linea de comandos para analizar logs de memoria
"""

import argparse
import sys
from pathlib import Path


def cmd_analyze(log_path: str):
    """Analiza un log de memoria"""
    from diagnostics.memory_monitor import MemoryMonitor
    
    monitor = MemoryMonitor()
    result = monitor.analyze_log(Path(log_path))
    
    print("\n" + "=" * 60)
    print("ANALISIS DE MEMORIA")
    print("=" * 60)
    
    if "error" in result:
        print(f"ERROR: {result['error']}")
        return
    
    print(f"Total snapshots:   {result['total_snapshots']}")
    print(f"Total operaciones: {result['total_operations']}")
    print(f"Total alertas:     {result['total_alerts']}")
    
    if result.get("summary"):
        s = result["summary"]
        print("\n--- Resumen VRAM ---")
        print(f"Inicio (promedio): {s['vram_start_avg_mb']:.0f} MB")
        print(f"Final (promedio):  {s['vram_end_avg_mb']:.0f} MB")
        print(f"Crecimiento:       {s['vram_growth_mb']:+.0f} MB")
        print(f"Pico maximo:       {s['vram_peak_mb']:.0f} MB")
        print(f"Minimo:            {s['vram_min_mb']:.0f} MB")
    
    print("\n--- Deteccion de Fugas ---")
    if result["leak_detected"]:
        print("⚠️  POSIBLE FUGA DETECTADA")
        for suspect in result["leak_suspects"]:
            print(f"  - {suspect}")
    else:
        print("✅ No se detectaron fugas obvias")
    
    if result.get("alerts"):
        print("\n--- Ultimas Alertas ---")
        for alert in result["alerts"]:
            print(f"  {alert}")
    
    print("=" * 60)


def cmd_live():
    """Monitor en tiempo real"""
    from diagnostics.memory_monitor import MemoryMonitor
    import time
    
    monitor = MemoryMonitor()
    print("Monitor de memoria en tiempo real (Ctrl+C para salir)")
    print("-" * 60)
    
    try:
        while True:
            snapshot = monitor.take_snapshot()
            print(f"\r{snapshot.to_log_line()}", end="", flush=True)
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nDetenido")


def cmd_summary():
    """Muestra resumen actual"""
    from diagnostics.memory_monitor import MemoryMonitor
    
    monitor = MemoryMonitor()
    print(monitor.get_summary())


def main():
    parser = argparse.ArgumentParser(
        description="Yui Memory Analyzer - Herramienta de diagnostico de memoria"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")
    
    # Subcomando: analyze
    analyze_parser = subparsers.add_parser("analyze", help="Analiza un log de memoria")
    analyze_parser.add_argument(
        "log_path",
        nargs="?",
        default="logs/memory.log",
        help="Ruta al archivo de log (default: logs/memory.log)"
    )
    
    # Subcomando: live
    subparsers.add_parser("live", help="Monitor en tiempo real")
    
    # Subcomando: summary
    subparsers.add_parser("summary", help="Muestra resumen actual de memoria")
    
    args = parser.parse_args()
    
    if args.command == "analyze":
        cmd_analyze(args.log_path)
    elif args.command == "live":
        cmd_live()
    elif args.command == "summary":
        cmd_summary()
    else:
        parser.print_help()


if __name__ == "__main__":
    # Agregar directorio padre al path para imports
    sys.path.insert(0, str(Path(__file__).parent.parent))
    main()
