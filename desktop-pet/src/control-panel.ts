/**
 * Yui AI Assistant - Panel de Control (Electron)
 * Comunicación via WebSocket con el backend Python
 */

// Declaración de Window con API de Electron
declare global {
    interface Window {
        electron?: {
            onWindowRestored?: (callback: () => void) => void;
            onGlobalMuteTrigger?: (callback: () => void) => void;
            updateMuteKey?: (newKey: string) => void;
        };
    }
}

// Tipos
type AppState = 'loading' | 'active' | 'listening' | 'processing' | 'sleeping' | 'muted' | 'proactive' | 'waking';

interface StateConfig {
    dotClass: string;
    text: string;
}

// Estado de la aplicación
const state = {
    currentState: 'loading' as AppState,
    isMuted: false,
    isSleeping: false,
    isPerformanceMode: false,
    muteKey: 'F1',
    wsConnected: false
};

// Configuración de estados visuales
const stateConfig: Record<AppState, StateConfig> = {
    loading: { dotClass: 'sleeping', text: 'Cargando...' },
    active: { dotClass: 'active', text: 'Activa' },
    listening: { dotClass: 'listening', text: 'Escuchando...' },
    processing: { dotClass: 'processing', text: 'Procesando...' },
    sleeping: { dotClass: 'sleeping', text: 'En reposo' },
    muted: { dotClass: 'muted', text: 'Silenciado' },
    proactive: { dotClass: 'proactive', text: 'Comentando...' },
    waking: { dotClass: 'waking', text: 'Despertando...' }
};

// Referencias a elementos del DOM
const elements = {
    statusDot: document.getElementById('statusDot')!,
    statusText: document.getElementById('statusText')!,
    muteIndicator: document.getElementById('muteIndicator')!,
    waveform: document.getElementById('waveform')!,
    micIcon: document.getElementById('micIcon')!,
    btnMute: document.getElementById('btnMute')!,
    btnSleep: document.getElementById('btnSleep')!,
    btnPerformance: document.getElementById('btnPerformance')!,
    llmBadge: document.getElementById('llmBadge')!,
    btnSettings: document.getElementById('btnSettings')!,
    btnCloseSettings: document.getElementById('btnCloseSettings')!,
    settingsModal: document.getElementById('settingsModal')!,
    currentMuteKey: document.getElementById('currentMuteKey')!,
    btnChangeMuteKey: document.getElementById('btnChangeMuteKey')!,
    vadThreshold: document.getElementById('vadThreshold') as HTMLInputElement,
    vadThresholdValue: document.getElementById('vadThresholdValue')!,
    proactiveEnabled: document.getElementById('proactiveEnabled') as HTMLInputElement,
    connectionStatus: document.getElementById('connectionStatus')!,
    // More Options Panel
    moreOptionsPanel: document.getElementById('moreOptionsPanel')!,
    moreOptionsHeader: document.getElementById('moreOptionsHeader')!,
    memoryMonitor: document.getElementById('memoryMonitor') as HTMLInputElement,
    detailedLogs: document.getElementById('detailedLogs') as HTMLInputElement,
    statUptime: document.getElementById('statUptime')!,
    statConversations: document.getElementById('statConversations')!,
    consoleToggleBtn: document.getElementById('consoleToggleBtn')!,
    consoleToggleText: document.getElementById('consoleToggleText')!,
    // Brightness
    brightnessSlider: document.getElementById('brightnessSlider') as HTMLInputElement,
    brightnessValue: document.getElementById('brightnessValue')!
};

// WebSocket
let ws: WebSocket | null = null;
let reconnectInterval: number | null = null;

// === WebSocket ===

function connectWebSocket(): void {
    const wsUrl = 'ws://localhost:58765';
    console.log('Conectando a WebSocket:', wsUrl);

    try {
        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log('WebSocket conectado');
            state.wsConnected = true;
            updateConnectionStatus(true);

            // Limpiar reconexión
            if (reconnectInterval) {
                clearInterval(reconnectInterval);
                reconnectInterval = null;
            }

            // Solicitar estado inicial
            sendAction('get_initial_state');
        };

        ws.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                handleWebSocketMessage(message);
            } catch (e) {
                console.error('Error parseando mensaje:', e);
            }
        };

        ws.onclose = () => {
            console.log('WebSocket desconectado');
            state.wsConnected = false;
            updateConnectionStatus(false);

            // Reconectar automáticamente
            if (!reconnectInterval) {
                reconnectInterval = window.setInterval(() => {
                    if (!state.wsConnected) {
                        console.log('Intentando reconectar...');
                        connectWebSocket();
                    }
                }, 3000);
            }
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

    } catch (error) {
        console.error('Error conectando WebSocket:', error);
    }
}

function sendAction(action: string, params: Record<string, any> = {}): void {
    if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ action, params }));
    } else {
        console.warn('WebSocket no conectado, no se puede enviar:', action);
    }
}

function handleWebSocketMessage(message: { type: string; data?: any; action?: string }): void {
    console.log('Mensaje recibido:', message.type);

    switch (message.type) {
        case 'initial_state':
            if (message.data) {
                state.muteKey = message.data.mute_key || 'F1';
                elements.currentMuteKey.textContent = state.muteKey;

                if (message.data.state) {
                    updateState(message.data.state);
                }

                // Persistir estado muted
                if (message.data.is_muted !== undefined) {
                    state.isMuted = message.data.is_muted;
                    updateMuteUI();
                }

                // Persistir estado sleeping (copiar lógica de mute)
                if (message.data.is_sleeping !== undefined) {
                    state.isSleeping = message.data.is_sleeping;
                    if (state.isSleeping) {
                        updateState('sleeping');
                    }
                }

                // Persistir estado de rendimiento y actualizar badge LLM
                if (message.data.is_performance_mode !== undefined) {
                    state.isPerformanceMode = message.data.is_performance_mode;
                    elements.btnPerformance.classList.toggle('active', state.isPerformanceMode);
                    updateLlmBadge(state.isPerformanceMode);
                }

                // Sincronizar estados de "Más Opciones"
                if (message.data.options) {
                    const opts = message.data.options;
                    elements.memoryMonitor.checked = opts.memory_monitoring || false;
                    elements.detailedLogs.checked = opts.detailed_logs || false;
                    updateConsoleState(opts.console_visible || false);
                }

                // Sincronizar brillo desde config
                if (message.data.brightness !== undefined) {
                    const brightness = message.data.brightness;
                    elements.brightnessSlider.value = brightness.toString();
                    elements.brightnessValue.textContent = Math.round(brightness * 100) + '%';
                }

                // Sincronizar checkbox de comentarios proactivos
                if (message.data.proactive_enabled !== undefined) {
                    elements.proactiveEnabled.checked = message.data.proactive_enabled;
                }
            }
            break;

        case 'state_change':
            if (message.data?.state) {
                updateState(message.data.state);
            }
            break;

        case 'transcript':
            // Transcript ya no se muestra en el panel
            break;

        case 'response':
            // Manejar respuestas de acciones (como get_session_stats)
            if (message.action === 'get_session_stats' && message.data) {
                updateSessionStats(message.data);
            }
            if (message.action === 'toggle_console' && message.data) {
                updateConsoleState(message.data.visible);
            }
            break;

        case 'mute_changed':
            if (message.data) {
                state.isMuted = message.data.is_muted;
                updateMuteUI();
            }
            break;

        case 'sleep_changed':
            if (message.data) {
                state.isSleeping = message.data.is_sleeping;
                if (state.isSleeping) {
                    updateState('sleeping');
                } else {
                    updateState('active');
                }
            }
            break;

        case 'performance_changed':
            if (message.data) {
                state.isPerformanceMode = message.data.is_performance_mode;
                elements.btnPerformance.classList.toggle('active', state.isPerformanceMode);
                const label = elements.btnPerformance.querySelector('.btn-label');
                if (label) {
                    label.textContent = state.isPerformanceMode ? 'Rendimiento ✓' : 'Rendimiento';
                }
                // Actualizar badge de LLM
                updateLlmBadge(state.isPerformanceMode);
            }
            break;

        case 'error':
            console.error('Error del servidor:', message.data?.message);
            break;
    }
}

function updateConnectionStatus(connected: boolean): void {
    if (connected) {
        elements.connectionStatus.classList.add('connected');
        elements.connectionStatus.querySelector('.connection-text')!.textContent = 'Conectado';
    } else {
        elements.connectionStatus.classList.remove('connected');
        elements.connectionStatus.querySelector('.connection-text')!.textContent = 'Desconectado';
    }
}

function updateLlmBadge(isPerformanceMode: boolean): void {
    if (isPerformanceMode) {
        elements.llmBadge.textContent = 'Groq';
        elements.llmBadge.classList.add('groq');
        elements.llmBadge.classList.remove('local');
    } else {
        elements.llmBadge.textContent = 'Local';
        elements.llmBadge.classList.add('local');
        elements.llmBadge.classList.remove('groq');
    }
}

// === UI Updates ===

function updateState(newState: AppState): void {
    state.currentState = newState;

    // Si esta muteado, no mostrar estados de escucha/procesamiento visualmente
    let displayState = newState;
    if (state.isMuted && (newState === 'listening' || newState === 'processing')) {
        displayState = 'active';
    }

    const config = stateConfig[displayState] || stateConfig.active;

    elements.statusDot.className = 'status-dot ' + config.dotClass;
    // El texto del estado muestra el estado real, el badge muteIndicator indica si esta muteado
    elements.statusText.textContent = config.text;

    if (newState === 'listening' || newState === 'processing') {
        if (!state.isMuted) {
            elements.waveform.classList.add('active');
            elements.micIcon.classList.add('active');
        } else {
            elements.waveform.classList.remove('active');
            elements.micIcon.classList.remove('active');
        }
    } else {
        elements.waveform.classList.remove('active');
        if (!state.isMuted) {
            elements.micIcon.classList.remove('active');
        }
    }

    elements.btnSleep.classList.toggle('sleeping', newState === 'sleeping');
}

function updateMuteUI(): void {
    elements.btnMute.classList.toggle('muted', state.isMuted);
    elements.muteIndicator.style.display = state.isMuted ? 'flex' : 'none';
    elements.micIcon.classList.toggle('muted', state.isMuted);

    const label = elements.btnMute.querySelector('.btn-label');
    if (label) {
        label.textContent = state.isMuted ? 'Activar' : 'Silenciar';
    }

    // Actualizar estado visual
    updateState(state.currentState);
}

// === More Options Panel ===

function formatUptime(seconds: number): string {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    if (hours > 0) {
        return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
}

function toggleMoreOptions(): void {
    elements.moreOptionsPanel.classList.toggle('expanded');
}

function setupCategoryCards(): void {
    // Agregar listeners a cada cuadro
    const optionCards = document.querySelectorAll('.option-card');

    optionCards.forEach(card => {
        card.addEventListener('click', (e) => {
            // No expandir si se hizo click en un input o button
            const target = e.target as HTMLElement;
            if (target.tagName === 'INPUT' || target.tagName === 'BUTTON' || target.closest('button')) {
                return;
            }

            card.classList.toggle('expanded');

            // Si es el cuadro de sesión y se expandió, solicitar datos
            if (card.id === 'cardSession' && card.classList.contains('expanded')) {
                requestSessionStats();
            }
        });
    });
}

function requestSessionStats(): void {
    sendAction('get_session_stats');
}

function updateSessionStats(stats: { uptime_seconds: number; conversation_count: number }): void {
    elements.statUptime.textContent = formatUptime(stats.uptime_seconds);
    elements.statConversations.textContent = stats.conversation_count.toString();
}

function setupConsoleToggle(): void {
    elements.consoleToggleBtn.addEventListener('click', () => {
        sendAction('toggle_console');
    });
}

function updateConsoleState(visible: boolean): void {
    elements.consoleToggleText.textContent = visible ? 'Ocultar' : 'Mostrar';
    elements.consoleToggleBtn.classList.toggle('active', visible);
}

// === Event Listeners ===

function setupEventListeners(): void {
    // Mute button
    elements.btnMute.addEventListener('click', () => {
        sendAction('toggle_mute');
    });

    // Sleep button
    elements.btnSleep.addEventListener('click', () => {
        sendAction('toggle_sleep');
    });

    // Performance mode button
    elements.btnPerformance.addEventListener('click', () => {
        sendAction('toggle_performance');
    });

    // Settings modal
    elements.btnSettings.addEventListener('click', () => {
        elements.settingsModal.classList.add('active');
    });

    elements.btnCloseSettings.addEventListener('click', () => {
        elements.settingsModal.classList.remove('active');
    });

    elements.settingsModal.addEventListener('click', (e) => {
        if (e.target === elements.settingsModal) {
            elements.settingsModal.classList.remove('active');
        }
    });

    // More Options Panel toggle
    elements.moreOptionsHeader.addEventListener('click', toggleMoreOptions);

    // Memory Monitor toggle
    elements.memoryMonitor.addEventListener('change', () => {
        sendAction('set_memory_monitoring', { enabled: elements.memoryMonitor.checked });
    });

    // Detailed Logs toggle
    elements.detailedLogs.addEventListener('change', () => {
        sendAction('set_detailed_logging', { enabled: elements.detailedLogs.checked });
    });

    // VAD threshold slider
    elements.vadThreshold.addEventListener('input', () => {
        const value = elements.vadThreshold.value;
        elements.vadThresholdValue.textContent = value;
        sendAction('set_vad_threshold', { threshold: parseFloat(value) });
    });

    // Proactive comments toggle
    elements.proactiveEnabled.addEventListener('change', () => {
        sendAction('set_proactive_enabled', { enabled: elements.proactiveEnabled.checked });
    });

    // Brightness slider
    elements.brightnessSlider.addEventListener('input', () => {
        const value = parseFloat(elements.brightnessSlider.value);
        elements.brightnessValue.textContent = Math.round(value * 100) + '%';
        // Enviar brillo a la ventana pet via IPC
        if ((window as any).electronAPI?.setBrightness) {
            (window as any).electronAPI.setBrightness(value);
        }
    });

    // Change mute key
    let waitingForKey = false;
    elements.btnChangeMuteKey.addEventListener('click', () => {
        waitingForKey = true;
        elements.currentMuteKey.textContent = 'Presiona una tecla...';
    });

    // Listener solo para capturar nueva tecla al cambiar keybind
    // El toggle_mute se maneja globalmente desde main.ts (uIOhook)
    document.addEventListener('keydown', (e) => {
        if (waitingForKey) {
            e.preventDefault();
            waitingForKey = false;
            const newKey = e.key.length === 1 ? e.key.toUpperCase() : e.key;
            state.muteKey = newKey;
            elements.currentMuteKey.textContent = newKey;
            sendAction('set_mute_key', { key: newKey });

            // Notificar a Electron para actualizar global shortcut
            if (window.electron?.updateMuteKey) {
                window.electron.updateMuteKey(newKey);
            }
        }
        // No se maneja toggle_mute aqui - el hook global en main.ts ya lo hace
    });
}

// === Inicialización ===

function init(): void {
    console.log('Inicializando Panel de Control...');
    setupEventListeners();
    setupCategoryCards();
    setupConsoleToggle();
    connectWebSocket();

    // Recibir brillo guardado desde main.ts (via IPC)
    if ((window as any).electronAPI?.onInitBrightness) {
        (window as any).electronAPI.onInitBrightness((value: number) => {
            console.log('[Brillo] Valor inicial recibido:', value);
            elements.brightnessSlider.value = value.toString();
            elements.brightnessValue.textContent = Math.round(value * 100) + '%';
        });
    }

    // Listener para cuando la ventana se restaura desde bandeja
    if (window.electron?.onWindowRestored) {
        window.electron.onWindowRestored(() => {
            console.log('Ventana restaurada, refrescando estado...');
            if (ws && ws.readyState === WebSocket.OPEN) {
                sendAction('get_initial_state');
            }
        });
    }

    // Listener para atajo global de mute
    if (window.electron?.onGlobalMuteTrigger) {
        window.electron.onGlobalMuteTrigger(() => {
            console.log('Atajo global de mute presionado');
            sendAction('toggle_mute');
        });
    }
}

// Iniciar cuando DOM esté listo
document.addEventListener('DOMContentLoaded', init);

// Exportar vacío para hacer este archivo un módulo (necesario para declare global)
export { };
