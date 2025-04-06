// Frontend login handling
document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const loginError = document.getElementById('loginError');
    
    // Utility functions for session management
    const SessionManager = {
        // Store user data in session storage
        setUserSession: function(userData) {
            sessionStorage.setItem('user', JSON.stringify(userData));
        },
        
        // Get user data from session storage
        getUserSession: function() {
            const userStr = sessionStorage.getItem('user');
            return userStr ? JSON.parse(userStr) : null;
        },
        
        // Clear session data
        clearSession: function() {
            sessionStorage.removeItem('user');
            localStorage.removeItem('token');
        },
        
        // Check if user is logged in
        isLoggedIn: function() {
            return !!localStorage.getItem('token') && !!sessionStorage.getItem('user');
        }
    };
    
    function showError(message) {
        loginError.textContent = message;
        loginError.style.display = 'block';
    }

    function clearError() {
        loginError.textContent = '';
        loginError.style.display = 'none';
    }
    
    loginForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        clearError();
        
        const email = document.getElementById('email').value.trim();
        const password = document.getElementById('password').value;
        
        try {
            console.log('Attempting login with:', { email, password: '***' });
            
            const requestBody = {
                email: email,
                password: password
            };
            
            console.log('Sending request with body:', JSON.stringify(requestBody));
            
            const response = await fetch('http://localhost:5006/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json'
                },
                body: JSON.stringify(requestBody)
            });

            const data = await response.json();
            console.log('Server response:', data);

            if (response.ok) {
                console.log('Login successful');
                // Store token in localStorage
                localStorage.setItem('token', data.token);
                // Store user data in sessionStorage
                SessionManager.setUserSession(data.user);
                // Redirect to index page
                window.location.href = 'index.html';
                console.error(data.message);
            } else {               
                showError(data.message || 'Login failed. Please try again.');
            }
        } catch (error) {
            console.error('Login error:', error);
            showError('Connection error. Please try again later.');
        }
    });

    // Check if user is already logged in
    if (SessionManager.isLoggedIn()) {
        window.location.href = 'index.html';
    }
});

// Export SessionManager for use in other files
window.SessionManager = SessionManager;

