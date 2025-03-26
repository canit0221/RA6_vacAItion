// 상수 정의
const BACKEND_BASE_URL = 'http://localhost:8000'; // 백엔드 기본 URL
const ACCESS_TOKEN_KEY = 'access_token'; // 로컬 스토리지에 저장된 토큰 키 이름
const USERNAME_KEY = 'username';

// 전역 상태 플래그 초기화
window.isProcessingDelete = false; // 일정 삭제 처리 중인지 여부 (기존 플래그)
window.deleteInProgress = false;   // 새로운 삭제 진행 중 플래그

// 전역 변수로 요청 중 상태 관리
let isSubmitting = false;

// UI 업데이트 함수
function updateUI() {
    const userNickname = localStorage.getItem('userNickname');
    const profileNavLink = document.getElementById('profileNavLink');
    
    if (userNickname && profileNavLink) {
        profileNavLink.textContent = `${userNickname}님의 프로필`;
    }
}

// 페이지 로드 시 실행
window.onload = function() {
    console.log('[Debug] window.onload 이벤트 발생');
    
    // 직접 일정 불러오기 함수 호출 
    loadScheduleDirectly();
    
    // 로그인 상태 확인
    if (!checkLoginStatus()) {
        return;
    }
    
    // UI 업데이트 추가
    updateUI();
    
    // 일정을 불러오는 중임을 표시
    showInfoMessage('일정을 불러오는 중입니다...');
    
    // 네비게이션 링크 설정 (로그아웃 기능 등록)
    setupNavLinks();
    
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
            option.textContent = category || '선택하기';
            selectElement.appendChild(option);
        });
        
        // 기존 입력 필드 대체
        companionInput.parentNode.replaceChild(selectElement, companionInput);
        
        // 라벨 텍스트 업데이트
        if (companionLabel) {
            companionLabel.textContent = 'with Who?';
        }
    }
    
    // 버튼 존재 여부 확인
    const saveBtn = document.querySelector('.save-btn');
    const submitBtn = document.querySelector('.submit-btn');
    const deleteBtn = document.querySelector('.delete-btn');
    
    // URL에서 날짜 매개변수 확인
    const urlParams = new URLSearchParams(window.location.search);
    const dateParam = urlParams.get('date');
    const addedParam = urlParams.get('added');
    
    console.log(`[Debug] URL 파라미터 - date: ${dateParam}, added: ${addedParam}`);
    
    // 신규 추가 여부 확인
    if (addedParam === 'true') {
        console.log('[Debug] 추천된 장소가 추가되었다는 메시지 표시');
        showSuccessMessage('추천된 장소가 목록에 추가되었습니다. 추천 장소는 일정과 별개로 관리됩니다.');
        
        // 메모 필드의 자동 채워진 내용만 필터링 (일정 시간 후 실행)
        setTimeout(() => {
            const memoInput = document.getElementById('memo');
            if (memoInput && memoInput.value) {
                // 추천 장소/이벤트 관련 자동 생성 메모 패턴 제거
                let memoText = memoInput.value;
                const autoMemoPatterns = [
                    /\[추천된 장소\][\s\S]*?(?=\n\n|\n$|$)/g,
                    /\[추천된 이벤트\][\s\S]*?(?=\n\n|\n$|$)/g,
                    /추천 이유:[\s\S]*?(?=\n\n|\n$|$)/g,
                    /참고 링크:[\s\S]*?(?=\n\n|\n$|$)/g,
                    /참고 정보:[\s\S]*?(?=\n\n|\n$|$)/g
                ];
                
                // 자동 생성 메모 패턴 제거
                autoMemoPatterns.forEach(pattern => {
                    memoText = memoText.replace(pattern, '');
                });
                
                // 연속된 빈 줄 제거 및 앞뒤 공백 제거
                memoText = memoText.replace(/\n{3,}/g, '\n\n').trim();
                
                // 필터링된 메모 설정
                memoInput.value = memoText;
                console.log('[Debug] 페이지 로드 후 메모에서 자동 생성된 내용 필터링 완료');
            }
        }, 500);
    }
    
    // 현재 날짜 구하기
    const currentDate = new Date();
    
    // 날짜 매개변수가 있으면 해당 날짜 설정, 없으면 현재 날짜
    let targetDate;
    if (dateParam) {
        // 날짜 파싱 (ISO 형식이 아닐 수 있으므로 직접 파싱)
        const dateParts = dateParam.split('-');
        if (dateParts.length === 3) {
            const year = parseInt(dateParts[0], 10);
            const month = parseInt(dateParts[1], 10) - 1; // JavaScript의 월은 0부터 시작
            const day = parseInt(dateParts[2], 10);
            const selectedDate = new Date(year, month, day);
            
            if (!isNaN(selectedDate.getTime())) {
                // 유효한 날짜인 경우
                console.log(`[Debug] 파라미터에서 날짜 설정: ${selectedDate}`);
                // 날짜 표시 업데이트
                updateDateDisplay(selectedDate);
                // 미니 캘린더 생성
                initializeMiniCalendar(selectedDate);
                // 해당 날짜에 저장된 일정 불러오기
                fetchScheduleForDate(dateParam);
                // 해당 날짜에 추천된 장소/이벤트 불러오기
                console.log('[Debug] 추천된 장소 가져오기 시작 (dateParts)');
                loadRecommendedPlaces(dateParam);
                // 폼 제출 이벤트 리스너 설정
                setupForm();
                return;
            }
        }
        
        // 날짜 파싱 실패시 fallback
        console.warn(`[Debug] 날짜 파싱 실패, fallback 사용: ${dateParam}`);
        updateDateDisplay(dateParam);
        try {
            targetDate = new Date(dateParam);
            initializeMiniCalendar(targetDate);
            // 해당 날짜에 저장된 일정 불러오기
            fetchScheduleForDate(dateParam);
            // 해당 날짜에 추천된 장소/이벤트 불러오기
            console.log('[Debug] 추천된 장소 가져오기 시작 (fallback)');
            loadRecommendedPlaces(dateParam);
        } catch (e) {
            console.error('[Debug] 날짜 처리 중 오류:', e);
            targetDate = currentDate;
        }
    } else {
        // 기본값: 현재 날짜
        console.log('[Debug] 날짜 파라미터 없음, 현재 날짜 사용');
        targetDate = currentDate;
        const dateStr = formatLocalDate(targetDate);
        updateDateDisplay(targetDate);
        initializeMiniCalendar(targetDate);
        // 오늘 날짜의 일정 불러오기
        fetchScheduleForDate(dateStr);
        // 오늘 날짜에 추천된 장소/이벤트 불러오기
        console.log('[Debug] 추천된 장소 가져오기 시작 (현재 날짜)');
        loadRecommendedPlaces(dateStr);
    }
    
    // 폼 제출 이벤트 리스너 설정
    setupForm();
};

// 직접 일정 데이터를 불러오는 새로운 함수 추가
async function loadScheduleDirectly() {
    try {
        // URL에서 날짜 가져오기
        const urlParams = new URLSearchParams(window.location.search);
        const dateParam = urlParams.get('date');
        const addedParam = urlParams.get('added');
        
        if (!dateParam) {
            return;
        }
        
        // 날짜 정규화
        const normalizedDate = normalizeDate(dateParam);
        
        if (!normalizedDate) {
            return;
        }
        
        // 접근 토큰 확인
        const token = localStorage.getItem('access_token');
        if (!token) {
            return;
        }
        
        // 전역 날짜 변수 업데이트
        selectedDate = new Date(normalizedDate);
        
        // API 요청: 해당 날짜의 일정 가져오기
        const response = await fetch(`${BACKEND_BASE_URL}/calendar/schedules/?date=${normalizedDate}`, {
            headers: {'Authorization': `Bearer ${token}`}
        });
        
        if (!response.ok) {
            return;
        }
        
        // 응답 데이터 가져오기
        const data = await response.json();
        
        // 데이터 구조 처리
        let schedules = [];
        
        // 새로운 API 응답 형식 처리 (날씨 포함)
        if (data.schedules && Array.isArray(data.schedules)) {
            schedules = data.schedules;
        }
        // 이전 API 응답 형식 처리 (배열만 반환)
        else if (Array.isArray(data)) {
            schedules = data;
        }
        // 단일 객체인 경우
        else if (typeof data === 'object' && data !== null) {
            if (data.id) {
                schedules = [data]; // 객체 하나면 배열로 변환
            }
        }
        
        // 날짜 파싱 - 연,월,일 분리
        const [year, month, day] = normalizedDate.split('-').map(num => parseInt(num, 10));
        
        // 정확히 일치하는 일정 찾기
        let foundSchedule = null;
        
        for (const item of schedules) {
            if (!item.date) continue;
            
            // 날짜 정규화하여 비교
            const itemNormalizedDate = normalizeDate(item.date);
            if (!itemNormalizedDate) continue;
            
            // 연, 월, 일이 모두 일치하는지 확인
            const [itemYear, itemMonth, itemDay] = itemNormalizedDate.split('-').map(num => parseInt(num, 10));
            
            if (itemYear === year && itemMonth === month && itemDay === day) {
                foundSchedule = item;
                break;
            }
        }
        
        // 일정 정보 채우기
        if (foundSchedule) {
            const locationInput = document.getElementById('location');
            const companionInput = document.getElementById('companion');
            const memoInput = document.getElementById('memo');
            
            if (locationInput) locationInput.value = foundSchedule.location || '';
            if (companionInput) companionInput.value = foundSchedule.companion || '';
            
            // 메모 처리: 추천 장소가 추가된 경우(added=true) 자동 생성된 메모 패턴 필터링
            if (memoInput && foundSchedule.memo) {
                let memoText = foundSchedule.memo;
                
                // 추천 장소 추가 시 자동 생성된 메모 패턴 필터링
                if (addedParam === 'true') {
                    // 추천 장소/이벤트 관련 자동 생성 메모 패턴 제거
                    const autoMemoPatterns = [
                        /\[추천된 장소\][\s\S]*?(?=\n\n|\n$|$)/g,
                        /\[추천된 이벤트\][\s\S]*?(?=\n\n|\n$|$)/g,
                        /추천 이유:[\s\S]*?(?=\n\n|\n$|$)/g,
                        /참고 링크:[\s\S]*?(?=\n\n|\n$|$)/g,
                        /참고 정보:[\s\S]*?(?=\n\n|\n$|$)/g
                    ];
                    
                    // 자동 생성 메모 패턴 제거
                    autoMemoPatterns.forEach(pattern => {
                        memoText = memoText.replace(pattern, '');
                    });
                    
                    // 연속된 빈 줄 제거
                    memoText = memoText.replace(/\n{3,}/g, '\n\n');
                    
                    // 앞뒤 공백 제거
                    memoText = memoText.trim();
                    
                    console.log('[Debug] loadScheduleDirectly - 메모에서 자동 생성된 내용 필터링 완료');
                }
                
                // 필터링된 메모 설정
                memoInput.value = memoText;
            } else if (memoInput) {
                memoInput.value = '';
            }
            
            // 추천 장소 추가 시 메시지 표시
            if (addedParam === 'true') {
                showInfoMessage('추천 장소가 추가되었습니다. 메모는 사용자가 직접 관리합니다.');
            }
            
            return true;
        } else {
            // 일정이 없는 경우 폼 초기화
            const locationInput = document.getElementById('location');
            const companionInput = document.getElementById('companion');
            const memoInput = document.getElementById('memo');
            
            if (locationInput) locationInput.value = '';
            if (companionInput) companionInput.value = '';
            if (memoInput) memoInput.value = '';
            
            // 추천 장소 추가 시 메시지 표시
            if (addedParam === 'true') {
                showInfoMessage('추천 장소가 추가되었지만, 해당 날짜에 저장된 일정이 없습니다.');
            }
            
            return false;
        }
    } catch (error) {
        console.error('일정 직접 로드 중 오류:', error);
        return false;
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
    const miniCalendar = document.querySelector('.mini-calendar');
    if (!miniCalendar) {
        return;
    }
    
    // 기존 캘린더 내용 제거
    miniCalendar.innerHTML = '';
    
    try {
        const currentMonth = selectedDate.getMonth();
        const currentYear = selectedDate.getFullYear();
        
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
                window.location.href = `add-schedule.html?date=${dateStr}`;
            });
            
            calendarGrid.appendChild(dayElement);
        }

        miniCalendar.appendChild(calendarGrid);
    } catch (error) {
        // 오류 처리
    }
}

// 날짜 표시 업데이트 함수
function updateDateDisplay(date) {
    // Date 객체가 아니면 변환 시도
    if (!(date instanceof Date)) {
        try {
            date = new Date(date);
        } catch (e) {
            return;
        }
    }
    
    if (!isNaN(date.getTime())) {
        const weekdays = ['일요일', '월요일', '화요일', '수요일', '목요일', '금요일', '토요일'];
        const year = date.getFullYear();
        const month = (date.getMonth() + 1).toString().padStart(2, '0');
        const day = date.getDate().toString().padStart(2, '0');
        const weekday = weekdays[date.getDay()];
        
        // 날짜 형식화 (날씨 아이콘은 별도로 추가됨)
        const formattedDate = `${year}.${month}.${day} ${weekday}`;
        
        const selectedDateElement = document.querySelector('.selected-date');
        if (selectedDateElement) {
            // 일단 날짜만 표시하고, 날씨 아이콘은 날씨 데이터를 가져온 후 추가
            selectedDateElement.textContent = formattedDate;
            
            // 날씨 데이터 가져오기
            fetchWeatherForDate(`${year}-${month}-${day}`).then(weatherData => {
                if (weatherData) {
                    // 날씨 아이콘 추가
                    let displayText = formattedDate;
                    
                    // 아이콘이 있으면 추가
                    if (weatherData.icon) {
                        displayText += ` ${weatherData.icon}`;
                    }
                    
                    selectedDateElement.textContent = displayText;
                    
                    // 텍스트 정보가 있으면 툴크으로 추가 (선택 사항)
                    if (weatherData.text) {
                        selectedDateElement.title = `날씨: ${weatherData.text}`;
                        
                        // description이 있고 text와 다르면 추가 정보로 표시
                        if (weatherData.description && weatherData.description !== weatherData.text) {
                            selectedDateElement.title += ` (${weatherData.description})`;
                        }
                    }
                }
            });
        }
        
        // 미니 캘린더 월 제목 업데이트
        const monthTitleElement = document.querySelector('.month-title');
        if (monthTitleElement) {
            const months = ['January', 'February', 'March', 'April', 'May', 'June', 
                           'July', 'August', 'September', 'October', 'November', 'December'];
            monthTitleElement.textContent = `${months[date.getMonth()]} ${year}`;
        }
    }
}

// 특정 날짜의 날씨 정보 가져오기
async function fetchWeatherForDate(dateStr) {
    try {
        // 1. 접근 토큰 확인
        const token = localStorage.getItem('access_token');
        if (!token) {
            return null;
        }
        
        // 2. 날짜 정규화 - YYYY-MM-DD 형식 확보
        const normalizedDate = normalizeDate(dateStr);
        if (!normalizedDate) {
            return null;
        }
        
        // 3. 일정 API 요청으로 날씨 데이터 가져오기 
        // (백엔드에는 별도 weather API가 없고 일정 API에서 날씨 정보를 포함하여 반환)
        const response = await fetch(`${BACKEND_BASE_URL}/calendar/schedules/`, {
            headers: {'Authorization': `Bearer ${token}`}
        });
        
        if (!response.ok) {
            return null;
        }
        
        // 4. 응답 데이터 가져오기
        const data = await response.json();
        
        // 5. 날씨 데이터 추출
        const weatherData = data.weather || [];
        
        if (!weatherData || weatherData.length === 0) {
            return {
                icon: '⏳',
                text: '날씨 정보 없음',
                description: '날씨 정보를 가져올 수 없습니다.'
            };
        }
        
        // 6. 특정 날짜의 날씨 찾기
        const weatherForDate = weatherData.find(item => 
            item.date === normalizedDate || 
            normalizeDate(item.date) === normalizedDate
        );
        
        // 7. 날씨 정보 추출 (이모티콘과 텍스트 설명 모두)
        if (weatherForDate) {
            const result = {
                icon: null,
                text: null,
                description: null,
                raw: weatherForDate // 원본 날씨 데이터 전체
            };
            
            // 아이콘 설정
            if (weatherForDate.icon) {
                result.icon = weatherForDate.icon;
            }
            
            // 텍스트 정보 설정 (날씨 설명)
            if (weatherForDate.sky) {
                result.text = weatherForDate.sky;
            } else if (weatherForDate.description) {
                result.text = weatherForDate.description;
            } else if (weatherForDate.weather_main) {
                result.text = weatherForDate.weather_main;
            }
            
            // 상세 설명 설정
            if (weatherForDate.description) {
                result.description = weatherForDate.description;
            } else if (weatherForDate.weather_description) {
                result.description = weatherForDate.weather_description;
            }
            
            // PTY(강수형태) 코드가 있으면 텍스트 정보에 추가
            if (weatherForDate.pty) {
                const ptyText = getPtyText(weatherForDate.pty);
                if (ptyText) {
                    result.text = result.text ? `${result.text}, ${ptyText}` : ptyText;
                }
            }
            
            // 날씨 정보가 없는 경우 기본값 설정
            if (!result.text) {
                if (result.icon) {
                    // 아이콘을 기반으로 텍스트 추론
                    result.text = getWeatherTextFromIcon(result.icon);
                } else {
                    result.text = '알 수 없는 날씨';
                }
            }
            
            // 아이콘이 없는 경우 텍스트를 기반으로 아이콘 생성
            if (!result.icon && result.text) {
                result.icon = mapWeatherConditionToIcon(result.text);
            }
            
            return result;
        }
        
        // 날씨 정보가 없는 경우 기본 값 반환
        return {
            icon: '🔭',
            text: '날씨 정보 없음',
            description: '해당 날짜의 날씨 정보를 찾을 수 없습니다.'
        };
        
    } catch (error) {
        return {
            icon: '⏳',
            text: '오류 발생',
            description: '날씨 정보를 가져오는 중 오류가 발생했습니다.'
        };
    }
}

// PTY(강수형태) 코드를 텍스트로 변환
function getPtyText(ptyCode) {
    const ptyMap = {
        '0': '없음',
        '1': '비',
        '2': '비/눈',
        '3': '눈',
        '4': '소나기'
    };
    
    return ptyMap[ptyCode.toString()] || null;
}

// 날씨 아이콘에서 텍스트 추출
function getWeatherTextFromIcon(icon) {
    const iconToText = {
        '☀️': '맑음',
        '🌤️': '구름조금',
        '⛅': '구름많음',
        '☁️': '흐림',
        '🌧️': '비',
        '❄️': '눈',
        '🌨️': '비/눈',
        '🌦️': '소나기',
        '🌫️': '안개',
        '⚡': '번개',
        '🌪️': '폭풍'
    };
    
    return iconToText[icon] || '알 수 없는 날씨';
}

// 네비게이션 링크 설정
function setupNavLinks() {
    const navLinks = document.querySelectorAll('nav a');
    
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            if (this.textContent.includes('Home')) {
                window.location.href = 'calendar.html';
            } else if (this.id === 'profileNavLink') {
                window.location.href = 'profile.html';
            } else if (this.textContent.includes('Logout')) {
                logout();
            }
        });
    });
}

// 폼 제출 이벤트 설정
function setupForm() {
    // 날짜 표시
    displayDate();
    
    // 일정 로드
    loadSchedule();
    
    // 저장 버튼과 다른 버튼들에 이벤트 리스너 추가 (중복 방지 코드 포함)
    const saveBtn = document.querySelector('.save-btn');
    const submitBtn = document.querySelector('.submit-btn');
    const deleteBtn = document.querySelector('.delete-btn');
    
    // 기존 이벤트 리스너 제거 (중복 방지)
    if (saveBtn) {
        saveBtn.removeEventListener('click', handleSave);
        saveBtn.addEventListener('click', handleSave);
        console.log('[Debug] 저장 버튼에 이벤트 리스너 설정 완료');
    }
    
    if (submitBtn) {
        submitBtn.removeEventListener('click', handleSubmit);
        submitBtn.addEventListener('click', handleSubmit);
    }
    
    if (deleteBtn) {
        deleteBtn.removeEventListener('click', handleDelete);
        deleteBtn.addEventListener('click', handleDelete);
    }
}

// 이벤트 핸들러 함수들
function handleSave(e) {
    e.preventDefault();
    saveScheduleToDB();
}

function handleSubmit(e) {
    e.preventDefault();
    submitSchedule();
}

function handleDelete(e) {
    e.preventDefault();
    try {
        // 전역 함수 호출
        if (typeof window.deleteSchedule === 'function') {
            window.deleteSchedule();
        } else {
            alert('일정 삭제 기능을 불러올 수 없습니다. 페이지를 새로고침 해주세요.');
        }
    } catch (error) {
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
        return dateStr; // 변환 실패 시 원본 반환
    }
}

// DB 저장 함수 - 현재 페이지에서 일정 저장 (수정 또는 생성)
async function saveScheduleToDB() {
    // 이미 요청 중이면 중복 요청 방지
    if (isSubmitting) {
        return;
    }
    
    // 요청 중 상태로 설정
    isSubmitting = true;
    
    // URL에서 날짜 파라미터 가져오기
    const urlParams = new URLSearchParams(window.location.search);
    let dateParam = urlParams.get('date');
    const addedParam = urlParams.get('added'); // 여기에 addedParam 추가
    
    // 날짜 파라미터가 없는 경우 현재 날짜 사용
    if (!dateParam) {
        const today = new Date();
        dateParam = formatLocalDate(today);
        console.log('[Debug] 날짜 파라미터가 없어 현재 날짜 사용:', dateParam);
    } else {
        console.log('[Debug] 일정 저장 시작 - 날짜:', dateParam);
    }
    
    // 날짜 정규화 (YYYY-MM-DD 형식으로 변환)
    const normalizedDate = normalizeDate(dateParam);
    if (!normalizedDate) {
        console.error('[Error] 날짜 정규화 실패:', dateParam);
        showErrorMessage('유효하지 않은 날짜 형식입니다.');
        isSubmitting = false;
        return;
    }
    
    console.log('[Debug] 정규화된 날짜:', normalizedDate);
    
    // 날짜 파싱 - 연,월,일 분리
    const [year, month, day] = normalizedDate.split('-').map(num => parseInt(num, 10));
    
    const location = document.getElementById('location').value.trim();
    const companion = document.getElementById('companion').value.trim();
    let memo = document.getElementById('memo').value.trim();
    
    // 추천된 장소가 추가된 경우(added=true), 메모 필드의 자동 생성된 내용 필터링
    if (addedParam === 'true') {
        console.log('[Debug] 추천 장소 추가 상태에서 일정 저장. 메모 필드 필터링 확인');
        
        // 자동 생성된 메모 내용 필터링
        const autoMemoPatterns = [
            /\[추천된 장소\][\s\S]*?(?=\n\n|\n$|$)/g,
            /\[추천된 이벤트\][\s\S]*?(?=\n\n|\n$|$)/g,
            /추천 이유:[\s\S]*?(?=\n\n|\n$|$)/g,
            /참고 링크:[\s\S]*?(?=\n\n|\n$|$)/g,
            /참고 정보:[\s\S]*?(?=\n\n|\n$|$)/g
        ];
        
        // 자동 생성 메모 패턴 제거
        let filteredMemo = memo;
        autoMemoPatterns.forEach(pattern => {
            filteredMemo = filteredMemo.replace(pattern, '');
        });
        
        // 연속된 빈 줄 제거 및 앞뒤 공백 제거
        filteredMemo = filteredMemo.replace(/\n{3,}/g, '\n\n').trim();
        
        // 필터링된 메모 사용
        memo = filteredMemo;
        console.log('[Debug] 저장 전 메모 필터링 결과:', memo.length ? '메모 내용 있음' : '메모 내용 없음');
    }
    
    console.log('[Debug] 폼 데이터:', { location, companion, memo });
    
    // 필수 필드 검증
    if (!location) {
        console.error('[Error] 위치 필드가 비어 있습니다.');
        showErrorMessage('위치를 입력해주세요.', 'location');
        document.getElementById('location').focus();
        isSubmitting = false;
        return;
    }
    
    // 구나 동 단위 입력 검증 - 임시로 비활성화
    /*
    if (!validateLocationFormat(location)) {
        console.error('[Error] 위치 형식이 잘못되었습니다:', location);
        showErrorMessage('위치 형식이 올바르지 않습니다. 구나 동 단위로 입력해주세요.', 'location');
        document.getElementById('location').focus();
        isSubmitting = false;
        return;
    }
    */
    
    // 저장 버튼 비활성화
    const saveBtn = document.querySelector('.save-btn');
    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = '저장 중...';
    }
    
    try {
        // 요청 데이터 준비
        const scheduleData = {
            date: normalizedDate,
            location: location,
            companion: companion || '',
            memo: memo || ''
        };
        
        console.log('[Debug] 전송할 데이터:', scheduleData);
        
        // 인증 토큰 확인
        const accessToken = localStorage.getItem('access_token');
        if (!accessToken) {
            console.error('[Error] 인증 토큰이 없습니다.');
            showErrorMessage('로그인이 필요합니다.');
            window.location.replace('login.html');
            return;
        }
        
        // 기존 일정이 있는지 먼저 확인 (중복 저장 방지)
        const checkResponse = await fetch(`${BACKEND_BASE_URL}/calendar/schedules/`, {
                headers: {
                    'Authorization': `Bearer ${accessToken}`
                }
            });
            
        if (!checkResponse.ok) {
            console.error('[Error] 일정 조회 실패:', checkResponse.status, checkResponse.statusText);
            throw new Error(`일정 조회 실패: ${checkResponse.status}`);
        }
        
        const data = await checkResponse.json();
        
        // 데이터를 항상 배열로 변환
        const schedules = Array.isArray(data) ? data :
                         (data.schedules && Array.isArray(data.schedules)) ? data.schedules :
                         (data ? [data] : []);
        
        console.log('[Debug] 기존 일정 데이터:', schedules);
        
        // 정확히 일치하는 일정 찾기 (연-월-일 전체 비교)
        let existingSchedule = null;
        
        for (const schedule of schedules) {
            if (!schedule.date) continue;
            
            // 날짜 정규화하여 비교
            const scheduleNormalizedDate = normalizeDate(schedule.date);
            if (!scheduleNormalizedDate) continue;
            
            // 연, 월, 일이 모두 일치하는지 확인
            const [scheduleYear, scheduleMonth, scheduleDay] = scheduleNormalizedDate.split('-').map(num => parseInt(num, 10));
            
            if (scheduleYear === year && scheduleMonth === month && scheduleDay === day) {
                existingSchedule = schedule;
                console.log('[Debug] 기존 일정 발견:', existingSchedule);
                break;
            }
        }
        
        let response;
        
        // 기존 일정이 있으면 업데이트(PUT), 없으면 새로 생성(POST)
        if (existingSchedule) {
            console.log('[Debug] 기존 일정 업데이트 시도:', existingSchedule.id);
            response = await fetch(`${BACKEND_BASE_URL}/calendar/schedules/${existingSchedule.id}/`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${accessToken}`
                },
                body: JSON.stringify(scheduleData)
            });
        } else {
            console.log('[Debug] 새 일정 생성 시도');
            response = await fetch(`${BACKEND_BASE_URL}/calendar/schedules/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${accessToken}`
                },
                body: JSON.stringify(scheduleData)
            });
        }
        
        console.log('[Debug] API 응답 상태:', response.status, response.statusText);
        
        // 응답 처리
        if (response.ok) {
            const result = await response.json();
            console.log('[Debug] 저장 성공:', result);
            
            // 성공 메시지 표시
            showSuccessMessage('일정이 성공적으로 저장되었습니다!');
            
            // 새로운 일정 데이터로 폼 업데이트
            document.getElementById('location').value = location;
            document.getElementById('companion').value = companion;
            document.getElementById('memo').value = memo;
        } else {
            // 오류 응답 자세히 처리
            console.error('[Error] 저장 실패:', response.status, response.statusText);
            let errorMessage = `저장에 실패했습니다 (${response.status})`;
            
            try {
                const errorData = await response.json();
                console.error('[Error] 상세 오류 데이터:', errorData);
                
                if (errorData.error) errorMessage += `: ${errorData.error}`;
                else if (errorData.message) errorMessage += `: ${errorData.message}`;
                else if (errorData.detail) errorMessage += `: ${errorData.detail}`;
                
                // 필드별 오류 처리
                if (errorData.location) {
                    showErrorMessage(`위치 오류: ${errorData.location}`, 'location');
                    return;
                }
                if (errorData.date) {
                    showErrorMessage(`날짜 오류: ${errorData.date}`);
                    return;
                }
            } catch (e) {
                console.error('[Error] 오류 응답 파싱 실패:', e);
            }
            
            showErrorMessage(errorMessage);
        }
        
    } catch (error) {
        // 오류 처리
        console.error('[Error] 일정 저장 중 오류:', error);
        showErrorMessage('일정 저장 중 오류가 발생했습니다: ' + error.message);
    } finally {
        // 저장 버튼 상태 복원
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.textContent = '저장하기';
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
function showErrorMessage(message, inputField = null) {
    showMessage(message, 'error');
    
    // 입력 필드에 오류 스타일 적용
    if (inputField) {
        // 모든 필드의 오류 스타일 초기화
        document.querySelectorAll('.form-group input, .form-group select, .form-group textarea').forEach(
            field => field.classList.remove('error-field')
        );
        
        // 오류가 있는 필드에 오류 스타일 추가
        const fieldElement = typeof inputField === 'string' 
            ? document.getElementById(inputField) 
            : inputField;
            
        if (fieldElement) {
            fieldElement.classList.add('error-field');
            fieldElement.focus();
        }
    }
}

/**
 * 메시지를 화면에 표시하는 공통 함수
 * @param {string} message - 표시할 메시지
 * @param {string} type - 메시지 타입 (success, info, error)
 */
function showMessage(message, type) {
    // 기존 메시지 요소가 있으면 제거
    const existingMessage = document.querySelector('.message');
    if (existingMessage) {
        existingMessage.remove();
    }
    
    // 메시지 요소 생성
    const messageElement = document.createElement('div');
    messageElement.className = `message ${type}-message`;
    messageElement.textContent = message;
    
    // 날짜 문자열 요소 찾기
    const selectedDateElement = document.querySelector('.selected-date');
    
    if (selectedDateElement) {
        // 메시지 컨테이너 찾기 또는 생성
        let messageContainer = document.querySelector('.message-container');
        if (!messageContainer) {
            messageContainer = document.createElement('div');
            messageContainer.className = 'message-container';
            
            // 날짜 문자열 바로 다음에 추가
            selectedDateElement.insertAdjacentElement('afterend', messageContainer);
        }
        
        // 메시지 추가
        messageContainer.appendChild(messageElement);
    } else {
        // 날짜 문자열 요소가 없는 경우 기존 방식으로 표시
        let messageContainer = document.querySelector('.message-container');
        if (!messageContainer) {
            messageContainer = document.createElement('div');
            messageContainer.className = 'message-container';
            
            // 페이지의 상단에 추가 (폼 바로 위)
            const formContainer = document.querySelector('.form-container') || document.querySelector('form') || document.body.firstChild;
            document.body.insertBefore(messageContainer, formContainer);
        }
        
        // 메시지 추가
        messageContainer.appendChild(messageElement);
    }
    
    // 일정 시간 후 메시지 자동 제거 (성공 및 정보 메시지만)
    if (type === 'success' || type === 'info') {
    setTimeout(() => {
            if (messageElement.parentNode) {
                messageElement.remove();
            }
        }, 5000);
    }
}

/**
 * 폼을 초기화하는 함수
 */
function resetForm() {
    const locationInput = document.getElementById('location');
    const contentTextarea = document.getElementById('content');
    
    if (locationInput) locationInput.value = '';
    if (contentTextarea) contentTextarea.value = '';
}

// 일정 제출 함수 - 저장 후 캘린더로 이동
async function submitSchedule() {
    // 이미 요청 중이면 중복 요청 방지
    if (isSubmitting) {
        return;
    }
    
    // 요청 중 상태로 설정
    isSubmitting = true;
    
    // 필수 데이터 확인
    const location = document.getElementById('location').value.trim();
    if (!location) {
        document.getElementById('location').focus();
        isSubmitting = false;
        return;
    }
    
    // 구나 동 단위 입력 검증
    if (!validateLocationFormat(location)) {
        document.getElementById('location').focus();
        isSubmitting = false;
        return;
    }
    
    // 버튼 상태 변경
    const submitBtn = document.querySelector('.submit-btn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = '저장 중...';
    }
    
    try {
    // 데이터 준비
    const urlParams = new URLSearchParams(window.location.search);
    const dateParam = urlParams.get('date');
        if (!dateParam) {
            throw new Error('날짜 정보가 없습니다.');
        }
        
        // 날짜 정규화
        const normalizedDate = normalizeDate(dateParam);
        
        if (!normalizedDate) {
            throw new Error('유효하지 않은 날짜 형식입니다.');
        }
        
        const companion = document.getElementById('companion').value.trim();
        const memo = document.getElementById('memo').value.trim();
        
        // 일정 데이터 객체
    const scheduleData = {
            date: normalizedDate,
        location: location,
            companion: companion || '',
            memo: memo || ''
    };
    
        // 토큰 확인
        const accessToken = localStorage.getItem('access_token');
        if (!accessToken) {
            window.location.href = 'login.html';
            return;
        }
        
        // 1. 기존 일정 확인 (같은 날짜의 일정 찾기)
        const getResponse = await fetch(`${BACKEND_BASE_URL}/calendar/schedules/`, {
            headers: { 'Authorization': `Bearer ${accessToken}` }
        });
        
        if (!getResponse.ok) {
            throw new Error(`일정 조회 실패 (${getResponse.status})`);
        }
        
        const data = await getResponse.json();
        
        // 일정 배열 추출
        const schedules = Array.isArray(data) ? data : 
                         (data.schedules && Array.isArray(data.schedules)) ? data.schedules : 
                         (data ? [data] : []);
        
        // 같은 날짜의 일정 찾기
        const [year, month, day] = normalizedDate.split('-').map(num => parseInt(num, 10));
        
        let existingSchedule = null;
        for (const item of schedules) {
            if (!item.date) continue;
            
            // 모든 날짜를 YYYY-MM-DD 형식으로 정규화
            const itemNormalizedDate = normalizeDate(item.date);
            if (!itemNormalizedDate) continue;
            
            // 연, 월, 일이 모두 일치하는지 확인
            const [itemYear, itemMonth, itemDay] = itemNormalizedDate.split('-').map(num => parseInt(num, 10));
            
            if (itemYear === year && itemMonth === month && itemDay === day) {
                existingSchedule = item;
                break;
            }
        }
        
        let response;
        
        // 2. 기존 일정이 있으면 업데이트, 없으면 새로 생성
        if (existingSchedule) {
            response = await fetch(`${BACKEND_BASE_URL}/calendar/schedules/${existingSchedule.id}/`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${accessToken}`
                },
                body: JSON.stringify(scheduleData)
            });
        } else {
            response = await fetch(`${BACKEND_BASE_URL}/calendar/schedules/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${accessToken}`
            },
            body: JSON.stringify(scheduleData)
            });
        }
        
                // 3. 응답 처리
                if (!response.ok) {
                    const errorData = await response.json().catch(() => ({}));
                    throw new Error(`일정 저장 실패 (${response.status})`);
                }
                
                // 캘린더로 이동
                
                // 방법 1: 직접 window.location.href 변경 (기본 방법)
                try {
        window.location.href = 'calendar.html';
                } catch (e) {
                    // 방법 1 실패
                }
        
                // 방법 2: setTimeout으로 지연 후 이동 시도
        setTimeout(() => {
                    try {
                        window.location.replace('calendar.html');
                    } catch (e) {
                        // 방법 2 실패
                        
                        // 방법 3: window.open 사용
                        try {
                            window.open('calendar.html', '_self');
                        } catch (e2) {
                            // 방법 3 실패
                            
                            // 방법 4: 홈 버튼 찾아서 클릭
                            const homeButton = document.querySelector('a[href="calendar.html"]');
            if (homeButton) {
                homeButton.click();
            } else {
                                // 방법 5: history API 사용
                                window.history.pushState({}, '', 'calendar.html');
                                window.location.reload();
            }
                        }
                    }
                }, 500);
                
    } catch (error) {
                // 오류 처리
    } finally {
                // 버튼 상태 복원 (에러 발생 시에만 필요)
                if (isSubmitting) { // 이미 페이지 이동 중이 아닌 경우에만
                    if (submitBtn) {
                        submitBtn.disabled = false;
                        submitBtn.textContent = '저장 후 캘린더로 이동';
                    }
        isSubmitting = false;
                }
    }
}

// 로그아웃 함수
async function logout() {
    try {
        const refreshToken = localStorage.getItem('refresh_token');
        const accessToken = localStorage.getItem('access_token');
        
                // 로그아웃 API, 호출 시도
        if (refreshToken && accessToken) {
            try {
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
            } catch (error) {
                        // API 호출 오류
            }
        }
    } catch (error) {
                // 처리 오류
    } finally {
        // 로컬 스토리지에서 토큰 제거 (항상 실행)
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        localStorage.removeItem('username');
        
                // 페이지 이동
        setTimeout(() => {
            window.location.href = 'login.html';
                }, 500);
    }
}

// 특정 날짜의 일정 불러오기
async function fetchScheduleForDate(date) {
    try {
        // URL 파라미터에서 added=true 여부 확인
        const urlParams = new URLSearchParams(window.location.search);
        const addedParam = urlParams.get('added');

        // 1. 접근 토큰 확인
        const token = localStorage.getItem('access_token');
        if (!token) {
            return;
        }
        
        // 2. 날짜 정규화 - YYYY-MM-DD 형식 확보
        const normalizedDate = normalizeDate(date);
        
        if (!normalizedDate) {
            return;
        }
        
        // 일정을 불러오는 중임을 표시
        if (addedParam !== 'true') { // 추천 장소가 추가된 경우에는 이 메시지를 표시하지 않음
            showInfoMessage('일정을 불러오는 중입니다...');
        }
        
        // 날짜 파싱
        const [year, month, day] = normalizedDate.split('-').map(num => parseInt(num, 10));
        
        // 3. 해당 날짜로 직접 API 요청 (서버 측 필터링)
        const response = await fetch(`${BACKEND_BASE_URL}/calendar/schedules/?date=${normalizedDate}`, {
            headers: {'Authorization': `Bearer ${token}`}
        });

        if (!response.ok) {
            showErrorMessage('일정을 불러올 수 없습니다.');
            return;
        }
        
        // 4. 응답 데이터 가져오기
        const data = await response.json();
        
        // 5. 데이터 구조 처리
        let schedules = [];
        let weatherData = null;
        
        // 새로운 API 응답 형식 처리 (날씨 포함)
        if (data.schedules && Array.isArray(data.schedules)) {
            schedules = data.schedules;
            weatherData = data.weather;
        }
        // 이전 API 응답 형식 처리 (배열만 반환)
        else if (Array.isArray(data)) {
            schedules = data;
        }
        // 단일 객체인 경우
        else if (typeof data === 'object' && data !== null) {
            if (data.id) {
                schedules = [data]; // 객체 하나면 배열로 변환
            }
        }
        
        // 6. 정규화된 날짜가 일치하는 일정 찾기
        let foundSchedule = null;
        for (const item of schedules) {
            if (!item.date) continue;
            
            // 모든 날짜를 YYYY-MM-DD 형식으로 정규화
            const itemNormalizedDate = normalizeDate(item.date);
            if (!itemNormalizedDate) continue;
            
            // 연, 월, 일이 모두 일치하는지 확인
            const [itemYear, itemMonth, itemDay] = itemNormalizedDate.split('-').map(num => parseInt(num, 10));
            
            if (itemYear === year && itemMonth === month && itemDay === day) {
                foundSchedule = item;
                break;
            }
        }
        
        // 7. 날씨 데이터 처리 (날씨 정보가 있으면)
        if (weatherData && Array.isArray(weatherData)) {
            // 해당 날짜의 날씨 찾기
            const dayWeather = weatherData.find(item => item.date === normalizedDate);
            if (dayWeather) {
                // 날씨 정보 업데이트
                updateWeatherDisplay(dayWeather);
            }
        }
        
        // 8. 일정이 있으면 폼에 데이터 표시
        if (foundSchedule) {
            // a. 요소 찾기
            const locationInput = document.getElementById('location');
            const companionInput = document.getElementById('companion');
            const memoInput = document.getElementById('memo');
            
            // b. 데이터 채우기 (null 체크 포함)
            if (locationInput) locationInput.value = foundSchedule.location || '';
            if (companionInput) companionInput.value = foundSchedule.companion || '';
            
            // 메모 처리: 추천 장소가 추가된 경우(added=true) 자동 생성된 메모 필터링
            if (memoInput && foundSchedule.memo) {
                let memoText = foundSchedule.memo;
                
                // 추천 장소 추가 시 자동 생성된 메모 패턴 필터링
                if (addedParam === 'true') {
                    // 추천 장소/이벤트 관련 자동 생성 메모 패턴 제거
                    const autoMemoPatterns = [
                        /\[추천된 장소\][\s\S]*?(?=\n\n|\n$|$)/g,
                        /\[추천된 이벤트\][\s\S]*?(?=\n\n|\n$|$)/g,
                        /추천 이유:[\s\S]*?(?=\n\n|\n$|$)/g,
                        /참고 링크:[\s\S]*?(?=\n\n|\n$|$)/g,
                        /참고 정보:[\s\S]*?(?=\n\n|\n$|$)/g
                    ];
                    
                    // 자동 생성 메모 패턴 제거
                    autoMemoPatterns.forEach(pattern => {
                        memoText = memoText.replace(pattern, '');
                    });
                    
                    // 연속된 빈 줄 제거
                    memoText = memoText.replace(/\n{3,}/g, '\n\n');
                    
                    // 앞뒤 공백 제거
                    memoText = memoText.trim();
                    
                    console.log('[Debug] 메모에서 자동 생성된 내용 필터링 완료');
                }
                
                // 필터링된 메모 설정
                memoInput.value = memoText;
            } else if (memoInput) {
                memoInput.value = '';
            }
            
            // 추천 장소 추가 시 메시지 표시
            if (addedParam === 'true') {
                showInfoMessage('추천 장소가 추가되었습니다. 메모는 사용자가 직접 관리합니다.');
            } else {
                // 성공 메시지 표시
                showSuccessMessage('저장된 일정을 불러왔습니다.');
            }
            
            return true;
        } else {
            // 폼 초기화
            const locationInput = document.getElementById('location');
            const companionInput = document.getElementById('companion');
            const memoInput = document.getElementById('memo');
            
            if (locationInput) locationInput.value = '';
            if (companionInput) companionInput.value = '';
            if (memoInput) memoInput.value = '';
            
            // 정보 메시지 표시
            if (addedParam === 'true') {
                showInfoMessage('추천 장소가 추가되었지만, 해당 날짜에 저장된 일정이 없습니다.');
            } else {
                showInfoMessage('해당 날짜에 저장된 일정이 없습니다.');
            }
            
            return false;
        }
    } catch (error) {
        console.error('일정 불러오기 오류:', error);
        // 오류 메시지 표시
        showErrorMessage('일정을 불러오는 중 오류가 발생했습니다.');
        return false;
    }
}

// 날씨 정보 업데이트 함수
function updateWeatherDisplay(weatherData) {
    if (!weatherData) return;
    
    try {
        // 선택된 날짜 표시 업데이트
        const selectedDateEl = document.querySelector('.selected-date');
        if (selectedDateEl) {
            // 기존 텍스트에서 이모티콘 제거 (이미 있는 경우)
            let dateText = selectedDateEl.textContent.replace(/[\u{1F300}-\u{1F5FF}\u{1F900}-\u{1F9FF}\u{1F600}-\u{1F64F}\u{1F680}-\u{1F6FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '').trim();
            
            // 날씨 아이콘 추가
            if (weatherData.icon) {
                dateText += ` ${weatherData.icon}`;
            }
            
            selectedDateEl.textContent = dateText;
        }
        
        // 미니 캘린더의 해당 날짜에도 날씨 아이콘 표시
        const calendarDay = document.querySelector(`.calendar-day.selected .weather-icon`);
        if (calendarDay && weatherData.icon) {
            calendarDay.textContent = weatherData.icon;
            
            // 툴크으로 날씨 설명 추가
            const dayEl = calendarDay.closest('.calendar-day');
            if (dayEl && weatherData.text) {
                dayEl.title = weatherData.text;
            }
        }
    } catch (error) {
        console.error('날씨 표시 업데이트 오류:', error);
    }
}

// 일정 삭제 함수
window.deleteSchedule = function() {
    // 이미 실행 중이면 중복 실행 방지
    if (window.deleteInProgress === true) {
        return;
    }
    
    // 실행 중 표시
    window.deleteInProgress = true;
    
    try {
        // URL에서 날짜 매개변수 추출
        const urlParams = new URLSearchParams(window.location.search);
        const dateParam = urlParams.get('date');
        if (!dateParam) {
            window.deleteInProgress = false;
            return;
        }
        
        // 날짜 정규화
        const normalizedDate = normalizeDate(dateParam);
        
        if (!normalizedDate) {
            window.deleteInProgress = false;
            return;
        }
        
        // 날짜를 연월일로 분리
        const [year, month, day] = normalizedDate.split('-').map(num => parseInt(num, 10));
        
        // 토큰 확인
        const token = localStorage.getItem('access_token');
        if (!token) {
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
        
        // 모든 일정 조회 (서버측 필터링 사용하지 않음)
        fetch(`${BACKEND_BASE_URL}/calendar/schedules/`, {
            headers: { 'Authorization': `Bearer ${token}` }
        })
        .then(response => response.json())
        .then(data => {
            // 데이터 구조 처리 - 새로운 API 응답 형식도 고려
            let schedules = [];
            
            // 새로운 API 응답 형식
            if (data.schedules && Array.isArray(data.schedules)) {
                schedules = data.schedules;
            }
            // 이전 API 응답 형식 (배열만 반환)
            else if (Array.isArray(data)) {
                schedules = data;
            }
            // 단일 객체인 경우
            else if (typeof data === 'object' && data !== null && data.id) {
                schedules = [data];
            }
            // 기타 경우는 빈 배열 유지
            
            // 정확히 일치하는 일정 찾기 (연-월-일 전체 비교)
            const matchingSchedule = schedules.find(schedule => {
                if (!schedule.date) return false;
                
                // 날짜 정규화하여 비교
                const scheduleNormalizedDate = normalizeDate(schedule.date);
                if (!scheduleNormalizedDate) return false;
                
                // 연, 월, 일이 모두 일치하는지 확인
                const [scheduleYear, scheduleMonth, scheduleDay] = scheduleNormalizedDate.split('-').map(num => parseInt(num, 10));
                
                return scheduleYear === year && scheduleMonth === month && scheduleDay === day;
            });
            
            if (!matchingSchedule) {
                // 일치하는 일정이 없음
                window.deleteInProgress = false;
                
                // 버튼 상태 복원
                if (deleteBtn) {
                    deleteBtn.disabled = false;
                    deleteBtn.textContent = '일정 삭제하기';
                }
                
                showErrorMessage('삭제할 일정을 찾을 수 없습니다.');
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
                
                // 1. 폼 필드 초기화
                document.getElementById('location').value = '';
                document.getElementById('companion').value = '';
                document.getElementById('memo').value = '';
                
                // 2. 1.5초 후 캘린더로 이동 (색상 업데이트 위해)
                setTimeout(() => {
                    window.location.href = 'calendar.html';
                }, 500);
            } else {
                // 삭제 실패
                
                // 버튼 상태 복원
                if (deleteBtn) {
                    deleteBtn.disabled = false;
                    deleteBtn.textContent = '일정 삭제하기';
                }
            }
            
            window.deleteInProgress = false;
        })
        .catch(error => {
            // 버튼 상태 복원
            if (deleteBtn) {
                deleteBtn.disabled = false;
                deleteBtn.textContent = '일정 삭제하기';
            }
            
            window.deleteInProgress = false;
        });
    } catch (error) {
        window.deleteInProgress = false;
        
        // 버튼 상태 복원
        const deleteBtn = document.querySelector('.delete-btn');
        if (deleteBtn) {
            deleteBtn.disabled = false;
            deleteBtn.textContent = '일정 삭제하기';
        }
    }
};

// 전역 함수로 명시적 등록 (파일 끝에 추가)
window.saveScheduleToDB = saveScheduleToDB;
window.submitSchedule = submitSchedule;
window.deleteSchedule = deleteSchedule;
window.fetchWeatherForDate = fetchWeatherForDate;
window.validateLocationFormat = validateLocationFormat;

// 날짜 정규화 함수
function normalizeDate(dateInput) {
    console.log(`[Debug] normalizeDate 함수 호출됨 - 입력값: ${dateInput}, 타입: ${typeof dateInput}`);
    
    try {
        // 이미 YYYY-MM-DD 형식이면 그대로 반환
        if (typeof dateInput === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(dateInput)) {
            console.log(`[Debug] 이미 정규화된 형식: ${dateInput}`);
            return dateInput;
        }
        
        // Date 객체면 변환
        let date;
        if (dateInput instanceof Date) {
            date = dateInput;
        } else {
            date = new Date(dateInput);
        }
        
        // 유효한 날짜인지 확인
        if (isNaN(date.getTime())) {
            console.error(`[Debug] 유효하지 않은 날짜 입력: ${dateInput}`);
            return null;
        }
        
        // YYYY-MM-DD 형식으로 반환
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const normalized = `${year}-${month}-${day}`;
        
        console.log(`[Debug] 정규화된 날짜: ${normalized}`);
        return normalized;
    } catch (error) {
        console.error(`[Debug] 날짜 정규화 중 오류 발생: ${error}`, error);
        return null;
    }
}

// 장소 입력 형식 검증 함수 - 임시로 모든 값 허용
function validateLocationFormat(location) {
    // 임시: 모든 입력 허용 (비어있지만 않으면 됨)
    return location != null && location.trim().length > 0;
    
    // 원래 검증 로직은 주석 처리
    /*
    // 한국 주소 형식 검증
    // 구 또는 동으로 끝나는 주소 패턴
    const districtPattern = /구$/; // 강남구, 서초구 등
    const dongPattern = /동$/;     // 역삼동, 삼성동 등
    const roPattern = /로$/;       // 테헤란로, 강남대로 등 
    const streetPattern = /길$/;   // 삼성로8길 등
    
    // 주소에 한글이 포함되어 있고, 구/동/로/길로 끝나는지 검사
    return (
        /[가-힣]/.test(location) && 
        (districtPattern.test(location) || 
         dongPattern.test(location) || 
         roPattern.test(location) || 
         streetPattern.test(location))
    );
    */
}

// 날씨 상태를 이모티콘으로 변환
function mapWeatherConditionToIcon(condition) {
    // 한국 기상청 날씨 코드에 따른 아이콘 매핑
    const weatherIcons = {
        '맑음': '☀️',
        '구름조금': '🌤️',
        '구름많음': '⛅',
        '흐림': '☁️',
        '비': '🌧️',
        '눈': '❄️',
        '비/눈': '🌨️',
        '소나기': '🌦️',
        '안개': '🌫️',
        '번개': '⚡',
        '폭우': '🌊',
        '황사': '😷',
        '미세먼지': '😷'
    };
    
    // PTY 코드에 따른 아이콘 매핑
    const ptyIcons = {
        '0': '☀️', // 맑음
        '1': '🌧️', // 비
        '2': '🌨️', // 비/눈
        '3': '❄️', // 눈
        '4': '🌧️'  // 소나기
    };
    
    // 일기 조건에 따른 아이콘 매핑
    const conditionIcons = {
        'clear': '☀️', 
        'sunny': '☀️',
        'partly_cloudy': '🌤️',
        'partly cloudy': '🌤️',
        'mostly_cloudy': '⛅',
        'mostly cloudy': '⛅',
        'cloudy': '☁️',
        'overcast': '☁️',
        'rain': '🌧️',
        'rainy': '🌧️',
        'snow': '❄️',
        'snowy': '❄️',
        'sleet': '🌨️',
        'shower': '🌦️',
        'fog': '🌫️',
        'mist': '🌫️',
        'haze': '🌫️',
        'thunderstorm': '⚡',
        'storm': '⚡',
        'dusty': '😷'
    };
    
    if (typeof condition === 'string') {
        // 먼저 한글 매핑 확인
        if (weatherIcons[condition]) {
            return weatherIcons[condition];
        }
        
        // 영어 매핑 확인 (소문자로 변환하여 비교)
        const lowerCondition = condition.toLowerCase();
        for (const [key, value] of Object.entries(conditionIcons)) {
            if (lowerCondition.includes(key)) {
                return value;
            }
        }
        
        return '🌤️'; // 기본 아이콘
    } else if (typeof condition === 'number' || !isNaN(parseInt(condition))) {
        return ptyIcons[condition.toString()] || '🌤️';
    }
    
    return '🌤️'; // 기본 아이콘
}

// 추천된 장소/이벤트 불러오기 함수
async function loadRecommendedPlaces(date) {
    try {
        const token = localStorage.getItem('access_token');
        if (!token) {
            return;
        }
        
        // 날짜 정규화
        const normalizedDate = normalizeDate(date);
        if (!normalizedDate) return;
        
        // 추천된 장소 목록 가져오기
        const response = await fetch(`${BACKEND_BASE_URL}/calendar/recommended-places/?date=${normalizedDate}`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (!response.ok) {
            console.error('추천된 장소를 불러오는데 실패했습니다.');
            return;
        }
        
        const data = await response.json();
        const recommendedPlaces = Array.isArray(data) ? data : [];
        
        // 추천된 장소/이벤트 표시
        displayRecommendedPlaces(recommendedPlaces);
        
    } catch (error) {
        console.error('추천된 장소 로드 중 오류:', error);
    }
}

// 추천된 장소/이벤트 표시 함수
function displayRecommendedPlaces(places) {
    console.log('[Debug] displayRecommendedPlaces 함수 호출됨');
    console.log('[Debug] 추천된 장소 응답 상태:', places ? '데이터 있음' : '데이터 없음');
    console.log('[Debug] 추천된 장소 데이터:', places);
    
    const container = document.getElementById('recommended-places-list');
    if (!container) {
        console.error('[Debug] recommended-places-list 컨테이너를 찾을 수 없습니다.');
        return;
    }
    
    // 컨테이너 초기화
    container.innerHTML = '';
    
    // 섹션 헤더 요소 선택
    const sectionHeader = document.querySelector('.recommended-places-header');
    if (!sectionHeader) {
        console.warn('[Debug] .recommended-places-header 요소를 찾을 수 없습니다.');
    }
    
    // 추천 장소가 없는 경우
    if (!places || places.length === 0) {
        console.log('[Debug] 표시할 추천 장소가 없습니다.');
        
        if (sectionHeader) {
            sectionHeader.textContent = '추천된 장소';
        }
        
        const noRecommendation = document.createElement('div');
        noRecommendation.className = 'no-recommendations';
        noRecommendation.textContent = '추천된 장소가 없습니다.';
        container.appendChild(noRecommendation);
        return;
    }
    
    if (sectionHeader) {
        sectionHeader.textContent = `추천된 장소`;
        sectionHeader.style.color = '#007bff';
    }
    
    // 각 추천 장소/이벤트에 대한 UI 요소 생성
    places.forEach((place, index) => {
        console.log(`[Debug] 장소 #${index + 1} 처리 중: ${place.place_name}`);
        console.log(`[Debug] 장소 타입: ${place.place_type}, 데이터:`, place);
        
        const placeItem = document.createElement('div');
        placeItem.className = 'recommended-item';
        placeItem.dataset.id = place.id;
        
        // 헤더 부분 (이름과 토글 버튼)
        const header = document.createElement('div');
        header.className = 'recommended-item-header';
        
        const name = document.createElement('div');
        name.className = 'recommended-item-name';
        name.textContent = place.place_name;
        header.appendChild(name);
        
        const toggleBtn = document.createElement('button');
        toggleBtn.className = 'recommended-item-toggle';
        toggleBtn.innerHTML = '▼';
        toggleBtn.setAttribute('aria-label', '상세 정보 토글');
        header.appendChild(toggleBtn);
        
        placeItem.appendChild(header);
        
        // 상세 정보 영역
        const details = document.createElement('div');
        details.className = 'recommended-item-details';
        
        // 장소/이벤트 유형에 따라 다른 정보 표시
        const isEvent = place.place_type === 'event';
        
        if (isEvent) {
            // 이벤트인 경우: 일시, 장소만 표시 (추천 이유 제거)
            if (place.event_date && place.event_date !== '정보 없음') {
                addDetailRow(details, '일시', place.event_date);
            }
            
            if (place.place_location && place.place_location !== '정보 없음') {
                addDetailRow(details, '장소', place.place_location);
            }
            
            // 추천 이유와 추가 정보는 표시하지 않음 (사용자 요청에 따라)
            
        } else {
            // 일반 장소인 경우: 위치만 표시 (추가 정보 제거)
            if (place.place_location && place.place_location !== '정보 없음') {
                addDetailRow(details, '위치', place.place_location);
            }
            
            // 추천 이유와 추가 정보는 표시하지 않음 (사용자 요청에 따라)
            
            // URL 링크도 표시하지 않음 (사용자 요청에 따라)
        }
        
        // 삭제 버튼 추가
        const actions = document.createElement('div');
        actions.className = 'recommended-item-actions';
        
        const removeBtn = document.createElement('button');
        removeBtn.className = 'remove-recommendation';
        removeBtn.textContent = '삭제';
        removeBtn.setAttribute('aria-label', '추천 장소 삭제');
        actions.appendChild(removeBtn);
        
        details.appendChild(actions);
        placeItem.appendChild(details);
        
        // 기본적으로 상세 정보 표시
        details.classList.add('visible');
        toggleBtn.classList.add('expanded');
        toggleBtn.innerHTML = '▲';
        
        // 이벤트 리스너 추가
        
        // 헤더 클릭 시 상세 정보 토글
        header.addEventListener('click', () => {
            details.classList.toggle('visible');
            toggleBtn.classList.toggle('expanded');
            toggleBtn.innerHTML = details.classList.contains('visible') ? '▲' : '▼';
        });
        
        // 삭제 버튼 클릭 시 추천 장소 삭제
        removeBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            removeRecommendedPlace(place.id, placeItem);
        });
        
        // 컨테이너에 추가
        container.appendChild(placeItem);
    });
    
    console.log('[Debug] 모든 추천 장소 표시 완료');
}

// 상세 정보 행 추가 헬퍼 함수
function addDetailRow(container, label, value) {
    const detailRow = document.createElement('div');
    detailRow.className = 'recommended-item-detail';
    
    const labelEl = document.createElement('strong');
    labelEl.textContent = label + ':';
    detailRow.appendChild(labelEl);
    
    // 값이 링크처럼 보이는 경우 (http:// 또는 https://)
    if (typeof value === 'string' && (value.startsWith('http://') || value.startsWith('https://'))) {
        const linkEl = document.createElement('a');
        linkEl.href = value;
        linkEl.textContent = '바로가기';
        linkEl.target = '_blank';
        linkEl.rel = 'noopener noreferrer';
        detailRow.appendChild(linkEl);
    } else {
        const valueEl = document.createElement('span');
        valueEl.textContent = value;
        
        // 레이블 유형에 따라 CSS 클래스 추가
        if (label === '일시') {
            valueEl.classList.add('event-date');
        } else if (label === '위치' || label === '장소') {
            valueEl.classList.add('location');
        } else if (label === '추천 이유') {
            valueEl.classList.add('reason');
        }
        
        detailRow.appendChild(valueEl);
    }
    
    container.appendChild(detailRow);
}

// 추천된 장소 삭제 함수
async function removeRecommendedPlace(id, element) {
    if (!confirm('이 추천 장소를 목록에서 삭제하시겠습니까? (일정은 그대로 유지됩니다)')) {
        return;
    }
    
    try {
        const token = localStorage.getItem('access_token');
        if (!token) {
            alert('로그인이 필요한 기능입니다.');
            return;
        }
        
        const response = await fetch(`${BACKEND_BASE_URL}/calendar/recommended-places/${id}/`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
        
        if (response.ok) {
            // UI에서 요소 제거
            element.remove();
            
            // 성공 메시지 표시
            showSuccessMessage('추천 장소가 목록에서 삭제되었습니다.');
            
            // 추천 장소 수 업데이트
            const sectionHeader = document.querySelector('.recommended-places-header');
            const remainingItems = document.querySelectorAll('.recommended-item').length;
            
            if (sectionHeader) {
                if (remainingItems > 0) {
                    sectionHeader.textContent = `추천된 장소`;
                } else {
                    sectionHeader.textContent = '추천된 장소';
                    sectionHeader.style.color = '';
                    
                    const container = document.getElementById('recommended-places-list');
                    if (container) {
                        const noRecommendation = document.createElement('div');
                        noRecommendation.className = 'no-recommendations';
                        noRecommendation.textContent = '추천된 장소가 없습니다.';
                        container.appendChild(noRecommendation);
                    }
                }
            }
        } else {
            throw new Error('응답 오류: ' + response.status);
        }
    } catch (error) {
        console.error('추천 장소 삭제 중 오류:', error);
        showErrorMessage('장소 삭제 중 오류가 발생했습니다.');
    }
}