// 상수 정의
const BACKEND_BASE_URL = 'http://localhost:8000'; // 백엔드 기본 URL
const ACCESS_TOKEN_KEY = 'access_token'; // 로컬 스토리지에 저장된 토큰 키 이름
const USERNAME_KEY = 'username';

// 전역 상태 플래그 초기화
window.isProcessingDelete = false; // 일정 삭제 처리 중인지 여부 (기존 플래그)
window.deleteInProgress = false;   // 새로운 삭제 진행 중 플래그

// 개발용 디버깅 초기화
console.log('[디버그-초기화] 스크립트 로드 시작');
console.log('[디버그-초기화] BACKEND_BASE_URL:', BACKEND_BASE_URL);
console.log('[디버그-초기화] ACCESS_TOKEN_KEY:', ACCESS_TOKEN_KEY);
console.log('[디버그-초기화] 저장된 토큰:', localStorage.getItem(ACCESS_TOKEN_KEY));

// 전역 변수로 요청 중 상태 관리
let isSubmitting = false;

// 페이지 로드 시 실행
document.addEventListener('DOMContentLoaded', () => {
    console.log('페이지 로드됨, 초기화 시작');
    
    // 로그인 상태 확인
    if (!checkLoginStatus()) {
        console.log('로그인 상태 확인 실패, 로그인 페이지로 리다이렉트');
        return;
    }
    console.log('로그인 상태 확인 성공');
    
    // 네비게이션 링크 설정 (로그아웃 기능 등록)
    setupNavLinks();
    console.log('네비게이션 링크 설정 완료');
    
    // with Who? 입력 필드를 카테고리 선택 태그로 변경
    const companionInput = document.getElementById('companion');
    if (companionInput) {
        const companionLabel = companionInput.parentNode.querySelector('label');
        const selectElement = document.createElement('select');
        selectElement.id = 'companion';
        selectElement.name = 'companion';
        
        // 카테고리 옵션 추가
        const categories = ['', '친구', '가족', '연인', '혼자'];
        categories.forEach(category => {
            const option = document.createElement('option');
            option.value = category;
            option.textContent = category || '선택하세요';
            selectElement.appendChild(option);
        });
        
        // 기존 입력 필드 대체
        companionInput.parentNode.replaceChild(selectElement, companionInput);
        
        // 라벨 텍스트 업데이트
        if (companionLabel) {
            companionLabel.textContent = 'with Who? (카테고리)';
        }
        
        console.log('with Who? 입력 필드를 카테고리 선택 태그로 변경 완료');
    }
    
    // 버튼 존재 여부 확인
    const saveBtn = document.querySelector('.save-btn');
    const submitBtn = document.querySelector('.submit-btn');
    const deleteBtn = document.querySelector('.delete-btn');
    console.log('저장 버튼 존재 여부:', saveBtn ? '있음' : '없음');
    console.log('캘린더로 이동 버튼 존재 여부:', submitBtn ? '있음' : '없음');
    console.log('삭제 버튼 존재 여부:', deleteBtn ? '있음' : '없음');
    
    // 디버깅용 메시지 표시
    showInfoMessage('페이지가 로드되었습니다. 테스트를 위한 메시지입니다.');
    
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
                // 해당 날짜에 저장된 일정 불러오기
                fetchScheduleForDate(dateParam);
                return;
            }
        }
        
        // 날짜 파싱 실패시 fallback
        updateDateDisplay(dateParam);
        try {
            initializeMiniCalendar(new Date(dateParam));
            // 해당 날짜에 저장된 일정 불러오기
            fetchScheduleForDate(dateParam);
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
        // 오늘 날짜의 일정 불러오기
        fetchScheduleForDate(dateStr);
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
    console.log('[디버그] 미니 캘린더 초기화 시작, 선택된 날짜:', selectedDate);
    const miniCalendar = document.querySelector('.mini-calendar');
    if (!miniCalendar) {
        console.error('[디버그] .mini-calendar 요소를 찾을 수 없습니다.');
        return;
    }
    
    // 기존 캘린더 내용 제거
    miniCalendar.innerHTML = '';
    
    try {
        const currentMonth = selectedDate.getMonth();
        const currentYear = selectedDate.getFullYear();
        
        console.log('[디버그] 캘린더 표시 - 연도:', currentYear, '월:', currentMonth + 1);
        
        // 월 제목 추가
        const monthTitle = document.querySelector('.month-title');
        if (monthTitle) {
            const months = ['January', 'February', 'March', 'April', 'May', 'June', 
                           'July', 'August', 'September', 'October', 'November', 'December'];
            monthTitle.textContent = `${months[currentMonth]} ${currentYear}`;
        }
        
        const firstDay = new Date(currentYear, currentMonth, 1);
        const lastDay = new Date(currentYear, currentMonth + 1, 0);
        const startingDay = firstDay.getDay();
        const monthLength = lastDay.getDate();

        // Create calendar grid
        const calendarGrid = document.createElement('div');
        calendarGrid.className = 'calendar-grid';
        
        // Add weekday headers
        const weekdays = ['일', '월', '화', '수', '목', '금', '토'];
        weekdays.forEach(day => {
            const dayHeader = document.createElement('div');
            dayHeader.textContent = day;
            dayHeader.className = 'calendar-header';
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
            
            // 선택된 날짜 하이라이트
            if (day === selectedDate.getDate()) {
                dayElement.classList.add('selected');
            }
            
            // 날짜 클릭 이벤트
            dayElement.addEventListener('click', () => {
                // 날짜 생성 (UTC 변환 없이 로컬 날짜 유지)
                const newDate = new Date(currentYear, currentMonth, day);
                // ISO 문자열 대신 로컬 날짜 형식 사용
                const dateStr = formatLocalDate(newDate);
                console.log(`[디버그] 미니 캘린더에서 선택된 날짜: ${day}일, 변환된 날짜 문자열: ${dateStr}`);
                window.location.href = `add-schedule.html?date=${dateStr}`;
            });
            
            calendarGrid.appendChild(dayElement);
        }

        miniCalendar.appendChild(calendarGrid);
        console.log('[디버그] 미니 캘린더 초기화 완료');
    } catch (error) {
        console.error('[디버그] 미니 캘린더 초기화 오류:', error);
    }
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
    console.log('[디버그] setupNavLinks 함수 실행');
    
    // 로그아웃 링크 (id 기반으로 찾기)
    const logoutLink = document.querySelector('#logoutLink');
    console.log('[디버그] 로그아웃 링크 요소:', logoutLink);
    
    if (logoutLink) {
        logoutLink.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('[디버그] 로그아웃 링크 클릭됨');
            logout();
        });
    } else {
        console.error('[디버그] 로그아웃 링크를 찾을 수 없습니다. (#logoutLink)');
    }
}

// 폼 제출 이벤트 설정
function setupForm() {
    console.log('[디버그] setupForm 함수 실행 시작');
    
    // 날짜 표시
    displayDate();
    
    // 모든 버튼 이벤트 디버깅
    document.querySelectorAll('button').forEach(btn => {
        console.log('[디버그] 발견된 버튼:', btn.className, btn.textContent);
    });
    
    // 이벤트 리스너는 HTML에서 관리하므로 여기서는 등록하지 않고 디버깅 정보만 출력
    const saveBtn = document.querySelector('.save-btn');
    const submitBtn = document.querySelector('.submit-btn');
    const deleteBtn = document.querySelector('.delete-btn');
    
    console.log('[디버그] 저장 버튼 존재 여부:', !!saveBtn);
    console.log('[디버그] 제출 버튼 존재 여부:', !!submitBtn);
    console.log('[디버그] 삭제 버튼 존재 여부:', !!deleteBtn);
    
    // 일정 로드
    loadSchedule();
    
    console.log('[디버그] setupForm 완료');
}

// 이벤트 핸들러 함수들
function handleSave(e) {
    e.preventDefault();
    console.log('[디버그] 저장 버튼 클릭됨 (handleSave)');
    saveScheduleToDB();
}

function handleSubmit(e) {
    e.preventDefault();
    console.log('[디버그] 캘린더로 이동 버튼 클릭됨 (handleSubmit)');
    submitSchedule();
}

function handleDelete(e) {
    e.preventDefault();
    console.log('[디버그] 삭제 버튼 클릭됨 (handleDelete)');
    try {
        console.log('[디버그] window.deleteSchedule 호출 시도 (handleDelete에서)');
        console.log('[디버그] window.deleteSchedule 타입:', typeof window.deleteSchedule);
        
        // 전역 함수 호출
        if (typeof window.deleteSchedule === 'function') {
            window.deleteSchedule();
        } else {
            console.error('[디버그] window.deleteSchedule 함수를 찾을 수 없음');
            alert('일정 삭제 기능을 불러올 수 없습니다. 페이지를 새로고침 해주세요.');
        }
    } catch (error) {
        console.error('[디버그] 삭제 함수 호출 중 오류:', error);
        alert('일정 삭제 중 오류가 발생했습니다.');
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

// DB 저장 함수 - 현재 페이지에서 일정 저장 (수정 또는 생성)
async function saveScheduleToDB() {
    console.log('saveScheduleToDB 함수 실행 시작');
    
    // 이미 요청 중이면 중복 요청 방지
    if (isSubmitting) {
        console.warn('이미 요청 중입니다. 중복 요청을 방지합니다.');
        return;
    }
    
    // 요청 중 상태로 설정
    isSubmitting = true;
    
    // URL에서 날짜 파라미터 가져오기
    const urlParams = new URLSearchParams(window.location.search);
    const dateParam = urlParams.get('date');
    
    if (!dateParam) {
        console.error('날짜 파라미터가 없음');
        showErrorMessage('날짜 정보가 없습니다.');
        isSubmitting = false;
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
        showErrorMessage('장소를 입력해주세요.');
        document.getElementById('location').focus();
        isSubmitting = false;
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
            showErrorMessage('인증 토큰이 없습니다. 다시 로그인해주세요.');
            window.location.replace('login.html');
            return;
        }
        
        // 1. 먼저 해당 날짜에 일정이 있는지 확인
        console.log('기존 일정 확인 중...');
        
        try {
            // 기존 일정 조회
            const getResponse = await fetch(`${BACKEND_BASE_URL}/calendar/schedules/?date=${date}`, {
                method: 'GET',
                headers: {
                    'Authorization': `Bearer ${accessToken}`
                }
            });
            
            if (getResponse.status === 401) {
                throw new Error('인증 실패');
            }
            
            if (!getResponse.ok) {
                throw new Error('일정 조회 실패');
            }
            
            const schedules = await getResponse.json();
            console.log('조회된 일정:', schedules);
            
            // 정규화된 날짜로 비교
            const normalizedRequestDate = normalizeDate(date);
            
            // 해당 날짜와 일치하는 일정만 필터링
            const matchingSchedules = schedules.filter(item => {
                const itemDate = normalizeDate(item.date);
                return itemDate === normalizedRequestDate;
            });
            
            let response;
            let method = 'POST';
            let apiUrl = `${BACKEND_BASE_URL}/calendar/schedules/`;
            let successMessage = '일정이 새로 저장되었습니다.';
            
            // 2. 일정이 있으면 PUT으로 업데이트, 없으면 POST로 생성
            if (matchingSchedules.length > 0) {
                const scheduleId = matchingSchedules[0].id;
                console.log('기존 일정 ID:', scheduleId, '업데이트 진행');
                
                method = 'PUT';
                apiUrl = `${BACKEND_BASE_URL}/calendar/schedules/${scheduleId}/`;
                successMessage = '일정이 업데이트되었습니다.';
            } else {
                console.log('일정 없음, 새로 생성');
            }
            
            // 저장 로직 실행
            console.log(`${method} 요청 URL:`, apiUrl);
            
            response = await fetch(apiUrl, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${accessToken}`
                },
                body: JSON.stringify(scheduleData)
            });
            
            // 응답 상태 코드 및 헤더 출력 (디버깅용)
            console.log('API 응답 받음');
            console.log('응답 상태 코드:', response.status);
            
            // 응답 텍스트 확인
            const responseText = await response.text();
            
            if (response.status === 401) {
                // 인증 실패 시 로그인 페이지로 리다이렉트
                console.error('인증 실패 (401)');
                localStorage.removeItem('access_token');
                localStorage.removeItem('refresh_token');
                localStorage.removeItem('username');
                showErrorMessage('세션이 만료되었습니다. 다시 로그인해주세요.');
                setTimeout(() => {
                    window.location.replace('login.html');
                }, 2000);
                return;
            }
            
            if (!response.ok) {
                // 오류 응답 처리
                console.error('서버 오류 응답:', response.status);
                let errorMessage = '서버 오류';
                try {
                    if (responseText) {
                        const errorData = JSON.parse(responseText);
                        errorMessage = errorData.detail || errorData.message || JSON.stringify(errorData);
                    }
                } catch (parseError) {
                    errorMessage = responseText || '서버 오류';
                }
                throw new Error(errorMessage);
            }
            
            // 성공 피드백
            console.log('일정 저장 성공');
            showSuccessMessage(successMessage);
            
            // 응답 데이터 (생성/업데이트된 일정 정보)
            try {
                if (responseText.trim()) {
                    const savedData = JSON.parse(responseText);
                    console.log('저장된 일정:', savedData);
                }
            } catch (parseError) {
                console.warn('응답 데이터 파싱 실패:', parseError);
            }
        } catch (fetchError) {
            throw fetchError;
        }
    } catch (error) {
        console.error('일정 저장 오류:', error);
        
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
        showErrorMessage(userMessage);
    } finally {
        // 저장 버튼 원래 상태로 복원
        const saveBtn = document.querySelector('.save-btn');
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.textContent = '현재 페이지에서 저장';
            saveBtn.style.backgroundColor = ''; // 원래 스타일로 복원
            console.log('저장 버튼 상태 복원');
        }
        
        // 요청 완료 상태로 설정
        isSubmitting = false;
    }
}

/**
 * 성공 메시지를 화면에 표시합니다
 * @param {string} message - 표시할 메시지
 */
function showSuccessMessage(message) {
    showMessage(message, 'success');
}

/**
 * 정보 메시지를 화면에 표시합니다
 * @param {string} message - 표시할 메시지
 */
function showInfoMessage(message) {
    showMessage(message, 'info');
}

/**
 * 오류 메시지를 화면에 표시합니다
 * @param {string} message - 표시할 메시지
 */
function showErrorMessage(message) {
    showMessage(message, 'error');
}

/**
 * 메시지를 화면에 표시하는 공통 함수
 * @param {string} message - 표시할 메시지
 * @param {string} type - 메시지 타입 (success, info, error)
 */
function showMessage(message, type) {
    console.log(`[디버그] ${type} 메시지 표시: ${message}`);
    
    // 기존 같은 타입 메시지가 있으면 제거
    const existingMsg = document.querySelector(`.${type}-message`);
    if (existingMsg) {
        existingMsg.remove();
    }
    
    // 새 메시지 생성
    const msgElement = document.createElement('div');
    msgElement.className = `message ${type}-message`;
    
    // 아이콘 선택
    let icon = '';
    if (type === 'success') icon = '✅';
    else if (type === 'info') icon = 'ℹ️';
    else if (type === 'error') icon = '⚠️';
    
    // 아이콘 추가
    const iconElement = document.createElement('span');
    iconElement.innerHTML = icon;
    iconElement.className = 'message-icon';
    
    // 메시지 텍스트 컨테이너
    const textContainer = document.createElement('div');
    textContainer.textContent = message;
    textContainer.className = 'message-text';
    
    // 닫기 버튼
    const closeButton = document.createElement('span');
    closeButton.innerHTML = '×';
    closeButton.className = 'message-close';
    closeButton.onclick = () => {
        msgElement.style.opacity = '0';
        setTimeout(() => msgElement.remove(), 500);
    };
    
    // 요소들 추가
    msgElement.appendChild(iconElement);
    msgElement.appendChild(textContainer);
    msgElement.appendChild(closeButton);
    
    // 폼 상단에 메시지 삽입
    const formContainer = document.querySelector('.schedule-details');
    if (formContainer) {
        formContainer.prepend(msgElement);
    } else {
        // 폼 컨테이너가 없으면 body에 추가
        document.body.prepend(msgElement);
    }
    
    // 7초 후 메시지 사라지게 하기
    setTimeout(() => {
        if (msgElement.parentNode) {  // 이미 닫히지 않았다면
            msgElement.style.opacity = '0';
            setTimeout(() => {
                if (msgElement.parentNode) {  // 이중 체크
                    msgElement.remove();
                }
            }, 500);
        }
    }, 7000);
}

/**
 * 폼을 초기화하는 함수
 */
function resetForm() {
    console.log('[디버그] 폼 초기화');
    const locationInput = document.getElementById('location');
    const contentTextarea = document.getElementById('content');
    
    if (locationInput) locationInput.value = '';
    if (contentTextarea) contentTextarea.value = '';
}

// 일정 제출 함수 - 저장 후 캘린더로 이동
async function submitSchedule() {
    console.log('submitSchedule 함수 실행 시작');
    
    // 이미 요청 중이면 중복 요청 방지
    if (isSubmitting) {
        console.warn('이미 요청 중입니다. 중복 요청을 방지합니다.');
        return;
    }
    
    // 요청 중 상태로 설정
    isSubmitting = true;
    
    // 필수 데이터 확인
    const location = document.getElementById('location').value;
    if (!location) {
        showErrorMessage('장소를 입력해주세요.');
        document.getElementById('location').focus();
        return;
    }
    
    // 데이터 준비
    const urlParams = new URLSearchParams(window.location.search);
    const dateParam = urlParams.get('date');
    const companion = document.getElementById('companion').value || '';
    const memo = document.getElementById('memo').value || '';
    
    const scheduleData = {
        date: formatDateForDjango(dateParam || formatLocalDate(new Date())),
        location: location,
        companion: companion,
        memo: memo
    };
    
    try {
        // 데이터 저장 요청
        const accessToken = localStorage.getItem('access_token');
        if (!accessToken) {
            showErrorMessage('로그인이 필요합니다.');
            window.location.href = 'login.html';
            return;
        }
        
        // 서버에 데이터 저장 요청 (비동기)
        fetch(`${BACKEND_BASE_URL}/calendar/schedules/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            },
            body: JSON.stringify(scheduleData)
        }).then(response => {
            console.log('서버 응답 받음:', response.status);
        }).catch(error => {
            console.error('서버 요청 에러:', error);
        });
        
        // 저장 요청 후 바로 캘린더 페이지로 이동 (Home 버튼처럼)
        console.log('캘린더 페이지로 즉시 이동합니다.');
        
        // 방법 1: 직접 위치 변경 (헤더의 Home 버튼과 동일)
        window.location.href = 'calendar.html';
        
        // 방법 2: 홈 버튼을 프로그래밍적으로 클릭
        // 바로 이동되지 않을 경우를 대비하여 홈 버튼 클릭
        setTimeout(() => {
            const homeButton = document.querySelector('nav.main-nav a[href="calendar.html"]');
            if (homeButton) {
                console.log('Home 버튼을 프로그래밍적으로 클릭합니다.');
                homeButton.click();
            } else {
                // 방법 3: replace로 시도
                window.location.replace('calendar.html');
            }
        }, 100);
    } catch (error) {
        console.error('일정 제출 오류:', error);
    } finally {
        // 요청 완료 상태로 설정
        isSubmitting = false;
    }
}

// 로그아웃 함수
async function logout() {
    console.log('[디버그] 로그아웃 함수 시작');
    
    try {
        const refreshToken = localStorage.getItem('refresh_token');
        const accessToken = localStorage.getItem('access_token');
        
        // 로그아웃 API 호출 시도
        if (refreshToken && accessToken) {
            try {
                console.log('[디버그] 로그아웃 API 호출 시도');
                
                const response = await fetch(`${BACKEND_BASE_URL}/logout/`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${accessToken}`
                    },
                    body: JSON.stringify({
                        refresh: refreshToken
                    })
                });
                
                console.log('[디버그] 로그아웃 API 응답:', response.status);
                
                // 응답 상태 확인
                if (response.ok) {
                    console.log('[디버그] 로그아웃 API 호출 성공');
                } else {
                    console.warn('[디버그] 로그아웃 API 오류 응답:', response.status);
                }
            } catch (error) {
                console.error('[디버그] 로그아웃 API 호출 중 오류:', error);
            }
        } else {
            console.log('[디버그] 토큰이 없어 API 호출을 건너뜁니다.');
        }
    } catch (error) {
        console.error('[디버그] 로그아웃 처리 중 오류:', error);
    } finally {
        // 로컬 스토리지에서 토큰 제거 (항상 실행)
        console.log('[디버그] 로컬 스토리지 토큰 제거');
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('username');
        
        // 사용자에게 로그아웃 메시지 표시
        showInfoMessage('로그아웃 되었습니다.');
        
        // 약간의 지연 후 페이지 이동 (메시지 표시 시간 확보)
        console.log('[디버그] 로그인 페이지로 이동 준비');
        setTimeout(() => {
            console.log('[디버그] 로그인 페이지로 이동');
            window.location.href = 'login.html';
        }, 1500);
    }
}

// 특정 날짜의 일정 불러오기
async function fetchScheduleForDate(date) {
    console.log(`${date} 날짜의 일정을 불러오는 중...`);
    
    try {
        const accessToken = localStorage.getItem('access_token');
        if (!accessToken) {
            console.error('인증 토큰이 없습니다.');
            return;
        }
        
        // 백엔드 API 호출 (날짜 파라미터로 해당 날짜의 일정 조회)
        const apiUrl = `${BACKEND_BASE_URL}/calendar/schedules/?date=${date}`;
        console.log('API 요청 URL:', apiUrl);
        
        const response = await fetch(apiUrl, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${accessToken}`
            }
        });
        
        // 응답 상태 코드 확인
        console.log('응답 상태 코드:', response.status);
        
        if (response.status === 401) {
            console.error('인증 실패 (401)');
            localStorage.removeItem('access_token');
            localStorage.removeItem('refresh_token');
            localStorage.removeItem('username');
            showErrorMessage('세션이 만료되었습니다. 다시 로그인해주세요.');
            setTimeout(() => {
                window.location.replace('login.html');
            }, 2000);
            return;
        }
        
        if (!response.ok) {
            console.error('일정 조회 실패:', response.status);
            return;
        }
        
        // 응답 데이터 파싱
        const data = await response.json();
        console.log('일정 조회 결과:', data);
        
        // 날짜 비교를 위한 정규화된 날짜 문자열 생성
        const normalizedRequestDate = normalizeDate(date);
        console.log('요청한 정규화된 날짜:', normalizedRequestDate);
        
        // 해당 날짜와 일치하는 일정만 필터링
        const matchingSchedules = data.filter(item => {
            const itemDate = normalizeDate(item.date);
            console.log(`일정 데이터 날짜: ${item.date}, 정규화된 날짜: ${itemDate}`);
            return itemDate === normalizedRequestDate;
        });
        
        console.log('필터링된 일정:', matchingSchedules);
        
        // 일정이 있으면 폼에 데이터 채우기
        if (matchingSchedules && matchingSchedules.length > 0) {
            // 가장 최근 일정 사용 (같은 날짜에 여러 일정이 있을 경우 첫 번째 항목 사용)
            const schedule = matchingSchedules[0];
            console.log('표시할 일정:', schedule);
            
            // 폼 필드에 데이터 채우기
            document.getElementById('location').value = schedule.location || '';
            document.getElementById('companion').value = schedule.companion || '';
            document.getElementById('memo').value = schedule.memo || '';
            
            // 폼 상단에 일정 불러옴 메시지 표시
            showInfoMessage(`${date} 날짜에 저장된 일정을 불러왔습니다.`);
        } else {
            console.log(`${date} 날짜에 저장된 일정이 없습니다.`);
            // 폼 필드 초기화
            document.getElementById('location').value = '';
            document.getElementById('companion').value = '';
            document.getElementById('memo').value = '';
        }
    } catch (error) {
        console.error('일정 불러오기 오류:', error);
    }
}

/**
 * 다양한 형식의 날짜 문자열을 비교 가능한 동일한 형식으로 정규화합니다.
 * @param {string} dateStr - 정규화할 날짜 문자열 (YYYY-MM-DD 또는 다른 형식)
 * @returns {string} - YYYY-MM-DD 형식의 정규화된 날짜
 */
function normalizeDate(dateStr) {
    if (!dateStr) return '';
    
    try {
        // ISO 문자열로 변환된 날짜에서 YYYY-MM-DD 부분만 추출
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) {
            console.log('[디버그] 유효하지 않은 날짜:', dateStr);
            return '';
        }
        
        const year = date.getFullYear();
        // 월과 일은 항상 2자리 숫자로 표현 (01, 02, ... 12)
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        
        return `${year}-${month}-${day}`;
    } catch (e) {
        console.error('[디버그] 날짜 정규화 오류:', e);
        return '';
    }
}

// 일정 로드 함수
function loadSchedule() {
    console.log('[디버그] loadSchedule 함수 시작');
    try {
        // URL에서 날짜 매개변수 추출
        const urlParams = new URLSearchParams(window.location.search);
        const dateParam = urlParams.get('date');
        
        if (!dateParam) {
            console.log('[디버그] 날짜 매개변수 없음');
            return;
        }
        
        console.log('[디버그] 로드할 날짜:', dateParam);
        
        // 로컬 스토리지에서 인증 토큰 가져오기
        const token = localStorage.getItem(ACCESS_TOKEN_KEY);
        if (!token) {
            console.log('[디버그] 인증 토큰 없음');
            showErrorMessage('로그인이 필요합니다.');
            return;
        }
        
        // 로딩 메시지 표시
        showInfoMessage('일정을 로딩중입니다...');
        
        // GET 요청으로 일정 정보 가져오기
        fetch(`${BACKEND_BASE_URL}/calendar/schedules/?date=${dateParam}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        })
        .then(response => {
            console.log('[디버그] GET 응답 상태:', response.status);
            
            if (response.status === 401 || response.status === 403) {
                throw new Error('로그인이 만료되었습니다.');
            }
            
            if (!response.ok) {
                throw new Error('일정 정보를 가져오는데 실패했습니다.');
            }
            
            return response.json();
        })
        .then(schedules => {
            console.log('[디버그] 조회된 모든 일정:', schedules);
            
            // 정규화된 날짜로 비교
            const normalizedRequestDate = normalizeDate(dateParam);
            console.log('[디버그] 정규화된 요청 날짜:', normalizedRequestDate);
            
            // 해당 날짜와 일치하는 일정만 필터링
            const matchingSchedules = schedules.filter(item => {
                const itemDate = normalizeDate(item.date);
                return itemDate === normalizedRequestDate;
            });
            
            console.log('[디버그] 필터링된 일정:', matchingSchedules);
            
            if (!matchingSchedules || matchingSchedules.length === 0) {
                console.log('[디버그] 일치하는 일정 없음');
                // 일정이 없으면 메시지 제거
                document.querySelector('.info-message')?.remove();
                return;
            }
            
            // 첫 번째 일정 사용 (날짜당 하나의 일정만 허용)
            const schedule = matchingSchedules[0];
            console.log('[디버그] 표시할 일정:', schedule);
            
            // 폼에 데이터 채우기
            document.getElementById('location').value = schedule.location || '';
            document.getElementById('content').value = schedule.content || '';
            
            // 로딩 완료 메시지 표시 후 제거
            document.querySelector('.info-message')?.remove();
            showSuccessMessage('일정이 로드되었습니다.');
        })
        .catch(error => {
            console.error('[디버그] 일정 로드 오류:', error);
            document.querySelector('.info-message')?.remove();
            showErrorMessage(error.message || '일정을 불러오는 중 오류가 발생했습니다.');
        });
    } catch (e) {
        console.error('[디버그] loadSchedule 전체 오류:', e);
        document.querySelector('.info-message')?.remove();
        showErrorMessage('일정을 불러오는 중 오류가 발생했습니다.');
    }
}

/**
 * 일정을 삭제하는 함수
 */
window.deleteSchedule = function() {
    console.log('[디버그] deleteSchedule 함수 시작');
    
    // 이미 실행 중이면 중복 실행 방지
    if (window.deleteInProgress === true) {
        console.log('[디버그] 이미 삭제 처리 중입니다.');
        return;
    }
    
    // 실행 중 표시
    window.deleteInProgress = true;
    
    try {
        // URL에서 날짜 매개변수 추출
        const urlParams = new URLSearchParams(window.location.search);
        const dateParam = urlParams.get('date');
        console.log('[디버그] URL에서 추출한 날짜:', dateParam);
        
        if (!dateParam) {
            console.log('[디버그] 날짜 매개변수 없음');
            showErrorMessage('삭제할 일정의 날짜 정보가 없습니다.');
            window.deleteInProgress = false;
            return;
        }
        
        // 장소 입력값 확인 (필수값)
        const locationInput = document.getElementById('location');
        console.log('[디버그] 장소 입력 필드:', locationInput);
        if (!locationInput || !locationInput.value.trim()) {
            console.log('[디버그] 장소가 입력되지 않음');
            showErrorMessage('삭제할 일정이 없습니다.');
            window.deleteInProgress = false;
            return;
        }
        
        // 사용자에게 확인 요청
        const userConfirmed = confirm('정말로 이 일정을 삭제하시겠습니까?');
        if (!userConfirmed) {
            console.log('[디버그] 사용자가 취소함');
            
            // 취소시 버튼 상태 복원
            const deleteBtn = document.querySelector('.delete-btn');
            if (deleteBtn) {
                deleteBtn.disabled = false;
                deleteBtn.textContent = '일정 삭제하기';
                deleteBtn.style.backgroundColor = '';
            }
            window.deleteInProgress = false;
            return;
        }
        
        console.log('[디버그] 사용자가 삭제 확인함 - 삭제 처리 진행');
        
        // 로컬 스토리지에서 인증 토큰 가져오기
        const token = localStorage.getItem(ACCESS_TOKEN_KEY);
        console.log('[디버그] 인증 토큰 존재 여부:', !!token);
        if (!token) {
            console.log('[디버그] 인증 토큰 없음');
            showErrorMessage('로그인이 필요합니다.');
            window.deleteInProgress = false;
            return;
        }
        
        // GET 요청으로 일정 ID 조회 후 삭제 처리
        console.log('[디버그] GET 요청으로 일정 조회 시작');
        
        fetch(`${BACKEND_BASE_URL}/calendar/schedules/?date=${dateParam}`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        })
        .then(response => {
            console.log('[디버그] GET 응답 상태:', response.status);
            
            if (!response.ok) {
                console.log('[디버그] GET 요청 실패');
                throw new Error('일정 정보를 가져오는데 실패했습니다.');
            }
            
            return response.json();
        })
        .then(schedules => {
            console.log('[디버그] 조회된 일정:', schedules);
            
            if (!schedules || schedules.length === 0) {
                console.log('[디버그] 일정이 없음');
                throw new Error('삭제할 일정을 찾을 수 없습니다.');
            }
            
            // 정규화된 날짜로 비교
            const normalizedRequestDate = normalizeDate(dateParam);
            console.log('[디버그] 정규화된 요청 날짜:', normalizedRequestDate);
            
            // 해당 날짜와 일치하는 일정만 필터링
            const matchingSchedules = schedules.filter(item => {
                const itemDate = normalizeDate(item.date);
                console.log(`[디버그] 일정 데이터 날짜: ${item.date}, 정규화된 날짜: ${itemDate}`);
                return itemDate === normalizedRequestDate;
            });
            
            console.log('[디버그] 필터링된 일정:', matchingSchedules);
            
            if (!matchingSchedules || matchingSchedules.length === 0) {
                console.log('[디버그] 일치하는 일정 없음');
                throw new Error('삭제할 일정을 찾을 수 없습니다.');
            }
            
            // 첫 번째 일정 ID 사용
            const scheduleId = matchingSchedules[0].id;
            console.log('[디버그] 삭제할 일정 ID:', scheduleId);
            
            // DELETE 요청 보내기
            console.log('[디버그] DELETE 요청 시작 - ID 사용');
            return fetch(`${BACKEND_BASE_URL}/calendar/schedules/${scheduleId}/`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });
        })
        .then(response => {
            console.log('[디버그] DELETE 응답 상태:', response.status);
            
            if (response.status === 401 || response.status === 403) {
                // 인증 오류
                console.log('[디버그] 인증 오류');
                throw new Error('로그인이 만료되었습니다.');
            }
            
            if (response.status === 404) {
                // 일정이 존재하지 않음
                console.log('[디버그] 404 - 일정 찾을 수 없음');
                throw new Error('삭제할 일정을 찾을 수 없습니다.');
            }
            
            if (response.status === 204 || response.status === 200) {
                // 성공적으로 삭제됨
                console.log('[디버그] 삭제 성공');
                showSuccessMessage('일정이 성공적으로 삭제되었습니다!');
                
                // 폼 초기화
                resetForm();
                
                // 1.5초 후 캘린더로 이동
                setTimeout(() => {
                    window.location.href = 'calendar.html';
                }, 1500);
                return;
            }
            
            // 기타 오류
            console.log('[디버그] 기타 오류 응답');
            if (response.headers.get('content-type')?.includes('application/json')) {
                return response.json().then(data => {
                    console.log('[디버그] 오류 데이터:', data);
                    throw new Error(data.detail || '일정 삭제 중 오류가 발생했습니다.');
                });
            } else {
                throw new Error('일정 삭제 중 오류가 발생했습니다.');
            }
        })
        .catch(error => {
            console.error('[디버그] 삭제 요청 오류:', error);
            showErrorMessage(error.message || '일정 삭제 중 오류가 발생했습니다.');
            
            // 오류 발생 시 버튼 상태 복원
            const deleteBtn = document.querySelector('.delete-btn');
            if (deleteBtn) {
                deleteBtn.disabled = false;
                deleteBtn.textContent = '일정 삭제하기';
                deleteBtn.style.backgroundColor = '';
            }
            
            // 오류 발생 시에도 처리 완료 상태로 설정
            window.deleteInProgress = false;
        })
        .finally(() => {
            console.log('[디버그] 삭제 처리 완료');
        });
    } catch (e) {
        console.error('[디버그] 전체 함수 오류:', e);
        showErrorMessage('일정 삭제 중 오류가 발생했습니다.');
        
        // 오류 발생 시 버튼 상태 복원
        const deleteBtn = document.querySelector('.delete-btn');
        if (deleteBtn) {
            deleteBtn.disabled = false;
            deleteBtn.textContent = '일정 삭제하기';
            deleteBtn.style.backgroundColor = '';
        }
        
        // 오류 발생 시 처리 완료 상태로 설정
        window.deleteInProgress = false;
    }
};

// 전역 함수 명시적 등록
console.log('[디버그] 전역 함수 등록 시작');
try {
    // deleteSchedule 함수 등록 확인
    console.log('[디버그] deleteSchedule 함수 타입(등록 전):', typeof window.deleteSchedule);
    // deleteSchedule은 이미 window 객체에 등록됨
    console.log('[디버그] deleteSchedule 함수 타입(등록 후):', typeof window.deleteSchedule);
    
    // DOMContentLoaded 이벤트 리스너 
    document.addEventListener('DOMContentLoaded', function() {
        console.log('[디버그] DOMContentLoaded 이벤트 발생');
        console.log('[디버그] 문서 로드 완료 시점의 deleteSchedule 함수 타입:', typeof window.deleteSchedule);
        
        // setupForm 함수 실행
        setupForm();
    });
    
    console.log('[디버그] 전역 함수 등록 및 초기화 완료');
} catch (e) {
    console.error('[디버그] 전역 함수 등록 오류:', e);
}

// 디버그 코드: 상수 확인
console.log('[디버그-JS] 상수 확인');
console.log('[디버그-JS] BACKEND_BASE_URL:', BACKEND_BASE_URL);
console.log('[디버그-JS] ACCESS_TOKEN_KEY:', ACCESS_TOKEN_KEY);
console.log('[디버그-JS] 로컬 스토리지 토큰:', localStorage.getItem(ACCESS_TOKEN_KEY));