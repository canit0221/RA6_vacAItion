const BACKEND_BASE_URL = 'https://vacaition.life';

document.addEventListener('DOMContentLoaded', () => {
    // 로그인 상태 확인
    checkLoginStatus();
    
    // 폼 제출 이벤트 리스너 추가
    const form = document.getElementById('changePasswordForm');
    if (form) {
        form.addEventListener('submit', handlePasswordChange);
    }
    
    // 사용자 아이디 표시
    const usernameInput = document.getElementById('username');
    if (usernameInput) {
        usernameInput.value = localStorage.getItem('username') || '';
    }
});

// 로그인 상태 확인
function checkLoginStatus() {
    const accessToken = localStorage.getItem('access_token');
    if (!accessToken) {
        alert('로그인이 필요한 페이지입니다.');
        window.location.href = '../pages/login.html';
    }
}

// 비밀번호 변경 처리
async function handlePasswordChange(e) {
    e.preventDefault();
    
    const currentPassword = document.getElementById('currentPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    const confirmPassword = document.getElementById('confirmPassword').value;
    
    if (newPassword !== confirmPassword) {
        alert('새 비밀번호가 일치하지 않습니다.');
        return;
    }
    
    try {
        const response = await fetch(`${BACKEND_BASE_URL}/api/accounts/change-password/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('access_token')}`
            },
            body: JSON.stringify({
                current_password: currentPassword,
                new_password: newPassword,
                confirm_password: confirmPassword,
                refresh: localStorage.getItem('refresh_token')
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            // 새로운 토큰 저장
            localStorage.setItem('access_token', data.access_token);
            localStorage.setItem('refresh_token', data.refresh_token);
            
            alert('비밀번호가 성공적으로 변경되었습니다.');
            window.location.href = '../pages/profile.html';
        } else {
            alert(data.message || '비밀번호 변경에 실패했습니다.');
        }
    } catch (error) {
        console.error('비밀번호 변경 에러:', error);
        alert('비밀번호 변경 중 오류가 발생했습니다.');
    }
} 