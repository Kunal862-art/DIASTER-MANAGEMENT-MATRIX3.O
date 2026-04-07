document.addEventListener('DOMContentLoaded', () => {
    // 1. Intercept offline form submissions natively
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!navigator.onLine) {
                e.preventDefault();
                const formData = new FormData(form);
                const dataObj = Object.fromEntries(formData.entries());
                
                // Route Mapping
                let endpoint = '';
                if (form.action.includes('/reports')) endpoint = '/api/sync/reports';
                if (form.action.includes('/attendance')) endpoint = '/api/sync/attendance';
                
                if (endpoint) {
                    saveToOfflineQueue({
                        timestamp: new Date().toISOString(),
                        endpoint: endpoint,
                        payload: dataObj,
                        formAction: form.action
                    });
                    showToast('Device Offline! Your data is securely saved locally and will sync when reconnected.', 'error');
                    form.reset(); // clear form out
                }
            }
        });
    });

    // 2. Listen to connection restored
    window.addEventListener('online', () => {
        showToast('Connection Restored! Syncing buffered data to the cloud...', 'success');
        syncOfflineQueue();
    });

    // 3. Try to sync on page load if online
    if (navigator.onLine) {
        syncOfflineQueue();
    }
});

function saveToOfflineQueue(item) {
    let queue = JSON.parse(localStorage.getItem('safestep_offline_queue') || '[]');
    queue.push(item);
    localStorage.setItem('safestep_offline_queue', JSON.stringify(queue));
}

async function syncOfflineQueue() {
    let queue = JSON.parse(localStorage.getItem('safestep_offline_queue') || '[]');
    if (queue.length === 0) return;

    let successfulSyncs = [];
    
    for (let i = 0; i < queue.length; i++) {
        let item = queue[i];
        try {
            const resp = await fetch(item.endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(item.payload)
            });
            if (resp.ok) {
                successfulSyncs.push(i);
            }
        } catch (e) {
            console.error('[SafeSTEP] Sync failed for item', item, e);
        }
    }

    if (successfulSyncs.length > 0) {
        // Remove successful items (backwards to avoid index shifting)
        for (let i = successfulSyncs.length - 1; i >= 0; i--) {
            queue.splice(successfulSyncs[i], 1);
        }
        localStorage.setItem('safestep_offline_queue', JSON.stringify(queue));
        showToast(`Successfully synced ${successfulSyncs.length} buffered offline items!`, 'success');
        
        // Reload to show the synced data if queue is fully cleared
        if (queue.length === 0) {
            setTimeout(() => window.location.reload(), 2000);
        }
    }
}

function showToast(message, type = 'success') {
    let container = document.getElementById('flash-messages');
    if (!container) {
       container = document.querySelector('.flash-messages-container');
    }
    if (!container) return;
    
    const alertId = `sync-alert-${Date.now()}`;
    
    // We create a new alert matching the visual structure in style.css
    const alertHtml = `
        <div id="${alertId}" class="alert alert-${type}" style="display: flex; justify-content: space-between; align-items: center;">
            <div>${message}</div>
            <span class="close-alert" onclick="document.getElementById('${alertId}').remove()">&times;</span>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', alertHtml);
    setTimeout(() => {
        const el = document.getElementById(alertId);
        if (el) el.remove();
    }, 6000);
}
