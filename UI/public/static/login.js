document.addEventListener('DOMContentLoaded', function () {
    const loginForm = document.getElementById('loginForm');
    const loginError = document.getElementById('loginError');
  
    // Utility for session and login management
    const SessionManager = {
      setUserSession(userData, token) {
        sessionStorage.setItem('user', JSON.stringify(userData));
        localStorage.setItem('token', token);
      },
      getUser() {
        const userStr = sessionStorage.getItem('user');
        return userStr ? JSON.parse(userStr) : null;
      },
      clearSession() {
        sessionStorage.removeItem('user');
        localStorage.removeItem('token');
      },
      isLoggedIn() {
        return !!sessionStorage.getItem('user') && !!localStorage.getItem('token');
      }
    };
  
    // Export to global scope so other files can use it
    window.SessionManager = SessionManager;
  
    function showError(message) {
      loginError.textContent = message;
      loginError.style.display = 'block';
    }
  
    function clearError() {
      loginError.textContent = '';
      loginError.style.display = 'none';
    }
  
    // If user is already logged in, redirect to home
    if (SessionManager.isLoggedIn()) {
      window.location.href = 'index.html';
      return;
    }
  
    // Handle form submission
    loginForm.addEventListener('submit', async function (e) {
      e.preventDefault();
      clearError();
  
      const email = document.getElementById('email').value.trim();
      const password = document.getElementById('password').value;
  
      if (!email || !password) {
        showError('Please enter your email and password.');
        return;
      }
  
      try {
        const response = await fetch('http://localhost:5006/login', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Accept: 'application/json'
          },
          body: JSON.stringify({ email, password })
        });
  
        const data = await response.json();
        console.log('Login response:', data);
  
        if (response.ok && data.user && data.token) {
          SessionManager.setUserSession(data.user, data.token);
          window.location.href = 'index.html'; // Redirect after successful login
        } else {
          showError(data.message || 'Login failed. Please try again.');
        }
      } catch (error) {
        console.error('Login error:', error);
        showError('Unable to connect to the server. Please try again later.');
      }
    });
  });
  