const BACKEND_BASE_URL = 'https://vacaition.life';
// 디버깅을 위한 로그 활성화
const DEBUG = true;

let currentSession = null;
let currentDate = null; // 현재 선택된 날짜 저장

document.addEventListener('DOMContentLoaded', () => {
    if (DEBUG) console.log('DOM 로드됨, 이벤트 리스너 등록 시작');
    
    // URL에서 날짜 파라미터 가져오기
    const urlParams = new URLSearchParams(window.location.search);
    currentDate = urlParams.get('date');
    
    if (DEBUG && currentDate) console.log('URL에서 날짜 파라미터 발견:', currentDate);
    
    // 로그인 상태 확인
    checkLoginStatus();
    
    // UI 업데이트 추가
    updateUI();
    
    // 네비게이션 이벤트 리스너 설정
    setupEventListeners();
    
    // 폼 제출 이벤트 리스너
    const messageForm = document.getElementById('messageForm');
    if (messageForm) {
        console.log('메시지 폼 찾음, submit 이벤트 리스너 등록');
        messageForm.addEventListener('submit', sendMessage);
        
        // 직접 버튼 클릭 이벤트 추가
        const sendButton = document.querySelector('.send-btn');
        if (sendButton) {
            console.log('전송 버튼 찾음, click 이벤트 리스너 등록');
            sendButton.addEventListener('click', function(e) {
                e.preventDefault();
                console.log('전송 버튼 클릭됨');
                sendMessage(e);
            });
        } else {
            console.error('전송 버튼을 찾을 수 없음');
        }
    } else {
        console.error('메시지 폼을 찾을 수 없음');
    }
    
    // 로그아웃 버튼 이벤트 리스너
    const logoutButton = document.getElementById('logoutButton');
    if (logoutButton) {
        logoutButton.addEventListener('click', logout);
    }
    
    // 초기 채팅 세션 로드
    loadChatSessions();
    
    // 버튼 클릭 모니터링 코드 추가
    // 메시지가 추가될 때마다 + 버튼을 다시 검사
    setInterval(checkAndAddButtonListeners, 1000);
});

// 로그인 상태 확인 함수
function checkLoginStatus() {
    const accessToken = localStorage.getItem('access_token');
    
    if (!accessToken) {
        // 비로그인 상태: 로그인 페이지로 리다이렉트
        alert('채팅을 사용하려면 로그인이 필요합니다.');
        window.location.href = '../pages/login.html';
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
}

// 날짜 표시 형식으로 변환 (YYYY-MM-DD -> YYYY.MM.DD)
function formatDateForDisplay(dateStr) {
    if (!dateStr) return '';
    
    // YYYY-MM-DD 형식을 YYYY.MM.DD 형식으로 변환
    const parts = dateStr.split('-');
    if (parts.length === 3) {
        return `${parts[0]}.${parts[1]}.${parts[2]}`;
    }
    return dateStr;
}

// 날짜에 대한 새 세션 생성 함수
async function createSessionForDate(date) {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) return;
    
    try {
        const formattedDate = formatDateForDisplay(date);
        const title = `${formattedDate} 일정 추천`;
        
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
            updateSessionTitle(formattedDate);
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
function updateSessionTitle(dateStr) {
    // 제목 업데이트
    const currentSessionTitle = document.getElementById('currentSessionTitle');
    if (currentSessionTitle) {
        currentSessionTitle.textContent = `${dateStr} 일정 추천`;
    }
}

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
        } else {
            console.error('메시지 로드 실패:', response.statusText);
        }
    } catch (error) {
        console.error('세션 로드 에러:', error);
    }
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
            
            // 현재 날짜 설정 (URL 파라미터 또는 오늘 날짜)
            const targetDate = currentDate || new Date().toISOString().split('T')[0];
            const formattedTargetDate = formatDateForDisplay(targetDate);
            console.log(`대상 날짜: ${formattedTargetDate}`);
            
            // 해당 날짜의 세션 찾기
            const dateSession = sessions.find(session => 
                session.title.includes(formattedTargetDate));
                
            if (dateSession) {
                // 해당 날짜의 세션이 있으면 해당 세션만 로드
                console.log(`${formattedTargetDate}에 해당하는 세션 발견:`, dateSession);
                await loadChatSession(dateSession.id);
                // 세션 제목 업데이트
                updateSessionTitle(formattedTargetDate);
            } else {
                // 해당 날짜의 세션이 없으면 새로 생성
                console.log(`${formattedTargetDate}에 해당하는 세션이 없어 새로 생성합니다.`);
                await createSessionForDate(targetDate);
            }
        } else {
            console.error('세션 로드 실패:', response.statusText);
        }
    } catch (error) {
        console.error('세션 로드 에러:', error);
    }
}

class ChatWebSocket {
    constructor(sessionId) {
        console.log('ChatWebSocket 생성, 세션 ID:', sessionId);
        
        if (ChatWebSocket.instance && ChatWebSocket.instance.sessionId === sessionId) {
            console.log('이미 동일한 세션 ID의 WebSocket 인스턴스가 있음');
            return ChatWebSocket.instance;
        }
        
        this.sessionId = sessionId;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 1000;
        this.manualClose = false;
        this.connectionStatus = 'none'; // 연결 상태 추적
        
        if (ChatWebSocket.instance) {
            console.log('기존 WebSocket 인스턴스 닫음');
            ChatWebSocket.instance.close();
        }
        
        ChatWebSocket.instance = this;
        this.setupWebSocket();
        
        return this;
    }

    setupWebSocket() {
        const accessToken = localStorage.getItem('access_token');
        if (!accessToken) {
            console.error('No access token found');
            this.connectionStatus = 'no_token';
            return;
        }

        try {
            if (this.ws) {
                console.log('기존 WebSocket 연결 닫음');
                this.ws.close();
            }
            
            this.connectionStatus = 'connecting';
            console.log('WebSocket 연결 시도 중...');
            
            // 현재 페이지의 URL 파라미터를 가져옴
            const urlParams = new URLSearchParams(window.location.search);
            const dateParam = urlParams.get('date');
            const locationParam = urlParams.get('location');
            const companionParam = urlParams.get('companion');
            const scheduleIdParam = urlParams.get('schedule_id'); // 일정 ID 파라미터 추가
            
            // WebSocket URL 생성 (기존 URL에 새 파라미터 추가)
            let wsUrl = `wss://vacaition.life/ws/chat/${this.sessionId}/?token=${accessToken}`;
            
            // schedule_id 파라미터 추가 (우선적으로 추가 - 더 중요한 정보)
            if (scheduleIdParam) {
                wsUrl += `&schedule_id=${encodeURIComponent(scheduleIdParam)}`;
                console.log('WebSocket URL에 schedule_id 파라미터 추가:', scheduleIdParam);
            }
            
            // date 파라미터 추가
            if (dateParam) {
                wsUrl += `&date=${encodeURIComponent(dateParam)}`;
                console.log('WebSocket URL에 date 파라미터 추가:', dateParam);
            }
            
            // location 파라미터 추가
            if (locationParam) {
                wsUrl += `&location=${encodeURIComponent(locationParam)}`;
                console.log('WebSocket URL에 location 파라미터 추가:', locationParam);
            }
            
            // companion 파라미터 추가
            if (companionParam) {
                wsUrl += `&companion=${encodeURIComponent(companionParam)}`;
                console.log('WebSocket URL에 companion 파라미터 추가:', companionParam);
            }
            
            console.log('최종 WebSocket 연결 URL:', wsUrl);
            
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket 연결 성공!');
                this.connectionStatus = 'connected';
                this.reconnectAttempts = 0;
                this.reconnectDelay = 1000;
                
                // 연결 성공 알림 표시
                const statusElement = document.getElementById('connection-status');
                if (statusElement) {
                    statusElement.textContent = '연결됨';
                    statusElement.className = 'status-connected';
                }
            };

            this.ws.onmessage = (event) => {
                console.log('WebSocket 메시지 수신:', event.data);
                try {
                    const data = JSON.parse(event.data);
                    console.log('파싱된 메시지:', data);
                    
                    // 연결 확인 메시지 처리
                    if (data.type === 'connection_established' || data.is_system) {
                        console.log('시스템 메시지:', data.message);
                        
                        // 연결 상태 표시 업데이트
                        const statusElement = document.getElementById('connection-status');
                        if (statusElement) {
                            statusElement.textContent = '연결됨';
                            statusElement.className = 'status-connected';
                        }
                        
                        // 시스템 메시지를 채팅창에 표시 (선택적)
                        // displaySystemMessage(data.message);
                        return;
                    }
                    
                    // 봇 메시지 처리
                    if (data.is_bot) {
                        if (data.is_streaming) {
                            // 스트리밍 메시지는 로그 출력하지 않음
                            let streamingMsg = document.querySelector('.message.bot.streaming');
                            if (streamingMsg) {
                                // 기존 스트리밍 메시지 업데이트 - textContent 사용
                                const contentDiv = streamingMsg.querySelector('.message-content');
                                // 현재 텍스트와 다른 경우에만 업데이트
                                if (contentDiv.textContent !== data.message) {
                                    contentDiv.textContent = data.message;
                                }
                            } else {
                                // 새 스트리밍 메시지 생성
                                displayMessage(data.message, true, true);
                            }
                        } else {
                            // 일반 메시지는 로그 출력
                            console.log('봇 메시지 수신:', data.message);
                            // 스트리밍이 아닌 일반 메시지는 새로 표시
                            // 기존 스트리밍 메시지가 있다면 제거
                            const streamingMsg = document.querySelector('.message.bot.streaming');
                            if (streamingMsg) {
                                streamingMsg.remove();
                            }
                            displayMessage(data.message, true);
                        }
                    }
                    // 사용자 메시지 처리 - is_user 대신 is_bot이 false인지 확인
                    else if (data.is_bot === false) {
                        // 사용자 메시지를 표시합니다.
                        displayMessage(data.message, false);
                        console.log('User message displayed');
                    }
                } catch (error) {
                    console.error('메시지 파싱 오류:', error);
                }
            };

            this.ws.onclose = (event) => {
                console.log('WebSocket 연결 닫힘, 코드:', event.code, '이유:', event.reason);
                this.connectionStatus = 'closed';
                
                // 연결 상태 표시 업데이트
                const statusElement = document.getElementById('connection-status');
                if (statusElement) {
                    statusElement.textContent = '연결 끊김';
                    statusElement.className = 'status-disconnected';
                }
                
                if (!this.manualClose && this.reconnectAttempts < this.maxReconnectAttempts) {
                    console.log('재연결 시도 중...');
                    setTimeout(() => {
                        this.reconnectAttempts++;
                        this.setupWebSocket();
                    }, this.reconnectDelay);
                    this.reconnectDelay *= 2; // 지수 백오프
                }
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket 오류:', error);
                this.connectionStatus = 'error';
                
                // 연결 상태 표시 업데이트
                const statusElement = document.getElementById('connection-status');
                if (statusElement) {
                    statusElement.textContent = '연결 오류';
                    statusElement.className = 'status-error';
                }
            };

        } catch (error) {
            console.error('WebSocket 설정 오류:', error);
            this.connectionStatus = 'setup_error';
        }
    }

    sendMessage(message) {
        console.log('sendMessage 호출됨, 메시지:', message);
        console.log('WebSocket 상태:', this.connectionStatus);
        
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.error('WebSocket이 연결되지 않음. 현재 상태:', this.ws ? this.ws.readyState : 'null');
            
            // 연결 상태가 아니라면 재연결 시도
            if (this.connectionStatus !== 'connecting') {
                console.log('WebSocket 재연결 시도');
                this.setupWebSocket();
                // 재연결 후 잠시 기다렸다가 메시지 전송 재시도
                setTimeout(() => {
                    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                        this.sendActualMessage(message);
                    } else {
                        console.error('재연결 후에도 WebSocket이 열리지 않음');
                        return false;
                    }
                }, 1000);
            }
            return false;
        }

        return this.sendActualMessage(message);
    }
    
    sendActualMessage(message) {
        try {
            console.log('WebSocket으로 메시지 전송:', message);
            this.ws.send(JSON.stringify({ message }));
            return true;
        } catch (error) {
            console.error('메시지 전송 중 오류 발생:', error);
            return false;
        }
    }

    close() {
        console.log('WebSocket 수동 종료');
        this.manualClose = true;
        this.connectionStatus = 'closed';
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }
}

// 싱글톤 인스턴스 저장을 위한 정적 속성
ChatWebSocket.instance = null;

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
        // 수정: API에서 받은 메시지도 is_bot 필드를 사용하도록 변경
        // (message.is_bot이 없으면 is_user의 반대값을 사용)
        const isBot = message.hasOwnProperty('is_bot') ? message.is_bot : !message.is_user;
        messageDiv.className = `message ${isBot ? 'bot' : 'user'}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        
        // 메시지 내용을 처리
        if (isBot) {
            try {
                // HTML 태그가 이미 포함된 경우 직접 사용, 그렇지 않은 경우 마크다운 변환
                if (message.content.includes('<b>') || message.content.includes('<i>') || message.content.includes('<u>')) {
                    console.log('HTML 태그가 발견되어 직접 렌더링:', message.content.substring(0, 50) + '...');
                    // 줄바꿈 문자(\n)를 <br> 태그로 변환 (HTML 태그 사용 시)
                    let content = message.content.replace(/\n/g, '<br>');
                    contentDiv.innerHTML = content;
                } 
                // 마크다운 렌더링을 위한 설정
                else if (typeof marked !== 'undefined') {
                    // 마크다운 처리 옵션 설정
                    marked.setOptions({
                        breaks: true,        // 줄바꿈 허용
                        gfm: true,           // GitHub Flavored Markdown 사용
                        headerIds: false,    // 헤더 ID 생성 비활성화
                        mangle: false,       // 이메일 주소 변경 방지
                        sanitize: false      // HTML 허용 (주의: XSS 위험)
                    });
                    
                    // 마크다운을 HTML로 변환
                    contentDiv.innerHTML = marked.parse(message.content);
                    console.log('마크다운으로 처리됨 (히스토리):', message.content.substring(0, 50) + '...');
                } else {
                    console.warn('Marked 라이브러리가 로드되지 않았습니다.');
                    // 마크다운 없이 표시할 때도 줄바꿈 보존
                    contentDiv.innerHTML = message.content.replace(/\n/g, '<br>');
                }
                
                // 봇 메시지에서 추천 장소 처리 (+ 버튼 추가)
                if (contentDiv.innerHTML.includes('<b>') || contentDiv.innerHTML.includes('<strong>')) {
                    console.log('봇 메시지에서 추천 장소 처리 시작');
                    enhancePlaceRecommendations(contentDiv);
                }
                
            } catch (error) {
                console.error('마크다운 처리 중 오류:', error);
                // 오류 발생 시에도 줄바꿈 보존
                contentDiv.innerHTML = message.content.replace(/\n/g, '<br>');
            }
        } else {
            // 사용자 메시지도 줄바꿈 보존
            contentDiv.innerHTML = message.content.replace(/\n/g, '<br>');
        }
        
        messageDiv.appendChild(contentDiv);
        chatMessages.appendChild(messageDiv);
    });
    
    // 스크롤을 항상 최신 메시지로 이동
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    // 메시지 렌더링 후 + 버튼 이벤트 리스너 확인
    setTimeout(checkAndAddButtonListeners, 100);
}

// 메시지 표시 함수
function displayMessage(content, isBot, isStreaming = false) {
    const chatMessages = document.getElementById('chatMessages');
    if (!chatMessages) {
        console.error('chatMessages 요소를 찾을 수 없습니다');
        return;
    }
    
    console.log(`메시지 표시 - 봇: ${isBot}, 스트리밍: ${isStreaming}, 길이: ${content.length}`);
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${isBot ? 'bot' : 'user'}${isStreaming ? ' streaming' : ''}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    if (isBot) {
        try {
            console.log('봇 메시지 처리 시작');
            
            // HTML 태그가 이미 포함된 경우 직접 사용, 그렇지 않은 경우 마크다운 변환
            if (content.includes('<b>') || content.includes('<i>') || content.includes('<u>')) {
                console.log('HTML 태그 발견, 직접 렌더링 모드');
                
                // 줄바꿈 문자(\n)를 <br> 태그로 변환 (HTML 태그 사용 시)
                content = content.replace(/\n/g, '<br>');
                contentDiv.innerHTML = content;
                
                // 개발자 도구에서 HTML 확인
                console.log('렌더링된 HTML 미리보기:');
                console.log(contentDiv.innerHTML.substring(0, 500));
            }
            // 마크다운 처리
            else if (typeof marked !== 'undefined') {
                console.log('마크다운 처리 모드');
                
                marked.setOptions({
                    breaks: true,
                    gfm: true,
                    headerIds: false,
                    mangle: false,
                    sanitize: false
                });
                
                contentDiv.innerHTML = marked.parse(content);
                console.log('마크다운 변환 후 HTML 미리보기:');
                console.log(contentDiv.innerHTML.substring(0, 500));
            } else {
                console.warn('Marked 라이브러리가 로드되지 않았습니다.');
                // 마크다운 없이 표시할 때도 줄바꿈 보존
                contentDiv.innerHTML = content.replace(/\n/g, '<br>');
            }
            
            // 스트리밍 중이 아닐 때만 추천 장소에 + 버튼 추가
            if (!isStreaming) {
                console.log('스트리밍이 아닌 메시지 - 추천 장소 처리 시작');
                
                // 렌더링된 내용에서 추천 장소 찾기
                const processedContentDiv = contentDiv.cloneNode(true);
                enhancePlaceRecommendations(processedContentDiv);
                
                // 추천 장소 처리 후 HTML 업데이트
                contentDiv.innerHTML = processedContentDiv.innerHTML;
                console.log('추천 장소 처리 완료');
            } else {
                console.log('스트리밍 메시지 - 추천 장소 처리 생략');
            }
        } catch (error) {
            console.error('메시지 처리 중 오류:', error);
            // 오류 발생 시에도 줄바꿈 보존
            contentDiv.innerHTML = content.replace(/\n/g, '<br>');
        }
    } else {
        // 사용자 메시지도 줄바꿈 보존
        contentDiv.innerHTML = content.replace(/\n/g, '<br>');
    }
    
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    // 스크롤을 최신 메시지로 이동
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    console.log('메시지 표시 완료');
}

// 추천 장소에 + 버튼 추가하는 함수
function enhancePlaceRecommendations(contentDiv) {
    console.log('enhancePlaceRecommendations 함수 호출됨');
    
    try {
        // 1. 모든 b 태그와 strong 태그 찾기
        const boldElements = contentDiv.querySelectorAll('b, strong');
        console.log(`발견된 <b>/<strong> 태그: ${boldElements.length}개`);
        
        // 이벤트 번호 패턴 (예: 1️⃣, 2️⃣ 등)
        const eventNumberPattern = /^[0-9️⃣]*\s*(.+)$/;
        
        // 각 bold 요소의 내용 디버깅
        boldElements.forEach((el, idx) => {
            console.log(`  - bold #${idx + 1}: "${el.textContent.trim()}"`);
        });
        
        if (boldElements.length > 0) {
            boldElements.forEach((item, index) => {
                // 추천 장소명 추출 (번호 이모지가 있으면 제거)
                let placeName = item.textContent.trim();
                const eventNameMatch = placeName.match(eventNumberPattern);
                if (eventNameMatch && eventNameMatch[1]) {
                    placeName = eventNameMatch[1].trim();
                }
                
                console.log(`#${index + 1} 장소/이벤트명 (정제 후): "${placeName}"`);
                
                // "+" 문자 제거 (버튼 클릭을 나타내는 텍스트가 있을 경우)
                placeName = placeName.replace(/\s*\+\s*$/, '').trim();
                
                // 이미 버튼이 추가된 경우 또는 텍스트 길이가 너무 짧은 경우 스킵
                // 또는 숫자로만 이루어진 경우 스킵 (예: "1️⃣" 등의 번호)
                const onlyNumbers = /^[0-9\s\u2000-\u3300]*$/;
                if (!placeName || placeName.length < 2 || onlyNumbers.test(placeName) || item.querySelector('.add-to-schedule-btn')) {
                    console.log(`  - "${placeName}" 스킵: 이미 버튼이 있거나 잘못된 형식`);
                    return;
                }
                
                console.log(`장소 "${placeName}" 에 + 버튼 추가 중...`);
                
                // 주변 정보 추출 시도 - 현재 요소의 부모 요소나 가까운 형제 요소들에서 정보 찾기
                let placeLocation = '정보 없음';
                let placeCategory = '정보 없음';
                let placeReason = '정보 없음';
                let placeUrl = '정보 없음';
                let eventDate = '정보 없음';
                let placeType = 'general';
                
                console.log('   장소 주변 정보 추출 시작');
                
                // 먼저 부모 요소 전체 텍스트에서 정보 추출 시도 (전체 문단에서 정보 찾기)
                const paragraphText = findParagraphText(item);
                if (paragraphText) {
                    console.log(`   전체 문단 텍스트 찾음 (길이: ${paragraphText.length})`);
                    console.log(`   문단 미리보기: ${paragraphText.substring(0, 100)}...`);
                    
                    // 일시 (📅 일시:) 정보 추출
                    if (paragraphText.includes('일시:') || paragraphText.includes('📅')) {
                        eventDate = extractInfoAfterMarker(paragraphText, ['일시:', '📅']);
                        placeType = 'event'; // 일시 정보가 있으면 이벤트로 판단
                        console.log(`   이벤트 일시 추출: "${eventDate}"`);
                    }
                    
                    // 위치 정보 (📍 장소:/위치:) 추출
                    if (paragraphText.includes('장소:') || paragraphText.includes('위치:') || paragraphText.includes('📍')) {
                        placeLocation = extractInfoAfterMarker(paragraphText, ['장소:', '위치:', '📍']);
                        console.log(`   위치 정보 추출: "${placeLocation}"`);
                    }
                    
                    // 추천 이유 (💫 추천 이유:) 추출
                    if (paragraphText.includes('추천 이유:') || paragraphText.includes('💫')) {
                        placeReason = extractInfoAfterMarker(paragraphText, ['추천 이유:', '💫']);
                        console.log(`   추천 이유 추출: "${placeReason}"`);
                    }
                    
                    // URL 또는 참고 정보 추출
                    if (paragraphText.includes('참고:') || paragraphText.includes('🔍')) {
                        placeUrl = extractInfoAfterMarker(paragraphText, ['참고:', '🔍']);
                        console.log(`   URL/참고 정보 추출: "${placeUrl}"`);
                    }
                    
                    // 분류 정보 (🏷️ 분류:) 추출
                    if (paragraphText.includes('분류:') || paragraphText.includes('🏷️')) {
                        placeCategory = extractInfoAfterMarker(paragraphText, ['분류:', '🏷️']);
                        console.log(`   분류 정보 추출: "${placeCategory}"`);
                    }
                }
                
                // 개별 형제 요소를 통한 상세 정보 추출 (기존 로직)
                let parentElement = item.parentElement;
                if (parentElement) {
                    // 부모 요소의 텍스트 내용 확인
                    const parentElementText = parentElement.textContent;
                    console.log(`   부모 요소 텍스트: ${parentElementText.substring(0, 50)}...`);
                    
                    // 형제 요소들을 탐색하면서 정보 추출
                    let currentElement = parentElement;
                    let foundLoops = 0;
                    
                    // 최대 10개의 형제 요소까지 탐색
                    while (currentElement && foundLoops < 10) {
                        foundLoops++;
                        
                        // 다음 형제 요소
                currentElement = currentElement.nextElementSibling;
                        
                        if (!currentElement) break;
                        
                        const elementText = currentElement.textContent.trim();
                        console.log(`   형제 요소 #${foundLoops} 텍스트: ${elementText.substring(0, 30)}...`);
                        
                        // 위치 정보 (📍 위치:/장소:) 추출
                        if ((elementText.includes('위치:') || elementText.includes('장소:') || elementText.includes('📍')) && placeLocation === '정보 없음') {
                            placeLocation = extractInfoAfterMarker(elementText, ['위치:', '장소:', '📍']);
                            console.log(`   위치 정보 추출: "${placeLocation}"`);
                        }
                        
                        // 분류 정보 (🏷️ 분류:) 추출
                        if ((elementText.includes('분류:') || elementText.includes('🏷️')) && placeCategory === '정보 없음') {
                            placeCategory = extractInfoAfterMarker(elementText, ['분류:', '🏷️']);
                            console.log(`   분류 정보 추출: "${placeCategory}"`);
                        }
                        
                        // 추천 이유 (💫 추천 이유:) 추출
                        if ((elementText.includes('추천 이유:') || elementText.includes('💫')) && placeReason === '정보 없음') {
                            placeReason = extractInfoAfterMarker(elementText, ['추천 이유:', '💫']);
                            console.log(`   추천 이유 추출: "${placeReason}"`);
                        }
                        
                        // URL (🔍 참고:) 추출
                        if ((elementText.includes('참고:') || elementText.includes('🔍')) && placeUrl === '정보 없음') {
                            placeUrl = extractInfoAfterMarker(elementText, ['참고:', '🔍']);
                            console.log(`   URL 추출: "${placeUrl}"`);
                        }
                        
                        // 특징 (✨ 특징:) 추출 - 있으면 추가 정보로 저장
                        if (elementText.includes('특징:') || elementText.includes('✨')) {
                            const feature = extractInfoAfterMarker(elementText, ['특징:', '✨']);
                            if (placeReason === '정보 없음') {
                                placeReason = feature;
                            } else {
                                placeReason += ' - ' + feature;
                            }
                            console.log(`   특징 추출: "${feature}"`);
                        }
                        
                        // 일시 (📅 일시:) 정보가 있으면 이벤트로 판단
                        if ((elementText.includes('일시:') || elementText.includes('📅')) && eventDate === '정보 없음') {
                            eventDate = extractInfoAfterMarker(elementText, ['일시:', '📅']);
                            placeType = 'event'; // 일시 정보가 있으면 이벤트로 판단
                            console.log(`   이벤트 일시 추출: "${eventDate}"`);
                        }
                    }
                }
                
                // 이벤트인 경우 event_date 설정
                if (placeType === 'event' && eventDate !== '정보 없음') {
                    // 이벤트 데이터를 URL 필드에 임시로 저장 (기존 로직 유지)
                    placeUrl = eventDate;
                }
                
                // 버튼 생성 및 추가
    const addButton = document.createElement('button');
    addButton.innerHTML = '+';
    addButton.className = 'add-to-schedule-btn';
    addButton.title = '일정에 추가';
    addButton.setAttribute('aria-label', '일정에 추가');
    
                // 추출한 정보를 버튼의 dataset에 저장
                addButton.dataset.placeName = placeName;
                addButton.dataset.placeLocation = placeLocation;
                addButton.dataset.placeCategory = placeCategory;
                addButton.dataset.placeReason = placeReason;
                addButton.dataset.placeUrl = placeUrl;
                addButton.dataset.placeType = placeType;
                
                // 이벤트 날짜 데이터 명시적 추가
                if (placeType === 'event' && eventDate !== '정보 없음') {
                    addButton.dataset.eventDate = eventDate;
                }
                
                // 버튼 추가
                item.appendChild(document.createTextNode(' '));
                item.appendChild(addButton);
                
                console.log(`'${placeName}'에 + 버튼 추가 완료, 추출 정보:`, {
                    location: placeLocation,
                    category: placeCategory,
                    reason: placeReason,
                    url: placeUrl,
                    type: placeType,
                    eventDate: eventDate
                });
            });
        } else {
            console.log('추천 장소/이벤트를 찾을 수 없습니다.');
        }
        
        console.log('추천 장소 처리 완료');
    } catch (error) {
        console.error('추천 장소 처리 중 오류 발생:', error);
    }
}

// 부모 단락 텍스트 찾기 (더 넓은 범위의 컨텍스트를 얻기 위해)
function findParagraphText(element) {
    // 상위 요소를 최대 3단계까지 올라가며 검색
    let current = element;
    let depth = 0;
    let paragraphText = "";
    
    while (current && depth < 3) {
        // 현재 요소가 p 태그이거나 div 태그인 경우
        if (current.tagName === 'P' || current.tagName === 'DIV') {
            paragraphText = current.textContent.trim();
            if (paragraphText.length > 50) { // 충분히 긴 텍스트를 찾았다면
                return paragraphText;
            }
        }
        current = current.parentElement;
        depth++;
    }
    
    // 충분한 텍스트를 찾지 못했다면 원래 요소의 부모 텍스트 반환
    if (paragraphText.length === 0 && element.parentElement) {
        return element.parentElement.textContent.trim();
    }
    
    return paragraphText;
}

// 텍스트에서 특정 마커 뒤의 정보를 추출하는 헬퍼 함수
function extractInfoAfterMarker(text, markers) {
    for (const marker of markers) {
        if (text.includes(marker)) {
            // 마커 뒤의 텍스트 추출
            const startIndex = text.indexOf(marker) + marker.length;
            // 다음 라인이나 다음 마커까지의 텍스트 추출
            let endIndex = text.indexOf('\n', startIndex);
            if (endIndex === -1) endIndex = text.length;
            
            // 다른 마커들 중 가장 가까운 위치 찾기
            for (const otherMarker of ['📍', '🏷️', '💫', '🔍', '✨', '📅']) {
                if (text.includes(otherMarker) && text.indexOf(otherMarker) > startIndex) {
                    const markerIndex = text.indexOf(otherMarker);
                    if (markerIndex < endIndex) {
                        endIndex = markerIndex;
                    }
                }
            }
            
            let extractedInfo = text.substring(startIndex, endIndex).trim();
            return extractedInfo || '정보 없음';
        }
    }
    return '정보 없음';
}

// 제목 요소에 + 버튼 추가
function addAddButton(titleElement, placeName) {
    console.log('addAddButton 함수 호출됨:', placeName);
    
    // 경고: innerHTML을 재설정하면 이벤트 리스너가 제거됨
    // 따라서 원본 콘텐츠는 수정하지 않고 버튼만 추가
    
    // 이미 버튼이 있으면 추가하지 않음
    if (titleElement.querySelector('.add-to-schedule-btn')) {
        console.log(`'${placeName}'에 이미 버튼이 있어 추가하지 않음`);
        return;
    }
    
    // 버튼 생성
    const addButton = document.createElement('button');
    addButton.innerHTML = '+';
    addButton.className = 'add-to-schedule-btn';
    addButton.title = '일정에 추가';
    addButton.setAttribute('aria-label', '일정에 추가');
    
    // 디버깅을 위한 인라인 스타일 추가
    addButton.style.zIndex = '1000';
    addButton.style.position = 'relative';
    
    // dataset에 장소 정보 저장
    addButton.dataset.placeName = placeName;
    
    // 이미 존재하는 dataset 정보 가져오기
    if (titleElement.dataset) {
        if (titleElement.dataset.placeLocation) 
            addButton.dataset.placeLocation = titleElement.dataset.placeLocation;
        
        if (titleElement.dataset.placeCategory) 
            addButton.dataset.placeCategory = titleElement.dataset.placeCategory;
        
        if (titleElement.dataset.placeReason) 
            addButton.dataset.placeReason = titleElement.dataset.placeReason;
        
        if (titleElement.dataset.placeUrl) 
            addButton.dataset.placeUrl = titleElement.dataset.placeUrl;
        
        if (titleElement.dataset.placeType) 
            addButton.dataset.placeType = titleElement.dataset.placeType;
        else
            addButton.dataset.placeType = 'general';
    }
    
    // 제목 요소에 버튼 직접 추가 (innerHTML 재설정하지 않음)
    titleElement.appendChild(document.createTextNode(' '));
    titleElement.appendChild(addButton);
    
    console.log(`'${placeName}'에 + 버튼 추가 완료, 데이터:`, Object.assign({}, addButton.dataset));
}

// 장소를 스케줄에 추가하는 함수
function addPlaceToSchedule(date, placeName, placeLocation, placeCategory, placeReason, placeUrl, placeType) {
    console.log(`[addPlaceToSchedule] 함수 호출됨: 날짜=${date}, 장소명=${placeName}`);
    displaySystemMessage(`"${placeName}" 장소를 ${date} 추천된 장소 목록에 추가 중...`);
    
    // 로컬 스토리지에서 토큰 가져오기
    const token = localStorage.getItem('access_token');
    if (!token) {
        console.error('인증 토큰이 없습니다. 로그인이 필요합니다.');
        displaySystemMessage('로그인이 필요합니다. 추천 장소 추가를 위해 로그인해주세요.');
            return;
        }
        
    // 이벤트/장소 유형에 따른 데이터 구성
    let requestData = {
        date: date,
        place_name: placeName,
        place_location: placeLocation !== '정보 없음' ? placeLocation : '위치 정보 없음',
        recommendation_reason: placeReason !== '정보 없음' ? placeReason : '챗봇 추천',
        additional_info: `카테고리: ${placeCategory}`,
        place_type: placeType
    };
    
    // 이벤트 타입인 경우 이벤트 일시 추가
    if (placeType === 'event') {
        // placeUrl에 임시 저장된 이벤트 일시 정보 추출
        let eventDate = placeUrl;
        
        // 이벤트 일시가 비어있는지 확인
        if (eventDate === '정보 없음' || !eventDate) {
            console.warn('이벤트 일시 정보가 없습니다. 기본값 사용.');
            eventDate = '기간 정보 없음';
        }
        
        requestData.event_date = eventDate;
        console.log(`이벤트 일시 정보 추가: ${eventDate}`);
    } 
    // 일반 장소 타입인 경우 URL 추가
    else if (placeUrl !== '정보 없음' && placeUrl) {
        requestData.place_url = placeUrl; // URL 정보
        console.log(`장소 URL 정보 추가: ${placeUrl}`);
    }
    
    console.log('API 요청 준비:', requestData);
    displaySystemMessage('서버에 추천 장소 추가 요청 중...');
    
    // 로딩 메시지 표시
    const loadingToast = showMessage(`"${placeName}" 추천 장소 목록에 추가 중...`, 'info');
    
    // API 요청 설정
    fetch(`${BACKEND_BASE_URL}/calendar/add-recommended-place/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify(requestData)
    })
    .then(response => {
        console.log(`API 응답 상태: ${response.status}`);
        
        // HTTP 상태 코드와 상태 텍스트 모두 로그
        console.log('응답 상태:', response.status, response.statusText);
        
        // 응답 헤더 확인
        console.log('응답 헤더:');
        response.headers.forEach((value, name) => {
            console.log(`${name}: ${value}`);
        });
        
        if (!response.ok) {
            if (response.status === 401) {
                throw new Error('인증이 만료되었습니다. 다시 로그인해주세요.');
            } else if (response.status === 400) {
                return response.json().then(data => {
                    throw new Error(`요청 오류: ${data.message || data.error || '잘못된 요청입니다.'}`);
                });
            } else if (response.status === 409) {
                throw new Error('이미 해당 날짜에 동일한 추천 장소가 존재합니다.');
            } else if (response.status === 405) {
                throw new Error('이 API 메서드는 지원되지 않습니다. 백엔드 관리자에게 문의하세요.');
        } else {
                throw new Error(`서버 오류 (${response.status}): 잠시 후 다시 시도해주세요.`);
            }
        }
        
        return response.json().catch(error => {
            console.warn('JSON 파싱 오류:', error);
            return { success: true, message: '추천 장소가 목록에 추가되었습니다. 추천 장소는 일정과 별도로 관리됩니다.' };
        });
    })
    .then(data => {
        console.log('추천 장소 추가 성공:', data);
        
        // 로딩 메시지 제거
        if (loadingToast) {
            loadingToast.remove();
        }
        
        // 성공 메시지 표시
        const successMsg = `✅ "${placeName}"이(가) ${date}의 추천된 장소 목록에 추가되었습니다.\n추천 장소는 일정과 별도로 관리됩니다.`;
        displaySystemMessage(successMsg);
        
        // 토스트 메시지로도 표시
        showMessage(successMsg, 'success');
        
        // 3초 후 일정 페이지로 이동할지 물어보기
        setTimeout(() => {
            if (confirm(`"${placeName}"이(가) 추천 장소 목록에 추가되었습니다.\n\n※ 주의: 이 장소는 아직 실제 일정에 추가되지 않았습니다.\n추천 장소 목록에만 추가되었으며, 실제 일정은 별도로 직접 작성해야 합니다.\n\n추천 장소 목록 페이지로 이동하시겠습니까?`)) {
                window.location.href = `add-schedule.html?date=${date}&added=true`;
            }
        }, 500);
    })
    .catch(error => {
        console.error('추천 장소 추가 실패:', error);
        
        // 로딩 메시지 제거
        if (loadingToast) {
            loadingToast.remove();
        }
        
        displaySystemMessage(`❌ 오류: ${error.message}`);
        
        // 오류 토스트 메시지
        showMessage(`추천 장소 추가 중 오류가 발생했습니다: ${error.message}`, 'error');
    });
}

// 알림 메시지 표시 함수
function showMessage(message, type = 'info') {
    // 기존 toast 요소가 있으면 제거
    const existingToast = document.querySelector('.toast-message');
    if (existingToast) {
        existingToast.remove();
    }
    
    // 새 toast 요소 생성
    const toast = document.createElement('div');
    toast.className = `toast-message toast-${type}`;
    toast.textContent = message;
    
    // body에 추가
    document.body.appendChild(toast);
    
    // CSS에 .show 클래스가 없으므로 직접 스타일 적용
    // (이미 애니메이션이 CSS에 정의되어 있음)
    
    // 자동으로 제거 (성공/에러 메시지의 경우)
    if (type !== 'info') {
        setTimeout(() => {
            toast.classList.add('toast-hide');
            setTimeout(() => {
                toast.remove();
            }, 500); // 페이드아웃 애니메이션 시간
        }, 3000);
    }
    
    return toast; // 참조 반환 (로딩 메시지를 수동으로 제거하기 위함)
}

// 메시지 전송 함수 수정
async function sendMessage(e) {
    console.log('sendMessage 함수 호출됨', e);
    e.preventDefault();
    
    const messageInput = document.getElementById('messageInput');
    const message = messageInput.value.trim();
    
    console.log('입력된 메시지:', message);
    
    if (!message) {
        console.log('메시지가 비어있음');
        return;
    }
    
    if (!currentSession) {
        console.warn('현재 세션이 없습니다.');
        
        // 날짜 기반으로 세션 생성
        try {
            console.log('세션 생성 시도');
            const date = currentDate || new Date().toISOString().split('T')[0];
            await createSessionForDate(date);
            
            // 약간의 지연 후 다시 시도
            setTimeout(() => {
                if (currentSession) {
                    console.log('새 세션 생성 후 메시지 재전송 시도');
                    sendMessageToSocket(message, messageInput);
                }
            }, 1000);
        } catch (error) {
            console.error('새 세션 생성 실패:', error);
        }
        return;
    }

    sendMessageToSocket(message, messageInput);
}

// 메시지 전송 로직을 별도 함수로 분리
function sendMessageToSocket(message, messageInput) {
    console.log('WebSocket으로 메시지 전송 시도:', message);
    console.log('현재 WebSocket 상태:', ChatWebSocket.instance ? ChatWebSocket.instance.ws.readyState : 'instance 없음');
    
    // 메시지 전송
    if (ChatWebSocket.instance && ChatWebSocket.instance.sendMessage(message)) {
        console.log('WebSocket으로 메시지 전송 성공');
        // 사용자 메시지는 서버에서 받아서 표시하도록 수정 (여기서 표시하지 않음)
        // displayMessage(message, false);
        // 입력창 초기화
        messageInput.value = '';
    } else {
        console.error('WebSocket 연결이 없거나 메시지 전송 실패');
        alert('메시지 전송에 실패했습니다. 페이지를 새로고침 후 다시 시도해주세요.');
    }
}

// 로그아웃 함수
async function logout() {
    console.log('로그아웃 함수 실행됨');
    try {
        const refreshToken = localStorage.getItem('refresh_token');
        const accessToken = localStorage.getItem('access_token');
        
        if (refreshToken && accessToken) {
            try {
                console.log('로그아웃 API 호출...');
                await fetch(`${BACKEND_BASE_URL}/logout/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${accessToken}`
                    },
                    body: JSON.stringify({
                        refresh: refreshToken
                    })
                });
            } catch (error) {
                console.error('로그아웃 API 에러:', error);
            }
        }
    } finally {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('username');
        
        alert('로그아웃 되었습니다.');
        window.location.replace('../pages/login.html');
    }
}

// UI 업데이트 함수
function updateUI() {
    const userNickname = localStorage.getItem('userNickname');
    const profileNavLink = document.getElementById('profileNavLink');
    
    if (userNickname && profileNavLink) {
        profileNavLink.textContent = `${userNickname}님의 프로필`;
    }
}

// 이벤트 리스너 설정
function setupEventListeners() {
    const navLinks = document.querySelectorAll('nav.main-nav a');
    
    if (navLinks.length >= 3) {  // Chat 링크가 제거되어 3개로 변경
        // 홈 링크
        navLinks[0].addEventListener('click', function(e) {
            e.preventDefault();
            window.location.href = '../index.html';
        });
        
        // 프로필 링크
        navLinks[1].addEventListener('click', function(e) {
            e.preventDefault();
            window.location.href = '../pages/profile.html';
        });
        
        // 로그아웃 링크
        navLinks[2].addEventListener('click', function(e) {
            e.preventDefault();
            console.log('로그아웃 링크 클릭됨');
            logout();
        });
    } else {
        console.warn('네비게이션 링크를 찾을 수 없습니다:', navLinks);
    }
}

// 채팅 세션 삭제 함수 수정
async function deleteChatSession(sessionId) {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
        alert('로그인이 필요한 기능입니다.');
        window.location.href = '../pages/login.html';
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
                
                // 새 세션 생성
                if (currentDate) {
                    await createSessionForDate(currentDate);
                } else {
                    const today = new Date().toISOString().split('T')[0];
                    await createSessionForDate(today);
                }
            }
        } else {
            console.error('채팅방 삭제 실패:', response.statusText);
            alert('채팅방 삭제에 실패했습니다.');
        }
    } catch (error) {
        console.error('채팅방 삭제 에러:', error);
        alert('채팅방 삭제 중 오류가 발생했습니다.');
    }
}

// 시스템 메시지 표시 함수
function displaySystemMessage(message) {
    console.log(`[System] ${message}`);
    
    const chatMessages = document.getElementById('chat-messages');
    if (!chatMessages) {
        console.error('chat-messages 요소를 찾을 수 없습니다.');
        return;
    }
    
    // 시스템 메시지 요소 생성
    const systemMessageDiv = document.createElement('div');
    systemMessageDiv.className = 'message system-message';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = message;
    
    systemMessageDiv.appendChild(contentDiv);
    chatMessages.appendChild(systemMessageDiv);
    
    // 최신 메시지로 스크롤
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// 현재 채팅 세션 정보를 반환하는 함수
function getCurrentChatSession() {
    // 1. URL에서 세션 ID 가져오기
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session');
    
    // 2. 전역 변수에서 현재 세션 정보 확인
    const currentSession = {
        id: sessionId || 'default',
        date: urlParams.get('date') || new Date().toISOString().split('T')[0] // URL에 date 파라미터가 있으면 사용, 없으면 오늘 날짜
    };
    
    console.log(`[getCurrentChatSession] 현재 세션 정보:`, currentSession);
    return currentSession;
}

// 버튼 이벤트 리스너 체크 및 추가 함수
function checkAndAddButtonListeners() {
    const buttons = document.querySelectorAll('.add-to-schedule-btn');
    console.log(`[Button Listener] ${buttons.length}개의 + 버튼 발견됨`);
    
    buttons.forEach((button, index) => {
        if (!button.hasAttribute('data-listener-added')) {
            console.log(`[Button Listener] #${index + 1} 버튼에 이벤트 리스너 추가 중...`);
            
            // 이벤트 리스너 추가
            button.onclick = function(event) {
                event.stopPropagation();
                
                // parentElement에서 장소명 추출
                const placeElement = button.parentElement;
                const placeName = placeElement.textContent.replace('+', '').trim();
                
                console.log(`+ 버튼 클릭됨! 장소명: "${placeName}"`);
                displaySystemMessage(`"${placeName}" 장소를 일정에 추가하려고 시도 중...`);
                
                // 현재 세션의 날짜 정보 가져오기
                let currentDate = new Date().toISOString().split('T')[0]; // 기본값 오늘
                
                try {
                    // 채팅 세션 날짜 있으면 사용
                    const chatSession = getCurrentChatSession();
                    if (chatSession && chatSession.date) {
                        currentDate = chatSession.date;
                        console.log(`채팅 세션 날짜 사용: ${currentDate}`);
                    } else {
                        console.log(`채팅 세션 날짜 없음, 오늘 날짜 사용: ${currentDate}`);
                    }
                    
                    // 버튼의 dataset에서 추출한 정보 가져오기
                    const placeLocation = button.dataset.placeLocation || '정보 없음';
                    const placeCategory = button.dataset.placeCategory || '정보 없음';
                    const placeReason = button.dataset.placeReason || '정보 없음';
                    const placeType = button.dataset.placeType || 'general';
                    
                    // URL 또는 이벤트 일시 정보
                    let placeUrl = button.dataset.placeUrl || '정보 없음';
                    
                    // 이벤트인 경우 eventDate 데이터 속성이 있으면 사용
                    if (placeType === 'event' && button.dataset.eventDate) {
                        placeUrl = button.dataset.eventDate; // 이벤트 일시로 덮어쓰기
                        console.log(`이벤트 일시 정보 사용: ${placeUrl}`);
                    }
                    
                    console.log(`장소 데이터:`, {
                        date: currentDate,
                        name: placeName,
                        location: placeLocation,
                        category: placeCategory,
                        reason: placeReason,
                        url: placeUrl,
                        type: placeType,
                        eventDate: button.dataset.eventDate || '없음'
                    });
                    
                    // 실제 일정 추가 함수 호출 - 추출한 정보 전달
                    addPlaceToSchedule(
                        currentDate, 
                        placeName, 
                        placeLocation, 
                        placeCategory, 
                        placeReason, 
                        placeUrl, 
                        placeType
                    );
                    
                } catch (error) {
                    console.error('일정 추가 중 오류 발생:', error);
                    displaySystemMessage(`오류: ${error.message}`);
                    alert(`일정 추가 중 오류가 발생했습니다: ${error.message}`);
                }
                
                return false;
            };
            
            // 이벤트 리스너가 추가되었음을 표시
            button.setAttribute('data-listener-added', 'true');
            button.style.backgroundColor = '#ff6f00'; // 표시용 색상 변경
            
            console.log(`[Button Listener] #${index + 1} 버튼에 이벤트 리스너 추가 완료`);
        }
    });
}

// 페이지 로드 시 및 주기적으로 버튼 리스너 체크
document.addEventListener('DOMContentLoaded', function() {
    console.log('DOMContentLoaded 이벤트 발생 - 버튼 리스너 체크 시작');
    
    // 초기 실행
    checkAndAddButtonListeners();
    
    // 주기적으로 체크 (새 메시지가 추가될 때 버튼도 추가될 수 있으므로)
    setInterval(checkAndAddButtonListeners, 1000);
}); 