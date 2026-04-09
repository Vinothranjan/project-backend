document.addEventListener('DOMContentLoaded', () => {
    const knownFacesContainer = document.getElementById('known-faces');
    const logsContainer = document.getElementById('activity-logs');
    const btnToggleGuest = document.getElementById('btn-toggle-guest');
    const statusText = document.getElementById('status-text');
    const protectionStatus = document.getElementById('protection-status');
    const systemTime = document.getElementById('system-time');

    // Update Clock
    setInterval(() => {
        const now = new Date();
        systemTime.textContent = now.toLocaleTimeString();
    }, 1000);

    // Fetch Known Faces
    async function fetchKnownFaces() {
        try {
            const response = await fetch('/api/known_faces');
            const faces = await response.json();
            
            knownFacesContainer.innerHTML = '';
            faces.forEach(name => {
                const card = document.createElement('div');
                card.className = 'face-card';
                card.innerHTML = `
                    <div style="width: 100%; height: 80px; background: rgba(255,255,255,0.05); border-radius: 8px; display: flex; align-items: center; justify-content: center;">
                        👤
                    </div>
                    <p>${name}</p>
                `;
                knownFacesContainer.appendChild(card);
            });
        } catch (err) {
            console.error('Error fetching faces:', err);
        }
    }

    const cameraModal = document.getElementById('camera-modal');
    const ipUrlInput = document.getElementById('ip-url');
    const btnTrain = document.getElementById('btn-train');

    // Camera Control
    window.startCamera = async (type) => {
        const url = ipUrlInput.value;
        addLog(`Attempting to start ${type} camera...`);
        try {
            const response = await fetch('/api/start_camera', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ type, url })
            });
            const data = await response.json();
            if (data.success) {
                cameraModal.style.display = 'none';
                addLog(`Success: ${type} camera active.`);
                // Refresh video feed
                const feed = document.getElementById('main-feed');
                feed.src = feed.src.split('?')[0] + '?t=' + new Date().getTime();
            } else {
                addLog(`Failed to start ${type} camera.`, true);
            }
        } catch (err) {
            console.error('Error starting camera:', err);
        }
    };

    // Training
    btnTrain.addEventListener('click', async () => {
        addLog("Starting model re-training...");
        try {
            await fetch('/api/train', { method: 'POST' });
            addLog("Success: Model trained with latest faces.");
            fetchKnownFaces();
        } catch (err) {
            addLog("Training failed.", true);
        }
    });

    // Update Status
    async function updateStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            
            // Handle Modal Visibility
            if (!data.camera_active && cameraModal.style.display !== 'flex') {
                cameraModal.style.display = 'flex';
            }

            if (data.guest_mode) {
                statusText.textContent = `GUEST ACCESS (${data.access_timer}s)`;
                protectionStatus.className = 'status-badge secured';
                btnToggleGuest.innerHTML = '🛡️ Revoke Access';
                btnToggleGuest.style.background = 'var(--danger)';
            } else {
                statusText.textContent = 'SECURED';
                protectionStatus.className = 'status-badge warning';
                btnToggleGuest.innerHTML = '🔓 Grant Access';
                btnToggleGuest.style.background = 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))';
            }
        } catch (err) {
            console.error('Error updating status:', err);
        }
    }

    // Toggle Guest Mode
    btnToggleGuest.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/toggle_guest', { method: 'POST' });
            const data = await response.json();
            addLog(data.guest_mode ? "Manual Guest Access Granted" : "Manual Guest Access Revoked", data.guest_mode);
            updateStatus();
        } catch (err) {
            console.error('Error toggling guest:', err);
        }
    });

    function addLog(msg, isAlert = false) {
        const entry = document.createElement('div');
        entry.className = `log-entry ${isAlert ? 'alert' : ''}`;
        const time = new Date().toLocaleTimeString();
        entry.innerHTML = `
            <div class="time">${time}</div>
            <div class="msg">${msg}</div>
        `;
        logsContainer.prepend(entry);
        if (logsContainer.children.length > 10) logsContainer.lastChild.remove();
    }

    // Initial Load
    fetchKnownFaces();
    setInterval(updateStatus, 2000);
});
