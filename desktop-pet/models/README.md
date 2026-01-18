# Directorio de Modelos Live2D

Coloca tus modelos Live2D aquí. Cada modelo debe estar en su propia carpeta.

## Estructura de Ejemplo

```
models/
└── tu-modelo/
    ├── tu-modelo.model3.json    (requerido)
    ├── tu-modelo.moc3           (requerido)
    ├── tu-modelo.physics3.json  (opcional)
    ├── textures/                 (requerido)
    ├── motions/                  (opcional)
    └── expressions/              (opcional)
```

## Configuración Básica

Edita `model-config.json` en el directorio padre (`desktop-pet/`) para apuntar a tu modelo:

```json
{
  "modelPath": "./models/tu-modelo/tu-modelo.model3.json",
  "scale": 0.4,
  "position": { "x": 0, "y": 100 }
}
```

---

## ⚠️ IMPORTANTE: Mapeo de Expresiones

Yui detecta emociones y cambia las expresiones del modelo automáticamente. Para que esto funcione, debes mapear las expresiones de tu modelo a las emociones del sistema.

### Archivos a modificar

Debes editar **DOS archivos**:

1. `desktop-pet/model-config.json` - Para el frontend (Electron)
2. `backend/continuous_listener.py` - Para el backend (Python)

### Paso 1: Identificar las expresiones de tu modelo

Revisa el archivo `.model3.json` de tu modelo o la carpeta `expressions/`. Los nombres de las expresiones varían por modelo.

**Ejemplo de expresiones disponibles:**
- Modelo A: `happy`, `sad`, `angry`, `surprised`
- Modelo B: `smile`, `cry`, `rage`, `shock`
- Modelo C: `exp_01`, `exp_02`, `exp_03`

### Paso 2: Editar model-config.json

En `desktop-pet/model-config.json`, mapea las emociones del sistema a las expresiones de TU modelo:

```json
{
  "expressions": {
    "idle": null,
    "speaking": null,
    "happy": "nombre-de-expresion-feliz",
    "sad": "nombre-de-expresion-triste",
    "angry": "nombre-de-expresion-enojada",
    "fear": "nombre-de-expresion-miedo",
    "disgust": "nombre-de-expresion-asco",
    "surprise": "nombre-de-expresion-sorpresa",
    "blush": "nombre-de-expresion-sonrojo"
  }
}
```

**Reglas:**
- Usa `null` si tu modelo NO tiene esa expresión
- El nombre debe coincidir EXACTAMENTE con el de tu modelo (case-sensitive)
- `idle` y `speaking` son opcionales (la versión actual de Yui no tiene soporte para hablar "lip sync" `speaking` déjalo en `null`)

### Paso 3: Editar continuous_listener.py

En `backend/continuous_listener.py`, busca el diccionario `emotion_to_expression` (alrededor de la línea 102) y actualízalo:

```python
self.emotion_to_expression = {
    'happy': 'nombre-de-expresion-feliz',      # o None si no tiene
    'sad': 'nombre-de-expresion-triste',
    'angry': 'nombre-de-expresion-enojada',
    'fear': 'nombre-de-expresion-miedo',
    'disgust': 'nombre-de-expresion-asco',
    'surprise': 'nombre-de-expresion-sorpresa',
    'neutral': None  # ← SIEMPRE debe ser None (resetea la expresión)
}
```

**⚠️ CRÍTICO:** `neutral` SIEMPRE debe ser `None`. Esto resetea la expresión del modelo a su estado por defecto.

### Errores comunes

| Error | Causa | Solución |
|-------|-------|----------|
| Expresión no cambia | Nombre mal escrito | Verifica case-sensitive |
| Expresión aleatoria al poner "Normal" | `neutral` no es `None` | Pon `'neutral': None` |
| Error en consola al cambiar expresión | La expresión no existe en el modelo | Revisa `.model3.json` |
| Solo edité un archivo | Falta sincronizar | Ambos archivos deben coincidir |

### Ejemplo completo

Si tu modelo tiene expresiones llamadas `smile`, `cry`, `rage`:

**model-config.json:**
```json
"expressions": {
    "happy": "smile",
    "sad": "cry", 
    "angry": "rage",
    "fear": null,
    "surprise": "smile"
}
```

**continuous_listener.py:**
```python
self.emotion_to_expression = {
    'happy': 'smile',
    'sad': 'cry',
    'angry': 'rage',
    'fear': None,
    'surprise': 'smile',
    'neutral': None
}
```

---

## Aviso de Copyright

Los modelos no están incluidos en este repositorio debido a copyright.
Asegúrate de tener los derechos para usar cualquier modelo que agregues.

Si usas modelos fan-made de personajes con copyright, incluye la atribución apropiada:
> (c) Todos los derechos reservados por [Titular Original del Copyright]

