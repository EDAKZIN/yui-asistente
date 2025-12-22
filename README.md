# 🎤 Yui AI Assistant

**Yui** es una asistente de voz con inteligencia artificial creada por **EDAKZIN**. Combina reconocimiento de voz, generación de lenguaje natural y clonación de voz para ofrecer una experiencia conversacional única.

## ✨ Características

- 🎙️ **STT (Speech-to-Text)**: OpenAI Whisper "medium" con GPU
- 🧠 **LLM**: Llama 3.2 3B con cuantización 4-bit (~2.5GB VRAM)
- 🗣️ **TTS con clonación de voz**: Coqui XTTS v2
- 💾 **Memoria selectiva**: ChromaDB con filtrado inteligente
- ⚡ **Comandos de voz**: Abrir apps, hora, fecha, búsqueda web
- 🔍 **Búsqueda web**: Brave Search API
- 🎭 **Personalidad única**: Amigable por defecto, sarcástica si la provocan
- 🖥️ **Desktop Pet**: Mascota Live2D con Electron + Panel de Control
- ⏰ **Recordatorios**: Sistema de recordatorios por voz
- 💬 **Comentarios proactivos**: Yui comenta cuando llevas tiempo sin hablar

## 🚀 Pipeline

```
Usuario → Whisper → Comandos/LLM → XTTS v2 → Audio
  habla   (medium)   (detecta)     (Navia)   (respuesta)
```

## 📋 Requisitos

- Python 3.11+
- Node.js 18+ (para Electron)
- NVIDIA GPU con CUDA (RTX 3060 o superior recomendado)
- ~8GB VRAM total durante ejecucion
- Windows 10/11

## 🔧 Instalacion

### Backend (Python)
```powershell
# Clonar repositorio
git clone https://github.com/EDAKZIN/yui-assistant.git
cd yui-assistant

# Crear entorno virtual
python -m venv venv
.\venv\Scripts\activate

# Instalar PyTorch con CUDA primero
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# Instalar dependencias Python
pip install -r requirements.txt

# Configurar variables de entorno
copy .env.example .env
# Edita .env y agrega tu BRAVE_API_KEY
```

### Frontend (Electron)
```powershell
# Instalar dependencias de Electron
cd desktop-pet
npm install
cd ..
```

### 🔑 Configurar Brave Search API

1. Ve a [https://brave.com/search/api/](https://brave.com/search/api/)
2. Crea una cuenta y obtén tu API key (plan Free: 2,000 consultas/mes)
3. Edita `.env` y agrega tu key:
   ```
   BRAVE_API_KEY=BSA_xxxxxxxxxx
   ```

## 🎮 Uso

### Modo Desktop Pet + Panel de Control (Recomendado)
```powershell
.\venv\Scripts\python.exe run_electron.py
```

Esto inicia:
- Desktop Pet (mascota Live2D en esquina)
- Panel de Control (accesible desde bandeja del sistema)
- Servidor WebSocket para comunicacion

1. **Espera** a que carguen los modelos (~2-3 min primera vez)
2. **Habla** diciendo "Yui" seguido de tu mensaje
3. **Yui responde** con voz clonada

## 🖥️ Interfaz

El sistema incluye:
- **Desktop Pet**: Mascota Live2D animada que sigue el cursor
- **Panel de Control**: Accesible desde la bandeja del sistema
  - Estado visual (activa, escuchando, procesando)
  - Transcripcion en vivo
  - Respuestas de Yui
  - Botones de control (silenciar, reposo, configuracion)
  - Tecla de silencio personalizable
- **Menu de bandeja**: Expresiones, animaciones, modelos

## ⚡ Comandos de Voz

| Comando | Ejemplo |
|---------|---------|
| Abrir apps | "Abre Chrome", "Abre Spotify" |
| Hora | "¿Qué hora es?" |
| Fecha | "¿Qué fecha es?", "¿Qué día es?" |
| Búsqueda web | "Busca quién es el presidente de Perú" |
| Recordatorios | "Recuérdame en 5 minutos revisar el correo" |
| Alarmas | "Pon una alarma para 2 minutos" |

**Aliases configurados:** Opera → Navegador Opera GX, VSCode → Visual Studio Code

## ⏰ Sistema de Recordatorios

Yui puede configurar recordatorios con lenguaje natural:

- "Yui, recuérdame en 5 minutos pararme"
- "Pon una alarma para 2 minutos"
- "Hazme un recordatorio en 30 segundos de revisar el celular"
- "Timer para 10 minutos"

Soporta:
- Números escritos: "en dos minutos", "en cinco segundos"
- Números dígitos: "en 5 minutos", "en 30 segundos"
- Horas, minutos, segundos

## 📁 Estructura

```
yui-asistente/
├── backend/
│   ├── yui_assistant.py    # Pipeline principal
│   ├── whisper_stt.py      # Speech-to-Text
│   ├── llama_llm.py        # LLM (Llama 3.2)
│   ├── coqui_tts.py        # Text-to-Speech (XTTS v2)
│   ├── commands.py         # Comandos de voz
│   ├── web_search.py       # Busqueda web (Brave API)
│   ├── memory_system.py    # Memoria selectiva (ChromaDB)
│   ├── continuous_listener.py # Escucha continua con VAD
│   ├── vad_listener.py     # Voice Activity Detection
│   ├── state_machine.py    # Maquina de estados
│   ├── reminders.py        # Sistema de recordatorios
│   ├── gui_api.py          # API para la GUI
│   ├── websocket_server.py # Servidor WebSocket
│   ├── logger.py           # Sistema de logging dual
│   └── audio_manager.py    # Grabacion/reproduccion
├── desktop-pet/            # Aplicacion Electron
│   ├── src/main.ts         # Proceso principal
│   ├── src/control-panel.ts  # Panel de control
│   ├── index.html          # Ventana Live2D
│   ├── control-panel.html  # Panel de control
│   └── models/             # Modelos Live2D
├── voice_samples/          # Muestras de voz para clonacion
├── logs/
│   ├── yui.log             # Log de conversaciones
│   └── yui_debug.log       # Log de funcionamiento interno
├── data/chromadb/          # Base de datos de memoria
├── .env                    # Variables de entorno (API keys)
├── config.json             # Configuracion
├── run_electron.py         # Lanzador principal
└── requirements.txt        # Dependencias Python
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
- Tecla de silencio (sección `gui`)
- Comentarios proactivos (sección `listening`)

## 🛠️ Stack Tecnológico

| Componente | Tecnología |
|------------|------------|
| STT | OpenAI Whisper (medium) |
| LLM | Llama 3.2 3B (HuggingFace) |
| TTS | Coqui XTTS v2 |
| VAD | Silero VAD |
| Búsqueda Web | Brave Search API |
| Memoria | ChromaDB + Sentence Transformers |
| Comandos | AppOpener |
| Cuantización | bitsandbytes 4-bit |
| GUI | Electron + Live2D |

## 📊 Rendimiento

- **Tiempo de respuesta**: 10-20 segundos (incluye TTS)
- **VRAM LLM**: ~2.5 GB
- **VRAM XTTS**: ~1.5 GB
- **VRAM Whisper medium**: ~1 GB
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
