// ===== Search Functionality =====
const searchInput = document.getElementById('searchInput');
const employeesTable = document.getElementById('employeesTable');

if (searchInput && employeesTable) {
    searchInput.addEventListener('input', function(e) {
        const searchTerm = e.target.value.toLowerCase().trim();
        const rows = employeesTable.querySelectorAll('tbody tr');
        
        rows.forEach(row => {
            // Skip empty state row
            if (row.querySelector('.empty-state')) {
                return;
            }
            
            const name = row.querySelector('.employee-name')?.textContent.toLowerCase() || '';
            const email = row.querySelector('.employee-email')?.textContent.toLowerCase() || '';
            const role = row.cells[1]?.textContent.toLowerCase() || '';
            const department = row.cells[2]?.textContent.toLowerCase() || '';
            const contact = row.cells[3]?.textContent.toLowerCase() || '';
            
            const matchFound = name.includes(searchTerm) || 
                              email.includes(searchTerm) || 
                              role.includes(searchTerm) || 
                              department.includes(searchTerm) ||
                              contact.includes(searchTerm);
            
            if (matchFound) {
                row.classList.remove('hidden');
            } else {
                row.classList.add('hidden');
            }
        });
        
        // Check if all rows are hidden
        const visibleRows = employeesTable.querySelectorAll('tbody tr:not(.hidden)');
        if (visibleRows.length === 0 || (visibleRows.length === 1 && visibleRows[0].querySelector('.empty-state'))) {
            showNoResults();
        } else {
            hideNoResults();
        }
    });
}

// ===== Department Filter =====
const departmentFilter = document.getElementById('departmentFilter');
let currentFilter = 'all';

if (departmentFilter) {
    departmentFilter.addEventListener('click', function() {
        // In a real implementation, this would show a dropdown menu
        // For now, we'll cycle through departments
        const departments = ['all', 'engineering', 'product', 'design', 'human resources', 'marketing', 'sales'];
        const currentIndex = departments.indexOf(currentFilter);
        const nextIndex = (currentIndex + 1) % departments.length;
        currentFilter = departments[nextIndex];
        
        filterByDepartment(currentFilter);
        updateFilterButtonText(currentFilter);
    });
}

function filterByDepartment(department) {
    const rows = employeesTable.querySelectorAll('tbody tr');
    
    rows.forEach(row => {
        if (row.querySelector('.empty-state')) {
            return;
        }
        
        if (department === 'all') {
            row.classList.remove('hidden');
        } else {
            const rowDepartment = row.getAttribute('data-department');
            if (rowDepartment === department.toLowerCase()) {
                row.classList.remove('hidden');
            } else {
                row.classList.add('hidden');
            }
        }
    });
}

function updateFilterButtonText(department) {
    const filterText = departmentFilter.querySelector('span:last-child');
    if (filterText) {
        if (department === 'all') {
            filterText.textContent = 'All Departments';
        } else {
            filterText.textContent = department.split(' ')
                .map(word => word.charAt(0).toUpperCase() + word.slice(1))
                .join(' ');
        }
    }
}

// ===== Edit Employee Function =====
function editEmployee(employeeId) {
    // Redirect to edit page or show edit modal
    console.log('Editing employee:', employeeId);
    
    // Example: redirect to edit page
    window.location.href = `/admin/employees/edit/${employeeId}`;
    
    // Or you can implement a modal for editing
}

// ===== Delete Employee Function =====
function deleteEmployee(employeeId, employeeName) {
    // Show confirmation dialog
    const confirmed = confirm(`Are you sure you want to delete ${employeeName}?`);
    
    if (confirmed) {
        // Send delete request
        fetch(`/admin/employees/delete/${employeeId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            },
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Remove row from table
                const row = document.querySelector(`tr[data-employee-id="${employeeId}"]`);
                if (row) {
                    row.remove();
                }
                
                // Show success message
                showNotification('Employee deleted successfully', 'success');
                
                // Check if table is empty
                const remainingRows = employeesTable.querySelectorAll('tbody tr').length;
                if (remainingRows === 0) {
                    showEmptyState();
                }
            } else {
                showNotification('Failed to delete employee', 'error');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showNotification('An error occurred while deleting employee', 'error');
        });
    }
}

// ===== Notification System =====
function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Add styles
    notification.style.cssText = `
        position: fixed;
        top: 24px;
        right: 24px;
        padding: 16px 24px;
        background: ${type === 'success' ? '#D1FAE5' : '#FEE2E2'};
        color: ${type === 'success' ? '#065F46' : '#991B1B'};
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        z-index: 9999;
        animation: slideIn 0.3s ease-out;
        font-weight: 500;
    `;
    
    // Add animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(400px);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
    
    // Add to page
    document.body.appendChild(notification);
    
    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, 3000);
}

// ===== Helper Functions =====
function showNoResults() {
    const tbody = employeesTable.querySelector('tbody');
    let noResultsRow = tbody.querySelector('.no-results-row');
    
    if (!noResultsRow) {
        noResultsRow = document.createElement('tr');
        noResultsRow.className = 'no-results-row';
        noResultsRow.innerHTML = `
            <td colspan="6" class="empty-state">
                <div style="font-size: 48px; margin-bottom: 16px;">🔍</div>
                <div style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">No results found</div>
                <div style="font-size: 14px;">Try adjusting your search or filters</div>
            </td>
        `;
        tbody.appendChild(noResultsRow);
    }
    
    noResultsRow.style.display = '';
}

function hideNoResults() {
    const noResultsRow = employeesTable.querySelector('.no-results-row');
    if (noResultsRow) {
        noResultsRow.style.display = 'none';
    }
}

function showEmptyState() {
    const tbody = employeesTable.querySelector('tbody');
    tbody.innerHTML = `
        <tr>
            <td colspan="6" class="empty-state">
                <div style="font-size: 48px; margin-bottom: 16px;">📋</div>
                <div style="font-size: 16px; font-weight: 600; margin-bottom: 8px;">No employees found</div>
                <div style="font-size: 14px;">Add your first employee to get started</div>
            </td>
        </tr>
    `;
}

// ===== Initialize on page load =====
document.addEventListener('DOMContentLoaded', function() {
    console.log('Employee Management System Loaded');
    
    // Add any initialization code here
    const employeeCount = employeesTable.querySelectorAll('tbody tr:not(.empty-state)').length;
    console.log(`Total employees: ${employeeCount}`);
});

// ===== Export functions for use in inline scripts =====
window.editEmployee = editEmployee;
window.deleteEmployee = deleteEmployee;