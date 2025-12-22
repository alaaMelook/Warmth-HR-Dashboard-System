// static/js/keycloak-init.js - بس لتخزين الـ token وإضافة header

document.addEventListener("DOMContentLoaded", function () {
    // جيب الـ access_token من الـ backend (اللي مخزن في session بعد /callback)
    fetch('/api/get-token')
        .then(response => {
            if (!response.ok) {
                console.warn("No token yet – user probably not logged in");
                return null;
            }
            return response.json();
        })
        .then(data => {
            if (data && data.access_token) {
                localStorage.setItem('access_token', data.access_token);
                localStorage.setItem('refresh_token', data.refresh_token || '');
                console.log("✅ Token loaded from backend and stored in localStorage");
                addAuthHeaderToFetch();
            }
        })
        .catch(err => console.error("Error fetching token:", err));

    // إضافة Authorization header تلقائيًا لكل API call
    function addAuthHeaderToFetch() {
        const originalFetch = window.fetch;
        window.fetch = function(url, options = {}) {
            if (url.startsWith('/api/') || url.includes('/api/')) {
                const token = localStorage.getItem('access_token');
                if (token) {
                    options.headers = {
                        ...options.headers,
                        'Authorization': `Bearer ${token}`
                    };
                }
            }
            return originalFetch(url, options);
        };
        console.log("✅ Authorization header interceptor activated");
    }

    // Logout button
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', function(e) {
            e.preventDefault();
            localStorage.clear();
            sessionStorage.clear();
            // نروح لـ Keycloak logout عشان يمسح الـ session هناك
            window.location.href = "http://localhost:8080/realms/HR-System/protocol/openid-connect/logout?redirect_uri=" + encodeURIComponent(window.location.origin + '/login');
        });
    }
});