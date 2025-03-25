const BACKEND_BASE_URL = 'https://vacaition.life';

document.addEventListener('DOMContentLoaded', () => {
    const forgotPasswordForm = document.getElementById('forgotPasswordForm');
    
    forgotPasswordForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const username = document.getElementById('username').value;
        const email = document.getElementById('email').value;
        
        try {
            const response = await fetch(`${BACKEND_BASE_URL}/request-password-reset/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    username,
                    email
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                alert('비밀번호 재설정 링크가 이메일로 발송되었습니다.\n이메일을 확인해주세요.');
                window.location.href = '../pages/login.html';
            } else {
                alert(data.message || '이메일 발송에 실패했습니다.');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('서버와의 통신 중 오류가 발생했습니다.');
        }
    });
}); 