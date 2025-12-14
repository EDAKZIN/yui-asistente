# 🎤 Yui AI Assistant

**Yui** es una asistente de voz con inteligencia artificial creada por **EDAKZIN**. Combina reconocimiento de voz, generación de lenguaje natural y clonación de voz para ofrecer una experiencia conversacional única.

## ✨ Características

- 🎙️ **STT (Speech-to-Text)**: OpenAI Whisper con GPU
- 🧠 **LLM**: Llama 3.2 3B con cuantización 4-bit (~2.5GB VRAM)
- 🗣️ **TTS con clonación de voz**: Coqui XTTS v2
- 💾 **Memoria persistente**: ChromaDB con búsqueda semántica
- 🎭 **Personalidad única**: Dulce pero con actitud cuando bromean

## 🚀 Pipeline

```
Usuario → Whisper → Llama 3.2 → XTTS v2 → Audio
  habla    (GPU)     (4-bit)    (Navia)   (respuesta)
```

## 📋 Requisitos

- Python 3.11+
- NVIDIA GPU con CUDA (RTX 3060 o superior recomendado)
- ~8GB VRAM total durante ejecución
- Windows 10/11

## 🔧 Instalación

```powershell
# Clonar repositorio
git clone https://github.com/EDAKZIN/yui-assistant.git
cd yui-assistant

# Crear entorno virtual
python -m venv venv
.\venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

## 🎮 Uso

```powershell
.\venv\Scripts\python.exe backend\yui_assistant.py
```

1. **Espera** a que carguen los modelos (~1-2 min primera vez)
2. **Presiona Enter** para empezar a grabar
3. **Habla** tu mensaje
4. **Presiona Enter** para detener y procesar
5. **Yui responde** con voz clonada

## 📁 Estructura

```
yui-assistant/
├── backend/
│   ├── yui_assistant.py    # Pipeline principal
│   ├── whisper_stt.py      # Speech-to-Text
│   ├── llama_llm.py        # LLM (Llama 3.2)
│   ├── coqui_tts.py        # Text-to-Speech (XTTS v2)
│   ├── memory_system.py    # Memoria (ChromaDB)
│   └── audio_manager.py    # Grabación/reproducción
├── voice_samples/          # Muestras de voz para clonación
├── data/chromadb/          # Base de datos de memoria
├── config.json             # Configuración
└── requirements.txt        # Dependencias
```

## 🎨 Personalización de Voz

Para cambiar la voz de Yui:
1. Coloca archivos de audio (.wav, .ogg, .mp3) en `voice_samples/`
2. Reinicia la aplicación
3. XTTS usará las nuevas muestras automáticamente

**Recomendaciones:**
- 10-30 segundos de audio claro
- Sin música de fondo
- Variedad de tonos/emociones

## ⚙️ Configuración

Edita `config.json` para ajustar:
- Modelo de Whisper (base, small, medium)
- Idioma de reconocimiento
- Parámetros del LLM

## 🛠️ Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| STT | OpenAI Whisper |
| LLM | Llama 3.2 3B (HuggingFace) |
| TTS | Coqui XTTS v2 |
| Memoria | ChromaDB + Sentence Transformers |
| Cuantización | bitsandbytes 4-bit |

## 📊 Rendimiento

- **Tiempo de respuesta**: 10-25 segundos (incluye TTS)
- **VRAM LLM**: ~2.5 GB
- **VRAM XTTS**: ~1.5 GB
- **Carga inicial**: ~2 minutos

## 📄 Licencia

MIT License - Creado por **EDAKZIN** 🚀
