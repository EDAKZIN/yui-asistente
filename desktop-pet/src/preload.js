/**
 * Script de precarga - Puente seguro entre renderer y proceso principal
 * NOTA: Debe usar CommonJS para Electron preload
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    setIgnoreMouseEvents: (ignore) => {
        ipcRenderer.send('set-ignore-mouse-events', ignore);
    },
    setWindowPosition: (x, y) => {
        ipcRenderer.send('set-window-position', x, y);
    },
    saveConfig: (config) => {
        ipcRenderer.send('save-config', config);
    },
    onConfigMode: (callback) => {
        ipcRenderer.on('config-mode', (event, enabled) => callback(enabled));
    },
    onDragMode: (callback) => {
        ipcRenderer.on('drag-mode', (event, enabled) => callback(enabled));
    },
    onPassthroughMode: (callback) => {
        ipcRenderer.on('passthrough-mode', (event, enabled) => callback(enabled));
    },
    onMouseTracking: (callback) => {
        ipcRenderer.on('mouse-tracking', (event, enabled) => callback(enabled));
    },
    onMousePosition: (callback) => {
        ipcRenderer.on('mouse-position', (event, pos) => callback(pos));
    },
    onExpression: (callback) => {
        ipcRenderer.on('expression', (event, name) => callback(name));
    },
    onMotion: (callback) => {
        ipcRenderer.on('motion', (event, name) => callback(name));
    },
    onMotionReset: (callback) => {
        ipcRenderer.on('motion-reset', () => callback());
    },
    startMouseTracking: () => {
        ipcRenderer.send('start-mouse-tracking');
    },
    stopMouseTracking: () => {
        ipcRenderer.send('stop-mouse-tracking');
    },
    // Configuración de subtítulos
    onSubtitleConfigMode: (callback) => {
        ipcRenderer.on('subtitle-config-mode', (event, enabled) => callback(enabled));
    },
    saveSubtitleConfig: (config) => {
        return ipcRenderer.invoke('save-subtitle-config', config);
    },
    // Accesorios (hat, jacket)
    onAccessory: (callback) => {
        ipcRenderer.on('accessory', (event, type, enabled) => callback(type, enabled));
    },
    // Brillo (recibir desde pet window)
    onBrightness: (callback) => {
        ipcRenderer.on('brightness', (event, value) => callback(value));
    },
    // Brillo inicial (desde config guardado)
    onInitBrightness: (callback) => {
        ipcRenderer.on('init-brightness', (event, value) => callback(value));
    },
    // Enviar brillo desde control panel
    setBrightness: (value) => {
        ipcRenderer.send('set-brightness', value);
    },
    // Notificacion de cierre de app (para animacion de despedida)
    onAppClosing: (callback) => {
        ipcRenderer.on('app-closing', () => callback());
    }
});
