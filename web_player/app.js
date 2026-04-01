// web_player/app.js

let charactersDict = {};
let scenarioEntries = [];
let audioCtx = null;
let currentTypingSource = null;

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
    messagesList: document.getElementById('messages-list'),
    typingIndicator: document.getElementById('typing-indicator'),
    typingText: document.getElementById('typing-text'),
    chatContainer: document.getElementById('chat-container')
};

fetch('../assets/profile_pictures/characters.json')
    .then(res => res.json())
    .then(data => {
        charactersDict = data;
        console.log("Characters loaded:", Object.keys(charactersDict));
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
        } catch (err) {
            alert("Invalid JSON file");
        }
    };
    reader.readAsText(file);
});

// Fullscreen + Start
dom.startBtn.addEventListener('click', async () => {
    window.AudioContext = window.AudioContext || window.webkitAudioContext;
    audioCtx = new AudioContext();

    await preloadCoreSounds();

    // Request fullscreen
    if(document.documentElement.requestFullscreen) {
        document.documentElement.requestFullscreen().catch(err => {
            console.warn(`Error attempting to enable fullscreen: ${err.message}`);
        });
    }

    // Hide overlay
    dom.startOverlay.classList.add('hidden');
    
    // Add recording mode styling (hides external scrollbars)
    document.body.classList.add('recording-mode');

    runSimulation();
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
    let pingUrl = '../assets/sounds/mp3/discord_ping.mp3';
    let typingUrl = '../assets/sounds/mp3/typing.mp3';

    audioBuffers.ping = await loadSoundBuffer(pingUrl) || await loadSoundBuffer('../assets/sounds/mp3/message.mp3');
    audioBuffers.typing = await loadSoundBuffer(typingUrl);
}

function playSound(buffer, loop = false) {
    if (!buffer || !audioCtx) return null;
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
    playSound(audioBuffers.userSounds[soundName], false);
}

function formatMessage(text) {
    if (!text) return "";
    let html = text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
    html = html.replace(/\*\*(.*?)\*\*/g, '<span class="bold">$1</span>');
    html = html.replace(/__(.*?)__/g, '<span class="italic">$1</span>');
    html = html.replace(/(@\w+)/g, '<span class="mention">$1</span>');
    return html;
}

function getAvatarUrl(userId) {
    if (charactersDict[userId] && charactersDict[userId].profile_pic) {
        return `../assets/profile_pictures/${charactersDict[userId].profile_pic}`;
    }
    return '';
}

function getColor(userId) {
    return (charactersDict[userId] && charactersDict[userId].role_color) ? charactersDict[userId].role_color : '#fff';
}

function getCurrentTimeStr() {
    const d = new Date();
    let hours = d.getHours();
    let mins = d.getMinutes();
    const ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12;
    hours = hours ? hours : 12;
    mins = mins < 10 ? '0'+mins : mins;
    return `Today at ${hours}:${mins} ${ampm}`;
}

let lastMessageUser = null;
let lastMessageTimeStr = null;

function appendMessage(entry) {
    const isGrouped = (entry.user_id === lastMessageUser && lastMessageTimeStr === getCurrentTimeStr() && entry.action === "message");
    lastMessageUser = entry.user_id;
    lastMessageTimeStr = getCurrentTimeStr();

    const div = document.createElement('div');
    div.className = 'message ' + (entry.has_ping ? 'pinged ' : '') + (isGrouped ? 'grouped' : '');
    
    // Store in cache for future replies
    messageCache[entry.id] = entry;

    if (entry.reply_to_id && messageCache[entry.reply_to_id]) {
        const replyTarget = messageCache[entry.reply_to_id];
        div.classList.add('Replies'); 
        
        const replyHeader = document.createElement('div');
        replyHeader.className = 'reply-header';
        
        const replyAvatarUrl = getAvatarUrl(replyTarget.user_id);
        const replyColor = getColor(replyTarget.user_id);
        
        replyHeader.innerHTML = `
            <img class="reply-avatar" src="${replyAvatarUrl}" onerror="this.style.display='none'">
            <span class="reply-author" style="color: ${replyColor}">${replyTarget.user_id}</span>
            <span class="reply-snippet">${formatMessage(replyTarget.message_content)}</span>
        `;
        div.appendChild(replyHeader);
        div.classList.remove('grouped'); 
        lastMessageUser = null; 
    }

    const wrapper = document.createElement('div');
    wrapper.className = 'message-content-wrapper';
    
    const avatarUrl = getAvatarUrl(entry.user_id);
    const color = getColor(entry.user_id);
    const timeStr = getCurrentTimeStr();
    
    let html = `
        <div class="message-avatar">
            <img src="${avatarUrl}" onerror="this.style.display='none'">
        </div>
        <div class="message-body">
    `;
    
    if (!isGrouped || entry.reply_to_id) {
        html += `
            <div class="message-header">
                <span class="username" style="color: ${color}">${entry.user_id}</span>
                <span class="timestamp">${timeStr}</span>
            </div>
        `;
    }

    html += `
            <div class="message-content">${formatMessage(entry.message_content)}</div>
        </div>
    `;
    
    wrapper.innerHTML = html;
    div.appendChild(wrapper);

    dom.messagesList.appendChild(div);
    
    // Sound playback exactly sync'd with DOM update
    playSound(audioBuffers.ping);
    if (entry.sound) playUserSound(entry.sound);

    scrollToBottom();
}

function appendSystemMessage(entry) {
    lastMessageUser = null; 
    
    const isJoin = entry.action === 'join';
    const svgPath = isJoin 
        ? "M18 9V14C18 15.657 16.657 17 15 17H14V19.25C14 19.94 13.164 20.285 12.676 19.797L9.878 17H5C3.343 17 2 15.657 2 14V9C2 7.343 3.343 6 5 6H15C16.657 6 18 7.343 18 9ZM14 3H16C16 2.45 15.55 2 15 2H5C3.343 2 2 3.343 2 5V14C2 14.28 2.22 14.5 2.5 14.5C2.78 14.5 3 14.28 3 14V5C3 3.895 3.895 3 5 3H14ZM21.732 10.268L18.895 7.432C18.608 7.145 18.145 7.145 17.858 7.432C17.571 7.719 17.571 8.182 17.858 8.469L19.387 10H15.5C15.224 10 15 10.224 15 10.5C15 10.776 15.224 11 15.5 11H19.387L17.858 12.531C17.571 12.818 17.571 13.281 17.858 13.568C18.145 13.855 18.608 13.855 18.895 13.568L21.732 10.732C21.859 10.605 21.859 10.395 21.732 10.268Z"
        : "M15.5 10H11.613L13.142 8.469C13.429 8.182 13.429 7.719 13.142 7.432C12.855 7.145 12.392 7.145 12.105 7.432L9.268 10.268C9.141 10.395 9.141 10.605 9.268 10.732L12.105 13.568C12.392 13.855 12.855 13.855 13.142 13.568C13.429 13.281 13.429 12.818 13.142 12.531L11.613 11H15.5C15.776 11 16 10.776 16 10.5C16 10.224 15.776 10 15.5 10ZM5 2H15C15.55 2 16 2.45 16 3H14C14 2.45 13.55 2 13 2H5C3.895 2 3 2.895 3 4V13C3 14.105 3.895 15 5 15H13C13.55 15 14 15.45 14 16H16C16 16.55 15.55 17 15 17H5C3.343 17 2 15.657 2 14V5C2 3.343 3.343 2 5 2ZM18 9V14C18 15.657 16.657 17 15 17H14V19.25C14 19.94 13.164 20.285 12.676 19.797L9.878 17H5C3.343 17 2 15.657 2 14V9C2 7.343 3.343 6 5 6H15C16.657 6 18 7.343 18 9Z";

    const verb = isJoin ? "joined the party." : "left the server.";
    const cls = isJoin ? "join" : "leave";
    
    const div = document.createElement('div');
    div.className = 'system-message';
    div.innerHTML = `
        <div class="system-icon ${cls}">
            <svg width="24" height="24" viewBox="0 0 24 24"><path d="${svgPath}"></path></svg>
        </div>
        <div class="system-text">
            <strong>${entry.user_id}</strong> ${verb}
        </div>
    `;

    dom.messagesList.appendChild(div);
    
    if (entry.sound) playUserSound(entry.sound);
    else playSound(audioBuffers.ping);
    
    scrollToBottom();
}

function scrollToBottom() {
    dom.chatContainer.scrollTop = dom.chatContainer.scrollHeight;
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function runSimulation() {
    for (let i = 0; i < scenarioEntries.length; i++) {
        const entry = scenarioEntries[i];

        if (entry.action === 'join' || entry.action === 'leave') {
            appendSystemMessage(entry);
        } else if (entry.action === 'message') {
            appendMessage(entry);
        } else if (entry.action === 'typing') {
            // Calculate strict typing duration
            const msgLength = (entry.message_content || "").length;
            const durationSec = Math.max(0.2, msgLength * 0.05);
            
            currentTypingSource = playSound(audioBuffers.typing, true);
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
        
        // Final Pause behavior happens AFTER the action completes
        const pauseSec = entry.pause_after || 0;
        if(pauseSec > 0) {
            await sleep(pauseSec * 1000);
        }
    }
}
