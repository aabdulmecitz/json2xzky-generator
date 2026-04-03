// web_player/app.js

let charactersDict = {};
let scenarioEntries = [];
let audioCtx = null;
let currentTypingSource = null;

let appConfig = {
    serverName: "json2xzky Server",
    channelName: "general",
    use24HourClock: false
};

// Cache map to resolve reply_to_id
let messageCache = {};

let audioBuffers = {
    ping: null,
    typing: null,
    userSounds: {}
};

const dom = {
    startOverlay: document.getElementById('start-overlay'),
    scenarioInput: document.getElementById('scenario-input'),
    startBtn: document.getElementById('start-btn'),
    instantBtn: document.getElementById('instant-btn'),
    messagesList: document.getElementById('messages-list'),
    typingIndicator: document.getElementById('typing-indicator'),
    typingText: document.getElementById('typing-text'),
    chatContainer: document.getElementById('chat-container'),
    btnHamburger: document.getElementById('btn-hamburger'),
    navDrawer: document.getElementById('nav-drawer'),
    drawerOverlay: document.getElementById('drawer-overlay'),
    pushNotification: document.getElementById('push-notification'),
    pushAvatar: document.getElementById('push-avatar'),
    pushTitle: document.getElementById('push-title'),
    pushText: document.getElementById('push-text'),
    incomingCall: document.getElementById('incoming-call'),
    callAvatar: document.getElementById('call-avatar'),
    callName: document.getElementById('call-name'),
    profileOverlay: document.getElementById('profile-overlay'),
    profileAvatar: document.getElementById('profile-avatar'),
    profileName: document.getElementById('profile-name'),
    connectedBanner: document.getElementById('voice-connected-banner')
};

let isInstant = false;
let simulationStartTime = null;

// Surprise! Load Dynamic Global Config
fetch('../assets/config.json')
    .then(res => res.json())
    .then(data => {
        appConfig = { ...appConfig, ...data };
        console.log("Config loaded:", appConfig);
        
        // Apply Config
        const serverHeader = document.querySelector('.server-header');
        if(serverHeader) serverHeader.innerHTML = `<span>${appConfig.serverName}</span><svg width="18" height="18" viewBox="0 0 24 24"><path fill="currentColor" d="M16.59 8.59L12 13.17 7.41 8.59 6 10l6 6 6-6z"/></svg>`;
        
        const headerTitle = document.querySelector('.header-title');
        if(headerTitle) headerTitle.innerHTML = `<span class="hash-icon-header"><svg width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M5.88657 21C5.57547 21 5.3399 20.7189 5.39427 20.4126L6.00001 17H2.59511C2.28449 17 2.04905 16.7198 2.10259 16.4138L2.27759 15.4138C2.31946 15.1746 2.52722 15 2.77011 15H6.35001L7.41001 9H4.00511C3.69449 9 3.45905 8.71977 3.51259 8.41381L3.68759 7.41381C3.72946 7.17456 3.93722 7 4.18011 7H7.76001L8.39677 3.41262C8.43914 3.17391 8.64664 3 8.88907 3H9.87344C10.1845 3 10.4201 3.28107 10.3657 3.58738L9.76001 7H15.76L16.3968 3.41262C16.4391 3.17391 16.6466 3 16.8891 3H17.8734C18.1845 3 18.4201 3.28107 18.3657 3.58738L17.76 7H21.1649C21.4755 7 21.7109 7.28023 21.6574 7.58619L21.4824 8.58619C21.4405 8.82544 21.2328 9 20.9899 9H17.41L16.35 15H19.7549C20.0655 15 20.3009 15.2802 20.2474 15.5862L20.0724 16.5862C20.0305 16.8254 19.8228 17 19.5799 17H16L15.3632 20.5874C15.3209 20.8261 15.1134 21 14.8709 21H13.8866C13.5755 21 13.3399 20.7189 13.3943 20.4126L14 17H8.00001L7.36323 20.5874C7.32086 20.8261 7.11336 21 6.87093 21H5.88657ZM9.41045 9L8.35045 15H14.3504L15.4104 9H9.41045Z"/></svg></span>${appConfig.channelName}`;
        
        // Update welcome header
        const welcomeH1 = document.querySelector('.welcome-header h1');
        if(welcomeH1) welcomeH1.textContent = `Welcome to #${appConfig.channelName}`;
        const welcomeP = document.querySelector('.welcome-header p');
        if(welcomeP) welcomeP.textContent = `This is the start of the #${appConfig.channelName} channel.`;
        
        const chatInput = document.getElementById('chat-input');
        if(chatInput) chatInput.placeholder = `Message #${appConfig.channelName}`;
    })
    .catch(err => console.log("Using default config settings"));

fetch('../assets/profile_pictures/characters.json')
    .then(res => res.json())
    .then(data => {
        charactersDict = data;
    })
    .catch(err => console.error("Failed to load characters.json", err));

dom.scenarioInput.addEventListener('change', (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (ev) => {
        try {
            scenarioEntries = JSON.parse(ev.target.result);
            dom.startBtn.disabled = false;
            dom.instantBtn.disabled = false;
        } catch (err) {
            alert("Invalid JSON file");
        }
    };
    reader.readAsText(file);
});

// Status bar clock
function updateStatusClock() {
    const el = document.getElementById('status-time');
    if (!el) return;
    const now = new Date();
    if (appConfig.use24HourClock) {
        el.textContent = now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit', hour12: false});
    } else {
        el.textContent = now.toLocaleTimeString([], {hour: 'numeric', minute:'2-digit', hour12: true}).replace(' ', '');
    }
}
updateStatusClock();
setInterval(updateStatusClock, 30000);

// Hide welcome header when simulation starts
function hideWelcome() {
    const w = document.getElementById('welcome-header');
    if (w) w.style.display = 'none';
}

// Fullscreen + Start
dom.startBtn.addEventListener('click', async () => {
    window.AudioContext = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AudioContext();

    await preloadCoreSounds();

    if(document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(err => {});
    }

    dom.startOverlay.classList.add('hidden');
    document.body.classList.add('recording-mode');
    runSimulation();
});

dom.instantBtn.addEventListener('click', async () => {
    isInstant = true;
    dom.startOverlay.classList.add('hidden');
    // Don't add 'recording-mode' here so the browser window stays scrollable!
    document.body.classList.add('instant-mode');
    runSimulation();
});

// Navigation Drawer Logic
function toggleDrawer(open) {
    if (open) {
        dom.navDrawer.classList.remove('drawer-closed');
        dom.drawerOverlay.classList.remove('drawer-closed');
    } else {
        dom.navDrawer.classList.add('drawer-closed');
        dom.drawerOverlay.classList.add('drawer-closed');
    }
}

if (dom.btnHamburger) dom.btnHamburger.addEventListener('click', () => toggleDrawer(true));
if (dom.drawerOverlay) dom.drawerOverlay.addEventListener('click', () => toggleDrawer(false));

let touchStartX = 0, touchEndX = 0;
document.addEventListener('touchstart', e => touchStartX = e.changedTouches[0].screenX);
document.addEventListener('touchend', e => {
    touchEndX = e.changedTouches[0].screenX;
    if (touchEndX < touchStartX - 50) toggleDrawer(false);
});

async function loadSoundBuffer(url) {
    try {
        const response = await fetch(url);
        const arrayBuffer = await response.arrayBuffer();
        return await audioCtx.decodeAudioData(arrayBuffer);
    } catch (err) {
        console.warn(`Could not load sound: ${url}`, err);
        return null;
    }
}

async function preloadCoreSounds() {
    audioBuffers.ping = await loadSoundBuffer('../assets/sounds/mp3/discord_ping.mp3') || await loadSoundBuffer('../assets/sounds/mp3/message.mp3');
    audioBuffers.typing = await loadSoundBuffer('../assets/sounds/mp3/typing.mp3');
}

function playSound(buffer, soundIdentifier, loop = false) {
    if (!buffer || !audioCtx) return null;
    
    if (simulationStartTime !== null && soundIdentifier) {
        console.log(JSON.stringify({
            type: "AUDIO_EVENT",
            file: `assets/sounds/mp3/${soundIdentifier}.mp3`,
            timestamp: (Date.now() - simulationStartTime) / 1000
        }));
    }

    const source = audioCtx.createBufferSource();
    source.buffer = buffer;
    source.loop = loop;
    source.connect(audioCtx.destination);
    source.start(0);
    return source;
}

async function playUserSound(soundName) {
    if (!audioBuffers.userSounds[soundName]) {
        audioBuffers.userSounds[soundName] = await loadSoundBuffer(`../assets/sounds/mp3/${soundName}.mp3`);
    }
    playSound(audioBuffers.userSounds[soundName], soundName, false);
}

function formatMessage(text) {
    if (!text) return "";
    let html = text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
    html = html.replace(/\*\*(.*?)\*\*/g, '<span class="bold">$1</span>');
    html = html.replace(/__(.*?)__/g, '<span class="italic">$1</span>');
    html = html.replace(/(@\w+)/g, '<span class="mention">$1</span>');
    html = html.replace(/\|\|(.*?)\|\|/g, '<span class="spoiler" onclick="this.classList.toggle(\'revealed\')">$1</span>');
    return html;
}

function applyTwemoji(element) {
    if (typeof twemoji !== 'undefined' && element) {
        twemoji.parse(element, { base: 'https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/', folder: 'svg', ext: '.svg' });
    }
}

const DISCORD_DEFAULT_COLORS = ['#5865f2', '#57f287', '#b9bbbe', '#ed4245', '#fee75c'];

// Returns a data-URI or real URL for a user/caller avatar.
// Falls back to a coloured initial-letter SVG so it never crashes.
function getAvatarUrl(userId) {
    if (!userId) return '';
    if (charactersDict[userId] && charactersDict[userId].profile_pic) {
        return `../assets/profile_pictures/${charactersDict[userId].profile_pic}`;
    }
    // Generate a tiny SVG data-URI as fallback
    const hash = userId.split('').reduce((a, b) => ((a << 5) - a) + b.charCodeAt(0), 0);
    const color = DISCORD_DEFAULT_COLORS[Math.abs(hash) % DISCORD_DEFAULT_COLORS.length];
    const initial = userId[0].toUpperCase();
    const svg = `<svg xmlns='http://www.w3.org/2000/svg' width='40' height='40'><rect width='40' height='40' rx='20' fill='${color}'/><text x='50%' y='50%' dominant-baseline='central' text-anchor='middle' font-size='20' font-family='sans-serif' fill='white'>${initial}</text></svg>`;
    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

function getAvatarHtml(userId, addClass="", baseClass="message-avatar") {
    const avatarSrc = getAvatarUrl(userId);
    return `<img class="${baseClass} ${addClass}" src="${avatarSrc}" onerror="this.onerror=null; this.src='../assets/profile_pictures/default.png';">`;
}

function getColor(userId) {
    if (charactersDict[userId] && charactersDict[userId].role_color) {
        return charactersDict[userId].role_color;
    }
    return '#fff';
}

function getCurrentTimeStr() {
    const d = new Date();
    let hours = d.getHours();
    let mins = d.getMinutes();
    
    if (!appConfig.use24HourClock) {
        const ampm = hours >= 12 ? 'PM' : 'AM';
        hours = hours % 12;
        hours = hours ? hours : 12;
        mins = mins < 10 ? '0'+mins : mins;
        return `Today at ${hours}:${mins} ${ampm}`;
    } else {
        mins = mins < 10 ? '0'+mins : mins;
        return `Today at ${hours}:${mins}`;
    }
}

let lastMessageUser = null;
let lastMessageTimeStr = null;

function appendMessage(entry) {
    const isGrouped = (entry.user_id === lastMessageUser && lastMessageTimeStr === getCurrentTimeStr() && (entry.action === "message" || entry.action === "send_message"));
    lastMessageUser = entry.user_id;
    lastMessageTimeStr = getCurrentTimeStr();

    const div = document.createElement('div');
    div.id = `msg_${entry.id}`;
    div.className = 'message ' + (entry.has_ping ? 'has-ping ' : '') + (isGrouped ? 'compact' : '');
    
    if(entry.id) messageCache[entry.id] = entry;

    if (entry.reply_to_id && messageCache[entry.reply_to_id] || entry.action === 'reply' && messageCache[entry.reply_to_id]) {
        const replyTarget = messageCache[entry.reply_to_id];
        div.classList.add('Replies'); 
        
        const replyHeader = document.createElement('div');
        replyHeader.className = 'reply-header';
        
        replyHeader.innerHTML = `
            ${getAvatarHtml(replyTarget.user_id, "reply-avatar", "reply-avatar-base")}
            <span style="color: ${getColor(replyTarget.user_id)}; font-weight: 500;">${replyTarget.user_id.replace('_moustache', '')}</span>
            <span class="reply-preview">${formatMessage(replyTarget.message_content || replyTarget.text)}</span>
        `;
        div.appendChild(replyHeader);
        div.classList.remove('compact'); 
        lastMessageUser = null; 
    }

    const wrapper = document.createElement('div');
    wrapper.className = 'message-content-wrapper';
    
    let html = `
        ${getAvatarHtml(entry.user_id)}
        <div class="message-body">
    `;
    
    if (!isGrouped || entry.reply_to_id || entry.action === 'reply') {
        const isReplyMsg = entry.reply_to_id || entry.action === 'reply';
        const repliedSpan = isReplyMsg ? `<span class="message-replied-text">replied</span>` : ``;
        html += `
            <div class="message-header">
                <span class="message-username" style="color: ${getColor(entry.user_id)}">${entry.user_id.replace('_moustache', '')}</span>
                ${repliedSpan}
                <span class="message-timestamp">${getCurrentTimeStr()}</span>
            </div>
        `;
    }

    html += `<div class="message-content" id="content_${entry.id}">${formatMessage(entry.message_content || entry.text)}</div>`;
    
    if (entry.action === 'send_attachment') {
        html += `<img src="../${entry.image_url}" class="attachment-image" onerror="this.style.display='none'">`;
    }
    
    if (entry.action === 'send_voice_note') {
        html += `
            <div class="voice-note">
                <div class="voice-play-btn"><svg viewBox="0 0 24 24" fill="white"><path d="M8 5v14l11-7z"/></svg></div>
                <div class="voice-waveform">
                    <div class="voice-waveform-bar" style="height: 12px;"></div>
                    <div class="voice-waveform-bar" style="height: 20px;"></div>
                    <div class="voice-waveform-bar" style="height: 8px;"></div>
                    <div class="voice-waveform-bar" style="height: 24px;"></div>
                    <div class="voice-waveform-bar" style="height: 16px;"></div>
                </div>
                <div class="voice-duration">${entry.duration_text || "0:04"}</div>
            </div>
        `;
    }
    
    html += `<div class="reactions-container" id="reactions_${entry.id}"></div>`;
    html += `</div>`;
    
    wrapper.innerHTML = html;
    div.appendChild(wrapper);
    dom.messagesList.appendChild(div);
    applyTwemoji(div);
    
    if (!isInstant) {
        playSound(audioBuffers.ping, 'message');
        if (entry.sound) playUserSound(entry.sound);
        if (entry.action === 'send_voice_note' && entry.audio_file) {
            playUserSound(entry.audio_file.replace('.mp3', ''));
        }
    }
    scrollToBottom();
}

function appendSystemMessage(entry) {
    lastMessageUser = null; 
    const isJoin = entry.type === 'join' || entry.action === 'join';
    const svgPath = isJoin 
        ? "M18 9V14C18 15.657 16.657 17 15 17H14V19.25C14 19.94 13.164 20.285 12.676 19.797L9.878 17H5C3.343 17 2 15.657 2 14V9C2 7.343 3.343 6 5 6H15C16.657 6 18 7.343 18 9ZM14 3H16C16 2.45 15.55 2 15 2H5C3.343 2 2 3.343 2 5V14C2 14.28 2.22 14.5 2.5 14.5C2.78 14.5 3 14.28 3 14V5C3 3.895 3.895 3 5 3H14ZM21.732 10.268L18.895 7.432C18.608 7.145 18.145 7.145 17.858 7.432C17.571 7.719 17.571 8.182 17.858 8.469L19.387 10H15.5C15.224 10 15 10.224 15 10.5C15 10.776 15.224 11 15.5 11H19.387L17.858 12.531C17.571 12.818 17.571 13.281 17.858 13.568C18.145 13.855 18.608 13.855 18.895 13.568L21.732 10.732C21.859 10.605 21.859 10.395 21.732 10.268Z"
        : "M15.5 10H11.613L13.142 8.469C13.429 8.182 13.429 7.719 13.142 7.432C12.855 7.145 12.392 7.145 12.105 7.432L9.268 10.268C9.141 10.395 9.141 10.605 9.268 10.732L12.105 13.568C12.392 13.855 12.855 13.855 13.142 13.568C13.429 13.281 13.429 12.818 13.142 12.531L11.613 11H15.5C15.776 11 16 10.776 16 10.5C16 10.224 15.776 10 15.5 10ZM5 2H15C15.55 2 16 2.45 16 3H14C14 2.45 13.55 2 13 2H5C3.895 2 3 2.895 3 4V13C3 14.105 3.895 15 5 15H13C13.55 15 14 15.45 14 16H16C16 16.55 15.55 17 15 17H5C3.343 17 2 15.657 2 14V5C2 3.343 3.343 2 5 2ZM18 9V14C18 15.657 16.657 17 15 17H14V19.25C14 19.94 13.164 20.285 12.676 19.797L9.878 17H5C3.343 17 2 15.657 2 14V9C2 7.343 3.343 6 5 6H15C16.657 6 18 7.343 18 9Z";
    
    const verb = entry.action === 'system_message' ? entry.message_content : (isJoin ? "joined the party." : "left the server.");
    const cls = isJoin ? "join" : "leave";
    
    const div = document.createElement('div');
    div.className = 'system-message';
    div.innerHTML = `
        <svg class="${cls === 'join' ? 'system-join' : 'system-leave'}" width="20" height="20" viewBox="0 0 24 24"><path fill="currentColor" d="${svgPath}"></path></svg>
        <span><span class="system-user">${entry.user_id || entry.user}</span> ${verb}</span>
    `;

    dom.messagesList.appendChild(div);
    applyTwemoji(div);
    if (!isInstant) playSound(audioBuffers.ping, 'message');
    scrollToBottom();
}

function scrollToBottom() {
    dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight;
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

// Central Event Handler Loop
async function runSimulation() {
    simulationStartTime = Date.now();
    for (let i = 0; i < scenarioEntries.length; i++) {
        const entry = scenarioEntries[i];
        const action = entry.action;

        // Force mapping user -> user_id
        if (!entry.user_id && entry.user) entry.user_id = entry.user;

        // 1. Navigation
        if (action === 'open_sidebar') {
            toggleDrawer(true);
        } else if (action === 'close_sidebar') {
            toggleDrawer(false);
        } else if (action === 'switch_server') {
            toggleDrawer(false);
        } else if (action === 'switch_channel') {
            dom.messagesList.innerHTML = '';
            toggleDrawer(false);
        
        // 2. Messaging
        } else if (action === 'type_message' || action === 'typing') {
            if (!isInstant) {
                const durationSec = entry.duration || Math.max(0.2, (entry.text || entry.message_content || "").length * 0.05);
                currentTypingSource = playSound(audioBuffers.typing, 'typing', true);
                dom.typingText.textContent = `${entry.user_id} is typing...`;
                dom.typingIndicator.classList.remove('hidden');
                scrollToBottom();
                await sleep(durationSec * 1000);
                dom.typingIndicator.classList.add('hidden');
                if (currentTypingSource) {
                    currentTypingSource.stop();
                    currentTypingSource = null;
                }
            }
        } else if (['message', 'send_message', 'reply', 'send_attachment', 'send_voice_note'].includes(action)) {
            appendMessage(entry);

            // Beluga Camera: emit zoom cue for Playwright
            if (entry.zoom || entry.focus) {
                const msgEl = document.getElementById(`msg_${entry.id}`);
                if (msgEl) {
                    const rect = msgEl.getBoundingClientRect();
                    console.log(JSON.stringify({
                        type: "ZOOM_CUE",
                        msg_id: entry.id,
                        timestamp: (Date.now() - simulationStartTime) / 1000,
                        bbox: {
                            x: Math.round(rect.x),
                            y: Math.round(rect.y),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        }
                    }));
                }
            }

            // Sequential Reveal Hook
            if (entry.crop_mode === 'sequential_reveal') {
                console.log(JSON.stringify({
                    type: "REVEAL_TIMESTAMP",
                    msg_id: entry.id,
                    group_id: entry.reveal_group_id,
                    timestamp: (Date.now() - simulationStartTime) / 1000
                }));
            }
        
        // 3. Message Mutations
        } else if (action === 'add_reaction') {
            const reactionContainer = document.getElementById(`reactions_${entry.target_msg_id}`);
            if (reactionContainer) {
                const pill = document.createElement('div');
                pill.className = 'reaction-pill';
                pill.innerHTML = `<span>${entry.emoji}</span><span>${entry.count || 1}</span>`;
                reactionContainer.appendChild(pill);
                applyTwemoji(pill);
                if (!isInstant) playUserSound('reaction');
            }
        } else if (action === 'edit_message') {
            const contentNode = document.getElementById(`content_${entry.target_msg_id}`);
            if (contentNode) {
                contentNode.innerHTML = formatMessage(entry.new_text) + '<span class="edited-stamp">(edited)</span>';
                applyTwemoji(contentNode);
            }
        } else if (action === 'delete_message') {
            const msgNode = document.getElementById(`msg_${entry.target_msg_id}`);
            if (msgNode) {
                msgNode.style.transition = 'opacity 0.3s ease';
                msgNode.style.opacity = '0';
                setTimeout(() => msgNode.remove(), 300);
            }
        } else if (action === 'reveal_spoiler') {
            const msgNode = document.getElementById(`msg_${entry.target_msg_id}`);
            if (msgNode) {
                const spoilers = msgNode.querySelectorAll('.spoiler');
                spoilers.forEach(s => s.classList.add('revealed'));
            }

        // 4. Overlays & System
        } else if (['join', 'leave', 'system_message'].includes(action)) {
            appendSystemMessage(entry);
        } else if (action === 'open_profile') {
            if (!isInstant) {
                const profileUrl = getAvatarUrl(entry.target_user || entry.user_id);
                if (dom.profileAvatar) dom.profileAvatar.src = profileUrl;
                if (dom.profileName) dom.profileName.textContent = entry.target_user || entry.user_id;
                if (dom.profileOverlay) dom.profileOverlay.classList.add('open');
                playUserSound('pop');
                const pSec = entry.pause_after || entry.duration || 3;
                setTimeout(() => { if (dom.profileOverlay) dom.profileOverlay.classList.remove('open'); }, pSec * 1000);
            }
        } else if (action === 'push_notification') {
            if (!isInstant) {
                if (dom.pushTitle) dom.pushTitle.textContent = entry.title || '';
                if (dom.pushText) dom.pushText.textContent = entry.body || '';
                if (dom.pushNotification) dom.pushNotification.classList.add('show');
                playUserSound('discord_ping');
                setTimeout(() => { if (dom.pushNotification) dom.pushNotification.classList.remove('show'); }, 4000);
            }
        } else if (action === 'incoming_call') {
            if (!isInstant) {
                const callerUrl = getAvatarUrl(entry.caller || entry.user_id);
                if (dom.callAvatar) dom.callAvatar.src = callerUrl;
                if (dom.callName) dom.callName.textContent = entry.caller || entry.user_id;
                dom.incomingCall.classList.add('active');
                playUserSound('discord_ringtone');
                const cSec = entry.pause_after || entry.duration || 5;
                setTimeout(() => dom.incomingCall.classList.remove('active'), cSec * 1000);
            }
        } else if (action === 'join_call') {
            if (!isInstant) {
                dom.incomingCall.classList.remove('active');
                dom.connectedBanner.classList.add('active');
                playUserSound('join_call');
            }
        } else if (action === 'toggle_mute') {
            if(!isInstant) playUserSound(entry.state ? 'mute_ping' : 'unmute');
        }
        
        if (!isInstant) {
            const pauseSec = entry.pause_after || entry.delay || 0;
            if(pauseSec > 0) await sleep(pauseSec * 1000);
        }
    }
    
    if (!isInstant) console.log("SIMULATION_COMPLETE");
    window.__simulationDone = true;
}
