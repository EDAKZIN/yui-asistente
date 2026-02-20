# Items 3D (Props)

Este directorio contiene modelos 3D usados como props/accesorios que interactuan con el personaje VRM.

## Modelos Utilizados

| Archivo | Fuente | Uso |
|---------|--------|-----|
| `low_poly_sci-fi_tablet.glb` | [Sketchfab - Low Poly Sci-Fi Tablet](https://sketchfab.com/3d-models/low-poly-sci-fi-tablet-ee1fde7ec1514fd5a61790809ebd46a6) | Tablet que Yui sostiene |

## Copyright

Los modelos 3D de terceros tienen sus propias licencias y **no se redistribuyen** en este repositorio.

Para usar este proyecto, descarga los modelos directamente desde sus fuentes:

1. Ve al enlace del modelo en Sketchfab
2. Descarga en formato **GLB** (preferido) o **GLTF**
3. Coloca el archivo en este directorio

## Agregar Nuevos Items

Para agregar un nuevo item al sistema, edita `index.html` y crea una funcion de carga similar a `loadTabletModel()`:

```javascript
async function loadMiItem() {
    const gltfLoader = new GLTFLoader();
    const gltf = await gltfLoader.loadAsync('./assets/items/mi_item.glb');
    miItemModel = gltf.scene;
    miItemModel.scale.setScalar(0.1); // Ajustar escala
    miItemModel.visible = false;
}
```

> **NOTA**: Ajusta la escala segun el tamano del modelo. Los modelos de Sketchfab suelen necesitar escalas entre 0.01 y 0.5.
