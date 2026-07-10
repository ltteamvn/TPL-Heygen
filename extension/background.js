// ===================================
// BACKGROUND SCRIPT - Service Worker
// ===================================

console.log('🔧 Background Script: Started');

// Default settings
const DEFAULT_SETTINGS = {
    autoReload: true,
    reloadInterval: 5, // minutes
    enabled: true,
    clearGrecaptcha: false // New setting
};

// Lấy settings từ storage
async function getSettings() {
    const result = await chrome.storage.sync.get(DEFAULT_SETTINGS);
    return result;
}

// Lưu settings
async function saveSettings(settings) {
    await chrome.storage.sync.set(settings);
}

// Tạo alarm cho auto reload
async function createReloadAlarm() {
    const settings = await getSettings();
    
    // Xóa alarm cũ
    await chrome.alarms.clear('autoReload');
    
    if (settings.enabled && settings.autoReload && settings.reloadInterval > 0) {
        // Tạo alarm mới (periodInMinutes)
        await chrome.alarms.create('autoReload', {
            periodInMinutes: settings.reloadInterval
        });
        await createCountdownAlarm();
        console.log(`✅ Auto reload alarm set: ${settings.reloadInterval} minutes`);
    } else {
        console.log('⏸️ Auto reload disabled');
        await chrome.alarms.clear('countdownTick');
    }
}

// Xử lý alarm
chrome.alarms.onAlarm.addListener(async (alarm) => {
    if (alarm.name === 'autoReload') {
        const settings = await getSettings();
        
        if (!settings.enabled || !settings.autoReload) {
            return;
        }

        console.log('⏰ Auto reload triggered');
        
        // Lấy tất cả tabs active
        const tabs = await chrome.tabs.query({ active: true });
        
        for (const tab of tabs) {
            try {
                // Gửi message đến content script để reload
                await chrome.tabs.sendMessage(tab.id, { type: 'RELOAD_PAGE' });
                console.log(`🔄 Reloaded tab: ${tab.id}`);
            } catch (error) {
                console.error(`Failed to reload tab ${tab.id}:`, error);
            }
        }
    }
});

// Gửi countdown đến tất cả tabs mỗi giây
chrome.alarms.onAlarm.addListener(async (alarm) => {
    if (alarm.name === 'countdownTick') {
        const settings = await getSettings();
        
        if (!settings.enabled || !settings.autoReload) {
            return;
        }

        // Lấy alarm tiếp theo
        const alarms = await chrome.alarms.getAll();
        const autoReloadAlarm = alarms.find(a => a.name === 'autoReload');
        
        if (autoReloadAlarm) {
            const now = Date.now();
            const alarmTime = autoReloadAlarm.scheduledTime;
            const remainingMs = Math.max(0, alarmTime - now);
            const remainingSeconds = Math.ceil(remainingMs / 1000);

            // Gửi countdown đến tất cả tabs
            const tabs = await chrome.tabs.query({});
            for (const tab of tabs) {
                try {
                    await chrome.tabs.sendMessage(tab.id, {
                        type: 'COUNTDOWN_UPDATE',
                        remainingSeconds: remainingSeconds,
                        totalSeconds: settings.reloadInterval * 60
                    });
                } catch (error) {
                    // Ignore errors for tabs that don't have content script
                }
            }
        }
    }
});

// Tạo alarm cho countdown (tick mỗi giây)
async function createCountdownAlarm() {
    await chrome.alarms.clear('countdownTick');
    await chrome.alarms.create('countdownTick', {
        periodInMinutes: 1 / 60 // Mỗi giây
    });
}

// Lắng nghe message từ popup hoặc content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.type === 'GET_SETTINGS') {
        getSettings().then(sendResponse);
        return true; // async response
    }
    
    if (request.type === 'SAVE_SETTINGS') {
        saveSettings(request.settings).then(async () => {
            await createReloadAlarm();
            sendResponse({ success: true });
        });
        return true;
    }
    
    if (request.type === 'RELOAD_NOW') {
        chrome.tabs.query({ active: true, currentWindow: true }).then(tabs => {
            if (tabs[0]) {
                chrome.tabs.sendMessage(tabs[0].id, { type: 'RELOAD_PAGE' });
                sendResponse({ success: true });
            }
        });
        return true;
    }

    if (request.type === 'CAPTCHA_STATUS_UPDATE') {
        console.log('📊 Captcha status:', request.data);
        // Có thể lưu status vào storage hoặc xử lý khác
    }
});

// Khởi tạo khi extension được install/update
chrome.runtime.onInstalled.addListener(async (details) => {
    console.log('🎉 Extension installed/updated:', details.reason);
    
    // Khởi tạo settings nếu chưa có
    const settings = await getSettings();
    await saveSettings(settings);
    
    // Tạo alarm
    await createReloadAlarm();
});

// Khởi tạo alarm khi service worker start
createReloadAlarm();