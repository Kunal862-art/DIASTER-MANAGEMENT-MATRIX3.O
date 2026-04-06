// SAFESTEP Main Interactions & Chatbot Logic
document.addEventListener('DOMContentLoaded', () => {
    // --- Typewriter Animation ---
    const typewriter = document.getElementById('typewriter-h1');
    if (typewriter) {
        const text = typewriter.textContent;
        typewriter.textContent = '';
        typewriter.style.borderRight = '2px solid var(--primary-color)';
        let i = 0;
        function type() {
            if (i < text.length) {
                typewriter.innerText += text.charAt(i);
                i++;
                setTimeout(type, 50); // Speed of typing
            } else {
                typewriter.style.borderRight = 'none'; // Remove cursor when done
            }
        }
        setTimeout(type, 500); // Initial delay
    }

    // --- UI Interactions ---
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            alert.style.transition = 'opacity 1s ease-out';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 1000);
        }, 3000);
    });

    // --- Chatbot Logic ---
    const chatWindow = document.getElementById('chat-window');
    const openChatBtn = document.getElementById('open-chat');
    const closeChatBtn = document.getElementById('close-chat');
    const clearChatBtn = document.getElementById('clear-chat');
    const chatMessages = document.getElementById('chat-messages');
    const chatInput = document.getElementById('chat-input');
    const sendChatBtn = document.getElementById('send-chat');

    // Toggle Chat Window
    if (openChatBtn) {
        openChatBtn.addEventListener('click', () => {
            chatWindow.style.display = 'flex';
            openChatBtn.style.display = 'none';
            loadChatHistory();
        });
    }

    if (closeChatBtn) {
        closeChatBtn.addEventListener('click', () => {
            chatWindow.style.display = 'none';
            openChatBtn.style.display = 'flex';
        });
    }

    // Load Chat History
    async function loadChatHistory() {
        try {
            const response = await fetch('/chat/history');
            const data = await response.json();
            if (data.history) {
                chatMessages.innerHTML = '';
                data.history.forEach(msg => {
                    appendMessage(msg.role === 'user' ? 'user' : 'bot', msg.content);
                });
                if (data.history.length === 0) {
                    appendMessage('bot', "👋 Hello! I'm your SAFESTEP assistant. How can I help you today?");
                }
                scrollToBottom();
            }
        } catch (error) {
            console.error('Error loading history:', error);
        }
    }

    // Send Message
    async function sendMessage() {
        const message = chatInput.value.trim();
        if (!message) return;

        appendMessage('user', message);
        chatInput.value = '';
        scrollToBottom();

        // Show typing indicator
        const typingId = 'typing-' + Date.now();
        const typingDiv = document.createElement('div');
        typingDiv.className = 'bot-msg typing';
        typingDiv.id = typingId;
        typingDiv.innerText = 'Thinking...';
        chatMessages.appendChild(typingDiv);
        scrollToBottom();

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: message })
            });
            const data = await response.json();
            
            document.getElementById(typingId).remove();

            if (data.response) {
                appendMessage('bot', data.response);
            } else if (data.error) {
                appendMessage('bot', '⚠️ Error: ' + data.error);
            }
            scrollToBottom();
        } catch (error) {
            document.getElementById(typingId).remove();
            appendMessage('bot', '⚠️ Failed to connect to server.');
            console.error('Chat error:', error);
        }
    }

    // Clear Chat
    if (clearChatBtn) {
        clearChatBtn.addEventListener('click', async () => {
            if (confirm('Are you sure you want to delete your entire chat history?')) {
                try {
                    const response = await fetch('/chat/clear', { method: 'POST' });
                    const data = await response.json();
                    if (data.success) {
                        chatMessages.innerHTML = '';
                        appendMessage('bot', 'History cleared. How can I help you now?');
                    }
                } catch (error) {
                    console.error('Clear error:', error);
                }
            }
        });
    }

    function appendMessage(role, content) {
        const msgDiv = document.createElement('div');
        msgDiv.className = role === 'user' ? 'user-msg' : 'bot-msg';
        msgDiv.innerText = content;
        chatMessages.appendChild(msgDiv);
    }

    function scrollToBottom() {
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    if (sendChatBtn) sendChatBtn.addEventListener('click', sendMessage);
    if (chatInput) {
        chatInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') sendMessage();
        });
    }
});
