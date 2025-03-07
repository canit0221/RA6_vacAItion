document.addEventListener('DOMContentLoaded', function() {
    const messageInput = document.getElementById('messageInput');
    const sendButton = document.getElementById('sendButton');
    const chatMessages = document.getElementById('chatMessages');
    const sessions = document.querySelector('.sessions');
    let currentChatSocket = null;
    let currentSessionId = null;

    // CSRF 토큰 가져오기
    let csrfToken = '';
    fetch('/chat/api/get-csrf-token/')
        .then(response => response.json())
        .then(data => {
            csrfToken = data.csrfToken;
        });

    // 새 채팅 버튼 이벤트
    document.querySelector('.new-chat-btn').addEventListener('click', async function() {
        try {
            const response = await fetch('/chat/api/sessions/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    title: `Chat Session ${new Date().toLocaleString()}`
                })
            });

            if (response.ok) {
                const session = await response.json();
                // 새 세션 요소 추가
                const sessionElement = createSessionElement(session);
                sessions.insertBefore(sessionElement, sessions.firstChild);
                // 새 세션으로 전환
                switchChatSession(session.id);
            }
        } catch (error) {
            console.error('Error creating new session:', error);
        }
    });

    // 세션 클릭 이벤트 (이벤트 위임 사용)
    sessions.addEventListener('click', function(e) {
        const sessionItem = e.target.closest('.session-item');
        if (sessionItem && !e.target.classList.contains('delete-btn')) {
            const sessionId = sessionItem.dataset.sessionId;
            switchChatSession(sessionId);
        }
    });

    // 세션 삭제 이벤트
    sessions.addEventListener('click', async function(e) {
        if (e.target.classList.contains('delete-btn')) {
            e.stopPropagation();
            const sessionId = e.target.dataset.sessionId;
            if (confirm('이 채팅 세션을 삭제하시겠습니까?')) {
                try {
                    const response = await fetch(`/chat/api/sessions/${sessionId}/`, {
                        method: 'DELETE',
                        headers: {
                            'X-CSRFToken': csrfToken
                        }
                    });
                    if (response.ok) {
                        const sessionElement = e.target.closest('.session-item');
                        sessionElement.remove();
                        if (currentSessionId === sessionId) {
                            const firstSession = document.querySelector('.session-item');
                            if (firstSession) {
                                switchChatSession(firstSession.dataset.sessionId);
                            }
                        }
                    }
                } catch (error) {
                    console.error('Error deleting session:', error);
                }
            }
        }
    });

    // 메시지 전송 이벤트
    async function sendMessage() {
        const message = messageInput.value.trim();
        if (!message || !currentChatSocket) return;

        messageInput.value = '';
        
        // 사용자 메시지 표시
        addMessage(message, true);
        
        // 로딩 애니메이션 표시
        const loadingMessage = addLoadingMessage();
        
        // WebSocket으로 메시지 전송
        currentChatSocket.send(JSON.stringify({
            'message': message
        }));
    }

    // 세션 전환 함수
    function switchChatSession(sessionId) {
        if (currentChatSocket) {
            currentChatSocket.close();
        }
        currentSessionId = sessionId;
        currentChatSocket = connectWebSocket(sessionId);
        loadPreviousMessages(sessionId);
        updateActiveSession(sessionId);
    }

    // WebSocket 연결 함수
    function connectWebSocket(sessionId) {
        const socket = new WebSocket(
            `ws://${window.location.host}/ws/chat/${sessionId}/`
        );

        socket.onmessage = function(e) {
            const data = JSON.parse(e.data);
            if (data.bot_response) {
                // 마지막 로딩 메시지 제거
                const loadingMessages = document.querySelectorAll('.message-wrapper.bot');
                const lastMessage = loadingMessages[loadingMessages.length - 1];
                if (lastMessage && lastMessage.querySelector('.loading-dots')) {
                    lastMessage.remove();
                }
                // 실제 응답 추가
                addMessage(data.bot_response, false);
            }
        };

        socket.onclose = function(e) {
            console.log('Chat socket closed');
        };

        return socket;
    }

    // 이전 메시지 로드 함수
    async function loadPreviousMessages(sessionId) {
        try {
            const response = await fetch(`/chat/api/messages/${sessionId}/`);
            if (!response.ok) {
                throw new Error('Failed to load messages');
            }
            const messages = await response.json();
            
            // 채팅 영역 초기화
            chatMessages.innerHTML = '';
            
            if (messages.length === 0) {
                // 새 세션인 경우에만 초기 메시지 표시
                addMessage('안녕하세요. 당신의 휴일을 책임지는 Hue입니다.\n무엇을 도와드릴까요?', false);
            } else {
                // 기존 메시지들 표시
                messages.forEach(msg => {
                    addMessage(msg.content, !msg.is_bot);
                });
            }

            // 스크롤을 가장 아래로
            chatMessages.scrollTop = chatMessages.scrollHeight;
        } catch (error) {
            console.error('Error loading messages:', error);
        }
    }

    // 메시지 추가 함수
    function addMessage(message, isUser, isLoading = false) {
        const messageWrapper = document.createElement('div');
        messageWrapper.className = `message-wrapper ${isUser ? 'user' : 'bot'}`;
        
        if (!isUser) {
            const botLabel = document.createElement('div');
            botLabel.className = 'bot-label';
            botLabel.textContent = 'Hue';
            messageWrapper.appendChild(botLabel);
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isLoading ? 'loading-dots' : ''}`;
        messageDiv.innerHTML = message.replace(/\n/g, '<br>');
        messageWrapper.appendChild(messageDiv);
        
        chatMessages.appendChild(messageWrapper);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        return messageWrapper;
    }

    // 세션 요소 생성 함수
    function createSessionElement(session) {
        const div = document.createElement('div');
        div.className = 'session-item';
        div.dataset.sessionId = session.id;
        div.innerHTML = `
            <div class="session-info">${session.title}</div>
            <button class="delete-btn" data-session-id="${session.id}">삭제</button>
        `;
        return div;
    }

    // 활성 세션 표시 함수
    function updateActiveSession(sessionId) {
        document.querySelectorAll('.session-item').forEach(el => {
            el.classList.remove('active');
            if (el.dataset.sessionId === sessionId) {
                el.classList.add('active');
            }
        });
    }

    // 로딩 메시지 추가 함수
    function addLoadingMessage() {
        const messageWrapper = document.createElement('div');
        messageWrapper.className = 'message-wrapper bot';
        
        const botLabel = document.createElement('div');
        botLabel.className = 'bot-label';
        botLabel.textContent = 'Hue';
        messageWrapper.appendChild(botLabel);

        const messageDiv = document.createElement('div');
        messageDiv.className = 'message loading-dots';
        messageDiv.innerHTML = '<span></span><span></span><span></span>';
        messageWrapper.appendChild(messageDiv);
        
        chatMessages.appendChild(messageWrapper);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        
        return messageWrapper;
    }

    // 이벤트 리스너 등록
    sendButton.addEventListener('click', sendMessage);
    messageInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });

    // 초기 세션 연결
    const firstSession = document.querySelector('.session-item');
    if (firstSession) {
        switchChatSession(firstSession.dataset.sessionId);
    }
}); 