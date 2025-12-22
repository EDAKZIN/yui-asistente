/**
 * Script de precarga - Puente seguro entre renderer y proceso principal
 */

import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('electronAPI', {
    setIgnoreMouseEvents: (ignore: boolean) => {
        ipcRenderer.send('set-ignore-mouse-events', ignore);
    },
    setWindowPosition: (x: number, y: number) => {
        ipcRenderer.send('set-window-position', x, y);
    }
});
