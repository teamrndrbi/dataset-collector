/**
 * Dataset Collector — Frontend Logic
 * Webcam capture, labeling, and upload management
 */

(function () {
    'use strict';

    // ─── State ──────────────────────────────────────────────
    const state = {
        stream: null,
        capturedImage: null,
        selectedLabel: null,
        labels: ['revisi besar', 'revisi kecil', 'lolos'],
        customLabels: [],
        history: [],
        isUploading: false,
    };

    // ─── DOM Elements ───────────────────────────────────────
    const $ = (id) => document.getElementById(id);

    const els = {
        webcam: $('webcam'),
        canvas: $('capture-canvas'),
        videoOverlay: $('video-overlay'),
        btnStartCamera: $('btn-start-camera'),
        btnCapture: $('btn-capture'),
        btnRetake: $('btn-retake'),
        btnUpload: $('btn-upload'),
        btnSettings: $('btn-settings'),
        btnCloseSettings: $('btn-close-settings'),
        btnSaveConfig: $('btn-save-config'),
        btnTestDrive: $('btn-test-drive'),
        btnAddLabel: $('btn-add-label'),
        btnLogoutDrive: $('btn-logout-drive'),
        cameraSection: $('camera-section'),
        previewSection: $('preview-section'),
        previewImage: $('preview-image'),
        labelGrid: $('label-grid'),
        newLabelInput: $('new-label-input'),
        settingsModal: $('settings-modal'),
        loadingOverlay: $('loading-overlay'),
        toastContainer: $('toast-container'),
        historyList: $('history-list'),
        totalCount: $('total-count'),
        nextIdBadge: $('next-id-badge'),
        driveStatus: $('drive-status'),
        authStatusText: $('auth-status-text'),
        cfgDatasetName: $('cfg-dataset-name'),
        cfgParentFolder: $('cfg-parent-folder'),
        cfgDriveEnabled: $('cfg-drive-enabled'),
        cfgClientSecret: $('cfg-client-secret'),
    };

    // ─── Init ───────────────────────────────────────────────
    function init() {
        loadCustomLabels();
        renderLabels();
        bindEvents();
        loadConfig();
        updateNextId();
    }

    // ─── Camera ─────────────────────────────────────────────
    async function startCamera() {
        try {
            const constraints = {
                video: { width: { ideal: 1280 }, height: { ideal: 960 }, facingMode: 'environment' },
                audio: false,
            };
            state.stream = await navigator.mediaDevices.getUserMedia(constraints);
            els.webcam.srcObject = state.stream;
            els.videoOverlay.classList.add('hidden');
            els.btnCapture.disabled = false;
            showToast('Kamera aktif', 'success');
        } catch (err) {
            console.error('Camera error:', err);
            showToast('Gagal mengakses kamera: ' + err.message, 'error');
        }
    }

    function captureImage() {
        if (!state.stream) return;
        const video = els.webcam;
        const canvas = els.canvas;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0);
        state.capturedImage = canvas.toDataURL('image/jpeg', 0.92);
        els.previewImage.src = state.capturedImage;
        els.cameraSection.style.display = 'none';
        els.previewSection.style.display = 'block';
        els.previewSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        updateUploadButton();
    }

    function retake() {
        state.capturedImage = null;
        state.selectedLabel = null;
        els.cameraSection.style.display = 'block';
        els.previewSection.style.display = 'none';
        renderLabels();
        updateUploadButton();
    }

    // ─── Labels ─────────────────────────────────────────────
    function loadCustomLabels() {
        try {
            const saved = localStorage.getItem('dc_custom_labels');
            if (saved) state.customLabels = JSON.parse(saved);
        } catch (e) { state.customLabels = []; }
    }

    function saveCustomLabels() {
        localStorage.setItem('dc_custom_labels', JSON.stringify(state.customLabels));
    }

    function getAllLabels() { return [...state.labels, ...state.customLabels]; }

    function renderLabels() {
        const grid = els.labelGrid;
        grid.innerHTML = '';
        getAllLabels().forEach((label) => {
            const chip = document.createElement('div');
            chip.className = 'label-chip' + (state.selectedLabel === label ? ' active' : '');
            const isCustom = state.customLabels.includes(label);
            if (isCustom) chip.classList.add('custom');
            chip.innerHTML = `<span>${label}</span>` +
                (isCustom ? `<button class="remove-label" title="Hapus label">&times;</button>` : '');
            chip.addEventListener('click', (e) => {
                if (e.target.classList.contains('remove-label')) { removeLabel(label); return; }
                state.selectedLabel = label;
                renderLabels();
                updateUploadButton();
            });
            grid.appendChild(chip);
        });
    }

    function addLabel() {
        const input = els.newLabelInput;
        const name = input.value.trim().toLowerCase();
        if (!name) return;
        if (getAllLabels().includes(name)) { showToast('Label sudah ada', 'warning'); return; }
        state.customLabels.push(name);
        saveCustomLabels();
        input.value = '';
        renderLabels();
        showToast(`Label "${name}" ditambahkan`, 'success');
    }

    function removeLabel(label) {
        state.customLabels = state.customLabels.filter((l) => l !== label);
        saveCustomLabels();
        if (state.selectedLabel === label) state.selectedLabel = null;
        renderLabels();
        updateUploadButton();
    }

    // ─── Upload ─────────────────────────────────────────────
    function updateUploadButton() {
        els.btnUpload.disabled = !(state.capturedImage && state.selectedLabel);
    }

    async function uploadImage() {
        if (state.isUploading || !state.capturedImage || !state.selectedLabel) return;
        state.isUploading = true;
        els.loadingOverlay.style.display = 'flex';
        try {
            const response = await fetch('/upload', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: state.capturedImage, label: state.selectedLabel }),
            });
            const result = await response.json();
            if (result.success) {
                const driveOk = result.drive_upload && result.drive_upload.success;
                showToast(`✅ ${result.file_name} — ${driveOk ? '☁️ Drive' : '💾 Lokal'}`, 'success');
                addHistoryItem({
                    id: result.id, fileName: result.file_name,
                    label: result.label, timestamp: result.timestamp, driveOk: driveOk,
                });
                updateNextId();
                setTimeout(() => retake(), 800);
            } else {
                showToast('❌ Upload gagal: ' + (result.error || 'Unknown'), 'error');
            }
        } catch (err) {
            showToast('❌ Network error: ' + err.message, 'error');
        } finally {
            state.isUploading = false;
            els.loadingOverlay.style.display = 'none';
        }
    }

    // ─── History ────────────────────────────────────────────
    function addHistoryItem(item) {
        state.history.unshift(item);
        const empty = els.historyList.querySelector('.empty-state');
        if (empty) empty.remove();
        const div = document.createElement('div');
        div.className = 'history-item';
        div.innerHTML = `
            <span class="h-id">#${item.id}</span>
            <span class="h-name">${item.fileName}</span>
            <span class="h-status ${item.driveOk ? 'drive' : 'local'}">${item.driveOk ? '☁️ Drive' : '💾 Local'}</span>
        `;
        els.historyList.prepend(div);
        els.totalCount.textContent = `${state.history.length} gambar`;
    }

    async function updateNextId() {
        try {
            const res = await fetch('/counter');
            const data = await res.json();
            els.nextIdBadge.textContent = `Next: #${data.next_id}`;
        } catch (e) { /* ignore */ }
    }

    // ─── Settings ───────────────────────────────────────────
    async function loadConfig() {
        try {
            const res = await fetch('/config');
            const cfg = await res.json();
            els.cfgDatasetName.value = cfg.dataset_name || 'Dataset';
            els.cfgParentFolder.value = cfg.parent_folder_id || '';
            els.cfgDriveEnabled.checked = cfg.drive_enabled || false;

            const dot = els.driveStatus.querySelector('.status-dot');
            const text = els.driveStatus.querySelector('.status-text');

            if (cfg.drive_authorized && cfg.drive_enabled) {
                dot.className = 'status-dot online';
                text.textContent = 'Drive Online';
                els.authStatusText.textContent = '✅ Status: Terhubung ke Google Drive';
                els.authStatusText.style.color = '#10b981';
                els.btnLogoutDrive.style.display = 'inline-flex';
            } else if (cfg.drive_authorized) {
                dot.className = 'status-dot online';
                text.textContent = 'Drive Ready';
                els.authStatusText.textContent = '✅ Authorized — aktifkan toggle "Enable" untuk mulai upload';
                els.authStatusText.style.color = '#f59e0b';
                els.btnLogoutDrive.style.display = 'inline-flex';
            } else {
                dot.className = 'status-dot offline';
                text.textContent = 'Drive Offline';
                els.authStatusText.textContent = '❌ Status: Belum terhubung — klik "Login Google Drive"';
                els.authStatusText.style.color = '#ef4444';
                els.btnLogoutDrive.style.display = 'none';
            }
        } catch (e) {
            console.error('Load config error:', e);
        }
    }

    async function saveConfig() {
        try {
            const payload = {
                dataset_name: els.cfgDatasetName.value,
                parent_folder_id: els.cfgParentFolder.value,
                drive_enabled: els.cfgDriveEnabled.checked,
            };
            const csText = els.cfgClientSecret.value.trim();
            if (csText) payload.client_secret = csText;

            const res = await fetch('/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const result = await res.json();
            if (result.success) {
                showToast(result.message, 'success');
                els.cfgClientSecret.value = '';
                loadConfig();
            } else {
                showToast('❌ ' + result.error, 'error');
            }
        } catch (e) { showToast('❌ Error: ' + e.message, 'error'); }
    }

    async function logoutDrive() {
        try {
            const res = await fetch('/auth/logout', { method: 'POST' });
            const result = await res.json();
            showToast(result.message, 'success');
            loadConfig();
        } catch (e) { showToast('❌ Error: ' + e.message, 'error'); }
    }

    async function testDriveConnection() {
        showToast('🔌 Testing connection...', 'info');
        try {
            const res = await fetch('/test-drive', { method: 'POST' });
            const result = await res.json();
            showToast(result.success ? '✅ ' + result.message : '❌ ' + result.error, result.success ? 'success' : 'error');
        } catch (e) { showToast('❌ Error: ' + e.message, 'error'); }
    }

    // ─── Toast ──────────────────────────────────────────────
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        els.toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(20px)';
            toast.style.transition = 'all 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    }

    // ─── Event Bindings ─────────────────────────────────────
    function bindEvents() {
        els.btnStartCamera.addEventListener('click', startCamera);
        els.btnCapture.addEventListener('click', captureImage);
        els.btnRetake.addEventListener('click', retake);
        els.btnUpload.addEventListener('click', uploadImage);
        els.btnAddLabel.addEventListener('click', addLabel);
        els.newLabelInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') addLabel(); });

        // Settings
        els.btnSettings.addEventListener('click', () => { els.settingsModal.style.display = 'flex'; });
        els.btnCloseSettings.addEventListener('click', () => { els.settingsModal.style.display = 'none'; });
        els.settingsModal.addEventListener('click', (e) => {
            if (e.target === els.settingsModal) els.settingsModal.style.display = 'none';
        });

        els.btnSaveConfig.addEventListener('click', saveConfig);
        els.btnTestDrive.addEventListener('click', testDriveConnection);
        els.btnLogoutDrive.addEventListener('click', logoutDrive);

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
            if (e.code === 'Space' && !els.btnCapture.disabled && els.cameraSection.style.display !== 'none') {
                e.preventDefault(); captureImage();
            }
            if (e.code === 'Enter' && !els.btnUpload.disabled && els.previewSection.style.display !== 'none') {
                e.preventDefault(); uploadImage();
            }
            if (e.code === 'Escape') {
                if (els.settingsModal.style.display !== 'none') els.settingsModal.style.display = 'none';
                else if (els.previewSection.style.display !== 'none') retake();
            }
        });
    }

    document.addEventListener('DOMContentLoaded', init);
})();
