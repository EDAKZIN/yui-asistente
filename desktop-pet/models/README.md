# Directorio de Modelos VRM

Coloca tus modelos VRM (`.vrm`) aqui. El modelo Yui incluido en este proyecto fue creado en **VRoid Studio** y es propiedad de **EDAKZIN**, por lo que **no se distribuye** en este repositorio.

## Crear tu Propio Modelo

Si quieres usar este proyecto con tu propio personaje:

1. Descarga [VRoid Studio](https://vroid.com/en/studio) (gratuito)
2. Crea tu personaje VRM
3. Exporta como `.vrm` (formato VRM 1.0 recomendado)
4. Coloca el archivo en este directorio dentro de su propia carpeta

### Estructura de Ejemplo

```
models/
└── Tu_Modelo/
    └── TuModelo.vrm
```

## Configuracion

Edita `model-config.json` en el directorio padre (`desktop-pet/`) para apuntar a tu modelo:

```json
{
  "modelPath": "./models/Tu_Modelo/TuModelo.vrm",
  "scale": 2.0,
  "position": { "x": 0, "y": -1.5 }
}
```

> [!NOTE]
> La posicion `y` controla la altura del modelo en pantalla. Valores mas negativos lo bajan (para que solo se vea la mitad superior como desktop pet).

---

## Mapeo de Expresiones

Yui detecta emociones y cambia las expresiones del modelo automaticamente. Para que esto funcione, debes mapear las expresiones de tu modelo VRM a las emociones del sistema.

### Archivos a modificar

Debes editar **DOS archivos**:

1. `desktop-pet/model-config.json` - Para el frontend (Electron)
2. `backend/continuous_listener.py` - Para el backend (Python)

### Paso 1: Identificar las expresiones de tu modelo

Abre tu modelo en VRoid Studio o Three.js Inspector. Las expresiones VRM estandar incluyen:
- `happy`, `angry`, `sad`, `relaxed`, `surprised`
- Tu modelo puede tener expresiones custom adicionales

### Paso 2: Editar model-config.json

```json
{
  "expressions": {
    "idle": null,
    "speaking": null,
    "happy": "happy",
    "sad": "sad",
    "angry": "angry",
    "fear": null,
    "disgust": null,
    "surprise": "surprised",
    "blush": "relaxed"
  }
}
```

**Reglas:**
- Usa `null` si tu modelo NO tiene esa expresion
- El nombre debe coincidir EXACTAMENTE con el de tu modelo (case-sensitive)
- `idle` y `speaking` son opcionales

### Paso 3: Editar continuous_listener.py

En `backend/continuous_listener.py`, busca el diccionario `emotion_to_expression` y actualizalo:

```python
self.emotion_to_expression = {
    'happy': 'happy',
    'sad': 'sad',
    'angry': 'angry',
    'fear': None,
    'disgust': None,
    'surprise': 'surprised',
    'neutral': None  # SIEMPRE debe ser None
}
```

### Errores comunes

| Error | Causa | Solucion |
|-------|-------|----------|
| Expresion no cambia | Nombre mal escrito | Verifica case-sensitive |
| Expresion aleatoria al poner "Normal" | `neutral` no es `None` | Pon `'neutral': None` |
| Error en consola | La expresion no existe en el modelo | Revisa las expresiones disponibles |
| Solo edite un archivo | Falta sincronizar | Ambos archivos deben coincidir |

---

## Aviso de Copyright

Los modelos VRM no estan incluidos en este repositorio. Asegurate de tener los derechos para usar cualquier modelo que agregues.

El modelo **Yui** es propiedad exclusiva de **EDAKZIN** y no se redistribuye.
