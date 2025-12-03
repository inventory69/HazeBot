// HazeBot Analytics - Browser Extension Helper
// This script can be used with browser extensions like Requestly or ModHeader
// to automatically inject JWT tokens into requests

// For use in browser console (temporary solution):
// =====================================================

// 1. Login and store token
async function loginToAnalytics(username, password) {
    try {
        const response = await fetch('https://api.haze.pro/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            localStorage.setItem('hazebot_jwt_token', data.token);
            localStorage.setItem('hazebot_user', data.user);
            localStorage.setItem('hazebot_role', data.role);
            console.log('✅ Login successful! Token stored.');
            console.log('User:', data.user, '| Role:', data.role);
            return data.token;
        } else {
            console.error('❌ Login failed:', data.error);
            return null;
        }
    } catch (error) {
        console.error('❌ Login error:', error);
        return null;
    }
}

// 2. Get stored token
function getToken() {
    const token = localStorage.getItem('hazebot_jwt_token');
    if (token) {
        console.log('Token found:', token.substring(0, 20) + '...');
        return token;
    } else {
        console.log('No token found. Please login first.');
        return null;
    }
}

// 3. Verify token is still valid
async function verifyToken() {
    const token = getToken();
    if (!token) return false;
    
    try {
        const response = await fetch('https://api.haze.pro/api/ping', {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.ok) {
            const data = await response.json();
            console.log('✅ Token is valid!');
            console.log('Username:', data.your_username);
            console.log('Role:', data.your_role);
            console.log('Permissions:', data.your_permissions);
            return true;
        } else {
            console.log('❌ Token is invalid or expired');
            localStorage.removeItem('hazebot_jwt_token');
            return false;
        }
    } catch (error) {
        console.error('❌ Verification error:', error);
        return false;
    }
}

// 4. Logout
function logout() {
    localStorage.removeItem('hazebot_jwt_token');
    localStorage.removeItem('hazebot_user');
    localStorage.removeItem('hazebot_role');
    console.log('✅ Logged out successfully');
}

// 5. Access Analytics Dashboard
function goToAnalytics() {
    const token = getToken();
    if (token) {
        console.log('Opening Analytics Dashboard...');
        console.log('Note: You need a browser extension to inject the Authorization header');
        console.log('Alternative: Use the /login page instead');
        window.location.href = 'https://api.haze.pro/analytics/';
    } else {
        console.log('Please login first using loginToAnalytics(username, password)');
    }
}

// Usage Instructions
console.log(`
🤖 HazeBot Analytics Browser Helper
====================================

1. Login:
   await loginToAnalytics('your-username', 'your-password')

2. Verify token:
   await verifyToken()

3. Get current token:
   getToken()

4. Logout:
   logout()

5. Go to Analytics:
   goToAnalytics()

Alternative: Use the login page at https://api.haze.pro/login
`);


// For Requestly Extension
// ========================
// Install Requestly Chrome Extension
// Add a "Modify Headers" rule:
// - URL Pattern: https://api.haze.pro/analytics/*
// - Header: Authorization
// - Value: Bearer <YOUR_TOKEN_HERE>


// For ModHeader Extension
// =======================
// Install ModHeader Chrome Extension
// Add a Request Header:
// - Name: Authorization
// - Value: Bearer <YOUR_TOKEN_HERE>
// - Filter: https://api.haze.pro/analytics/*


// For Tampermonkey Script (Auto-inject token)
// ============================================
// Create a new Tampermonkey script with this code:

const TAMPERMONKEY_SCRIPT = `
// ==UserScript==
// @name         HazeBot Analytics Auto-Auth
// @namespace    http://tampermonkey.net/
// @version      1.0
// @description  Automatically inject JWT token for HazeBot Analytics
// @author       HazeBot Team
// @match        https://api.haze.pro/analytics/*
// @grant        none
// ==/UserScript==

(function() {
    'use strict';
    
    // Get token from localStorage
    const token = localStorage.getItem('hazebot_jwt_token');
    
    if (!token) {
        console.log('⚠️ No HazeBot token found. Redirecting to login...');
        if (!window.location.pathname.includes('/login')) {
            window.location.href = '/login?redirect=' + encodeURIComponent(window.location.pathname);
        }
        return;
    }
    
    // Intercept fetch requests
    const originalFetch = window.fetch;
    window.fetch = function(...args) {
        let [resource, config] = args;
        
        // Add Authorization header to all requests
        if (!config) config = {};
        if (!config.headers) config.headers = {};
        
        if (typeof config.headers.set === 'function') {
            config.headers.set('Authorization', 'Bearer ' + token);
        } else {
            config.headers['Authorization'] = 'Bearer ' + token;
        }
        
        return originalFetch(resource, config);
    };
    
    console.log('✅ HazeBot Analytics Auto-Auth enabled');
})();
`;

console.log('\nTo use Tampermonkey script, copy the code below:');
console.log('Tampermonkey script available in TAMPERMONKEY_SCRIPT variable');
console.log('Run: console.log(TAMPERMONKEY_SCRIPT) to view the script');
