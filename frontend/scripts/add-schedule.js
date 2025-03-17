const BACKEND_BASE_URL = 'http://localhost:8000';

// 페이지 로드 시 실행
document.addEventListener('DOMContentLoaded', () => {
    console.log('페이지 로드됨, 초기화 시작');
    
    // 로그인 상태 확인
    if (!checkLoginStatus()) {
        console.log('로그인 상태 확인 실패, 로그인 페이지로 리다이렉트');
        return;
    }
    console.log('로그인 상태 확인 성공');
    
    // 버튼 존재 여부 확인
    const saveBtn = document.querySelector('.save-btn');
    const submitBtn = document.querySelector('.submit-btn');
    console.log('저장 버튼 존재 여부:', saveBtn ? '있음' : '없음');
    console.log('캘린더로 이동 버튼 존재 여부:', submitBtn ? '있음' : '없음');
    
    // URL에서 날짜 파라미터 가져오기
    const urlParams = new URLSearchParams(window.location.search);
    const dateParam = urlParams.get('date');
    console.log('URL 파라미터 확인:', urlParams.toString());
    
    if (dateParam) {
        console.log('URL에서 받은 날짜 파라미터:', dateParam);
        // 날짜 파싱 (ISO 형식이 아닐 수 있으므로 직접 파싱)
        const dateParts = dateParam.split('-');
        if (dateParts.length === 3) {
            const year = parseInt(dateParts[0], 10);
            const month = parseInt(dateParts[1], 10) - 1; // JavaScript의 월은 0부터 시작
            const day = parseInt(dateParts[2], 10);
            const selectedDate = new Date(year, month, day);
            
            if (!isNaN(selectedDate.getTime())) {
                // 유효한 날짜인 경우
                console.log('파싱된 날짜:', formatLocalDate(selectedDate));
                // 날짜 표시 업데이트
                updateDateDisplay(selectedDate);
                // 미니 캘린더 생성
                initializeMiniCalendar(selectedDate);
                return;
            }
        }
        
        // 날짜 파싱 실패시 fallback
        updateDateDisplay(dateParam);
        try {
            initializeMiniCalendar(new Date(dateParam));
        } catch (e) {
            console.error('날짜 파싱 오류:', e);
        }
    } else {
        // 날짜 파라미터가 없으면 오늘 날짜 사용
        const today = new Date();
        const dateStr = formatLocalDate(today);
        console.log('오늘 날짜 사용:', dateStr);
        updateDateDisplay(today);
        initializeMiniCalendar(today);
    }
    
    // 로그아웃 이벤트 리스너 설정
    setupNavLinks();
    
    // 폼 제출 이벤트 리스너 설정
    setupForm();
});

// 로그인 상태 확인 함수
function checkLoginStatus() {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
        // 비로그인 상태: 로그인 페이지로 리다이렉트
        window.location.replace('login.html');
        return false;
    }
    return true;
}

// 날짜 문자열 생성 함수 (YYYY-MM-DD) - 로컬 시간대 기준
function formatLocalDate(date) {
    const year = date.getFullYear();
    const month = (date.getMonth() + 1).toString().padStart(2, '0');
    const day = date.getDate().toString().padStart(2, '0');
    return `${year}-${month}-${day}`;
}

// 미니 캘린더 초기화 함수
function initializeMiniCalendar(selectedDate) {
    const miniCalendar = document.querySelector('.mini-calendar');
    if (!miniCalendar) return;
    
    // 기존 캘린더 내용 제거
    miniCalendar.innerHTML = '';
    
    const currentMonth = selectedDate.getMonth();
    const currentYear = selectedDate.getFullYear();
    
    const firstDay = new Date(currentYear, currentMonth, 1);
    const lastDay = new Date(currentYear, currentMonth + 1, 0);
    const startingDay = firstDay.getDay();
    const monthLength = lastDay.getDate();

    // Create calendar grid
    const calendarGrid = document.createElement('div');
    calendarGrid.className = 'calendar-grid';
    calendarGrid.style.display = 'grid';
    calendarGrid.style.gridTemplateColumns = 'repeat(7, 1fr)';
    calendarGrid.style.gap = '5px';
    calendarGrid.style.marginTop = '10px';

    // Add weekday headers
    const weekdays = ['일', '월', '화', '수', '목', '금', '토'];
    weekdays.forEach(day => {
        const dayHeader = document.createElement('div');
        dayHeader.textContent = day;
        dayHeader.className = 'calendar-header';
        dayHeader.style.textAlign = 'center';
        dayHeader.style.fontSize = '14px';
        dayHeader.style.fontWeight = 'bold';
        calendarGrid.appendChild(dayHeader);
    });

    // Add empty cells
    for (let i = 0; i < startingDay; i++) {
        const emptyDay = document.createElement('div');
        emptyDay.className = 'calendar-day empty';
        calendarGrid.appendChild(emptyDay);
    }

    // Add days
    for (let day = 1; day <= monthLength; day++) {
        const dayElement = document.createElement('div');
        dayElement.textContent = day;
        dayElement.className = 'calendar-day';
        dayElement.style.textAlign = 'center';
        dayElement.style.padding = '5px';
        dayElement.style.borderRadius = '50%';
        dayElement.style.cursor = 'pointer';
        
        // 선택된 날짜 하이라이트
        if (day === selectedDate.getDate()) {
            dayElement.style.backgroundColor = '#bbdefb';
            dayElement.style.fontWeight = 'bold';
        }
        
        // 날짜 클릭 이벤트
        dayElement.addEventListener('click', () => {
            // 날짜 생성 (UTC 변환 없이 로컬 날짜 유지)
            const newDate = new Date(currentYear, currentMonth, day);
            // ISO 문자열 대신 로컬 날짜 형식 사용
            const dateStr = formatLocalDate(newDate);
            console.log(`선택된 날짜: ${day}일, 변환된 날짜 문자열: ${dateStr}`);
            window.location.href = `add-schedule.html?date=${dateStr}`;
        });
        
        calendarGrid.appendChild(dayElement);
    }

    miniCalendar.appendChild(calendarGrid);
}

// 날짜 표시 업데이트 함수
function updateDateDisplay(date) {
    // Date 객체가 아니면 변환 시도
    if (!(date instanceof Date)) {
        console.log('Date 객체가 아닌 입력:', date);
        try {
            date = new Date(date);
        } catch (e) {
            console.error('날짜 변환 실패:', e);
            return;
        }
    }
    
    if (!isNaN(date.getTime())) {
        const weekdays = ['일요일', '월요일', '화요일', '수요일', '목요일', '금요일', '토요일'];
        const year = date.getFullYear();
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const day = date.getDate().toString().padStart(2, '0');
        const weekday = weekdays[date.getDay()];
        
        const formattedDate = `${year}.${month}.${day} ${weekday} ⭐`;
        console.log('표시할 날짜:', formattedDate);
        const selectedDateElement = document.querySelector('.selected-date');
        if (selectedDateElement) {
            selectedDateElement.textContent = formattedDate;
        }
        
        // 미니 캘린더 월 제목 업데이트
        const monthTitleElement = document.querySelector('.month-title');
        if (monthTitleElement) {
            const months = ['January', 'February', 'March', 'April', 'May', 'June', 
                           'July', 'August', 'September', 'October', 'November', 'December'];
            monthTitleElement.textContent = `${months[date.getMonth()]} ${year}`;
        }
    } else {
        console.error('유효하지 않은 날짜:', date);
    }
}

// 네비게이션 링크 설정
function setupNavLinks() {
    // 로그아웃 링크
    const logoutLink = document.querySelector('nav a[href="#"]');
    if (logoutLink && logoutLink.textContent.includes('Logout')) {
        logoutLink.addEventListener('click', (e) => {
            e.preventDefault();
            logout();
        });
    }
}

// 폼 제출 이벤트 설정
function setupForm() {
    // 저장하기 버튼 - DB에 저장하되 페이지 유지
    const saveBtn = document.querySelector('.save-btn');
    if (saveBtn) {
        console.log('저장 버튼 이벤트 리스너 등록됨');
        saveBtn.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('저장 버튼 클릭됨');
            // 버튼에 즉각적인 시각적 피드백 제공
            saveBtn.style.backgroundColor = '#e3f2fd';
            saveScheduleToDB(); // DB에 저장 함수 호출
        });
    } else {
        console.error('저장 버튼을 찾을 수 없음');
    }
    
    // 일정 생성하기 버튼 - DB에 저장하고 캘린더 페이지로 이동
    const submitBtn = document.querySelector('.submit-btn');
    if (submitBtn) {
        submitBtn.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('캘린더로 이동 버튼 클릭됨');
            submitSchedule();
        });
    } else {
        console.error('제출 버튼을 찾을 수 없음');
    }
}

// Django 형식의 날짜 문자열로 변환 (YYYY-MM-DD)
function formatDateForDjango(dateStr) {
    // 이미 올바른 형식이면 그대로 반환
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
        return dateStr;
    }
    
    // 날짜 파싱 (ISO 형식이 아닐 수 있으므로 직접 파싱)
    const dateParts = dateStr.split('-');
    if (dateParts.length === 3) {
        const year = parseInt(dateParts[0], 10);
        const month = parseInt(dateParts[1], 10) - 1; // JavaScript의 월은 0부터 시작
        const day = parseInt(dateParts[2], 10);
        const parsedDate = new Date(year, month, day);
        
        if (!isNaN(parsedDate.getTime())) {
            // 유효한 날짜인 경우, 로컬 날짜 형식으로 반환
            return formatLocalDate(parsedDate);
        }
    }
    
    // 다른 형식이라면 Date 객체를 통해 변환
    try {
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) {
            throw new Error('유효하지 않은 날짜');
        }
        // toISOString 대신 formatLocalDate 사용
        return formatLocalDate(date);
    } catch (error) {
        console.error('날짜 형식 변환 실패:', error);
        return dateStr; // 변환 실패 시 원본 반환
    }
}

// DB 저장 함수 - 현재 페이지에서 일정 저장
async function saveScheduleToDB() {
    console.log('saveScheduleToDB 함수 실행 시작');
    
    // URL에서 날짜 파라미터 가져오기
    const urlParams = new URLSearchParams(window.location.search);
    const dateParam = urlParams.get('date');
    
    if (!dateParam) {
        console.error('날짜 파라미터가 없음');
        alert('날짜 정보가 없습니다.');
        return;
    }
    
    // Django 형식으로 날짜 변환
    const date = formatDateForDjango(dateParam);
    console.log('저장 요청 날짜 (원본):', dateParam, '변환된 날짜:', date);
    
    const location = document.getElementById('location').value;
    const companion = document.getElementById('companion').value;
    const memo = document.getElementById('memo').value;
    
    console.log('입력값 확인:', { location, companion, memo });
    
    // 필수 필드 검증
    if (!location) {
        console.error('장소가 입력되지 않음');
        alert('장소를 입력해주세요.');
        document.getElementById('location').focus();
        return;
    }
    
    // 저장 버튼 비활성화 및 로딩 표시
    const saveBtn = document.querySelector('.save-btn');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = '저장 중...';
        console.log('저장 버튼 비활성화 및 로딩 표시');
    }
    
    try {
        // 요청 데이터 준비
        const scheduleData = {
            date: date,
            location: location,
            companion: companion || '', // 빈 문자열로 기본값 설정
            memo: memo || ''           // 빈 문자열로 기본값 설정
        };
        
        console.log('요청 데이터:', JSON.stringify(scheduleData, null, 2));
        
        // 헤더 출력 (디버깅용)
        const accessToken = localStorage.getItem('access_token');
        console.log('인증 토큰:', accessToken ? '있음' : '없음');
        if (!accessToken) {
            console.error('인증 토큰이 없습니다. 다시 로그인해주세요.');
            alert('인증 토큰이 없습니다. 다시 로그인해주세요.');
            window.location.replace('login.html');
            return;
        }
        
        // DB에 저장 (서버 API 호출)
        // 백엔드 API 경로 확인
        const apiUrl = `${BACKEND_BASE_URL}/calendar/schedules/`;
        console.log('API 요청 URL:', apiUrl);
        console.log('API 요청 시작...');
        
        try {
            // 개발자 도구(F12)를 열고 네트워크 탭에서 요청을 확인하세요
            console.log('fetch 요청 보내는 중...');
            
            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${accessToken}`
                },
                body: JSON.stringify(scheduleData),
                mode: 'cors',
                credentials: 'include'  // 쿠키 포함하여 CORS 요청 (필요한 경우)
            });
            
            // 응답 상태 코드 및 헤더 출력 (디버깅용)
            console.log('API 응답 받음');
            console.log('응답 상태 코드:', response.status);
            console.log('응답 상태 텍스트:', response.statusText);
            console.log('응답 헤더:', [...response.headers].map(h => `${h[0]}: ${h[1]}`).join(', '));
            
            // 응답 텍스트 확인 (디버깅용)
            const responseText = await response.text();
            console.log('응답 본문:', responseText);
            
            if (response.status === 401) {
                // 인증 실패 시 로그인 페이지로 리다이렉트
                console.error('인증 실패 (401)');
                localStorage.removeItem('access_token');
                localStorage.removeItem('refresh_token');
                localStorage.removeItem('username');
                alert('세션이 만료되었습니다. 다시 로그인해주세요.');
                window.location.replace('login.html');
                return;
            }
            
            if (response.status === 404) {
                console.error('API 엔드포인트를 찾을 수 없습니다:', apiUrl);
                throw new Error(`API 엔드포인트를 찾을 수 없습니다. 서버 설정을 확인하세요 (404 Not Found).`);
            }
            
            if (response.status === 500) {
                console.error('서버 내부 오류:', apiUrl);
                throw new Error(`서버 내부 오류가 발생했습니다. 데이터베이스 연결이나 서버 로그를 확인하세요 (500 Internal Server Error).`);
            }
            
            if (!response.ok) {
                // 응답 텍스트를 JSON으로 파싱 시도
                console.error('서버 오류 응답:', response.status);
                let errorMessage = '서버 오류';
                try {
                    const errorData = JSON.parse(responseText);
                    errorMessage = errorData.detail || errorData.message || JSON.stringify(errorData);
                    console.error('오류 데이터:', errorData);
                } catch (parseError) {
                    console.error('JSON 파싱 오류:', parseError);
                    errorMessage = responseText || '서버 오류';
                }
                throw new Error(errorMessage);
            }
            
            // 성공 피드백
            console.log('일정 저장 성공');
            showSuccessMessage('일정이 DB에 저장되었습니다.');
            
            // 응답 데이터 (생성된 일정 정보)
            let savedData;
            try {
                if (responseText.trim()) {
                    savedData = JSON.parse(responseText);
                    console.log('저장된 일정:', savedData);
                    // 일정 저장 성공 후 폼 초기화 (선택 사항)
                    // document.getElementById('location').value = '';
                    // document.getElementById('companion').value = '';
                    // document.getElementById('memo').value = '';
                } else {
                    console.log('응답이 비어 있음 (일정 저장은 성공)');
                }
            } catch (parseError) {
                console.warn('응답 데이터 파싱 실패:', parseError);
            }
        } catch (fetchError) {
            console.error('API 요청 실패:', fetchError);
            // 네트워크 오류인지 확인
            if (fetchError.name === 'TypeError' && fetchError.message.includes('NetworkError')) {
                console.error('네트워크 오류 감지됨');
                throw new Error(`서버 연결 실패: 백엔드 서버(${BACKEND_BASE_URL})가 실행 중인지 확인하세요.`);
            } else if (fetchError.name === 'TypeError' && fetchError.message.includes('Failed to fetch')) {
                console.error('서버 연결 실패');
                throw new Error(`서버 연결 실패: 백엔드 서버(${BACKEND_BASE_URL})가 실행 중인지 확인하고, CORS 설정이 올바른지 확인하세요.`);
            } else {
                throw new Error(`API 요청 실패: ${fetchError.message}`);
            }
        }
        
    } catch (error) {
        console.error('일정 저장 오류:', error);
        // 오류 메시지에 대한 상세 정보 출력
        console.error('오류 유형:', error.name);
        console.error('오류 메시지:', error.message);
        console.error('오류 스택:', error.stack);
        
        // 사용자에게 친절한 오류 메시지 표시
        let userMessage = '일정 저장 실패';
        if (error.message.includes('서버 연결 실패')) {
            userMessage = `${error.message}\n\n백엔드 서버가 실행 중인지 확인하세요.`;
        } else if (error.message.includes('API 엔드포인트를 찾을 수 없습니다')) {
            userMessage = `일정 저장 API를 찾을 수 없습니다. 서버 관리자에게 문의하세요.`;
        } else if (error.message.includes('서버 내부 오류')) {
            userMessage = `서버 내부 오류가 발생했습니다. 서버 관리자에게 문의하세요.`;
        } else {
            userMessage = `${userMessage}: ${error.message || '서버 통신 중 오류가 발생했습니다.'}`;
        }
        
        console.error('사용자에게 표시할 오류 메시지:', userMessage);
        alert(userMessage);
    } finally {
        // 저장 버튼 원래 상태로 복원
        const saveBtn = document.querySelector('.save-btn');
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.textContent = '현재 페이지에서 저장';
            saveBtn.style.backgroundColor = ''; // 원래 스타일로 복원
            console.log('저장 버튼 상태 복원');
        }
    }
}

// 성공 메시지 표시 함수
function showSuccessMessage(message) {
    // 기존 메시지가 있으면 제거
    const existingMsg = document.querySelector('.success-message');
    if (existingMsg) {
        existingMsg.remove();
    }
    
    // 새 메시지 생성
    const msgElement = document.createElement('div');
    msgElement.className = 'success-message';
    msgElement.textContent = message;
    msgElement.style.backgroundColor = '#e8f5e9';
    msgElement.style.color = '#2e7d32';
    msgElement.style.padding = '10px 15px';
    msgElement.style.borderRadius = '4px';
    msgElement.style.marginTop = '10px';
    msgElement.style.marginBottom = '15px';
    msgElement.style.fontSize = '14px';
    msgElement.style.fontWeight = '500';
    msgElement.style.boxShadow = '0 2px 4px rgba(0,0,0,0.1)';
    msgElement.style.transition = 'opacity 0.5s ease';
    msgElement.style.display = 'flex';
    msgElement.style.alignItems = 'center';
    msgElement.style.justifyContent = 'space-between';
    
    // 체크 아이콘 추가
    const checkIcon = document.createElement('span');
    checkIcon.innerHTML = '✓';
    checkIcon.style.marginRight = '10px';
    checkIcon.style.fontSize = '18px';
    checkIcon.style.fontWeight = 'bold';
    
    // 메시지 텍스트 컨테이너
    const textContainer = document.createElement('div');
    textContainer.textContent = message;
    textContainer.style.flex = '1';
    
    // 닫기 버튼
    const closeButton = document.createElement('span');
    closeButton.innerHTML = '×';
    closeButton.style.cursor = 'pointer';
    closeButton.style.marginLeft = '10px';
    closeButton.style.fontSize = '18px';
    closeButton.style.fontWeight = 'bold';
    closeButton.onclick = () => {
        msgElement.style.opacity = '0';
        setTimeout(() => msgElement.remove(), 500);
    };
    
    // 요소들 추가
    msgElement.appendChild(checkIcon);
    msgElement.appendChild(textContainer);
    msgElement.appendChild(closeButton);
    
    // 버튼 그룹 위에 삽입
    const buttonGroup = document.querySelector('.button-group');
    if (buttonGroup) {
        buttonGroup.parentNode.insertBefore(msgElement, buttonGroup);
    } else {
        // 버튼 그룹이 없으면 폼 끝에 추가
        const formContainer = document.querySelector('.schedule-details');
        if (formContainer) {
            formContainer.appendChild(msgElement);
        } else {
            // 폼 컨테이너도 없으면 body에 추가
            document.body.appendChild(msgElement);
        }
    }
    
    // 5초 후 메시지 사라지게 하기
    setTimeout(() => {
        if (msgElement.parentNode) {  // 이미 닫히지 않았다면
            msgElement.style.opacity = '0';
            setTimeout(() => {
                if (msgElement.parentNode) {  // 이중 체크
                    msgElement.remove();
                }
            }, 500);
        }
    }, 5000);
}

// 일정 제출 함수 - 저장 후 캘린더로 이동
async function submitSchedule() {
    const location = document.getElementById('location').value;
    const companion = document.getElementById('companion').value;
    const memo = document.getElementById('memo').value;
    
    // URL에서 날짜 파라미터 가져오기
    const urlParams = new URLSearchParams(window.location.search);
    const dateParam = urlParams.get('date');
    
    if (!dateParam) {
        alert('날짜 정보가 없습니다.');
        return;
    }
    
    // Django 형식으로 날짜 변환
    const date = formatDateForDjango(dateParam);
    console.log('제출 요청 날짜 (원본):', dateParam, '변환된 날짜:', date);
    
    // 필수 필드 검증
    if (!location) {
        alert('장소를 입력해주세요.');
        document.getElementById('location').focus();
        return;
    }
    
    // 버튼 비활성화 및 로딩 표시
    const submitBtn = document.querySelector('.submit-btn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = '저장 중...';
    }
    
    try {
        // 요청 데이터 준비
        const scheduleData = {
            date: date,
            location: location,
            companion: companion || '', // 빈 문자열로 기본값 설정
            memo: memo || ''           // 빈 문자열로 기본값 설정
        };
        
        console.log('요청 데이터:', JSON.stringify(scheduleData, null, 2));
        console.log('인증 토큰:', localStorage.getItem('access_token') ? '있음' : '없음');
        console.log('API 요청 URL:', `${BACKEND_BASE_URL}/calendar/schedules/`);
        
        const response = await fetch(`${BACKEND_BASE_URL}/calendar/schedules/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify(scheduleData)
        });
        
        // 응답 상태 코드 및 헤더 출력 (디버깅용)
        console.log('응답 상태 코드:', response.status);
        console.log('응답 상태 텍스트:', response.statusText);
        console.log('응답 헤더:', [...response.headers].map(h => `${h[0]}: ${h[1]}`).join(', '));
        
        // 응답 텍스트 확인 (디버깅용)
        const responseText = await response.text();
        console.log('응답 본문:', responseText);
        
        if (response.status === 401) {
            // 인증 실패 시 로그인 페이지로 리다이렉트
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            localStorage.removeItem('username');
            alert('세션이 만료되었습니다. 다시 로그인해주세요.');
            window.location.replace('login.html');
            return;
        }
        
        if (!response.ok) {
            // 응답 텍스트를 JSON으로 파싱 시도
            let errorMessage = '서버 오류';
            try {
                const errorData = JSON.parse(responseText);
                errorMessage = errorData.detail || errorData.message || JSON.stringify(errorData);
                console.error('오류 데이터:', errorData);
            } catch (parseError) {
                console.error('JSON 파싱 오류:', parseError);
                errorMessage = responseText || '서버 오류';
            }
            alert(`일정 생성 실패: ${errorMessage}`);
            return;
        }
        
        // 성공 알림 후 캘린더 페이지로 이동
        alert('일정이 성공적으로 생성되었습니다.');
        window.location.href = 'calendar.html';
        
    } catch (error) {
        console.error('일정 제출 오류:', error);
        alert('서버 통신 중 오류가 발생했습니다.');
    } finally {
        // 버튼 원래 상태로 복원
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = '저장 후 캘린더로 이동';
        }
    }
}

// 로그아웃 함수
async function logout() {
    try {
        const refreshToken = localStorage.getItem('refresh_token');
        const accessToken = localStorage.getItem('access_token');
        
        if (refreshToken && accessToken) {
            try {
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
        // 로컬 스토리지에서 토큰 제거
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('username');
        
        alert('로그아웃 되었습니다.');
        window.location.replace('login.html');
    }
} 