/**
 * Yui Desktop Pet - Proceso Principal de Electron
 * MUTE GLOBAL: main.ts → WebSocket directo al backend
 */

import { app, BrowserWindow, Tray, Menu, ipcMain, screen, nativeImage } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import { fileURLToPath } from 'url';
import { WebSocket } from 'ws';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ==================== LOGGING ====================
const logsDir = path.join(__dirname, '..', '..', 'logs');
if (!fs.existsSync(logsDir)) {
    fs.mkdirSync(logsDir, { recursive: true });
}

const logStream = fs.createWriteStream(path.join(logsDir, 'electron.log'), { flags: 'w' });
const originalLog = console.log;
const originalError = console.error;

console.log = (...args: any[]) => {
    const timestamp = new Date().toISOString();
    const message = `[${timestamp}] ${args.join(' ')}`;
    logStream.write(message + '\n');
    originalLog.apply(console, args);
};

console.error = (...args: any[]) => {
    const timestamp = new Date().toISOString();
    const message = `[${timestamp}] ERROR: ${args.join(' ')}`;
    logStream.write(message + '\n');
    originalError.apply(console, args);
};

console.log('====== ELECTRON LOG INICIADO ======');

let mainWindow: BrowserWindow | null = null;
let controlWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
const isMac = process.platform === 'darwin';

// WebSocket directo al backend (sin pasar por frontend)
let backendWS: WebSocket | null = null;

function connectToBackend() {
    backendWS = new WebSocket('ws://localhost:58765');

    backendWS.on('open', () => {
        console.log('[Backend WS] Conectado a ws://localhost:58765');
    });

    backendWS.on('error', (err) => {
        console.error('[Backend WS] Error:', err.message);
    });

    backendWS.on('close', () => {
        console.log('[Backend WS] Desconectado, reintentando en 5s...');
        setTimeout(connectToBackend, 5000);
    });
}

// Cargar configuracion guardada
function loadConfig(): any {
    const configPath = path.join(__dirname, '..', 'model-config.json');
    try {
        const data = fs.readFileSync(configPath, 'utf-8');
        return JSON.parse(data);
    } catch {
        return {};
    }
}

// Guardar configuracion
function saveConfig(config: any): void {
    const configPath = path.join(__dirname, '..', 'model-config.json');
    try {
        fs.writeFileSync(configPath, JSON.stringify(config, null, 4), 'utf-8');
    } catch (error) {
        console.error('Error guardando configuracion:', error);
    }
}

// Cargar config global (backend config.json)
function loadGlobalConfig(): any {
    const globalConfigPath = path.join(__dirname, '..', '..', 'config.json');
    try {
        const data = fs.readFileSync(globalConfigPath, 'utf-8');
        return JSON.parse(data);
    } catch (error) {
        console.error('[Config Global] Error cargando config.json:', error);
        return {};
    }
}

function createWindow(): void {
    const { width, height } = screen.getPrimaryDisplay().workAreaSize;
    const config = loadConfig();

    const windowX = config.windowX !== undefined ? config.windowX : width - 420;
    const windowY = config.windowY !== undefined ? config.windowY : height - 520;

    mainWindow = new BrowserWindow({
        width: 400,
        height: 500,
        x: windowX,
        y: windowY,
        transparent: true,
        frame: false,
        resizable: false,
        alwaysOnTop: true,
        skipTaskbar: true,
        hasShadow: false,
        focusable: false,
        backgroundColor: '#00000000',
        webPreferences: {
            preload: path.join(__dirname, '..', 'src', 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false
        }
    });

    mainWindow.loadFile(path.join(__dirname, '..', 'index.html'));
    mainWindow.setAlwaysOnTop(true, 'screen-saver');

    if (isMac) {
        mainWindow.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
    }

    mainWindow.on('closed', () => {
        mainWindow = null;
    });

    createTray();
}

function createControlWindow(): void {
    if (controlWindow && !controlWindow.isDestroyed()) {
        controlWindow.show();
        controlWindow.focus();
        return;
    }

    controlWindow = new BrowserWindow({
        width: 550,
        height: 700,
        minWidth: 450,
        minHeight: 500,
        resizable: true,
        frame: true,
        title: 'Yui - Panel de Control',
        backgroundColor: '#1a1a1a',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, '..', 'src', 'preload.js'),
            devTools: true
        }
    });

    controlWindow.loadFile(path.join(__dirname, '..', 'control-panel.html'));
    controlWindow.setMenuBarVisibility(false);

    controlWindow.on('closed', () => {
        controlWindow = null;
    });
}

function createTray(): void {
    const iconPath = path.join(__dirname, '..', 'icon.png');

    try {
        let trayIcon: Electron.NativeImage;
        if (isMac) {
            trayIcon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 });
        } else {
            trayIcon = nativeImage.createFromPath(iconPath);
        }
        tray = new Tray(trayIcon);
    } catch {
        tray = new Tray(nativeImage.createEmpty());
    }

    tray.setToolTip('Yui Desktop Pet');

    const contextMenu = Menu.buildFromTemplate([
        {
            label: 'Mostrar/Ocultar Pet',
            click: () => {
                if (mainWindow?.isVisible()) {
                    mainWindow.hide();
                } else {
                    mainWindow?.show();
                }
            }
        },
        {
            label: 'Panel de Control',
            click: () => {
                createControlWindow();
            }
        },
        { type: 'separator' },
        {
            label: 'Expresiones',
            submenu: [
                { label: 'Normal', click: () => mainWindow?.webContents.send('expression', 'neutral') },
                { label: 'Enojada', click: () => mainWindow?.webContents.send('expression', 'angry') },
                { label: 'Llorando', click: () => mainWindow?.webContents.send('expression', 'cry') },
                { label: 'Sorprendida', click: () => mainWindow?.webContents.send('expression', 'baozhen') },
                { label: 'Feliz 1', click: () => mainWindow?.webContents.send('expression', 'qizi1') },
                { label: 'Feliz 2', click: () => mainWindow?.webContents.send('expression', 'qizi2') },
                { label: 'Ojos Blancos', click: () => mainWindow?.webContents.send('expression', 'white eyes') }
            ]
        },
        {
            label: 'Animaciones',
            submenu: [
                { label: 'Cola/Accesorios', click: () => mainWindow?.webContents.send('motion', 'Scene1') },
                { label: 'Curiosa', click: () => mainWindow?.webContents.send('motion', 'haoqi') },
                { label: 'Somnolienta', click: () => mainWindow?.webContents.send('motion', 'keshui') },
                { label: 'Alma Saliendo', click: () => mainWindow?.webContents.send('motion', 'linghun') },
                { label: 'Agitar Bandera', click: () => mainWindow?.webContents.send('motion', 'qizi') },
                { label: 'Mover Cabeza', click: () => mainWindow?.webContents.send('motion', 'yaotou') },
                { label: 'Temblar', click: () => mainWindow?.webContents.send('motion', 'zhentou') }
            ]
        },
        { type: 'separator' },
        {
            label: 'Ajustar Escala',
            type: 'checkbox',
            checked: false,
            click: (menuItem) => {
                mainWindow?.webContents.send('config-mode', menuItem.checked);
            }
        },
        {
            label: 'Ajustar Subtitulos',
            type: 'checkbox',
            checked: false,
            click: (menuItem) => {
                mainWindow?.webContents.send('subtitle-config-mode', menuItem.checked);
            }
        },
        {
            label: 'Arrastrar',
            type: 'checkbox',
            checked: false,
            click: (menuItem) => {
                mainWindow?.webContents.send('drag-mode', menuItem.checked);
                if (menuItem.checked) {
                    mainWindow?.setIgnoreMouseEvents(false);
                } else {
                    if (!isMac) {
                        mainWindow?.setIgnoreMouseEvents(true, { forward: true });
                    }
                }
            }
        },
        {
            label: 'Atravesar',
            type: 'checkbox',
            checked: false,
            click: (menuItem) => {
                mainWindow?.webContents.send('passthrough-mode', menuItem.checked);
                if (menuItem.checked) {
                    if (isMac) {
                        mainWindow?.setIgnoreMouseEvents(true);
                    } else {
                        mainWindow?.setIgnoreMouseEvents(true, { forward: true });
                    }
                } else {
                    mainWindow?.setIgnoreMouseEvents(false);
                }
            }
        },
        {
            label: 'Seguir Cursor',
            type: 'checkbox',
            checked: true,
            click: (menuItem) => {
                mainWindow?.webContents.send('mouse-tracking', menuItem.checked);
            }
        },
        { type: 'separator' },
        {
            label: 'Reiniciar',
            click: () => {
                // Enviar comando de shutdown al backend via WebSocket
                if (backendWS && backendWS.readyState === WebSocket.OPEN) {
                    backendWS.send(JSON.stringify({ action: 'shutdown' }));
                }
                // Dar tiempo para que el backend reciba el mensaje
                setTimeout(() => {
                    app.quit();
                }, 500);
            }
        },
        { label: 'Salir', click: () => app.quit() }
    ]);

    tray.setContextMenu(contextMenu);
}

// IPC handlers
ipcMain.on('set-ignore-mouse-events', (_event, ignore: boolean) => {
    if (isMac) {
        mainWindow?.setIgnoreMouseEvents(ignore);
    } else {
        mainWindow?.setIgnoreMouseEvents(ignore, { forward: true });
    }
});

ipcMain.on('set-window-position', (_event, x: number, y: number) => {
    const newX = Math.round(x);
    const newY = Math.round(y);
    mainWindow?.setPosition(newX, newY);

    const config = loadConfig();
    config.windowX = newX;
    config.windowY = newY;
    saveConfig(config);
});

ipcMain.on('save-config', (_event, config: object) => {
    const configPath = path.join(__dirname, '..', 'model-config.json');
    try {
        fs.writeFileSync(configPath, JSON.stringify(config, null, 4), 'utf-8');
        console.log('Configuracion guardada:', configPath);
    } catch (error) {
        console.error('Error guardando configuracion:', error);
    }
});

// Handler para guardar configuracion de subtitulos
ipcMain.handle('save-subtitle-config', async (_event, subtitleConfig: object) => {
    const configPath = path.join(__dirname, '..', 'model-config.json');
    try {
        const fullConfig = loadConfig();
        fullConfig.subtitles = { ...fullConfig.subtitles, ...subtitleConfig };
        fs.writeFileSync(configPath, JSON.stringify(fullConfig, null, 4), 'utf-8');
        console.log('Configuracion de subtitulos guardada');
        return true;
    } catch (error) {
        console.error('Error guardando config de subtitulos:', error);
        return false;
    }
});

// Mouse tracking
let mouseTrackingInterval: NodeJS.Timeout | null = null;

ipcMain.on('start-mouse-tracking', () => {
    if (mouseTrackingInterval) return;
    mouseTrackingInterval = setInterval(() => {
        const cursorPos = screen.getCursorScreenPoint();
        const winBounds = mainWindow?.getBounds();
        if (winBounds) {
            mainWindow?.webContents.send('mouse-position', {
                x: cursorPos.x - winBounds.x,
                y: cursorPos.y - winBounds.y,
                screenX: cursorPos.x,
                screenY: cursorPos.y
            });
        }
    }, 50);
});

ipcMain.on('stop-mouse-tracking', () => {
    if (mouseTrackingInterval) {
        clearInterval(mouseTrackingInterval);
        mouseTrackingInterval = null;
    }
});

// ==================== GLOBAL HOTKEY ====================
(async () => {
    try {
        const { uIOhook } = await import('uiohook-napi');

        const keyCodeMap: { [key: string]: number } = {
            'F1': 59, 'F2': 60, 'F3': 61, 'F4': 62,
            'F5': 63, 'F6': 64, 'F7': 65, 'F8': 66,
            'F9': 67, 'F10': 68, 'F11': 69, 'F12': 70,
            '|': 43
        };

        const globalConfig = loadGlobalConfig();
        const muteKey = globalConfig.gui?.mute_key || 'F1';
        const currentMuteKeyCode = keyCodeMap[muteKey] || 59;

        console.log(`[Config] Mute key: ${muteKey}`);
        console.log(`[UIOHook] Configurando keycode: ${currentMuteKeyCode}`);

        uIOhook.start();
        console.log('[UIOHook] Hook iniciado');

        // Conectar al backend WS
        connectToBackend();

        // CRÍTICO: Usar 'keyup' para evitar múltiples disparos
        uIOhook.on('keyup', (e) => {
            if (e.keycode === currentMuteKeyCode) {
                console.log('[UIOHook] Mute key soltada - toggling');

                // Enviar DIRECTO al backend via WebSocket
                if (backendWS && backendWS.readyState === WebSocket.OPEN) {
                    backendWS.send(JSON.stringify({ action: 'toggle_mute', params: {} }));
                    console.log('[UIOHook] Comando enviado a backend WS');
                } else {
                    console.error('[UIOHook] Backend WS no conectado');
                }
            }
        });

        app.on('will-quit', () => {
            try {
                uIOhook.stop();
                backendWS?.close();
                console.log('[UIOHook] Hook detenido');
            } catch (e) {
                console.error('[UIOHook] Error:', e);
            }
        });

    } catch (error) {
        console.error('[UIOHook] Error:', error);
    }
})();

app.whenReady().then(() => {
    createWindow();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    if (!isMac) {
        app.quit();
    }
});
