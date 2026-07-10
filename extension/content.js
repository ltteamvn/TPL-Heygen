// ===================================
// CONTENT SCRIPT - Inject script vào page
// ===================================

(function() {
    class Logger {
        constructor(context) {
            this.context = context;
        }
        log(message, data = null) {
            if (data) console.log(`[${this.context}] ${message}`, data);
            else console.log(`[${this.context}] ${message}`);
        }
        debug(message, data = null) {
            if (data) console.log(`[${this.context}] ${message}`, data);
            else console.log(`[${this.context}] ${message}`);
        }
        warn(message, data = null) {
            if (data) console.warn(`[${this.context}] ⚠️ ${message}`, data);
            else console.warn(`[${this.context}] ⚠️ ${message}`);
        }
        error(message, data = null) {
            if (data) console.error(`[${this.context}] ❌ ${message}`, data);
            else console.error(`[${this.context}] ❌ ${message}`);
        }
        success(message, data = null) {
            if (data) console.log(`[${this.context}] ✅ ${message}`, data);
            else console.log(`[${this.context}] ✅ ${message}`);
        }
    }

    const logger = new Logger('ContentScript');

    logger.log('Initializing...');

    // Inject captcha client script vào page context
    function injectCaptchaScript() {
        const script = document.createElement('script');
        script.src = chrome.runtime.getURL('injected.js');
        script.type = 'text/javascript';
        
        (document.head || document.documentElement).appendChild(script);
        
        script.onload = function() {
            logger.success('Captcha client injected successfully');
            script.remove();
        };

        script.onerror = function() {
            logger.error('Failed to inject captcha client');
        };
    }

    // Lắng nghe tin nhắn từ injected script
    window.addEventListener('message', function(event) {
        if (event.source !== window) return;
        
        // Nhận log từ injected script
        if (event.data.type === 'CAPTCHA_LOG') {
            logger.log('From Injected', event.data.message);
        }
        
        // Nhận status update
        if (event.data.type === 'CAPTCHA_STATUS') {
            // Gửi status lên background script nếu cần
            try {
                chrome.runtime.sendMessage({
                    type: 'CAPTCHA_STATUS_UPDATE',
                    data: event.data.data
                });
            } catch (error) {
                logger.warn('Could not send status update', error);
            }
        }

        // Nhận request settings từ injected script
        if (event.data.type === 'GET_SETTINGS_REQUEST') {
            try {
                chrome.runtime.sendMessage({ type: 'GET_SETTINGS' }, (response) => {
                    if (chrome.runtime.lastError) {
                        logger.warn('Extension error', chrome.runtime.lastError);
                        return;
                    }
                    
                    if (!response) {
                        logger.warn('No response from background');
                        return;
                    }
                    
                    try {
                        logger.log('Sending settings to injected', response);
                        window.postMessage({
                            type: 'GET_SETTINGS_RESPONSE',
                            settings: response
                        }, '*');
                    } catch (error) {
                        logger.warn('Could not send settings response', error);
                    }
                });
            } catch (error) {
                logger.warn('Could not request settings', error);
            }
        }
    });

    // Lắng nghe tin nhắn từ background script
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
        if (request.type === 'GET_PAGE_INFO') {
            sendResponse({
                url: window.location.href,
                title: document.title
            });
        }

        if (request.type === 'RELOAD_PAGE') {
            logger.log('Reloading page...');
            // Clear localStorage trước khi reload
            localStorage.removeItem('_grecaptcha');
            logger.log('Cleared _grecaptcha from localStorage');
            window.location.reload();
        }

        if (request.type === 'COUNTDOWN_UPDATE') {
            // Gửi countdown đến injected script
            window.postMessage({
                type: 'COUNTDOWN_UPDATE',
                remainingSeconds: request.remainingSeconds,
                totalSeconds: request.totalSeconds
            }, '*');
        }
    });

    // Inject script khi DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', injectCaptchaScript);
    } else {
        injectCaptchaScript();
    }

    logger.success('Ready');
})();