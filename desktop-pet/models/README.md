# Directorio de Modelos Live2D

Coloca tus modelos Live2D aqui. Cada modelo debe estar en su propia carpeta.

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

## Configuracion

Edita `model-config.json` en el directorio padre para apuntar a tu modelo:

```json
{
  "modelPath": "./models/tu-modelo/tu-modelo.model3.json",
  "scale": 0.4,
  "position": { "x": 0, "y": 100 },
  "expressions": {
    "idle": null,
    "happy": "nombre-expresion"
  },
  "motions": {
    "idle": "nombre-motion",
    "speaking": "otro-motion"
  }
}
```

## Aviso de Copyright

Los modelos no estan incluidos en este repositorio debido a copyright.
Asegurate de tener los derechos para usar cualquier modelo que agregues.

Si usas modelos fan-made de personajes con copyright, incluye la atribucion apropiada:
> (c) Todos los derechos reservados por [Titular Original del Copyright]
