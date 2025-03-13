const BACKEND_BASE_URL = 'http://localhost:8000';
let currentSession = null;
let socket = null;

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
                loadChatSession(sessions[0].id);
            } else {
                // 세션이 없으면 새 세션 생성
                createNewChat();
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

// 특정 채팅 세션 로드 함수
async function loadChatSession(sessionId) {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) return;
    
    currentSession = sessionId;
    
    try {
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
            
            // 웹소켓 연결
            connectWebSocket(sessionId);
        } else {
            console.error('메시지 로드 실패:', response.statusText);
        }
    } catch (error) {
        console.error('메시지 로드 에러:', error);
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
        // 로그인 상태가 아니면 로그인 페이지로 이동
        alert('로그인이 필요한 기능입니다.');
        window.location.href = 'login.html';
        return;
    }
    
    // 새 채팅 생성 플래그 설정 (연결 종료 메시지 숨기기 위함)
    localStorage.setItem('just_created_chat', 'true');
    
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
            
            // 세션 생성 후 지연 시간을 늘림 (백엔드에서 세션이 완전히 생성될 시간을 확보)
            setTimeout(() => {
                loadChatSession(session.id); // 직접 새 세션을 로드
                
                // 2초 후에 플래그 제거 (연결 종료/에러 메시지 억제 용도)
                setTimeout(() => {
                    localStorage.removeItem('just_created_chat');
                }, 2000);
            }, 1000); // 1초로 지연 시간 증가
        } else {
            console.error('세션 생성 실패:', response.statusText);
            localStorage.removeItem('just_created_chat'); // 실패 시 플래그 제거
        }
    } catch (error) {
        console.error('세션 생성 에러:', error);
        localStorage.removeItem('just_created_chat'); // 예외 발생 시 플래그 제거
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

// 채팅 메시지 전송 함수
function sendMessage(e) {
    e.preventDefault();
    
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();
    
    if (!message) return;
    
    const accessToken = localStorage.getItem('access_token');
    
    if (!accessToken) {
        // 로그인 상태가 아니면 로그인 페이지로 이동
        alert('채팅을 사용하려면 로그인이 필요합니다.');
        window.location.href = 'login.html';
        return;
    }
    
    if (!currentSession) {
        console.warn('현재 세션이 없습니다. 새 채팅 세션을 생성합니다.');
        createNewChat();
        
        // 세션 생성 후 잠시 대기 후 메시지 재전송 시도
        setTimeout(() => {
            const retryMsg = messageInput.value.trim();
            if (retryMsg && currentSession) {
                sendMessageToServer(retryMsg);
            }
        }, 1500);
        return;
    }
    
    sendMessageToServer(message);
    
    // 입력창 초기화
    messageInput.value = '';
}

// 서버로 메시지 전송 함수
function sendMessageToServer(message) {
    console.log('메시지 전송 시도:', message, '세션:', currentSession);
    
    // 웹소켓 상태 확인
    if (!socket) {
        console.error('웹소켓이 초기화되지 않았습니다.');
        addMessageToChat('서버에 연결되어 있지 않습니다. 페이지를 새로고침 해주세요.', true);
        return;
    }
    
    if (socket.readyState !== WebSocket.OPEN) {
        console.error('웹소켓 연결 상태:', socket.readyState);
        
        // 재연결 시도
        if (socket.readyState === WebSocket.CLOSED || socket.readyState === WebSocket.CLOSING) {
            console.log('연결이 끊어졌습니다. 재연결 시도...');
            connectWebSocket(currentSession);
            
            // 잠시 후 메시지 재전송 시도
            setTimeout(() => {
                if (socket && socket.readyState === WebSocket.OPEN) {
                    socket.send(JSON.stringify({
                        message: message,
                        session_id: currentSession
                    }));
                    addMessageToChat(message, false);
                } else {
                    alert('서버에 연결할 수 없습니다. 페이지를 새로고침 해주세요.');
                }
            }, 1000);
            return;
        }
        
        alert('채팅 서버에 연결할 수 없습니다. 페이지를 새로고침 해주세요.');
        return;
    }
    
    try {
        // 메시지 전송
        socket.send(JSON.stringify({
            message: message,
            session_id: currentSession
        }));
        
        // 화면에 사용자 메시지 추가
        addMessageToChat(message, false);
        
        console.log('메시지 전송 성공');
    } catch (error) {
        console.error('메시지 전송 오류:', error);
        addMessageToChat('메시지 전송에 실패했습니다. 다시 시도해주세요.', true);
    }
}

// 채팅창에 메시지 추가 함수
function addMessageToChat(content, isBot) {
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

// 웹소켓 연결 함수
function connectWebSocket(sessionId) {
    // 기존 소켓이 있으면 닫기
    if (socket) {
        socket.close();
    }
    
    // 인증 토큰 확인
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
        console.error('인증 토큰이 없습니다. 채팅을 이용할 수 없습니다.');
        return;
    }
    
    // 현재 세션 ID 저장
    currentSession = sessionId;
    
    // 웹소켓 URL
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.hostname}:8000/ws/chat/${sessionId}/?token=${accessToken}`;
    
    console.log('웹소켓 연결 시도:', wsUrl);
    
    try {
        socket = new WebSocket(wsUrl);
        
        socket.onopen = () => {
            console.log('웹소켓 연결 성공:', sessionId);
            
            // 연결 성공 메시지 (삭제)
            // addMessageToChat('서버에 연결되었습니다. 질문을 입력해주세요!', true);
        };
        
        socket.onmessage = (event) => {
            console.log('웹소켓 메시지 수신:', event.data);
            try {
                const data = JSON.parse(event.data);
                
                // 봇 응답 처리
                if (data.bot_response) {
                    addMessageToChat(data.bot_response, true);
                }
                // 이전 방식 호환성 유지
                else if (data.message) {
                    addMessageToChat(data.message, data.is_bot);
                }
            } catch (e) {
                console.error('메시지 파싱 오류:', e);
                if (typeof event.data === 'string') {
                    addMessageToChat(event.data, true);
                }
            }
        };
        
        socket.onerror = (error) => {
            console.error('웹소켓 에러:', error);
            
            // 새 채팅 생성 직후에는 에러 메시지 표시하지 않음
            const isAfterNewChatCreation = localStorage.getItem('just_created_chat') === 'true';
            
            if (!isAfterNewChatCreation) {
                addMessageToChat('서버 연결에 문제가 발생했습니다. 새로고침을 해보세요.', true);
            }
        };
        
        socket.onclose = (event) => {
            console.log('웹소켓 연결 종료:', event.code, event.reason);
            
            // 정상적인 종료(1000) 또는 새 채팅방을 만든 직후(createNewChat 호출 후 1초 이내)인 경우 
            // 메시지를 표시하지 않음
            const isAfterNewChatCreation = localStorage.getItem('just_created_chat') === 'true';
            
            if (event.code !== 1000 && !isAfterNewChatCreation) {
                addMessageToChat(`서버와의 연결이 끊어졌습니다. (코드: ${event.code})`, true);
            }
            
            // 새 채팅 생성 플래그 제거
            if (isAfterNewChatCreation) {
                localStorage.removeItem('just_created_chat');
            }
        };
    } catch (error) {
        console.error('웹소켓 초기화 오류:', error);
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

// 채팅 세션 삭제 함수
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
                if (socket) {
                    socket.close();
                    socket = null;
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