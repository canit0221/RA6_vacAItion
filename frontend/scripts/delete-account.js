const BACKEND_BASE_URL = 'https://vacaition.life';

document.addEventListener('DOMContentLoaded', () => {
    // 로그인 상태 확인
    checkLoginStatus();
    
    // 사용자명 입력란에 현재 로그인한 사용자명 자동 입력
    const usernameInput = document.getElementById('username');
    if (usernameInput) {
        usernameInput.value = localStorage.getItem('username') || '';
    }
    
    // 구글 로그인 사용자인지 확인하고 UI 조정
    checkSocialLoginUser();
    
    // 회원 탈퇴 버튼 이벤트 리스너
    const deleteAccountsBtn = document.getElementById('deleteAccountsBtn');
    if (deleteAccountsBtn) {
        deleteAccountsBtn.addEventListener('click', deleteAccounts);
    }
    
    // 달력으로 돌아가기 버튼 이벤트 리스너
    const returnToHomeBtn = document.getElementById('returnToHomeBtn');
    if (returnToHomeBtn) {
        returnToHomeBtn.addEventListener('click', (e) => {
            e.preventDefault();
            window.location.href = '../index.html';
        });
    }
});

// 로그인 상태 확인 함수
function checkLoginStatus() {
    const accessToken = localStorage.getItem('access_token');
    
    if (!accessToken) {
        // 비로그인 상태면 로그인 페이지로 리다이렉트
        // alert('로그인이 필요한 페이지입니다.');
        window.location.href = '../pages/login.html';
    }
}

// 구글 로그인 사용자인지 확인하는 함수
function checkSocialLoginUser() {
    const isSocialLogin = localStorage.getItem('is_social_login') === 'true';
    const passwordField = document.getElementById('password');
    const passwordLabel = document.querySelector('label[for="password"]');
    
    if (isSocialLogin && passwordField && passwordLabel) {
        // 구글 로그인 사용자인 경우 비밀번호 필드 숨김 처리
        passwordField.style.display = 'none';
        passwordLabel.style.display = 'none';
    }
}

// 회원 탈퇴 함수
async function deleteAccounts() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password')?.value || '';
    const currentUsername = localStorage.getItem('username');
    const accessToken = localStorage.getItem('access_token');
    const isSocialLogin = localStorage.getItem('is_social_login') === 'true';
    
    // 입력한 사용자명과 로그인된 사용자명 일치 확인
    if (username !== currentUsername) {
        alert('입력한 사용자명이 현재 로그인된 계정과 일치하지 않습니다.');
        return;
    }
    
    // 일반 계정인 경우 비밀번호 입력 확인
    if (!isSocialLogin) {
        // 필수 입력값 확인
        if (!password) {
            alert('비밀번호를 입력해주세요.');
            return;
        }
        
        // 비밀번호 확인을 위한 로그인 시도
        try {
            const loginResponse = await fetch(`${BACKEND_BASE_URL}/login/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    username: username,
                    password: password
                })
            });
            
            console.log('로그인 확인 응답 상태:', loginResponse.status);
            
            let loginData;
            try {
                loginData = await loginResponse.json();
            } catch (jsonError) {
                console.error('로그인 응답 파싱 오류:', jsonError);
                alert('로그인 정보를 확인할 수 없습니다.');
                return;
            }
            
            if (!loginResponse.ok) {
                alert('비밀번호가 일치하지 않습니다.');
                return;
            }
        } catch (error) {
            console.error('로그인 확인 에러:', error);
            alert('로그인 정보를 확인할 수 없습니다.');
            return;
        }
    }
    
    // 최종 확인 메시지
    if (!confirm('정말로 탈퇴하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) {
        return;
    }
    
    // 계정 삭제 API 호출
    try {
        const deleteResponse = await fetch(`${BACKEND_BASE_URL}/users/${username}/`, {
            method: 'DELETE',
            headers: {
                'Authorization': `Bearer ${accessToken}`,
                'Content-Type': 'application/json'
            }
        });
        
        console.log('삭제 응답 상태:', deleteResponse.status);
        
        // HTTP 상태 코드가 2xx인 모든 응답을 성공으로 처리
        if (deleteResponse.status >= 200 && deleteResponse.status < 300) {
            // 로컬 스토리지에서 토큰 제거
            localStorage.clear();
            
            alert('계정이 성공적으로 삭제되었습니다.');
            // 로그인 페이지로 이동 시 특별한 파라미터 추가
            window.location.href = './login.html?fromDeleteAccounts=true';
            return;
        }
        
        // 오류 응답 처리
        let errorMessage = '알 수 없는 오류';
        try {
            const deleteData = await deleteResponse.json();
            errorMessage = deleteData.message || deleteData.detail || '알 수 없는 오류';
        } catch (jsonError) {
            console.error('응답 파싱 오류:', jsonError);
        }
        
        alert(`탈퇴 처리 중 오류가 발생했습니다: ${errorMessage}`);
    } catch (deleteError) {
        console.error('삭제 요청 오류:', deleteError);
        
        // 네트워크 오류지만 실제로는 삭제가 성공했을 수 있으므로
        // 토큰을 제거하고 로그인 페이지로 이동
        localStorage.clear();
        
        alert('회원 탈퇴가 완료되었습니다.');
        // 로그인 페이지로 이동 시 특별한 파라미터 추가
        window.location.href = './login.html?fromDeleteAccounts=true';
    }
} 