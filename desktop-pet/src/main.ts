/**
 * Yui Desktop Pet - Proceso Principal de Electron
 * Ventana transparente con modelo Live2D + Panel de Control
 */

import { app, BrowserWindow, Tray, Menu, ipcMain, screen, nativeImage } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

let mainWindow: BrowserWindow | null = null;
let controlWindow: BrowserWindow | null = null;
let tray: Tray | null = null;
const isMac = process.platform === 'darwin';

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

function createWindow(): void {
    const { width, height } = screen.getPrimaryDisplay().workAreaSize;
    const config = loadConfig();

    // Usar posicion guardada o default
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

    // Abrir DevTools para debug (descomentar cuando sea necesario)
    // mainWindow.webContents.openDevTools({ mode: 'detach' });

    // Click-through desactivado por defecto (se activa con modo atravesar)

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
    // Si ya existe, solo mostrarla
    if (controlWindow && !controlWindow.isDestroyed()) {
        controlWindow.show();
        controlWindow.focus();
        return;
    }

    controlWindow = new BrowserWindow({
        width: 450,
        height: 700,
        minWidth: 350,
        minHeight: 500,
        resizable: true,
        frame: true,
        title: 'Yui - Panel de Control',
        backgroundColor: '#1a1a1a',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            devTools: true
        }
    });

    controlWindow.loadFile(path.join(__dirname, '..', 'control-panel.html'));

    // Ocultar menu de la ventana
    controlWindow.setMenuBarVisibility(false);

    // DevTools solo para debug (descomentar si necesario)
    // controlWindow.webContents.openDevTools({ mode: 'detach' });

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
        // Crear tray vacio si no se encuentra el icono
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
        { label: 'Salir', click: () => app.quit() }
    ]);

    tray.setContextMenu(contextMenu);
}

// Manejadores IPC para toggle de click-through
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

    // Guardar posicion en config
    const config = loadConfig();
    config.windowX = newX;
    config.windowY = newY;
    saveConfig(config);
});

// Guardar configuracion del modelo
ipcMain.on('save-config', (_event, config: object) => {
    const configPath = path.join(__dirname, '..', 'model-config.json');
    try {
        fs.writeFileSync(configPath, JSON.stringify(config, null, 4), 'utf-8');
        console.log('Configuracion guardada:', configPath);
    } catch (error) {
        console.error('Error guardando configuracion:', error);
    }
});

// Mouse tracking global
let mouseTrackingInterval: NodeJS.Timeout | null = null;

ipcMain.on('start-mouse-tracking', () => {
    if (mouseTrackingInterval) return;
    mouseTrackingInterval = setInterval(() => {
        const cursorPos = screen.getCursorScreenPoint();
        const winBounds = mainWindow?.getBounds();
        if (winBounds) {
            // Enviar posicion relativa a la ventana
            mainWindow?.webContents.send('mouse-position', {
                x: cursorPos.x - winBounds.x,
                y: cursorPos.y - winBounds.y,
                screenX: cursorPos.x,
                screenY: cursorPos.y
            });
        }
    }, 50); // 20 FPS
});

ipcMain.on('stop-mouse-tracking', () => {
    if (mouseTrackingInterval) {
        clearInterval(mouseTrackingInterval);
        mouseTrackingInterval = null;
    }
});

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
