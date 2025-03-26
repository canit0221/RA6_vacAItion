const BACKEND_BASE_URL = 'https://vacaition.life';

document.addEventListener('DOMContentLoaded', () => {
    // 이미 로그인된 상태인지 확인
    checkAlreadyLoggedIn();
    
    const loginForm = document.getElementById('loginForm');
    const googleLoginBtn = document.getElementById('googleLoginBtn');
    
    // 구글 로그인 버튼 이벤트 리스너 추가
    googleLoginBtn.addEventListener('click', () => {
        // 프론트엔드의 콜백 페이지를 통한 로그인 처리
        // 정확한 URL 생성 (localhost:5500으로 직접 지정)
        const callbackUrl = 'https://ra6vacaition.vercel.app/pages/google-callback.html';
        const googleAuthURL = `${BACKEND_BASE_URL}/accounts/google/login/?redirect_uri=${encodeURIComponent(callbackUrl)}`;
        console.log('Google Auth URL:', googleAuthURL);
        window.location.href = googleAuthURL;
    });
    
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        
        try {
            const response = await fetch(`${BACKEND_BASE_URL}/login/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    username,
                    password
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // 토큰을 로컬 스토리지에 저장
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('refresh_token', data.refresh_token);
                localStorage.setItem('username', data.username);
                
                // 알림창 없이 바로 채팅 페이지로 이동
                window.location.href = '../index.html';
            } else {
                alert(data.message || '로그인에 실패했습니다.');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('서버와의 통신 중 오류가 발생했습니다.');
        }
    });
});

// 이미 로그인된 상태인지 확인하는 함수
function checkAlreadyLoggedIn() {
    // URL 파라미터 확인
    const urlParams = new URLSearchParams(window.location.search);
    const fromDeleteAccounts = urlParams.get('fromDeleteAccounts');
    
    // 회원 탈퇴 후 이동한 경우 검사를 건너뜀
    if (fromDeleteAccounts === 'true') {
        return;
    }
    
    // 액세스 토큰이 있는지 확인
    const accessToken = localStorage.getItem('access_token');
    if (accessToken) {
        // 이미 로그인되어 있다면 채팅 페이지로 이동
        window.location.href = '../index.html';
    }
}

// 구글 로그인 콜백 처리를 위한 함수
// URL에 토큰 정보가 있는지 확인하고 있으면 저장
function handleGoogleLoginCallback() {
    const urlParams = new URLSearchParams(window.location.search);
    const accessToken = urlParams.get('access');
    const refreshToken = urlParams.get('refresh');
    const username = urlParams.get('username');
    
    // 추가 정보 입력이 필요한지 확인하는 파라미터 추가
    const needAdditionalInfo = urlParams.get('need_additional_info');
    const tempData = urlParams.get('temp_data');
    
    // 추가 정보 입력이 필요한 경우
    if (needAdditionalInfo === 'true' && tempData) {
        // 추가 정보 입력 페이지로 리다이렉트
        window.location.href = `./google-additional-info.html?data=${tempData}`;
        return;
    }
    
    if (accessToken && refreshToken && username) {
        localStorage.setItem('access_token', accessToken);
        localStorage.setItem('refresh_token', refreshToken);
        localStorage.setItem('username', username);
        
        // 토큰 정보를 저장한 후 메인 페이지로 리디렉션
        window.location.href = '../index.html';
    }
}

// 페이지 로드 시 콜백 처리 함수 실행
handleGoogleLoginCallback();
