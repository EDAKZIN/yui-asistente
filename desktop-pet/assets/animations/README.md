# Animaciones FBX (Mixamo)

Este directorio contiene animaciones FBX descargadas de [Mixamo](https://www.mixamo.com/) y retargueteadas para modelos VRM usando `vrm-mixamo-retarget`.

## Animaciones Utilizadas

| Archivo | Fuente | Uso |
|---------|--------|-----|
| `Hello.fbx` | [Mixamo - Hello](https://www.mixamo.com/#/?page=1&query=hello) | Saludo/despedida |
| `Using Tablet.fbx` | [Mixamo - Using Tablet](https://www.mixamo.com/#/?page=1&query=table) | Yui usando tablet |

## Copyright

Las animaciones de Mixamo estan sujetas a los [terminos de uso de Mixamo](https://www.mixamo.com/faq). **No se redistribuyen** en este repositorio.

Para usar este proyecto, descarga las animaciones directamente desde Mixamo:

1. Ve a [mixamo.com](https://www.mixamo.com/) y crea una cuenta gratuita
2. Busca la animacion deseada
3. Descarga en formato **FBX Binary (.fbx)**
4. Configuracion recomendada:
   - **Skin**: Without Skin
   - **Frames per Second**: 30
   - **Keyframe Reduction**: none
5. Coloca el archivo `.fbx` en este directorio

## Agregar Nuevas Animaciones

Para agregar una nueva animacion al sistema:

1. Descarga el FBX desde Mixamo
2. Colocalo en este directorio
3. En `index.html`, agrega la carga en `loadRetargetedAnimations()`:

```javascript
const miFBX = await fbxLoader.loadAsync('./assets/animations/MiAnimacion.fbx');
animationClips.miAnimacion = removePositionTracks(retargetAnimation(miFBX, vrm));
```

> **NOTA**: `removePositionTracks()` elimina el root motion para que el personaje no se desplace de su posicion.
