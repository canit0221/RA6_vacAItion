const BACKEND_BASE_URL = 'http://localhost:8000';

// 디버깅용 로그
console.log('캘린더 페이지 로드됨');
console.log('토큰 상태:', localStorage.getItem('access_token') ? '있음' : '없음');
// 문제 해결 후 이 코드는 삭제하세요

// 백엔드 서버 연결 확인
async function checkServerConnection() {
    try {
        // 존재하는 API 경로로 변경 (로그인 API 사용)
        const response = await fetch(`${BACKEND_BASE_URL}/login/`, { 
            method: 'OPTIONS'
        });
        console.log('서버 연결 상태:', response.status);
        return true;
    } catch (error) {
        console.error('서버 연결 실패:', error);
        return false;
    }
}

// 페이지 로드 시 서버 연결 확인
checkServerConnection().then(isConnected => {
    if (!isConnected) {
        console.warn('백엔드 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.');
    } else {
        console.log('백엔드 서버 연결 성공');
    }
});

// 전역 로그아웃 함수 (HTML에서 직접 호출 가능)
window.doLogout = function() {
    console.log('전역 로그아웃 함수 호출됨');
    // 로컬 스토리지에서 토큰 제거
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('username');
    
    alert('로그아웃 되었습니다.');
    window.location.replace('login.html');
};

class Calendar {
    constructor() {
        this.date = new Date();
        this.currentMonth = this.date.getMonth();
        this.currentYear = this.date.getFullYear();
        this.selectedDate = null;
        
        this.monthYearElement = document.querySelector('.month-year');
        this.daysContainer = document.querySelector('#calendar-days');
        
        this.initializeControls();
        this.render();
        this.fetchMonthlySchedules();
    }

    initializeControls() {
        document.querySelector('.prev-month').addEventListener('click', () => {
            this.currentMonth--;
            if (this.currentMonth < 0) {
                this.currentMonth = 11;
                this.currentYear--;
            }
            this.render();
            this.fetchMonthlySchedules();
        });

        document.querySelector('.next-month').addEventListener('click', () => {
            this.currentMonth++;
            if (this.currentMonth > 11) {
                this.currentMonth = 0;
                this.currentYear++;
            }
            this.render();
            this.fetchMonthlySchedules();
        });
    }

    async fetchMonthlySchedules() {
        try {
            // 백엔드 URL 구조에 맞는 정확한 API 엔드포인트
            const apiUrl = `${BACKEND_BASE_URL}/calendar/schedules/?year=${this.currentYear}&month=${this.currentMonth + 1}`;
            console.log('스케줄 API 호출:', apiUrl);
            
            const response = await fetch(apiUrl, {
                headers: {
                    'Authorization': `Bearer ${localStorage.getItem('access_token')}`
                }
            });
            
            if (response.status === 401) {
                // 인증 실패 시 로그인 페이지로 리다이렉트
                localStorage.removeItem('access_token');
                localStorage.removeItem('refresh_token');
                localStorage.removeItem('username');
                window.location.replace('login.html');
                return;
            }

            if (response.status === 404) {
                console.error('API 엔드포인트를 찾을 수 없습니다:', apiUrl);
                this.updateCalendarWithSchedules([]);
                this.showErrorMessage('스케줄 API를 찾을 수 없습니다. 서버 설정을 확인하세요.');
                return;
            }

            if (response.status === 500) {
                console.error('서버 내부 오류:', apiUrl);
                this.updateCalendarWithSchedules([]);
                this.showErrorMessage('서버 오류가 발생했습니다. 데이터베이스 연결이나 마이그레이션 상태를 확인하세요.');
                return;
            }

            if (!response.ok) {
                console.error(`API 오류 ${response.status}: ${apiUrl}`);
                this.updateCalendarWithSchedules([]);
                this.showErrorMessage(`API 오류 (${response.status})`);
                return;
            }

            // 성공!
            console.log('API 응답:', response);
            const schedules = await response.json();
            this.updateCalendarWithSchedules(schedules);
            
        } catch (error) {
            console.error('스케줄 가져오기 오류:', error);
            // 에러 시 빈 일정으로 업데이트
            this.updateCalendarWithSchedules([]);
            this.showErrorMessage('서버 통신 중 오류가 발생했습니다.');
        }
    }

    updateCalendarWithSchedules(schedules) {
        // 모든 일정 표시 제거
        document.querySelectorAll('.day').forEach(day => {
            day.classList.remove('has-event');
        });

        // 일정이 있는 날짜에 표시
        schedules.forEach(schedule => {
            const scheduleDate = new Date(schedule.date);
            const dayElement = document.querySelector(`.day[data-date="${scheduleDate.getDate()}"]`);
            if (dayElement) {
                dayElement.classList.add('has-event');
            }
        });
    }

    render() {
        const firstDay = new Date(this.currentYear, this.currentMonth, 1);
        const lastDay = new Date(this.currentYear, this.currentMonth + 1, 0);
        const startingDay = firstDay.getDay();
        const monthLength = lastDay.getDate();

        // Update month and year display
        const months = ['January', 'February', 'March', 'April', 'May', 'June', 
                       'July', 'August', 'September', 'October', 'November', 'December'];
        this.monthYearElement.textContent = `${months[this.currentMonth]} ${this.currentYear}`;

        // Clear previous days
        this.daysContainer.innerHTML = '';

        // Add empty cells for days before the first day of the month
        for (let i = 0; i < startingDay; i++) {
            const emptyDay = document.createElement('div');
            emptyDay.className = 'day empty';
            this.daysContainer.appendChild(emptyDay);
        }

        // Add days of the month
        for (let day = 1; day <= monthLength; day++) {
            const dayElement = document.createElement('div');
            dayElement.className = 'day';
            dayElement.textContent = day;
            dayElement.setAttribute('data-date', day);

            // Add weather icon (mock data)
            const weatherIcon = document.createElement('span');
            weatherIcon.className = 'weather-icon';
            if (Math.random() > 0.5) {
                weatherIcon.textContent = '☀️';
            } else {
                weatherIcon.textContent = '☁️';
            }
            dayElement.appendChild(weatherIcon);

            // Add click event
            dayElement.addEventListener('click', () => {
                // Remove previous selection
                const previousSelected = document.querySelector('.day.selected');
                if (previousSelected) {
                    previousSelected.classList.remove('selected');
                }
                
                // Add new selection
                dayElement.classList.add('selected');
                this.selectedDate = new Date(this.currentYear, this.currentMonth, day);
                
                // Navigate to add schedule page with date parameter
                // UTC 변환을 방지하기 위해 toISOString 대신 로컬 날짜 형식 사용
                const year = this.selectedDate.getFullYear();
                const month = (this.selectedDate.getMonth() + 1).toString().padStart(2, '0');
                const dayVal = this.selectedDate.getDate().toString().padStart(2, '0');
                const dateStr = `${year}-${month}-${dayVal}`;
                console.log(`선택한 날짜: ${year}년 ${month}월 ${dayVal}일, URL 파라미터: ${dateStr}`);
                window.location.href = `add-schedule.html?date=${dateStr}`;
            });

            this.daysContainer.appendChild(dayElement);
        }
    }

    // 오류 메시지 표시
    showErrorMessage(message) {
        // 기존 에러 메시지 제거
        const existingError = document.querySelector('.error-message');
        if (existingError) {
            existingError.remove();
        }
        
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.style.color = 'red';
        errorDiv.style.padding = '10px';
        errorDiv.style.margin = '10px 0';
        errorDiv.style.border = '1px solid red';
        errorDiv.style.borderRadius = '5px';
        errorDiv.style.backgroundColor = '#ffebee';
        errorDiv.style.fontSize = '14px';
        errorDiv.textContent = message;
        
        // 캘린더 위에 오류 메시지 추가
        const calendarContainer = document.querySelector('.calendar-container');
        if (calendarContainer) {
            calendarContainer.prepend(errorDiv);
        } else {
            // 캘린더 컨테이너가 없으면 body에 추가
            document.body.prepend(errorDiv);
        }
    }
}

// 로그인 상태 확인 함수
function checkLoginStatus() {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
        window.location.replace('login.html');
        return false;
    }
    return true;
}

// UI 업데이트 함수
function updateUI() {
    // 사용자 이름 표시
    const username = localStorage.getItem('username');
    const profileLink = document.getElementById('profileLink');
    if (username && profileLink) {
        profileLink.textContent = `${username}님의 프로필`;
    }
}

// 이벤트 리스너 설정
function setupEventListeners() {
    // 프로필 링크
    const profileLink = document.getElementById('profileLink');
    if (profileLink) {
        profileLink.addEventListener('click', (e) => {
            e.preventDefault();
            window.location.href = 'profile.html';
        });
    }

    // 로그아웃 링크 (간단하게 로그아웃 링크만 사용)
    const logoutLink = document.getElementById('logoutLink') || document.querySelector('a.logout');
    if (logoutLink) {
        console.log('로그아웃 버튼 찾음', logoutLink);
        logoutLink.addEventListener('click', (e) => {
            e.preventDefault();
            console.log('로그아웃 클릭됨');
            doLogout(); // 전역 로그아웃 함수 사용
        });
    } else {
        console.warn('로그아웃 버튼을 찾을 수 없습니다');
        
        // 버튼이 없으면 생성 (임시 해결책)
        const nav = document.querySelector('nav');
        if (nav) {
            const newLogoutLink = document.createElement('a');
            newLogoutLink.href = '#';
            newLogoutLink.id = 'logoutLink';
            newLogoutLink.className = 'logout';
            newLogoutLink.textContent = '로그아웃';
            newLogoutLink.addEventListener('click', (e) => {
                e.preventDefault();
                doLogout();
            });
            nav.appendChild(newLogoutLink);
            console.log('로그아웃 버튼 생성됨');
        }
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
                // 서버에 맞는 로그아웃 경로 사용
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

// DOM 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
    // 로그인 상태 확인
    if (!checkLoginStatus()) return;
    
    // UI 업데이트
    updateUI();
    
    // 이벤트 리스너 설정
    setupEventListeners();
    
    // 캘린더 초기화
    new Calendar();
}); 