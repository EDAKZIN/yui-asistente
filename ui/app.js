/**
 * Yui AI Assistant - Frontend JavaScript
 * Handles UI interactions and communication with Python backend via pywebview
 */

// Estado de la aplicación
const state = {
    isConnected: false,
    isMuted: false,
    currentState: 'loading', // loading, active, listening, processing, sleeping, muted
    muteKey: 'F1'
};

// Elementos del DOM
const elements = {
    statusDot: document.getElementById('statusDot'),
    statusText: document.getElementById('statusText'),
    waveform: document.getElementById('waveform'),
    micIcon: document.getElementById('micIcon'),
    transcriptContent: document.getElementById('transcriptContent'),
    responseContent: document.getElementById('responseContent'),
    muteIndicator: document.getElementById('muteIndicator'),
    btnMute: document.getElementById('btnMute'),
    btnSleep: document.getElementById('btnSleep'),
    btnSettings: document.getElementById('btnSettings'),
    btnClearTranscript: document.getElementById('btnClearTranscript'),
    settingsModal: document.getElementById('settingsModal'),
    btnCloseSettings: document.getElementById('btnCloseSettings'),
    vadThreshold: document.getElementById('vadThreshold'),
    vadThresholdValue: document.getElementById('vadThresholdValue'),
    proactiveEnabled: document.getElementById('proactiveEnabled'),
    currentMuteKey: document.getElementById('currentMuteKey'),
    btnChangeMuteKey: document.getElementById('btnChangeMuteKey')
};

// ==================== ESTADO ====================

const stateConfig = {
    loading: { text: 'Cargando...', dotClass: 'sleeping' },
    active: { text: 'Activa', dotClass: 'active' },
    listening: { text: 'Escuchando...', dotClass: 'listening' },
    processing: { text: 'Procesando...', dotClass: 'processing' },
    sleeping: { text: 'En reposo', dotClass: 'sleeping' },
    waking: { text: 'Despertando...', dotClass: 'listening' },
    muted: { text: 'Silenciado', dotClass: 'muted' }
};

function updateState(newState) {
    state.currentState = newState;
    const config = stateConfig[newState] || stateConfig.active;

    // Actualizar indicador de estado
    elements.statusDot.className = 'status-dot ' + config.dotClass;
    elements.statusText.textContent = config.text;

    // Actualizar visualizador de audio (independiente de mute)
    if (newState === 'listening' || newState === 'processing') {
        elements.waveform.classList.add('active');
        if (!state.isMuted) {
            elements.micIcon.classList.add('active');
        }
    } else {
        elements.waveform.classList.remove('active');
        if (!state.isMuted) {
            elements.micIcon.classList.remove('active');
        }
    }

    // Actualizar botón sleep
    elements.btnSleep.classList.toggle('sleeping', newState === 'sleeping');
}

// ==================== TRANSCRIPCIÓN ====================

function updateTranscript(text, isUser = true) {
    const placeholder = elements.transcriptContent.querySelector('.transcript-placeholder');
    if (placeholder) {
        placeholder.remove();
    }

    const p = document.createElement('p');
    p.textContent = text;
    p.style.color = isUser ? '#ffffff' : 'var(--accent-cyan)';
    p.style.marginBottom = '8px';

    elements.transcriptContent.appendChild(p);
    elements.transcriptContent.scrollTop = elements.transcriptContent.scrollHeight;
}

function updateResponse(text) {
    elements.responseContent.innerHTML = `<p>${text}</p>`;
}

function clearTranscript() {
    elements.transcriptContent.innerHTML = '<p class="transcript-placeholder">Esperando audio...</p>';
}

// ==================== CONTROLES ====================

function updateMuteUI() {
    // Actualizar indicador de mute separado
    if (elements.muteIndicator) {
        elements.muteIndicator.style.display = state.isMuted ? 'flex' : 'none';
    }
    // Actualizar botón mute
    elements.btnMute.classList.toggle('muted', state.isMuted);
    elements.btnMute.querySelector('.btn-label').textContent = state.isMuted ? 'Activar' : 'Silenciar';
    // Actualizar icono mic
    elements.micIcon.classList.toggle('muted', state.isMuted);
}

async function toggleMute() {
    try {
        if (window.pywebview && window.pywebview.api) {
            const result = await window.pywebview.api.toggle_mute();
            state.isMuted = result.muted;
            updateMuteUI();
        } else {
            // Demo mode sin backend
            state.isMuted = !state.isMuted;
            updateMuteUI();
        }
    } catch (error) {
        console.error('Error toggling mute:', error);
    }
}

async function toggleSleep() {
    try {
        if (window.pywebview && window.pywebview.api) {
            const result = await window.pywebview.api.toggle_sleep();
            updateState(result.sleeping ? 'sleeping' : 'active');
        } else {
            // Demo mode
            const isSleeping = state.currentState === 'sleeping';
            updateState(isSleeping ? 'active' : 'sleeping');
        }
    } catch (error) {
        console.error('Error toggling sleep:', error);
    }
}

function openSettings() {
    elements.settingsModal.classList.add('active');
}

function closeSettings() {
    elements.settingsModal.classList.remove('active');
}

// ==================== CONFIGURACIÓN ====================

async function updateVadThreshold() {
    const value = parseFloat(elements.vadThreshold.value);
    elements.vadThresholdValue.textContent = value.toFixed(2);

    if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.set_vad_threshold(value);
    }
}

async function updateProactiveEnabled() {
    const enabled = elements.proactiveEnabled.checked;

    if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.set_proactive_enabled(enabled);
    }
}

let isListeningForKey = false;

function startKeyCapture() {
    if (isListeningForKey) return;

    isListeningForKey = true;
    elements.currentMuteKey.textContent = 'Presiona una tecla...';
    elements.currentMuteKey.style.color = 'var(--status-listening)';
}

function handleKeyCapture(event) {
    if (!isListeningForKey) return;

    event.preventDefault();
    const key = event.key === ' ' ? 'Space' : event.key;
    state.muteKey = key;
    elements.currentMuteKey.textContent = key;
    elements.currentMuteKey.style.color = 'var(--accent-cyan)';
    isListeningForKey = false;

    // Guardar en backend
    if (window.pywebview && window.pywebview.api) {
        window.pywebview.api.set_mute_key(key);
    }
}

// ==================== ATAJOS DE TECLADO ====================

function handleGlobalKeydown(event) {
    // Si estamos capturando tecla para keybind
    if (isListeningForKey) {
        handleKeyCapture(event);
        return;
    }

    // Mute key
    if (event.key === state.muteKey || event.key.toUpperCase() === state.muteKey) {
        event.preventDefault();
        toggleMute();
    }

    // Escape para cerrar modal
    if (event.key === 'Escape') {
        closeSettings();
    }
}

// ==================== COMUNICACIÓN CON BACKEND ====================

// Funciones llamadas desde Python
window.yuiCallbacks = {
    onStateChange: function (newState) {
        updateState(newState);
    },

    onTranscript: function (text) {
        updateTranscript(text, true);
    },

    onResponse: function (text) {
        updateResponse(text);
    },

    onError: function (message) {
        console.error('Backend error:', message);
        updateResponse('Error: ' + message);
    },

    onConnected: function () {
        state.isConnected = true;
        updateState('active');
        console.log('Connected to Yui backend');
    }
};

// ==================== INICIALIZACIÓN ====================

function init() {
    // Event listeners para controles
    elements.btnMute.addEventListener('click', toggleMute);
    elements.btnSleep.addEventListener('click', toggleSleep);
    elements.btnSettings.addEventListener('click', openSettings);
    elements.btnCloseSettings.addEventListener('click', closeSettings);
    elements.btnClearTranscript.addEventListener('click', clearTranscript);

    // Event listeners para configuración
    elements.vadThreshold.addEventListener('input', updateVadThreshold);
    elements.proactiveEnabled.addEventListener('change', updateProactiveEnabled);
    elements.btnChangeMuteKey.addEventListener('click', startKeyCapture);

    // Click fuera del modal para cerrar
    elements.settingsModal.addEventListener('click', (e) => {
        if (e.target === elements.settingsModal) {
            closeSettings();
        }
    });

    // Atajos de teclado globales
    document.addEventListener('keydown', handleGlobalKeydown);

    // Función para inicializar estado desde backend
    function initializeFromBackend() {
        console.log('Calling get_initial_state...');
        window.pywebview.api.get_initial_state().then(initialState => {
            console.log('=== INITIAL STATE RECEIVED ===');
            console.log('Full response:', JSON.stringify(initialState));
            console.log('mute_key from backend:', initialState.mute_key);

            state.isMuted = initialState.muted;
            state.muteKey = initialState.mute_key || 'F1';

            console.log('state.muteKey set to:', state.muteKey);

            // Actualizar elemento visual
            const keyElement = document.getElementById('currentMuteKey');
            if (keyElement) {
                keyElement.textContent = state.muteKey;
                console.log('Element updated to:', keyElement.textContent);
            }

            elements.vadThreshold.value = initialState.vad_threshold || 0.65;
            elements.vadThresholdValue.textContent = (initialState.vad_threshold || 0.65).toFixed(2);
            elements.proactiveEnabled.checked = initialState.proactive_enabled !== false;
            updateState(initialState.state || 'active');
            updateMuteUI();

            console.log('=== INIT COMPLETE ===');
        }).catch(err => {
            console.error('ERROR getting initial state:', err);
        });
    }

    // Usar pywebviewready event para asegurar que el API esté lista
    if (window.pywebview && window.pywebview.api) {
        // API ya está lista
        console.log('pywebview.api already available');
        initializeFromBackend();
    } else {
        // Esperar a que pywebview esté listo
        console.log('Waiting for pywebviewready event...');
        window.addEventListener('pywebviewready', function () {
            console.log('pywebviewready event fired!');
            initializeFromBackend();
        });

        // Fallback: si el evento no se dispara, intentar después de 2 segundos
        setTimeout(() => {
            if (window.pywebview && window.pywebview.api) {
                console.log('Fallback: pywebview.api available after delay');
                initializeFromBackend();
            } else {
                // Demo mode sin backend
                console.log('Running in demo mode (no backend connected)');
                updateState('active');
            }
        }, 2000);
    }
}

// Iniciar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', init);
