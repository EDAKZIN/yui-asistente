"""
Yui AI Assistant - Pipeline Principal
Integra todos los componentes: STT, LLM, TTS, RVC
"""

import sys
from pathlib import Path

# Agregar backend al path
sys.path.insert(0, str(Path(__file__).parent))

from config import Config
from logger import YuiLogger
from audio_manager import AudioManager
from whisper_stt import WhisperSTT
from llama_llm import LlamaLLM
from coqui_tts import CoquiTTS
from memory_system import MemorySystem
import logging

class YuiAssistant:
    """Asistente de voz Yui - Pipeline completo"""
    
    def __init__(self):
        """Inicializa el asistente Yui"""
        print("=" * 70)
        print(" " * 20 + "YUI AI ASSISTANT")
        print("=" * 70)
        
        # Obtener ruta raíz del proyecto (un nivel arriba de backend/)
        self.project_root = Path(__file__).parent.parent
        
        # Cargar configuración
        self.config = Config.load()
        
        # Configurar logging con ruta relativa
        log_dir = self.project_root / self.config['paths']['logs_dir']
        self.logger = YuiLogger.setup(str(log_dir))
        
        self.logger.info("Inicializando Yui AI Assistant...")
        
        # Inicializar componentes
        self._init_components()
        
        self.logger.info(" Yui inicializada correctamente")
        print("=" * 70)
    
    def _init_components(self):
        """Inicializa todos los componentes del pipeline"""
        # Audio Manager
        sample_rate = self.config['audio']['sample_rate']
        channels = self.config['audio']['channels']
        self.audio_manager = AudioManager(sample_rate=sample_rate, channels=channels)
        
        # Whisper STT
        whisper_config = self.config['models']['whisper']
        self.whisper = WhisperSTT(
            model_size=whisper_config['model_size'],
            language=whisper_config['language']
        )
        
        # Llama LLM
        llama_config = self.config['models']['llama']
        llama_path = self.config['paths']['llama_model']
        self.llama = LlamaLLM(
            model_path=llama_path,
            max_length=llama_config['max_length'],
            temperature=llama_config['temperature'],
            top_p=llama_config['top_p'],
            device=llama_config['device']
        )
        
        
        # TTS con Coqui XTTS v2 (usa rutas relativas)
        voice_samples_path = self.project_root / self.config['paths'].get('voice_samples_dir', 'voice_samples')
        self.tts = CoquiTTS(voice_samples_dir=str(voice_samples_path))
        
        # Sistema de Memoria (ruta relativa)
        chromadb_path = self.project_root / self.config['paths']['chromadb_path']
        self.memory = MemorySystem(db_path=str(chromadb_path))
    
    def load_models(self):
        """Carga todos los modelos en memoria"""
        self.logger.info("Cargando modelos...")
        
        print("\n Cargando modelos (esto puede tardar 1-2 minutos)...")
        
        # Cargar Whisper
        print("  [1/4] Cargando Whisper...")
        self.whisper.load_model()
        
        # Cargar Llama
        print("  [2/4] Cargando Llama (esto puede tardar más)...")
        self.llama.load_model()
        
        # Cargar XTTS v2
        print("  [3/4] Cargando XTTS v2 con voz de Navia...")
        self.tts.load_model()
        
        # Cargar sistema de memoria
        print("  [4/4] Cargando sistema de memoria...")
        self.memory.load()
        
        print(" Todos los modelos cargados\n")
    
    def process_voice_input(self, duration: float = None) -> dict:
        """
        Procesa una entrada de voz completa
        
        Args:
            duration: Duración de grabación en segundos (None = hasta Enter)
        
        Returns:
            Diccionario con 'transcript', 'response', 'audio'
        """
        try:
            # Obtener dispositivo de micrófono seleccionado
            device = getattr(self, 'selected_mic', None)
            
            # 1. Grabar audio del usuario (usando micrófono seleccionado)
            if duration:
                audio_input = self.audio_manager.record(duration=duration, device=device)
            else:
                audio_input = self.audio_manager.record_until_enter(device=device)
            
            if len(audio_input) == 0:
                self.logger.warning("No se grabó audio")
                return {"success": False, "error": "No audio recorded"}
            
            # 2. Transcribir con Whisper
            transcript = self.whisper.transcribe(audio_input)
            
            if not transcript:
                self.logger.warning("No se detectó habla")
                return {"success": False, "error": "No speech detected"}
            
            # 3. Generar respuesta con Llama
            response_text = self.llama.generate_response(transcript)
            
            # 4. Sintetizar con pyttsx3 (ya reproduce directamente)
            print(f"\n Yui: {response_text}\n")
            self.tts.synthesize(response_text)
            
            # 5. Guardar conversación en memoria
            self.memory.add_conversation(transcript, response_text)
            
            return {
                "success": True,
                "transcript": transcript,
                "response": response_text
            }
            
        except KeyboardInterrupt:
            self.logger.info("Proceso interrumpido por el usuario")
            return {"success": False, "error": "Interrupted"}
        except Exception as e:
            self.logger.error(f"Error en pipeline: {e}")
            return {"success": False, "error": str(e)}
    
    def run_interactive(self):
        """Modo interactivo continuo"""
        print("\n" + "=" * 70)
        print("MODO INTERACTIVO")
        print("=" * 70)
        print("Instrucciones:")
        print("  - Presiona Enter para empezar a grabar")
        print("  - Habla tu mensaje")
        print("  - Presiona Enter nuevamente para detener y procesar")
        print("  - Escribe 'salir' o presiona Ctrl+C para terminar")
        print("=" * 70 + "\n")
        
        while True:
            try:
                # Esperar comando del usuario
                cmd = input("Presiona Enter para hablar (o escribe 'salir' para terminar): ").strip().lower()
                
                if cmd in ['salir', 'exit', 'quit']:
                    print("\n ¡Hasta luego!")
                    break
                
                # Procesar entrada de voz
                result = self.process_voice_input(duration=None)
                
                if not result["success"]:
                    print(f" {result.get('error', 'Error desconocido')}")
                
            except KeyboardInterrupt:
                print("\n\n ¡Hasta luego!")
                break
            except Exception as e:
                self.logger.error(f"Error en modo interactivo: {e}")
                print(f" Error: {e}")
    
    def test_components(self):
        """Prueba cada componente individualmente"""
        print("\n" + "=" * 70)
        print("MODO PRUEBA DE COMPONENTES")
        print("=" * 70)
        
        # Probar audio
        print("\n[1/4] Probando grabación de audio...")
        input("  Presiona Enter para grabar 3 segundos de audio de prueba...")
        test_audio = self.audio_manager.record(duration=3.0)
        print("   Grabación completada")
        
        # Probar Whisper
        print("\n[2/4] Probando Whisper STT...")
        transcript = self.whisper.transcribe(test_audio)
        print(f"  Transcripción: '{transcript}'")
        
        # Probar Llama
        print("\n[3/4] Probando Llama LLM...")
        test_input = "Hola, ¿cómo estás?"
        response = self.llama.generate_response(test_input)
        print(f"  Respuesta: '{response}'")
        
        # Probar Piper + RVC
        print("\n[4/4] Probando Piper TTS + RVC...")
        tts_audio, tts_sr = self.piper.synthesize(response)
        final_audio, final_sr = self.rvc.convert_voice(tts_audio, tts_sr)
        print("  Reproduciendo audio...")
        self.audio_manager.play(final_audio, final_sr)
        
        print("\n Prueba de componentes completada")
        print("=" * 70)


def main():
    """Función principal"""
    try:
        # Crear asistente
        yui = YuiAssistant()
        
        # Cargar modelos
        yui.load_models()
        
        # Opción de configurar micrófono
        print("\n¿Deseas configurar el micrófono?")
        print("  1. Usar micrófono por defecto")
        print("  2. Listar dispositivos y seleccionar")
        mic_choice = input("\nOpción (1/2, Enter=1): ").strip()
        
        selected_device = None
        if mic_choice == "2":
            yui.audio_manager.list_devices()
            try:
                device_id = input("Ingresa el ID del micrófono (o Enter para default): ").strip()
                if device_id:
                    selected_device = int(device_id)
                    print(f"  Usando dispositivo: {selected_device}")
            except ValueError:
                print("  ID inválido, usando dispositivo por defecto")
        
        # Guardar dispositivo seleccionado
        yui.selected_mic = selected_device
        
        # Mostrar menú
        print("\nSelecciona un modo:")
        print("  1. Modo interactivo (conversación continua)")
        print("  2. Prueba de componentes")
        print("  3. Una sola interacción")
        
        choice = input("\nOpción (1/2/3): ").strip()
        
        if choice == "1":
            yui.run_interactive()
        elif choice == "2":
            yui.test_components()
        elif choice == "3":
            print("\n Una sola interacción:")
            yui.process_voice_input(duration=None)
        else:
            print("Opción no válida")
    
    except KeyboardInterrupt:
        print("\n\n ¡Hasta luego!")
    except Exception as e:
        print(f"\n Error fatal: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
