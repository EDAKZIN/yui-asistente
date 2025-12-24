"""
Yui AI Assistant - Módulo TTS con Coqui XTTS v2
Text-to-Speech con clonación de voz usando XTTS
Soporta múltiples muestras de voz para mejor calidad
"""

import torch
from TTS.api import TTS
import logging
import os
import tempfile
import sounddevice as sd
import soundfile as sf
import glob

logger = logging.getLogger('Yui.Coqui')

class CoquiTTS:
    """Sintetizador de voz con clonación usando Coqui XTTS v2"""
    
    def __init__(self, voice_samples_dir: str = "voice_samples"):
        """
        Inicializa Coqui TTS
        
        Args:
            voice_samples_dir: Carpeta con muestras de voz (.wav, .ogg, .mp3)
        """
        self.voice_samples_dir = voice_samples_dir
        self.voice_samples = []
        self.tts = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        logger.info("Inicializando Coqui XTTS v2")
        logger.info(f"  Carpeta de voces: {voice_samples_dir}")
        logger.info(f"  Dispositivo: {self.device}")
        
        # Callback para notificar cuando síntesis completa
        self._on_synthesis_complete = None
    
    def set_synthesis_complete_callback(self, callback):
        """
        Configura callback para cuando TTS completa síntesis
        
        Args:
            callback: Función a llamar con el texto sintetizado
        """
        self._on_synthesis_complete = callback
    
    def _find_voice_samples(self):
        """Busca todas las muestras de voz en la carpeta"""
        samples = []
        for ext in ['*.wav', '*.ogg', '*.mp3', '*.flac']:
            pattern = os.path.join(self.voice_samples_dir, ext)
            samples.extend(glob.glob(pattern))
        
        if samples:
            logger.info(f"  Encontradas {len(samples)} muestras de voz")
            for s in samples[:5]:  # Mostrar solo primeras 5
                logger.info(f"    - {os.path.basename(s)}")
            if len(samples) > 5:
                logger.info(f"    ... y {len(samples) - 5} más")
        else:
            logger.warning(f"  No se encontraron muestras en {self.voice_samples_dir}")
        
        return samples
    
    def load_model(self):
        """Carga el modelo XTTS v2"""
        if self.tts is not None:
            logger.warning("XTTS ya está cargado")
            return
        
        try:
            logger.info(" Cargando modelo XTTS v2...")
            logger.info("  Primera vez descargará ~1.8GB (se guarda en caché)")
            
            # Cargar modelo XTTS v2
            self.tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(self.device)
            
            # Buscar muestras de voz
            self.voice_samples = self._find_voice_samples()
            
            if not self.voice_samples:
                logger.error("  No hay muestras de voz disponibles")
                raise FileNotFoundError("Se requiere al menos 1 muestra de voz")
            
            logger.info(" XTTS v2 cargado correctamente")
            logger.info(f"  Muestras de voz: {len(self.voice_samples)}")
            
        except Exception as e:
            logger.error(f" Error al cargar XTTS: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def synthesize(self, text: str, language: str = "es"):
        """
        Sintetiza texto a voz con clonación
        
        Args:
            text: Texto a sintetizar
            language: Código de idioma (es, en, fr, de, it, pt, etc.)
        """
        if self.tts is None:
            self.load_model()
        
        logger.info(f" Sintetizando: '{text[:50]}...'")
        
        try:
            # Crear archivo temporal para audio
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                output_path = tmp_file.name
            
            # Usar múltiples muestras si están disponibles (mejor calidad)
            # XTTS acepta lista de archivos de referencia
            speaker_wavs = self.voice_samples if self.voice_samples else None
            
            if speaker_wavs:
                # Usar todas las muestras disponibles para mejor calidad
                # La primera síntesis tardará más, pero las siguientes usan el embedding cacheado
                samples_to_use = speaker_wavs
                logger.debug(f"  Usando {len(samples_to_use)} muestras de referencia")
                
                self.tts.tts_to_file(
                    text=text,
                    speaker_wav=samples_to_use,
                    language=language,
                    file_path=output_path
                )
            else:
                # Sin muestras - usar voz predeterminada
                self.tts.tts_to_file(
                    text=text,
                    language=language,
                    file_path=output_path
                )
            
            # Cargar audio en memoria
            audio_data, sample_rate = sf.read(output_path)
            
            # CRITICO: Notificar GUI AQUI - justo antes que audio suene
            # Timing perfecto: subtitulo aparece EXACTAMENTE cuando audio empieza
            if self._on_synthesis_complete is not None:
                self._on_synthesis_complete(text)
            
            # Reproducir audio INMEDIATAMENTE después del notify
            sd.play(audio_data, sample_rate)
            sd.wait()
            
            # Limpiar archivo temporal
            os.unlink(output_path)
            
            
            logger.info("  Síntesis completada")
            
        except Exception as e:
            logger.error(f" Error al sintetizar: {e}")
            import traceback
            logger.error(traceback.format_exc())
            raise
    
    def change_voice(self, new_samples_dir: str):
        """
        Cambia la voz a usar (para cambiar personaje)
        
        Args:
            new_samples_dir: Nueva carpeta con muestras de voz
        """
        logger.info(f" Cambiando voz a: {new_samples_dir}")
        self.voice_samples_dir = new_samples_dir
        self.voice_samples = self._find_voice_samples()
        logger.info(f"  Nueva voz cargada: {len(self.voice_samples)} muestras")
    
    def list_available_voices(self) -> list:
        """Lista las muestras de voz disponibles"""
        return [os.path.basename(s) for s in self.voice_samples]
