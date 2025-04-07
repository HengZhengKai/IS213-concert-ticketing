// Define SessionManager in the global scope immediately
const SessionManager = {
    setUserSession: function(userData) {
        try { sessionStorage.setItem('user', JSON.stringify(userData)); } catch (e) { console.error("Error setting user session:", e); }
    },
    getUserSession: function() {
        try { const userStr = sessionStorage.getItem('user'); return userStr ? JSON.parse(userStr) : null; } catch (e) { console.error("Error getting user session:", e); return null; }
    },
    clearSession: function() {
        try { sessionStorage.removeItem('user'); localStorage.removeItem('token'); } catch (e) { console.error("Error clearing session:", e); }
    },
    isLoggedIn: function() {
        try { return !!localStorage.getItem('token') && !!sessionStorage.getItem('user'); } catch (e) { console.error("Error checking login status:", e); return false; }
    }
};

// Assign to window immediately after definition
window.SessionManager = SessionManager;

// Login form specific logic runs only after DOM is loaded and only if form exists
document.addEventListener('DOMContentLoaded', function() {
    console.log("[login.js] DOMContentLoaded fired.");
    const loginForm = document.getElementById('loginForm');
    const loginError = document.getElementById('loginError');
    
    // Check if we are on the login page by checking for the form
    if (loginForm && loginError) {
        console.log("[login.js] Login form found, setting up listeners.");
        
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
            
            const emailInput = document.getElementById('email');
            const passwordInput = document.getElementById('password');
            if (!emailInput || !passwordInput) { 
                console.error("[login.js] Email or password input not found!"); 
                return; 
            }
            const email = emailInput.value.trim();
            const password = passwordInput.value;
            
            try {
                console.log('[login.js] Attempting login with:', { email, password: '***' });
                
                const requestBody = { email: email, password: password };
                console.log('[login.js] Sending request with body:', JSON.stringify(requestBody));
                
                // Fetch points to user_service (port 5006) login endpoint
                const response = await fetch('http://localhost:5006/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify(requestBody)
                });

                const data = await response.json();
                console.log('[login.js] Server response:', data);

                if (response.ok && data.token && data.user) { // Check for token and user
                    console.log('[login.js] Login successful');
                    localStorage.setItem('token', data.token);
                    SessionManager.setUserSession(data.user); 
                    window.location.href = 'index.html';
                } else {
                    const errorMsg = data.message || 'Login failed. Please try again.';
                    console.error('[login.js] Login failed:', errorMsg);
                    showError(errorMsg);
                }
            } catch (error) {
                console.error('[login.js] Login error:', error);
                showError('Connection error. Please try again later.');
            }
        });

        // Redirect check (only runs if form exists)
        // Added check for pathname to prevent potential redirect loops 
        if (SessionManager.isLoggedIn() && window.location.pathname.includes('/login.html')) {
             console.log("[login.js] User already logged in on login page, redirecting to index.");
            window.location.href = 'index.html';
        }
        
    } else {
         console.log("[login.js] Login form not found on this page.");
    }
});

