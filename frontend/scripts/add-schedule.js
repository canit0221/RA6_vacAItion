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
    
    // 직접 일정 불러오기 함수 호출 추가
    loadScheduleDirectly();
    
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

// 직접 일정 데이터를 불러오는 새로운 함수 추가
async function loadScheduleDirectly() {
    try {
        console.log('일정 직접 불러오기 시작');
        
        // URL에서 날짜 가져오기
        const urlParams = new URLSearchParams(window.location.search);
        const dateParam = urlParams.get('date');
        if (!dateParam) {
            console.log('날짜 파라미터 없음');
            return;
        }
        
        console.log('불러올 날짜:', dateParam);
        
        // 선택한 날짜에서 일(day) 추출 (01 → 1, 19 → 19)
        const selectedDay = dateParam.split('-')[2].replace(/^0/, '');
        console.log('선택한 날짜의 일:', selectedDay);
        
        // 토큰 가져오기
        const token = localStorage.getItem('access_token');
        if (!token) {
            console.log('인증 토큰 없음');
            return;
        }
        
        // 모든 일정 가져오기 (필터링은 프론트엔드에서)
        const response = await fetch(`${BACKEND_BASE_URL}/calendar/schedules/`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            console.error('일정 조회 실패:', response.status);
            return;
        }
        
        // 모든 일정 데이터
        const allSchedules = await response.json();
        console.log('가져온 모든 일정:', allSchedules);
        
        // 배열이 아니면 변환
        const schedules = Array.isArray(allSchedules) ? allSchedules : [allSchedules];
        
        // 각 일정 날짜 출력 (디버깅용)
        schedules.forEach((item, index) => {
            console.log(`일정 ${index+1}:`, item);
            console.log(`- 날짜: ${item.date}, 장소: ${item.location}`);
        });
        
        // 일정에서 해당 날짜(일) 찾기
        let foundSchedule = null;
        
        for (const schedule of schedules) {
            // 날짜 형식에 따라 일(day) 추출
            let scheduleDay = '';
            
            if (schedule.date) {
                if (typeof schedule.date === 'string') {
                    if (schedule.date.includes('-')) {
                        // YYYY-MM-DD 형식
                        scheduleDay = schedule.date.split('-')[2].replace(/^0/, '');
                    } else if (schedule.date.length === 8) {
                        // YYYYMMDD 형식
                        scheduleDay = schedule.date.slice(-2).replace(/^0/, '');
                    } else {
                        scheduleDay = schedule.date.replace(/^0/, '');
                    }
                } else {
                    scheduleDay = String(schedule.date).replace(/^0/, '');
                }
                
                console.log(`비교: 일정 날짜의 일(${scheduleDay}) vs 선택한 날짜의 일(${selectedDay})`);
                
                // 날짜(일)이 일치하면 저장
                if (scheduleDay === selectedDay) {
                    console.log('일치하는 일정 찾음:', schedule);
                    foundSchedule = schedule;
                    break;
                }
            }
        }
        
        // 일정이 있으면 폼에 입력
        if (foundSchedule) {
            console.log('폼에 데이터 입력 중:', foundSchedule);
            
            // DOM 요소 직접 접근
            const locationInput = document.getElementById('location');
            const companionInput = document.getElementById('companion');
            const memoInput = document.getElementById('memo');
            
            if (locationInput) {
                locationInput.value = foundSchedule.location || '';
                console.log('장소 입력됨:', foundSchedule.location);
            } else {
                console.error('location 입력란을 찾을 수 없음');
            }
            
            if (companionInput) {
                companionInput.value = foundSchedule.companion || '';
                console.log('동반자 입력됨:', foundSchedule.companion);
            } else {
                console.error('companion 입력란을 찾을 수 없음');
            }
            
            if (memoInput) {
                memoInput.value = foundSchedule.memo || '';
                console.log('메모 입력됨:', foundSchedule.memo);
            } else {
                console.error('memo 입력란을 찾을 수 없음');
            }
            
            // 확인 메시지 표시
            showSuccessMessage('저장된 일정을 불러왔습니다.');
        } else {
            console.log('일치하는 일정이 없습니다.');
        }
    } catch (error) {
        console.error('일정 불러오기 오류:', error);
    }
}

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
        console.warn('이미 요청 중입니다.');
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
    
    // 날짜 확인
    console.log('저장 요청 날짜:', dateParam);
    
    const location = document.getElementById('location').value;
    const companion = document.getElementById('companion').value;
    const memo = document.getElementById('memo').value;
    
    // 필수 필드 검증
    if (!location) {
        console.error('장소가 입력되지 않음');
        showErrorMessage('장소를 입력해주세요.');
        document.getElementById('location').focus();
        isSubmitting = false;
        return;
    }
    
    // 저장 버튼 비활성화
    const saveBtn = document.querySelector('.save-btn');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = '저장 중...';
    }
    
    try {
        // 요청 데이터 준비
        const scheduleData = {
            date: dateParam,
            location: location,
            companion: companion || '',
            memo: memo || ''
        };
        
        console.log('요청 데이터:', scheduleData);
        
        // 인증 토큰 확인
        const accessToken = localStorage.getItem('access_token');
        if (!accessToken) {
            console.error('인증 토큰이 없습니다.');
            window.location.replace('login.html');
            return;
        }
        
        // 단순화: 항상 POST로 새 일정 생성
        const apiUrl = `${BACKEND_BASE_URL}/calendar/schedules/`;
        
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            },
            body: JSON.stringify(scheduleData)
        });
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`서버 오류 (${response.status}): ${errorText}`);
        }
        
        // 성공 메시지
        showSuccessMessage('일정이 저장되었습니다!');
        
        // 새로운 일정 데이터로 폼 업데이트
        document.getElementById('location').value = location;
        document.getElementById('companion').value = companion;
        document.getElementById('memo').value = memo;
        
    } catch (error) {
        console.error('일정 저장 오류:', error);
        showErrorMessage(`저장 실패: ${error.message}`);
    } finally {
        // 저장 버튼 상태 복원
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.textContent = '현재 페이지에서 저장';
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
        if (!accessToken) return;
        
        // API 호출
        const response = await fetch(`${BACKEND_BASE_URL}/calendar/schedules/`, {
            headers: { 'Authorization': `Bearer ${accessToken}` }
        });
        
        if (!response.ok) return;
        
        // 응답 데이터 파싱
        const data = await response.json();
        console.log('받은 데이터:', data);
        
        // 일정 데이터 추출 (schedules 속성이 있으면 사용, 아니면 전체 사용)
        const allSchedules = data.schedules || data;
        
        // 배열이 아니면 빈 배열로 설정
        const schedules = Array.isArray(allSchedules) ? allSchedules : [];
        console.log('처리할 일정 배열:', schedules);
        
        // 선택한 날짜에서 일(day) 추출
        const selectedDay = date.split('-')[2].replace(/^0/, '');
        console.log('선택한 날의 일:', selectedDay);
        
        // 해당 날짜의 일정 찾기
        const matchingSchedule = schedules.find(schedule => {
            if (!schedule.date) return false;
            
            // date가 문자열인지 확인
            const dateStr = String(schedule.date);
            
            // 날짜 형식에 따라 일 추출
            let scheduleDay;
            if (dateStr.includes('-')) {
                // YYYY-MM-DD 형식
                scheduleDay = dateStr.split('-')[2].replace(/^0/, '');
            } else {
                // 다른 형식 (마지막 두 자리가 일)
                scheduleDay = dateStr.slice(-2).replace(/^0/, '');
            }
            
            console.log(`일정: ${schedule.location}, 날짜: ${schedule.date}, 일: ${scheduleDay}, 비교: ${selectedDay}`);
            return scheduleDay === selectedDay;
        });
        
        // 일정을 찾았으면 폼에 데이터 채우기
        if (matchingSchedule) {
            console.log('일치하는 일정 찾음:', matchingSchedule);
            
            document.getElementById('location').value = matchingSchedule.location || '';
            document.getElementById('companion').value = matchingSchedule.companion || '';
            document.getElementById('memo').value = matchingSchedule.memo || '';
            
            showInfoMessage('일정을 불러왔습니다.');
        } else {
            console.log('일치하는 일정 없음');
            
            // 폼 초기화
            document.getElementById('location').value = '';
            document.getElementById('companion').value = '';
            document.getElementById('memo').value = '';
        }
    } catch (error) {
        console.error('일정 불러오기 오류:', error);
        console.error('삭제 처리 오류:', error);
        window.deleteInProgress = false;
    }
};

// 전역 함수 명시적 등록 (파일 하단에 추가)
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

// 전역 함수 명시적 등록 (파일 하단에 추가)
window.saveScheduleToDB = saveScheduleToDB;
window.submitSchedule = submitSchedule;

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
        if (!dateParam) {
            showErrorMessage('삭제할 일정의 날짜 정보가 없습니다.');
            window.deleteInProgress = false;
            return;
        }
        
        // 토큰 확인
        const token = localStorage.getItem('access_token');
        if (!token) {
            showErrorMessage('로그인이 필요합니다.');
            window.deleteInProgress = false;
            return;
        }
        
        // 확인 대화상자
        if (!confirm('이 일정을 삭제하시겠습니까?')) {
            window.deleteInProgress = false;
            return;
        }
        
        // 삭제 버튼 상태 변경
        const deleteBtn = document.querySelector('.delete-btn');
        if (deleteBtn) {
            deleteBtn.disabled = true;
            deleteBtn.textContent = '삭제 중...';
        }
        
        // 선택한 날짜에서 일(day) 추출
        const selectedDay = dateParam.split('-')[2].replace(/^0/, '');
        
        // 모든 일정 가져오기
        fetch(`${BACKEND_BASE_URL}/calendar/schedules/`, {
            headers: { 'Authorization': `Bearer ${token}` }
        })
        .then(response => response.json())
        .then(data => {
            // API 응답 형식에 따라 일정 배열 추출
            const allSchedules = data.schedules || data;
            const schedules = Array.isArray(allSchedules) ? allSchedules : [];
            
            // 날짜와 일치하는 일정 찾기
            const matchingSchedule = schedules.find(schedule => {
                if (!schedule.date) return false;
                
                // 날짜의 일(day) 부분만 추출
                const scheduleDay = String(schedule.date).includes('-')
                    ? schedule.date.split('-')[2].replace(/^0/, '')
                    : String(schedule.date).slice(-2).replace(/^0/, '');
                
                return scheduleDay === selectedDay;
            });
            
            if (!matchingSchedule) {
                showErrorMessage('삭제할 일정을 찾을 수 없습니다.');
                window.deleteInProgress = false;
                
                // 버튼 상태 복원
                if (deleteBtn) {
                    deleteBtn.disabled = false;
                    deleteBtn.textContent = '일정 삭제하기';
                }
                
                return;
            }
            
            // 일정 ID로 삭제 요청
            return fetch(`${BACKEND_BASE_URL}/calendar/schedules/${matchingSchedule.id}/`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });
        })
        .then(response => {
            if (!response) return; // 이전 단계에서 오류 발생
            
            if (response.status === 204 || response.status === 200) {
                // 삭제 성공
                showSuccessMessage('일정이 성공적으로 삭제되었습니다!');
                
                // 1. 폼 필드 초기화
                document.getElementById('location').value = '';
                document.getElementById('companion').value = '';
                document.getElementById('memo').value = '';
                
                // 2. 1.5초 후 캘린더로 이동 (색상 업데이트 위해)
                setTimeout(() => {
                    window.location.href = 'calendar.html';
                }, 1500);
            } else {
                // 삭제 실패
                showErrorMessage(`삭제 실패 (${response.status})`);
                
                // 버튼 상태 복원
                if (deleteBtn) {
                    deleteBtn.disabled = false;
                    deleteBtn.textContent = '일정 삭제하기';
                }
            }
            
            window.deleteInProgress = false;
        })
        .catch(error => {
            console.error('삭제 요청 오류:', error);
            showErrorMessage('일정 삭제 중 오류가 발생했습니다.');
            
            // 버튼 상태 복원
            if (deleteBtn) {
                deleteBtn.disabled = false;
                deleteBtn.textContent = '일정 삭제하기';
            }
            
            window.deleteInProgress = false;
        });
    } catch (error) {
        console.error('전체 함수 오류:', error);
        showErrorMessage('일정 삭제 중 오류가 발생했습니다.');
        window.deleteInProgress = false;
        
        // 버튼 상태 복원
        const deleteBtn = document.querySelector('.delete-btn');
        if (deleteBtn) {
            deleteBtn.disabled = false;
            deleteBtn.textContent = '일정 삭제하기';
        }
    }
};