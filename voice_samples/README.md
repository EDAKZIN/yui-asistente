# Voice Samples

Esta carpeta contiene las muestras de voz utilizadas para el clonado de voz TTS.

## ⚠️ IMPORTANTE

**Los archivos de audio NO están incluidos en este repositorio por razones de copyright.**

Debes proporcionar tus propias muestras de audio para el clonado de voz.

## 📋 Requisitos para las muestras de voz

Para que el TTS pueda clonar una voz correctamente, necesitas:

1. **Formato**: `.wav` o `.ogg` (preferiblemente WAV 22050Hz mono)
2. **Duración**: Entre 5-30 segundos por archivo
3. **Calidad**: Audio limpio, sin ruido de fondo ni música
4. **Contenido**: Solo voz hablando (no cantar, no efectos)
5. **Cantidad**: Al menos 3-5 muestras diferentes

## 🎤 Opciones para obtener muestras

### Opción 1: Grabar tu propia voz
- Usa un micrófono de calidad
- Graba en un ambiente silencioso
- Habla de forma natural

### Opción 2: Usar voces sintéticas libres
- [ElevenLabs](https://elevenlabs.io/) - Voces sintéticas
- [CoquiTTS](https://coqui.ai/) - Voces de demostración

### Opción 3: Voces de dominio público
- Busca grabaciones de dominio público
- Verifica la licencia antes de usar

## 📁 Estructura esperada

Coloca tus archivos de audio directamente en esta carpeta:

```
voice_samples/
├── README.md (este archivo)
├── sample_01.wav
├── sample_02.wav
├── sample_03.wav
└── ...
```

## 🔧 Configuración

Una vez que tengas tus muestras, el TTS las usará automáticamente para:
- Clonar la voz al sintetizar respuestas
- Generar el archivo `.json` de referencia

---

**Nota**: Los archivos `.wav` y `.ogg` están ignorados por git para proteger tu privacidad y evitar problemas de copyright.
