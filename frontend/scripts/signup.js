const BACKEND_BASE_URL = 'https://vacaition.life';

document.addEventListener('DOMContentLoaded', () => {
    console.log('signup.js loaded');
    const signupForm = document.getElementById('signupForm');
    
    // 비밀번호 입력 필드 관련 요소
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirmPassword');
    
    // 비밀번호 안내 메시지를 표시할 요소 찾기
    let passwordFeedback = document.getElementById('passwordFeedback');
    
    // 없으면 새로 생성해서 비밀번호 입력 필드 뒤에 추가
    if (!passwordFeedback) {
        passwordFeedback = document.createElement('div');
        passwordFeedback.id = 'passwordFeedback';
        passwordFeedback.className = 'feedback-message';
        passwordFeedback.style.marginTop = '10px';
        passwordInput.parentNode.insertBefore(passwordFeedback, passwordInput.nextSibling);
    }
    
    // 비밀번호 확인 안내 메시지를 표시할 요소 찾기
    let confirmPasswordFeedback = document.getElementById('confirmPasswordFeedback');
    
    // 없으면 새로 생성해서 비밀번호 확인 입력 필드 뒤에 추가
    if (!confirmPasswordFeedback) {
        confirmPasswordFeedback = document.createElement('div');
        confirmPasswordFeedback.id = 'confirmPasswordFeedback';
        confirmPasswordFeedback.className = 'feedback-message';
        confirmPasswordFeedback.style.marginTop = '10px';
        confirmPasswordInput.parentNode.insertBefore(confirmPasswordFeedback, confirmPasswordInput.nextSibling);
    }
    
    // 비밀번호 입력 필드에 이벤트 리스너 추가
    passwordInput.addEventListener('input', validatePassword);
    
    // 비밀번호 확인 입력 필드에 이벤트 리스너 추가
    confirmPasswordInput.addEventListener('input', () => {
        validatePasswordMatch(passwordInput.value, confirmPasswordInput.value);
    });
    
    // 비밀번호 유효성 검사 함수
    function validatePassword() {
        const password = passwordInput.value;
        
        // 피드백 메시지 초기화
        passwordFeedback.textContent = '';
        passwordFeedback.style.color = '';
        
        if (password.length === 0) {
            passwordFeedback.textContent = '비밀번호를 입력해 주세요.';
            passwordFeedback.style.color = '#999';
            return false;
        } else if (password.length < 8) {
            passwordFeedback.textContent = '비밀번호는 최소 8자 이상이어야 합니다.';
            passwordFeedback.style.color = '#ff3860';
            return false;
        } else if (/^\d+$/.test(password)) {
            passwordFeedback.textContent = '비밀번호는 숫자로만 구성될 수 없습니다.';
            passwordFeedback.style.color = '#ff3860';
            return false;
        } else {
            passwordFeedback.textContent = '적합한 비밀번호입니다.';
            passwordFeedback.style.color = '#23d160';
            
            // 비밀번호 확인 필드가 비어있지 않다면 일치 여부 확인
            if (confirmPasswordInput.value) {
                validatePasswordMatch(password, confirmPasswordInput.value);
            }
            
            return true;
        }
    }
    
    // 비밀번호 일치 여부 확인 함수
    function validatePasswordMatch(password, confirmPassword) {
        confirmPasswordFeedback.textContent = '';
        confirmPasswordFeedback.style.color = '';
        
        if (!confirmPassword) {
            confirmPasswordFeedback.textContent = '비밀번호를 한번 더 입력해 주세요.';
            confirmPasswordFeedback.style.color = '#999';
            return false;
        } else if (password !== confirmPassword) {
            confirmPasswordFeedback.textContent = '비밀번호가 일치하지 않습니다.';
            confirmPasswordFeedback.style.color = '#ff3860';
            return false;
        } else {
            confirmPasswordFeedback.textContent = '비밀번호가 일치합니다.';
            confirmPasswordFeedback.style.color = '#23d160';
            return true;
        }
    }
    
    signupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const username = document.getElementById('username').value;
        const nickname = document.getElementById('nickname').value;
        const email = document.getElementById('email').value;
        const address = document.getElementById('address').value;
        const password = document.getElementById('password').value;
        const confirmPassword = document.getElementById('confirmPassword').value;
        
        // 비밀번호 검증
        if (!validatePassword()) {
            return;
        }
        
        // 비밀번호 일치 여부 확인
        if (!validatePasswordMatch(password, confirmPassword)) {
            return;
        }
        
        try {
            const response = await fetch(`${BACKEND_BASE_URL}/signup/`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    username,
                    nickname,
                    email,
                    user_address: address,
                    password
                })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // 회원가입 성공 시 바로 로그인 페이지로 이동
                // 현재 "Login here" 링크의 href 속성 값을 가져와서 사용
                const loginLink = document.querySelector('.login-link a');
                if (loginLink) {
                    // 로그인 링크의 href 값으로 페이지 이동
                    window.location.href = loginLink.getAttribute('href');
                } else {
                    // 링크를 찾지 못한 경우 기본 경로 사용
                    window.location.href = '../pages/login.html';
                }
            } else {
                // 서버에서 반환된 에러 메시지 처리
                if (data.errors) {
                    const errorMessages = [];
                    for (const field in data.errors) {
                        errorMessages.push(`${field}: ${data.errors[field].join(' ')}`);
                    }
                    alert(errorMessages.join('\n'));
                } else {
                    alert(data.message || '회원가입에 실패했습니다.');
                }
            }
        } catch (error) {
            console.error('Error:', error);
            alert('서버와의 통신 중 오류가 발생했습니다.');
        }
    }); 
}); 