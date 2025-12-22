// ====================================
// Keycloak Token Management - COMPLETE & FIXED
// ====================================

/**
 * Get access token from backend session
 */
async function getAccessToken() {
    try {
        const response = await fetch('/api/get-token', {
            method: 'GET',
            credentials: 'include'
        });
        
        if (!response.ok) {
            console.error('❌ Failed to get token:', response.status);
            return null;
        }
        
        const data = await response.json();
        console.log('✅ Token retrieved successfully');
        return data.access_token;
    } catch (error) {
        console.error('❌ Error fetching token:', error);
        return null;
    }
}

/**
 * Make authenticated API call with JWT token
 */
async function authenticatedFetch(url, options = {}) {
    const token = await getAccessToken();
    
    if (!token) {
        console.error('❌ No access token available');
        window.location.href = '/login';
        return null;
    }
    
    console.log('🔐 Making authenticated request to:', url);
    console.log('🎫 Using token:', token.substring(0, 20) + '...');
    
    const headers = {
        ...options.headers,
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
    };
    
    try {
        const response = await fetch(url, {
            ...options,
            headers,
            credentials: 'include'
        });
        
        console.log('📬 Response status:', response.status);
        
        if (response.status === 401) {
            console.warn('⚠️ Token expired, redirecting to login...');
            alert('Your session has expired. Please login again.');
            window.location.href = '/login';
            return null;
        }
        
        if (response.status === 403) {
            console.error('🚫 Access forbidden');
            alert('Access denied. You do not have permission for this action.');
            return response;
        }
        
        return response;
    } catch (error) {
        console.error('❌ Fetch error:', error);
        throw error;
    }
}

// ====================================
// DELETE BUTTON HANDLER (CRITICAL FIX)
// ====================================

/**
 * Setup delete buttons with proper Authorization header
 * This intercepts ALL delete form submissions
 */
function setupDeleteButtons() {
    // Find all delete forms (they use POST method with hidden _method or actual DELETE)
    const deleteForms = document.querySelectorAll('form[action*="delete"], button[data-action*="delete"]');
    
    console.log(`🔍 Found ${deleteForms.length} delete forms/buttons`);
    
    deleteForms.forEach(form => {
        // If it's a button, find its parent form
        const actualForm = form.tagName === 'FORM' ? form : form.closest('form');
        
        if (!actualForm) return;
        
        console.log('🗑️ Setting up delete handler for:', actualForm.action);
        
        actualForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            const actionUrl = this.action;
            const confirmMsg = this.dataset.confirm || 'Are you sure you want to delete this item?';
            
            // Confirm deletion
            if (!confirm(confirmMsg)) {
                console.log('❌ Delete cancelled by user');
                return;
            }
            
            console.log('🔐 Sending DELETE request to:', actionUrl);
            
            // Get token
            const token = await getAccessToken();
            if (!token) {
                alert('Authentication required. Please login again.');
                window.location.href = '/login';
                return;
            }
            
            console.log('🎫 Token obtained:', token.substring(0, 30) + '...');
            
            try {
                // Send DELETE request with Authorization header
                const response = await fetch(actionUrl, {
                    method: 'DELETE',
                    headers: {
                        'Authorization': `Bearer ${token}`,
                        'Content-Type': 'application/json'
                    },
                    credentials: 'include'
                });
                
                console.log('📬 Delete response status:', response.status);
                
                if (response.ok) {
                    const result = await response.json();
                    console.log('✅ Delete successful:', result);
                    
                    alert(result.message || 'Item deleted successfully');
                    
                    // Redirect or reload
                    if (this.dataset.redirect) {
                        window.location.href = this.dataset.redirect;
                    } else {
                        window.location.reload();
                    }
                } else if (response.status === 403) {
                    alert('Access denied. You do not have permission to delete this item.');
                } else if (response.status === 401) {
                    alert('Session expired. Please login again.');
                    window.location.href = '/login';
                } else {
                    const error = await response.json().catch(() => ({ message: 'Delete failed' }));
                    alert('Error: ' + (error.message || 'Failed to delete item'));
                }
            } catch (error) {
                console.error('❌ Delete error:', error);
                alert('An error occurred while deleting. Please try again.');
            }
        });
    });
}

// ====================================
// FORM INTERCEPTORS - Add Authorization to Forms
// ====================================

/**
 * Intercept form submissions that require authentication
 */
function setupFormInterceptors() {
    // Find all forms with data-requires-auth attribute
    const authForms = document.querySelectorAll('form[data-requires-auth="true"]');
    
    console.log(`🔍 Found ${authForms.length} authenticated forms`);
    
    authForms.forEach(form => {
        console.log('📝 Setting up auth form:', form.action);
        
        form.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const actionUrl = this.action;
            const method = this.method.toUpperCase() || 'POST';
            
            console.log(`🔐 Submitting authenticated form: ${method} ${actionUrl}`);
            
            // Get token
            const token = await getAccessToken();
            if (!token) {
                alert('Authentication required. Please login again.');
                window.location.href = '/login';
                return;
            }
            
            const formData = new FormData(this);
            
            try {
                const response = await fetch(actionUrl, {
                    method: method,
                    headers: {
                        'Authorization': `Bearer ${token}`
                    },
                    body: formData,
                    credentials: 'include'
                });
                
                console.log('📬 Form response status:', response.status);
                
                if (response.ok) {
                    console.log('✅ Form submitted successfully');
                    
                    // Redirect or reload
                    if (this.dataset.redirect) {
                        window.location.href = this.dataset.redirect;
                    } else {
                        window.location.reload();
                    }
                } else if (response.status === 403) {
                    alert('Access denied. You do not have permission for this action.');
                } else if (response.status === 401) {
                    alert('Session expired. Please login again.');
                    window.location.href = '/login';
                } else {
                    alert('Error submitting form. Please try again.');
                }
            } catch (error) {
                console.error('❌ Form submission error:', error);
                alert('An error occurred. Please try again.');
            }
        });
    });
}

// ====================================
// AJAX BUTTON HANDLERS (Check-in/Check-out)
// ====================================

/**
 * Handle check-in/check-out buttons
 */
function setupAttendanceButtons() {
    const checkInBtn = document.getElementById('check-in-btn');
    const checkOutBtn = document.getElementById('check-out-btn');
    
    if (checkInBtn) {
        console.log('⏰ Setting up check-in button');
        checkInBtn.addEventListener('click', async () => {
            const response = await authenticatedFetch('/api/attendance/check-in', {
                method: 'POST'
            });
            
            if (!response) return;
            
            if (response.ok) {
                const result = await response.json();
                alert(result.message || 'Checked in successfully!');
                window.location.reload();
            }
        });
    }
    
    if (checkOutBtn) {
        console.log('⏰ Setting up check-out button');
        checkOutBtn.addEventListener('click', async () => {
            const response = await authenticatedFetch('/api/attendance/check-out', {
                method: 'POST'
            });
            
            if (!response) return;
            
            if (response.ok) {
                const result = await response.json();
                alert(result.message || 'Checked out successfully!');
                window.location.reload();
            }
        });
    }
}

// ====================================
// API FUNCTIONS (Examples)
// ====================================

/**
 * Get employees
 */
async function getEmployees() {
    const response = await authenticatedFetch('/api/employees');
    if (!response) return;
    
    if (response.ok) {
        return await response.json();
    }
}

/**
 * Create employee
 */
async function createEmployee(employeeData) {
    const response = await authenticatedFetch('/api/employees', {
        method: 'POST',
        body: JSON.stringify(employeeData)
    });
    
    if (!response) return;
    
    if (response.ok) {
        const result = await response.json();
        console.log('Employee created:', result);
        return result;
    } else if (response.status === 403) {
        alert('You do not have permission to create employees');
    } else {
        console.error('Failed to create employee:', response.status);
    }
}

/**
 * Delete employee (can also be called programmatically)
 */
async function deleteEmployee(employeeId) {
    if (!confirm('Are you sure you want to delete this employee?')) return;
    
    const response = await authenticatedFetch(`/api/employees/${employeeId}`, {
        method: 'DELETE'
    });
    
    if (!response) return;
    
    if (response.ok) {
        alert('Employee deleted successfully');
        window.location.reload();
    }
}

/**
 * Check if user is authenticated
 */
async function isAuthenticated() {
    const token = await getAccessToken();
    return !!token;
}

/**
 * Logout function
 */
function logout() {
    window.location.href = '/logout';
}

// ====================================
// PAGE LOAD INITIALIZATION
// ====================================

document.addEventListener('DOMContentLoaded', async function() {
    console.log('🔐 Keycloak Integration Initializing...');
    console.log('📍 Current page:', window.location.pathname);
    
    // Check if user is authenticated
    const token = await getAccessToken();
    if (token) {
        console.log('✅ User is authenticated');
        console.log('🎫 Token preview:', token.substring(0, 30) + '...');
    } else {
        console.log('⚠️ No token found (might be on login page)');
    }
    
    // Setup all interceptors and handlers
    setupDeleteButtons();     // 🗑️ Critical for delete functionality
    setupFormInterceptors();  // 📝 For forms with data-requires-auth
    setupAttendanceButtons(); // ⏰ For check-in/check-out
    
    console.log('✅ All handlers initialized successfully');
    
    // Test on employees page
    if (window.location.pathname.includes('/admin/employees')) {
        console.log('📋 On employees page - ready for operations');
    }
});

// ====================================
// EXPORT FOR GLOBAL USE
// ====================================
window.keycloakAuth = {
    getAccessToken,
    authenticatedFetch,
    getEmployees,
    createEmployee,
    deleteEmployee,
    isAuthenticated,
    logout
};

console.log('✅ Keycloak Auth loaded. Available at: window.keycloakAuth');