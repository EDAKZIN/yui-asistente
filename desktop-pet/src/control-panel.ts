/**
 * Yui AI Assistant - Panel de Control (Electron)
 * Comunicación via WebSocket con el backend Python
 */

// Tipos
type AppState = 'loading' | 'active' | 'listening' | 'processing' | 'sleeping' | 'muted';

interface StateConfig {
    dotClass: string;
    text: string;
}

// Estado de la aplicación
const state = {
    currentState: 'loading' as AppState,
    isMuted: false,
    isSleeping: false,
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
    muted: { dotClass: 'muted', text: 'Silenciado' }
};

// Referencias a elementos del DOM
const elements = {
    statusDot: document.getElementById('statusDot')!,
    statusText: document.getElementById('statusText')!,
    muteIndicator: document.getElementById('muteIndicator')!,
    waveform: document.getElementById('waveform')!,
    micIcon: document.getElementById('micIcon')!,
    transcriptContent: document.getElementById('transcriptContent')!,
    responseContent: document.getElementById('responseContent')!,
    btnMute: document.getElementById('btnMute')!,
    btnSleep: document.getElementById('btnSleep')!,
    btnSettings: document.getElementById('btnSettings')!,
    btnCloseSettings: document.getElementById('btnCloseSettings')!,
    btnClearTranscript: document.getElementById('btnClearTranscript')!,
    settingsModal: document.getElementById('settingsModal')!,
    currentMuteKey: document.getElementById('currentMuteKey')!,
    btnChangeMuteKey: document.getElementById('btnChangeMuteKey')!,
    vadThreshold: document.getElementById('vadThreshold') as HTMLInputElement,
    vadThresholdValue: document.getElementById('vadThresholdValue')!,
    proactiveEnabled: document.getElementById('proactiveEnabled') as HTMLInputElement,
    connectionStatus: document.getElementById('connectionStatus')!
};

// WebSocket
let ws: WebSocket | null = null;
let reconnectInterval: number | null = null;

// === WebSocket ===

function connectWebSocket(): void {
    const wsUrl = 'ws://localhost:8765';
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
                if (message.data.is_muted !== undefined) {
                    state.isMuted = message.data.is_muted;
                    updateMuteUI();
                }
            }
            break;

        case 'state_change':
            if (message.data?.state) {
                updateState(message.data.state);
            }
            break;

        case 'transcript':
            if (message.data?.text) {
                addTranscript(message.data.text);
            }
            break;

        case 'response':
            if (message.data?.text) {
                setResponse(message.data.text);
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

function addTranscript(text: string): void {
    const placeholder = elements.transcriptContent.querySelector('.transcript-placeholder');
    if (placeholder) {
        placeholder.remove();
    }

    const p = document.createElement('p');
    p.textContent = text;
    p.style.marginBottom = '8px';
    p.style.paddingBottom = '8px';
    p.style.borderBottom = '1px solid var(--border-color)';

    elements.transcriptContent.appendChild(p);
    elements.transcriptContent.scrollTop = elements.transcriptContent.scrollHeight;
}

function setResponse(text: string): void {
    const placeholder = elements.responseContent.querySelector('.response-placeholder');
    if (placeholder) {
        placeholder.remove();
    }

    elements.responseContent.innerHTML = '';
    const p = document.createElement('p');
    p.textContent = text;
    elements.responseContent.appendChild(p);
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

    // Clear transcript
    elements.btnClearTranscript.addEventListener('click', () => {
        elements.transcriptContent.innerHTML = '<p class="transcript-placeholder">Esperando audio...</p>';
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

    // Change mute key
    let waitingForKey = false;
    elements.btnChangeMuteKey.addEventListener('click', () => {
        waitingForKey = true;
        elements.currentMuteKey.textContent = 'Presiona una tecla...';
    });

    document.addEventListener('keydown', (e) => {
        if (waitingForKey) {
            e.preventDefault();
            waitingForKey = false;
            const newKey = e.key.length === 1 ? e.key.toUpperCase() : e.key;
            state.muteKey = newKey;
            elements.currentMuteKey.textContent = newKey;
            sendAction('set_mute_key', { key: newKey });
        } else {
            // Verificar si es la tecla de mute
            const pressedKey = e.key.length === 1 ? e.key.toUpperCase() : e.key;
            if (pressedKey === state.muteKey || e.key === state.muteKey) {
                e.preventDefault();
                console.log('Mute key pressed:', state.muteKey);
                sendAction('toggle_mute');
            }
        }
    });
}

// === Inicialización ===

function init(): void {
    console.log('Inicializando Panel de Control...');
    setupEventListeners();
    connectWebSocket();
}

// Iniciar cuando DOM esté listo
document.addEventListener('DOMContentLoaded', init);
