const BACKEND_BASE_URL = 'https://vacaition.life';

document.addEventListener('DOMContentLoaded', () => {
    // URL에서 uid와 token 파라미터 추출
    const urlParams = new URLSearchParams(window.location.search);
    const uid = urlParams.get('uid');
    const token = urlParams.get('token');

    const resetPasswordForm = document.getElementById('resetPasswordForm');
    
    resetPasswordForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const newPassword = document.getElementById('newPassword').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        
        if (newPassword !== confirmPassword) {
            alert('새 비밀번호가 일치하지 않습니다.');
            return;
        }
        
        try {
            const response = await fetch(`${BACKEND_BASE_URL}/reset-password/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    uid: uid,
                    token: token,
                    new_password: newPassword
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                alert('비밀번호가 성공적으로 변경되었습니다.');
                window.location.href = '../pages/login.html';
            } else {
                alert(data.detail || data.message || '비밀번호 변경에 실패했습니다.');
            }
        } catch (error) {
            console.error('Error:', error);
            alert('비밀번호 변경 중 오류가 발생했습니다.');
        }
    });
}); 