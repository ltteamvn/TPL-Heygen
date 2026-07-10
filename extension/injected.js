// ===================================
// INJECTED SCRIPT - Chạy trong page context
// ===================================

(async function () {
    class Logger {
        constructor(context) {
            this.context = context;
        }
        log(message, data = null) {
            if (data) console.log(`[${this.context}] ${message}`, data);
            else console.log(`[${this.context}] ${message}`);
        }
        debug(message, data = null) {
            if (data) console.debug(`[${this.context}] ${message}`, data);
            else console.debug(`[${this.context}] ${message}`);
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

    const logger = new Logger('CaptchaClient');

    logger.log('🚀 Starting Captcha Client...');

    const CONFIG = {
        siteKey: '6LdsFiUsAAAAAIjVDZcuLhaHiDn5nnHVXVRQGeMV',
        socketServer: 'http://localhost:3000', // URL NestJS server
    };

    // Cache settings - lưu để tránh request lặp lại
    let cachedSettings = null;

    // Helper để gửi log về content script
    function sendLog(message) {
        window.postMessage({
            type: 'CAPTCHA_LOG',
            message: message
        }, '*');
    }

    // Helper để gửi status update
    function sendStatus(status, data = {}) {
        window.postMessage({
            type: 'CAPTCHA_STATUS',
            data: { status, ...data }
        }, '*');
    }

    // Load settings từ content script
    async function getSettings() {
        // Return cached settings nếu có
        if (cachedSettings) {
            logger.log('Using cached settings', cachedSettings);
            return cachedSettings;
        }

        return await new Promise((resolve) => {
            window.postMessage({
                type: 'GET_SETTINGS_REQUEST'
            }, '*');
            
            logger.log('Requesting settings from background...');
            
            let responseReceived = false;
            
            const listener = (event) => {
                if (event.source !== window) return;
                if (event.data.type === 'GET_SETTINGS_RESPONSE') {
                    window.removeEventListener('message', listener);
                    responseReceived = true;
                    cachedSettings = event.data.settings;
                    logger.success('Settings received', cachedSettings);
                    resolve(cachedSettings);
                }
            };
            window.addEventListener('message', listener);
            
            // Timeout after 2s if no response
            setTimeout(() => {
                window.removeEventListener('message', listener);
                
                // Chỉ return defaults, không cache!
                if (!responseReceived) {
                    logger.warn('Settings request timeout, using defaults (NOT cached)');
                    resolve({ clearGrecaptcha: false });
                }
            }, 2000);
        });
    }

    // Tạo CSS cho countdown badge
    function createCountdownStyles() {
        const style = document.createElement('style');
        style.textContent = `
            #countdown-badge {
                position: fixed;
                bottom: 28px;
                right: 28px;
                min-width: 156px;
                height: 88px;
                border-radius: 12px;
                background: linear-gradient(135deg, #5b7cfa 0%, #748ffc 100%);
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
                color: white;
                box-shadow: 0 10px 32px rgba(91, 124, 250, 0.35),
                            inset 0 1px 2px rgba(255, 255, 255, 0.3);
                z-index: 999999;
                transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
                opacity: 0.97;
                cursor: default;
                padding: 14px 16px;
                gap: 6px;
                backdrop-filter: blur(8px);
                border: 1px solid rgba(255, 255, 255, 0.2);
            }

            #countdown-badge:hover {
                transform: translateY(-3px);
                opacity: 1;
                box-shadow: 0 14px 40px rgba(91, 124, 250, 0.45),
                            inset 0 1px 2px rgba(255, 255, 255, 0.3);
            }

            #countdown-badge.hidden {
                display: none;
            }

            #countdown-badge-label {
                font-size: 11px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.8px;
                opacity: 0.85;
                white-space: nowrap;
                text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
            }

            #countdown-badge-time {
                font-size: 36px;
                font-weight: 700;
                text-align: center;
                line-height: 1;
                font-variant-numeric: tabular-nums;
                text-shadow: 0 2px 4px rgba(0, 0, 0, 0.15);
                letter-spacing: -1px;
            }

            #countdown-badge-progress {
                position: absolute;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                border-radius: 12px;
                background: linear-gradient(135deg, 
                    rgba(91, 124, 250, 0.15) 0%,
                    rgba(116, 143, 252, 0.15) 100%);
                opacity: 0.5;
                pointer-events: none;
            }
        `;
        document.head.appendChild(style);
    }

    // Tạo countdown badge element
    function createCountdownBadge() {
        if (document.getElementById('countdown-badge')) {
            return;
        }

        const badge = document.createElement('div');
        badge.id = 'countdown-badge';
        badge.className = 'hidden';
        badge.innerHTML = `
            <div id="countdown-badge-progress"></div>
            <div id="countdown-badge-label">Before Reload</div>
            <div id="countdown-badge-time">--</div>
        `;
        document.body.appendChild(badge);
    }

    // Update countdown badge
    function updateCountdownBadge(remainingSeconds, totalSeconds) {
        const badge = document.getElementById('countdown-badge');
        if (!badge) return;

        if (remainingSeconds <= 0) {
            badge.classList.add('hidden');
            return;
        }

        badge.classList.remove('hidden');

        const timeElement = document.querySelector('#countdown-badge-time');
        const seconds = Math.max(0, remainingSeconds);
        timeElement.textContent = String(seconds).padStart(2, '0') + 's';

        // Color gradient: blue -> orange -> red
        let bgColor;
        const percentage = remainingSeconds / totalSeconds;

        if (percentage > 0.6) {
            // Xanh dương - sắp sửa reload
            bgColor = 'linear-gradient(135deg, #5b7cfa 0%, #748ffc 100%)';
        } else if (percentage > 0.3) {
            // Cam - cảnh báo
            bgColor = 'linear-gradient(135deg, #ffa500 0%, #ff8c00 100%)';
        } else {
            // Đỏ - gần reload ngay
            bgColor = 'linear-gradient(135deg, #ff4757 0%, #ff3838 100%)';
        }
        badge.style.background = bgColor;
    }

    // Load Socket.IO
    function loadSocketIO() {
        return new Promise((resolve, reject) => {
            if (window.io) {
                resolve(window.io);
                return;
            }

            const script = document.createElement('script');
            script.src = 'https://cdn.socket.io/4.5.4/socket.io.min.js';
            script.onload = () => resolve(window.io);
            script.onerror = reject;
            document.head.appendChild(script);
        });
    }

    // Chờ grecaptcha load
    async function waitForRecaptcha() {
        logger.log('Waiting for reCAPTCHA...');
        sendLog('Waiting for reCAPTCHA...');

        const maxAttempts = 60;
        for (let i = 0; i < maxAttempts; i++) {
            if (window.grecaptcha?.enterprise?.execute) {
                logger.success('reCAPTCHA ready!');
                sendLog('reCAPTCHA ready!');
                return true;
            }
            await new Promise(resolve => setTimeout(resolve, 500));
        }
        throw new Error('reCAPTCHA not loaded after 30s');
    }

    // Solve captcha
    async function solveCaptcha(action = 'VIDEO_GENERATION') {
        try {
            logger.log('Executing reCAPTCHA...');
            sendLog('Executing reCAPTCHA...');

            const token = await window.grecaptcha.enterprise.execute(
                CONFIG.siteKey,
                { action: action }
            );

            logger.success('Token obtained', token.substring(0, 50) + '...');
            sendLog('Token obtained: ' + token.substring(0, 50) + '...');
            sendStatus('token_obtained', { tokenLength: token.length });

            // Clear _grecaptcha from localStorage nếu config enabled
            try {
                const settings = await getSettings();

                logger.log('Settings received', settings);
                logger.log('clearGrecaptcha value', settings.clearGrecaptcha);
                
                if (settings.clearGrecaptcha === true) {
                    localStorage.removeItem('_grecaptcha');
                    logger.log('Cleared _grecaptcha from localStorage');
                    sendLog('Cleared _grecaptcha from localStorage');
                } else {
                    logger.log('Skip clearing _grecaptcha (disabled)');
                }
            } catch (error) {
                logger.warn('Could not clear _grecaptcha', error);
            }

            return token;
        } catch (error) {
            logger.error('Captcha error', error);
            sendLog('Captcha error: ' + error.message);
            sendStatus('error', { error: error.message });
            throw error;
        }
    }

    try {
        // Tạo countdown badge styles
        createCountdownStyles();

        // Tạo countdown badge element
        createCountdownBadge();

        // Lắng nghe countdown updates từ content script
        window.addEventListener('message', (event) => {
            if (event.source !== window) return;

            if (event.data.type === 'COUNTDOWN_UPDATE') {
                updateCountdownBadge(event.data.remainingSeconds, event.data.totalSeconds);
            }
        });

        // Load Socket.IO
        logger.log('Loading Socket.IO...');
        sendLog('Loading Socket.IO...');
        const io = await loadSocketIO();

        // Connect to server
        logger.log('Connecting to server...');
        sendLog('Connecting to server...');
        const socket = io(CONFIG.socketServer, {
            transports: ['websocket', 'polling'],
            autoConnect: true
        });

        socket.on('connect', () => {
            logger.success('Connected to server! Socket ID', socket.id);
            sendLog('Connected to server! Socket ID: ' + socket.id);
            sendStatus('connected', { socketId: socket.id });

            socket.emit('client:ready', {
                projectId: CONFIG.projectId,
                timestamp: new Date().toISOString()
            });
        });

        socket.on('disconnect', () => {
            logger.log('Disconnected from server');
            sendLog('Disconnected from server');
            sendStatus('disconnected');
        });

        socket.on('connect_error', (error) => {
            logger.error('Connection error', error);
            sendLog('Connection error: ' + error.message);
            sendStatus('connection_error', { error: error.message });
        });

        // Lắng nghe yêu cầu solve captcha từ server
        socket.on('server:request-captcha', async (data) => {
            logger.log('Received captcha request', data);
            sendLog('Received captcha request');

            try {
                const action = data?.action || 'VIDEO_GENERATION';

                const token = await solveCaptcha(action);

                socket.emit('client:captcha-solved', {
                    requestId: data?.requestId,
                    token,
                    timestamp: new Date().toISOString()
                });

                logger.log('Sent token to server');
                sendLog('Sent token to server');
            } catch (error) {
                socket.emit('client:captcha-error', {
                    requestId: data?.requestId,
                    error: error.message,
                    timestamp: new Date().toISOString()
                });
                logger.error('Failed to solve captcha', error);
                sendLog('Failed to solve captcha: ' + error.message);
            }
        });

        // Lắng nghe yêu cầu reload page từ server
        socket.on('server:reload-page', (data) => {
            logger.log('Received reload page request', data);
            sendLog('Server requested page reload');
            sendStatus('reload_requested', { delay: data?.delay || 0 });

            const delay = data?.delay || 0;

            // Clear localStorage trước khi reload
            localStorage.removeItem('_grecaptcha');
            logger.log('Cleared _grecaptcha from localStorage');

            if (delay > 0) {
                logger.log(`Reloading in ${delay}ms...`);
                sendLog(`Reloading in ${delay}ms...`);
                setTimeout(() => {
                    window.location.reload();
                }, delay);
            } else {
                window.location.reload();
            }
        });

        // Wait for reCAPTCHA
        await waitForRecaptcha();

        // Test solve captcha ngay
        logger.log('Testing captcha solve...');
        sendLog('Testing captcha solve...');
        const testToken = await solveCaptcha();
        logger.success('Test successful! Token length', testToken.length);
        sendLog('Test successful! Token length: ' + testToken.length);

        // Expose utilities
        window.captchaClient = {
            socket,
            solveCaptcha,
            config: CONFIG,

            // Manual solve và gửi lên server
            solveAndSend: async () => {
                try {
                    const token = await solveCaptcha();
                    socket.emit('client:captcha-manual', {
                        token,
                        timestamp: new Date().toISOString()
                    });
                    return token;
                } catch (error) {
                    console.error('Error:', error);
                    throw error;
                }
            },

            // Manual reload page
            reloadPage: (delay = 0) => {
                logger.log(`Reloading page${delay ? ` in ${delay}ms` : ''}...`);
                sendLog(`Reloading page${delay ? ` in ${delay}ms` : ''}...`);

                // Clear localStorage trước khi reload
                localStorage.removeItem('_grecaptcha');
                logger.log('Cleared _grecaptcha from localStorage');

                if (delay > 0) {
                    setTimeout(() => window.location.reload(), delay);
                } else {
                    window.location.reload();
                }
            }
        };

        logger.success('Captcha Client Ready!');
        logger.log('Available commands:');
        logger.log('  - captchaClient.solveAndSend() // Solve và gửi manual');
        logger.log('  - captchaClient.reloadPage(delay?) // Reload page với delay (ms)');
        logger.log('  - captchaClient.socket // Access socket trực tiếp');

        sendLog('Captcha Client Ready!');
        sendStatus('ready');

    } catch (error) {
        logger.error('Initialization failed', error);
        sendLog('Initialization failed: ' + error.message);
        sendStatus('init_failed', { error: error.message });
    }
})();
