# 🎤 Yui AI Assistant

**Yui** es una asistente de voz con inteligencia artificial creada por **EDAKZIN**. Combina reconocimiento de voz, generacion de lenguaje natural y clonacion de voz para ofrecer una experiencia conversacional unica con subtitulos sincronizados y expresiones faciales dinamicas.

## Caracteristicas

- **STT (Speech-to-Text)**: faster-whisper "medium" con INT8 (optimizado)
- **LLM**: Llama 3.2 3B **Abliterated** GGUF (~2.7GB VRAM, sin censura)
- **TTS con clonacion de voz**: Coqui XTTS v2
- **Memoria selectiva**: ChromaDB con filtrado inteligente
- **Comandos de voz**: Abrir apps, hora, fecha, busqueda web
- **Busqueda web**: Brave Search API con contexto de fecha
- **Personalidad unica**: Amigable por defecto, sarcastica si la provocan
- **Desktop Pet**: Mascota Live2D con Electron + Panel de Control
- **Expresiones faciales**: Detecta emociones y cambia expresiones automaticamente
- **Eventos especiales**: Felicita en Navidad, Ano Nuevo, cumpleanos
- **Subtitulos sincronizados**: Aparecen exactamente cuando el audio empieza
- **Recordatorios**: Sistema de recordatorios por voz
- **Comentarios proactivos**: Yui comenta cuando llevas tiempo sin hablar
- **Modo reposo**: Di "descansa" para liberar VRAM, di "Yui" para despertar
- **Gestión automática de VRAM**: Los modelos se descargan/cargan según el estado
- **Configuracion desde tray**: Ajusta escala, subtitulos y mas desde el menu

## 🚀 Pipeline

```
Usuario → faster-whisper → Comandos/LLM → Emociones → XTTS v2 → Audio
  habla    (medium INT8)    (detecta)     (expresion)  (clonada)    (respuesta)
```

## 📋 Requisitos

- Python 3.11+
- Node.js 18+ (para Electron)
- NVIDIA GPU con CUDA (RTX 3060 o superior recomendado)
- ~10GB VRAM peak durante uso activo (optimizado con GGUF Q5_K_M)
- Windows 10/11

## 📦 Assets Requeridos

> **IMPORTANTE**: Este proyecto requiere assets que debes proveer tú mismo por razones de licencia/copyright.

| Asset | Ubicación | Instrucciones |
|-------|-----------|---------------|
| Modelo Live2D | `desktop-pet/models/` | Ver [README](desktop-pet/models/README.md) |
| Muestras de voz | `voice_samples/` | Ver [README](voice_samples/README.md) |

## 🔧 Instalacion

### Arquitectura
```
yui-asistente/
├── venv/                  # Backend principal (LLM, STT, WebSocket)
├── tts-service/
│   └── venv_tts/          # Microservicio TTS (DeepSpeed + Coqui)
├── backend/               # Código Python
├── desktop-pet/           # Frontend Electron
└── start_yui.bat          # Script de inicio
```

### Backend Principal (Python)
```powershell
# Crear entorno virtual
python -m venv venv
.\venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
copy .env.example .env
# Edita .env y agrega tu BRAVE_API_KEY y GROQ_API_KEY
```

### TTS Microservicio
```powershell
cd tts-service
py -3.11 -m venv venv_tts
.\venv_tts\Scripts\activate

# PyTorch 2.2.2 + CUDA 11.8 (requerido para DeepSpeed 0.13.1)
pip install torch==2.2.2+cu118 torchaudio==2.2.2+cu118 --index-url https://download.pytorch.org/whl/cu118

# DeepSpeed 0.13.1 pre-compilado para Windows
pip install https://github.com/daswer123/deepspeed-windows/releases/download/13.1/deepspeed-0.13.1+cu118-cp311-cp311-win_amd64.whl

# Coqui TTS y RealtimeTTS (sin deps para evitar conflictos)
pip install coqui-tts realtimetts --no-deps

# Resto de dependencias
pip install -r requirements_tts.txt
cd ..
```

> **NOTA**: PyTorch 2.2.2+cu118 es compatible con DeepSpeed 0.13.1. El backend principal usa PyTorch 2.6+ (CUDA 12.4) sin conflictos gracias a la arquitectura de microservicios aislados.

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

### Inicio Automatico (Recomendado)
```powershell
.\start_yui.bat
```

Este script inicia automáticamente:
1. **Backend Principal** - LLM, STT, WebSocket (puerto 58765)
2. **TTS Microservice** se inicia automáticamente cuando Yui habla (puerto 51001)
3. **Desktop Pet** - Mascota Live2D con Electron

### Espera ~2-3 minutos la primera vez (carga de modelos)

**Para interactuar:**
1. Di "Yui" seguido de tu mensaje
2. Yui responderá con voz clonada

## Interfaz

El sistema incluye:
- **Desktop Pet**: Mascota Live2D animada que sigue el cursor
- **Panel de Control**: Accesible desde la bandeja del sistema
  - Estado visual (activa, escuchando, procesando)
  - Transcripcion en vivo
  - Respuestas de Yui
  - Botones de control (silenciar, reposo, rendimiento, configuracion)
  - Tecla de silencio personalizable
- **Menu de bandeja**:
  - Expresiones y animaciones
  - Ajustar escala del modelo
  - Ajustar subtitulos (posicion, tamano)
  - Arrastrar ventana
  - Modo atravesar (passthrough)
  - Reiniciar aplicacion

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
│   ├── yui_assistant.py      # Pipeline principal
│   ├── whisper_stt.py        # Speech-to-Text (faster-whisper)
│   ├── llama_llm.py          # LLM local (llama-cpp-python GGUF)
│   ├── groq_llm.py           # LLM nube (Groq API - modo rendimiento)
│   ├── coqui_tts.py          # Cliente TTS (WebSocket + gestión proceso)
│   ├── commands.py           # Comandos de voz (apps, hora, fecha)
│   ├── web_search.py         # Búsqueda web (Brave API)
│   ├── memory_system.py      # Memoria selectiva (ChromaDB)
│   ├── reflection_system.py  # Sistema de reflexión
│   ├── continuous_listener.py # Escucha continua con VAD
│   ├── vad_listener.py       # Voice Activity Detection (Silero)
│   ├── wake_word.py          # Detector de wake word (OpenAI Whisper)
│   ├── state_machine.py      # Máquina de estados
│   ├── reminders.py          # Sistema de recordatorios
│   ├── emotion_detector.py   # Detección de emociones (RoBERTuito)
│   ├── special_events.py     # Eventos especiales (Navidad, cumple)
│   ├── gui_api.py            # API para la GUI
│   ├── websocket_server.py   # Servidor WebSocket (puerto 58765)
│   ├── logger.py             # Sistema de logging dual
│   ├── config.py             # Configuración centralizada
│   └── audio_manager.py      # Grabación/reproducción
├── tts-service/              # Microservicio TTS (aislado)
│   ├── tts_server.py         # Servidor WebSocket TTS (puerto 51001)
│   ├── requirements_tts.txt  # Dependencias TTS
│   └── venv_tts/             # Entorno virtual aislado
├── desktop-pet/              # Aplicación Electron
│   ├── src/main.ts           # Proceso principal
│   ├── src/control-panel.ts  # Panel de control
│   ├── index.html            # Ventana Live2D
│   ├── control-panel.html    # Panel de control
│   └── models/               # Modelos VRM
├── voice_samples/            # Muestras de voz para clonación
├── logs/
│   ├── yui.log               # Log de conversaciones
│   ├── yui_debug.log         # Log de funcionamiento interno
│   └── tts_process.log       # Log del proceso TTS
├── data/chromadb/            # Base de datos de memoria
├── .env                      # Variables de entorno (API keys)
├── config.json               # Configuración
├── run_electron.py           # Lanzador principal
├── start_yui.bat             # Script de inicio rápido
└── requirements.txt          # Dependencias Python
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
| STT | faster-whisper (medium INT8) |
| LLM Local | Llama 3.2 3B **Abliterated** GGUF Q5_K_M via llama-cpp-python |
| LLM Nube | Groq API (Llama 90B) |
| TTS | Coqui XTTS v2 + DeepSpeed (microservicio aislado) |
| Emociones | pysentimiento/RoBERTuito |
| VAD | Silero VAD |
| Wake Word | OpenAI Whisper base (modo reposo) |
| Búsqueda Web | Brave Search API |
| Memoria | ChromaDB + Sentence Transformers |
| Comandos | AppOpener |
| Backend | PyTorch 2.6 + CUDA 12.4 + llama-cpp-python (CUDA 12.1) |
| TTS Service | PyTorch 2.2.2 + DeepSpeed 0.13.1 (proceso separado) |
| GUI | Electron + Live2D (pixi-live2d-display) |

## 📊 Rendimiento

- **Tiempo de respuesta**: 10-20 segundos (incluye TTS)
- **VRAM LLM**: ~2.7 GB (carga) + KV Cache dinámico
- **VRAM XTTS**: ~3.5 GB (con DeepSpeed)
- **VRAM faster-whisper medium (INT8)**: ~1 GB
- **VRAM Emociones**: ~0.5 GB
- **VRAM Peak total**: ~9-10 GB
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

---
**Versión 6.2.0** - Última actualización: 2026-01-16
