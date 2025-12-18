# 🎤 Yui AI Assistant

**Yui** es una asistente de voz con inteligencia artificial creada por **EDAKZIN**. Combina reconocimiento de voz, generación de lenguaje natural y clonación de voz para ofrecer una experiencia conversacional única.

## ✨ Características

- 🎙️ **STT (Speech-to-Text)**: OpenAI Whisper "small" con GPU
- 🧠 **LLM**: Llama 3.2 3B con cuantización 4-bit (~2.5GB VRAM)
- 🗣️ **TTS con clonación de voz**: Coqui XTTS v2
- 💾 **Memoria selectiva**: ChromaDB con filtrado inteligente
- ⚡ **Comandos de voz**: Abrir apps, hora, fecha, búsqueda web
- 🔍 **Búsqueda web**: Brave Search API
- 🎭 **Personalidad única**: Amigable por defecto, sarcástica si la provocan

## 🚀 Pipeline

```
Usuario → Whisper → Comandos/LLM → XTTS v2 → Audio
  habla   (small)    (detecta)     (Navia)   (respuesta)
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

# Instalar PyTorch con CUDA primero
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
copy .env.example .env
# Edita .env y agrega tu BRAVE_API_KEY
```

### 🔑 Configurar Brave Search API

1. Ve a [https://brave.com/search/api/](https://brave.com/search/api/)
2. Crea una cuenta y obtén tu API key (plan Free: 2,000 consultas/mes)
3. Edita `.env` y agrega tu key:
   ```
   BRAVE_API_KEY=BSA_xxxxxxxxxx
   ```

## 🎮 Uso

```powershell
.\venv\Scripts\python.exe backend\yui_assistant.py
```

1. **Espera** a que carguen los modelos (~2-3 min primera vez)
2. **Presiona Enter** para empezar a grabar
3. **Habla** tu mensaje
4. **Presiona Enter** para detener y procesar
5. **Yui responde** con voz clonada

## ⚡ Comandos de Voz

| Comando | Ejemplo |
|---------|---------|
| Abrir apps | "Abre Chrome", "Abre Spotify" |
| Hora | "¿Qué hora es?" |
| Fecha | "¿Qué fecha es?", "¿Qué día es?" |
| Búsqueda web | "Busca quién es el presidente de Perú" |

**Aliases configurados:** Opera → Navegador Opera GX, VSCode → Visual Studio Code

## 📁 Estructura

```
yui-asistente/
├── backend/
│   ├── yui_assistant.py    # Pipeline principal
│   ├── whisper_stt.py      # Speech-to-Text
│   ├── llama_llm.py        # LLM (Llama 3.2)
│   ├── coqui_tts.py        # Text-to-Speech (XTTS v2)
│   ├── commands.py         # Comandos de voz
│   ├── web_search.py       # Búsqueda web (Brave API)
│   ├── memory_system.py    # Memoria selectiva (ChromaDB)
│   ├── logger.py           # Sistema de logging dual
│   └── audio_manager.py    # Grabación/reproducción
├── voice_samples/          # Muestras de voz para clonación
├── logs/
│   ├── yui.log             # Log de conversaciones
│   └── yui_debug.log       # Log de funcionamiento interno
├── data/chromadb/          # Base de datos de memoria
├── .env                    # Variables de entorno (API keys)
├── .env.example            # Ejemplo de variables de entorno
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
- Modelo de Whisper (tiny, base, small, medium)
- Idioma de reconocimiento
- Parámetros del LLM

## 🛠️ Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| STT | OpenAI Whisper (small) |
| LLM | Llama 3.2 3B (HuggingFace) |
| TTS | Coqui XTTS v2 |
| Búsqueda Web | Brave Search API |
| Memoria | ChromaDB + Sentence Transformers |
| Comandos | AppOpener |
| Cuantización | bitsandbytes 4-bit |

## 📊 Rendimiento

- **Tiempo de respuesta**: 15-30 segundos (incluye TTS)
- **VRAM LLM**: ~2.5 GB
- **VRAM XTTS**: ~1.5 GB
- **VRAM Whisper small**: ~0.5 GB
- **Carga inicial**: ~2-3 minutos

## 📝 Logs

| Archivo | Contenido |
|---------|-----------|
| `logs/yui.log` | Conversaciones (INFO+) |
| `logs/yui_debug.log` | Funcionamiento interno (DEBUG) |

Los logs se reinician en cada ejecución.

## 🔒 Seguridad

Apps bloqueadas por seguridad: cmd, powershell, regedit, taskmgr, diskpart, y más.

## 📄 Licencia

MIT License - Creado por **EDAKZIN** 🚀
