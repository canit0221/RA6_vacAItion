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
    const loginLink = document.getElementById('loginLink');
    const signupLink = document.getElementById('signupLink');
    const profileLink = document.getElementById('profileLink');
    const logoutLink = document.getElementById('logoutLink');
    
    if (accessToken) {
        // 로그인 상태
        if (loginLink) loginLink.style.display = 'none';
        if (signupLink) signupLink.style.display = 'none';
        if (profileLink) profileLink.style.display = 'block';
        if (logoutLink) logoutLink.style.display = 'block';
        
        // 채팅 기능 초기화
        initializeChat();
    } else {
        // 비로그인 상태
        if (loginLink) loginLink.style.display = 'block';
        if (signupLink) signupLink.style.display = 'block';
        if (profileLink) profileLink.style.display = 'none';
        if (logoutLink) logoutLink.style.display = 'none';
        
        // 비로그인 상태일 때는 간단한 체험형 챗봇으로 동작
        initializeDemoChatBot();
    }
}

// 채팅 초기화 함수
function initializeChat() {
    // 채팅 세션 목록 가져오기
    loadChatSessions();
}

// 체험형 챗봇 초기화
function initializeDemoChatBot() {
    const sessionList = document.getElementById('sessionList');
    if (sessionList) {
        sessionList.innerHTML = '<div class="session-item active">체험 모드</div>';
    }
    
    const chatMessages = document.getElementById('chatMessages');
    if (chatMessages) {
        chatMessages.innerHTML = `
            <div class="message bot">
                <div class="message-content">
                    <p>안녕하세요! 휴일 계획을 도와드릴 Hue입니다.</p>
                    <p>회원가입 후 이용하시면 더 많은 기능을 사용하실 수 있습니다.</p>
                </div>
            </div>
        `;
    }
}

// 채팅 세션 목록 로드 함수
async function loadChatSessions() {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) return;
    
    try {
        const response = await fetch(`${BACKEND_BASE_URL}/api/chatbot/api/sessions/`, {
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
        sessionItem.textContent = session.title || '새 채팅';
        sessionItem.setAttribute('data-session-id', session.id);
        
        sessionItem.addEventListener('click', () => {
            loadChatSession(session.id);
            
            // 현재 선택된 세션 하이라이트
            document.querySelectorAll('.session-item').forEach(item => {
                item.classList.remove('active');
            });
            sessionItem.classList.add('active');
        });
        
        sessionList.appendChild(sessionItem);
    });
}

// 특정 채팅 세션 로드 함수
async function loadChatSession(sessionId) {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) return;
    
    currentSession = sessionId;
    
    try {
        const response = await fetch(`${BACKEND_BASE_URL}/api/chatbot/api/messages/${sessionId}/`, {
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
        // 첫 메시지가 없으면 환영 메시지 표시
        chatMessages.innerHTML = `
            <div class="message bot">
                <div class="message-content">
                    <p>안녕하세요! 휴일 계획을 도와드릴 Hue입니다. 어떤 휴일을 계획 중이신가요?</p>
                </div>
            </div>
        `;
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
    
    try {
        const title = '새 채팅 ' + new Date().toLocaleString();
        const response = await fetch(`${BACKEND_BASE_URL}/api/chatbot/api/sessions/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            },
            body: JSON.stringify({ title })
        });
        
        if (response.ok) {
            const session = await response.json();
            loadChatSessions();
        } else {
            console.error('세션 생성 실패:', response.statusText);
        }
    } catch (error) {
        console.error('세션 생성 에러:', error);
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
    
    if (accessToken && currentSession) {
        // 로그인 상태 + 세션 있음: 웹소켓으로 전송
        if (socket && socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({
                message: message,
                session_id: currentSession
            }));
            
            // 화면에 사용자 메시지 추가
            addMessageToChat(message, false);
            
            // 입력창 초기화
            messageInput.value = '';
        } else {
            alert('채팅 서버에 연결할 수 없습니다. 페이지를 새로고침 해주세요.');
        }
    } else {
        // 비로그인 또는 데모 모드: 간단한 응답
        addMessageToChat(message, false);
        
        // 입력창 초기화
        messageInput.value = '';
        
        // 약간의 딜레이 후 봇 응답
        setTimeout(() => {
            const demoResponses = [
                "더 자세한 정보를 위해 로그인해 주세요!",
                "계정을 만들면 대화를 저장하고 맞춤형 추천을 받을 수 있어요.",
                "회원가입하시면 더 많은 기능을 이용하실 수 있습니다.",
                "휴일 계획에 대해 더 도움을 드리고 싶네요. 회원가입 해보세요!"
            ];
            const randomResponse = demoResponses[Math.floor(Math.random() * demoResponses.length)];
            addMessageToChat(randomResponse, true);
        }, 1000);
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
    
    const username = localStorage.getItem('username');
    
    // 웹소켓 URL
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.hostname}:8000/ws/chat/${sessionId}/?token=${localStorage.getItem('access_token')}`;
    
    socket = new WebSocket(wsUrl);
    
    socket.onopen = () => {
        console.log('웹소켓 연결 성공');
    };
    
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.message) {
            addMessageToChat(data.message, data.is_bot);
        }
    };
    
    socket.onerror = (error) => {
        console.error('웹소켓 에러:', error);
    };
    
    socket.onclose = () => {
        console.log('웹소켓 연결 종료');
    };
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