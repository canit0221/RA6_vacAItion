const BACKEND_BASE_URL = 'http://localhost:8000';
let currentSession = null;

document.addEventListener('DOMContentLoaded', () => {
    // 로그인 상태 확인
    checkLoginStatus();
    
    // 폼 제출 이벤트 리스너
    const messageForm = document.getElementById('messageForm');
    if (messageForm) {
        messageForm.addEventListener('submit', sendMessage);
    }
    
    // 새 채팅 버튼 이벤트 리스너
    const newChatBtn = document.getElementById('newChatBtn');
    if (newChatBtn) {
        newChatBtn.addEventListener('click', createNewChat);
    }
    
    // 로그아웃 버튼 이벤트 리스너
    const logoutButton = document.getElementById('logoutButton');
    if (logoutButton) {
        logoutButton.addEventListener('click', logout);
    }
    
    // 초기 채팅 목록 로드
    loadChatSessions();
});

// 로그인 상태 확인 함수
function checkLoginStatus() {
    const accessToken = localStorage.getItem('access_token');
    
    if (!accessToken) {
        // 비로그인 상태: 로그인 페이지로 리다이렉트
        alert('채팅을 사용하려면 로그인이 필요합니다.');
        window.location.href = 'login.html';
        return;
    }
    
    // 로그인 상태: UI 업데이트
    const loginLink = document.getElementById('loginLink');
    const signupLink = document.getElementById('signupLink');
    const profileLink = document.getElementById('profileLink');
    const logoutLink = document.getElementById('logoutLink');
    
    if (loginLink) loginLink.style.display = 'none';
    if (signupLink) signupLink.style.display = 'none';
    if (profileLink) profileLink.style.display = 'block';
    if (logoutLink) logoutLink.style.display = 'block';
    
    // 채팅 기능 초기화
    initializeChat();
}

// 채팅 초기화 함수
function initializeChat() {
    // 채팅 세션 목록 가져오기
    loadChatSessions();
}

// 채팅 세션 목록 로드 함수
async function loadChatSessions() {
    console.log('Loading chat sessions...');
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) return;
    
    try {
        const response = await fetch(`${BACKEND_BASE_URL}/chat/api/sessions/`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${accessToken}`
            }
        });
        
        if (response.ok) {
            const sessions = await response.json();
            displayChatSessions(sessions);
            
            // 세션이 있으면 첫 번째 세션을 로드
            if (sessions.length > 0) {
                await loadChatSession(sessions[0].id);
            }
        } else {
            console.error('세션 로드 실패:', response.statusText);
        }
    } catch (error) {
        console.error('세션 로드 에러:', error);
    }
}

// 채팅 세션 목록 표시 함수
function displayChatSessions(sessions) {
    const sessionList = document.getElementById('sessionList');
    if (!sessionList) return;
    
    sessionList.innerHTML = '';
    
    sessions.forEach(session => {
        const sessionItem = document.createElement('div');
        sessionItem.className = 'session-item';
        
        // 세션 컨테이너 생성 (세션 제목 + 삭제 버튼을 담을 컨테이너)
        const sessionContainer = document.createElement('div');
        sessionContainer.className = 'session-container';
        sessionContainer.style.display = 'flex';
        sessionContainer.style.justifyContent = 'space-between';
        sessionContainer.style.alignItems = 'center';
        sessionContainer.style.width = '100%';
        
        // 세션 제목 컨테이너
        const titleContainer = document.createElement('div');
        titleContainer.textContent = session.title || '새 채팅';
        titleContainer.style.cursor = 'pointer';
        titleContainer.style.flexGrow = '1';
        
        // 세션 삭제 버튼
        const deleteButton = document.createElement('button');
        deleteButton.innerHTML = '🗑️';
        deleteButton.className = 'delete-chat-btn';
        deleteButton.style.background = 'none';
        deleteButton.style.border = 'none';
        deleteButton.style.cursor = 'pointer';
        deleteButton.style.fontSize = '16px';
        deleteButton.style.padding = '4px';
        deleteButton.style.marginLeft = '8px';
        deleteButton.style.opacity = '0.7';
        deleteButton.title = '채팅방 삭제';
        
        // 마우스 오버 효과
        deleteButton.onmouseover = () => {
            deleteButton.style.opacity = '1';
        };
        deleteButton.onmouseout = () => {
            deleteButton.style.opacity = '0.7';
        };
        
        // 삭제 버튼 클릭 이벤트
        deleteButton.addEventListener('click', (e) => {
            e.stopPropagation(); // 클릭 이벤트 전파 방지
            if (confirm('정말로 이 채팅방을 삭제하시겠습니까?')) {
                deleteChatSession(session.id);
            }
        });
        
        // 채팅방 클릭 이벤트
        titleContainer.addEventListener('click', () => {
            loadChatSession(session.id);
            
            // 현재 선택된 세션 하이라이트
            document.querySelectorAll('.session-item').forEach(item => {
                item.classList.remove('active');
            });
            sessionItem.classList.add('active');
        });
        
        // 컨테이너에 요소들 추가
        sessionContainer.appendChild(titleContainer);
        sessionContainer.appendChild(deleteButton);
        sessionItem.appendChild(sessionContainer);
        
        // 세션 ID 설정
        sessionItem.setAttribute('data-session-id', session.id);
        
        // 세션 목록에 추가
        sessionList.appendChild(sessionItem);
    });
}

class ChatWebSocket {
    constructor(sessionId) {
        if (ChatWebSocket.instance && ChatWebSocket.instance.sessionId === sessionId) {
            return ChatWebSocket.instance;
        }
        
        this.sessionId = sessionId;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.manualClose = false;
        
        if (ChatWebSocket.instance) {
            ChatWebSocket.instance.close();
        }
        
        ChatWebSocket.instance = this;
        this.setupWebSocket();
    }

    setupWebSocket() {
        const accessToken = localStorage.getItem('access_token');
        if (!accessToken) {
            console.error('No access token found');
            return;
        }

        try {
            if (this.ws) {
                this.ws.close();
            }
            
            const wsUrl = `ws://localhost:8000/ws/chat/${this.sessionId}/?token=${accessToken}`;
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected successfully');
                this.reconnectAttempts = 0;
                this.reconnectDelay = 1000;
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                if (data.bot_response) {
                    displayMessage(data.bot_response, true);
                }
            };

            this.ws.onclose = (event) => {
                if (!this.manualClose && this.reconnectAttempts < this.maxReconnectAttempts) {
                    console.log('WebSocket connection closed. Attempting to reconnect...');
                    setTimeout(() => {
                        this.reconnectAttempts++;
                        this.setupWebSocket();
                    }, this.reconnectDelay);
                    this.reconnectDelay *= 2; // 지수 백오프
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

        } catch (error) {
            console.error('WebSocket setup error:', error);
        }
    }

    sendMessage(message) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.error('WebSocket is not connected');
            return false;
        }

        try {
            this.ws.send(JSON.stringify({ message }));
            return true;
        } catch (error) {
            console.error('Send message error:', error);
            return false;
        }
    }

    close() {
        this.manualClose = true;
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// 싱글톤 인스턴스 저장을 위한 정적 속성
ChatWebSocket.instance = null;

// 채팅 초기화 함수 수정
async function loadChatSession(sessionId) {
    try {
        currentSession = sessionId;
        // 새로운 WebSocket 연결 생성 (싱글톤 패턴 사용)
        new ChatWebSocket(sessionId);
        
        // 메시지 로드
        const accessToken = localStorage.getItem('access_token');
        if (!accessToken) return;
        
        const response = await fetch(`${BACKEND_BASE_URL}/chat/api/messages/${sessionId}/`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${accessToken}`
            }
        });
        
        if (response.ok) {
            const messages = await response.json();
            displayChatMessages(messages);
            
            // 현재 세션 타이틀 업데이트
            updateSessionTitle(sessionId);
            
            // 현재 선택된 세션 하이라이트
            document.querySelectorAll('.session-item').forEach(item => {
                item.classList.remove('active');
                if (item.getAttribute('data-session-id') === sessionId) {
                    item.classList.add('active');
                }
            });
        } else {
            console.error('메시지 로드 실패:', response.statusText);
        }
    } catch (error) {
        console.error('세션 로드 에러:', error);
    }
}

// 채팅 메시지 표시 함수
function displayChatMessages(messages) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;
    
    chatMessages.innerHTML = '';
    
    if (messages.length === 0) {
        // 첫 메시지가 없을 때는 빈 채팅방으로 시작
        return;
    }
    
    messages.forEach(message => {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${message.is_bot ? 'bot' : 'user'}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        const content = document.createElement('p');
        content.textContent = message.content;
        
        contentDiv.appendChild(content);
        messageDiv.appendChild(contentDiv);
        
        chatMessages.appendChild(messageDiv);
    });
    
    // 스크롤을 맨 아래로
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// 새 채팅 세션 생성 함수
async function createNewChat() {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
        alert('로그인이 필요한 기능입니다.');
        window.location.href = 'login.html';
        return;
    }
    
    try {
        const title = '새 채팅 ' + new Date().toLocaleString();
        const response = await fetch(`${BACKEND_BASE_URL}/chat/api/sessions/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            },
            body: JSON.stringify({ title })
        });
        
        if (response.ok) {
            const session = await response.json();
            // 새로운 세션 생성 후 해당 세션으로 이동
            await loadChatSession(session.id);
            // 세션 목록 새로고침
            loadChatSessions();
        } else {
            console.error('세션 생성 실패:', response.statusText);
            alert('새 채팅방 생성에 실패했습니다.');
        }
    } catch (error) {
        console.error('세션 생성 에러:', error);
        alert('새 채팅방 생성 중 오류가 발생했습니다.');
    }
}

// 세션 제목 업데이트 함수
function updateSessionTitle(sessionId) {
    const sessionItems = document.querySelectorAll('.session-item');
    sessionItems.forEach(item => {
        if (item.getAttribute('data-session-id') === sessionId) {
            document.getElementById('currentSessionTitle').textContent = item.textContent;
        }
    });
}

// 메시지 표시 함수
function displayMessage(content, isBot) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) return;
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isBot ? 'bot' : 'user'}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    const contentP = document.createElement('p');
    contentP.textContent = content;
    
    contentDiv.appendChild(contentP);
    messageDiv.appendChild(contentDiv);
    
    chatMessages.appendChild(messageDiv);
    
    // 스크롤을 맨 아래로
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// 메시지 전송 함수 수정
async function sendMessage(e) {
    e.preventDefault();
    
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();
    
    if (!message) return;
    
    if (!currentSession) {
        console.warn('현재 세션이 없습니다.');
        return;
    }

    // 메시지 전송
    if (ChatWebSocket.instance && ChatWebSocket.instance.sendMessage(message)) {
        // 사용자 메시지 표시
        displayMessage(message, false);
        // 입력창 초기화
        messageInput.value = '';
    }
}

// 로그아웃 함수
async function logout() {
    try {
        const refreshToken = localStorage.getItem('refresh_token');
        
        if (!refreshToken) {
            alert('이미 로그아웃 되었습니다.');
            window.location.href = 'login.html';
            return;
        }
        
        const response = await fetch(`${BACKEND_BASE_URL}/api/account/logout/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify({
                refresh: refreshToken
            })
        });
        
        // 로컬 스토리지에서 토큰 제거
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('username');
        
        alert('로그아웃 되었습니다.');
        window.location.href = 'login.html';
    } catch (error) {
        console.error('로그아웃 에러:', error);
        // 에러가 발생해도 로컬 스토리지는 비우기
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('username');
        alert('로그아웃 처리 중 오류가 발생했습니다.');
        window.location.href = 'login.html';
    }
}

// 채팅 세션 삭제 함수 수정
async function deleteChatSession(sessionId) {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
        alert('로그인이 필요한 기능입니다.');
        window.location.href = 'login.html';
        return;
    }
    
    try {
        const response = await fetch(`${BACKEND_BASE_URL}/chat/api/sessions/${sessionId}/`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${accessToken}`
            }
        });
        
        if (response.ok) {
            console.log('채팅방 삭제 성공:', sessionId);
            
            // 현재 선택된 채팅방이 삭제된 경우
            if (currentSession === sessionId) {
                currentSession = null;
                // 웹소켓 연결 종료
                if (ChatWebSocket.instance) {
                    ChatWebSocket.instance.close();
                }
                // 채팅창 비우기
                const chatMessages = document.getElementById('chatMessages');
                if (chatMessages) {
                    chatMessages.innerHTML = '';
                }
                // 세션 제목 초기화
                const currentSessionTitle = document.getElementById('currentSessionTitle');
                if (currentSessionTitle) {
                    currentSessionTitle.textContent = '';
                }
            }
            
            // 채팅 세션 목록 다시 로드
            loadChatSessions();
        } else {
            console.error('채팅방 삭제 실패:', response.statusText);
            alert('채팅방 삭제에 실패했습니다.');
        }
    } catch (error) {
        console.error('채팅방 삭제 에러:', error);
        alert('채팅방 삭제 중 오류가 발생했습니다.');
    }
} 