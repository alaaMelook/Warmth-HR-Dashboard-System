# 🔐 HR Officer Role Setup Guide

## ✅ What's Implemented

### Role Hierarchy:

1. **EMPLOYEE** - Read Only Access
   - Can view their own data
   - Cannot access admin dashboard
2. **HR_OFFICER** - Create, Read, Update (CRU)
   - ✅ Can access admin dashboard
   - ✅ Can create employees
   - ✅ Can read all data
   - ✅ Can update employees
   - ❌ Cannot delete employees (Admin only)
3. **HR_ADMIN** - Full CRUD Access
   - ✅ Full access to everything
   - ✅ Can delete employees

---

## 🚀 Setup HR_OFFICER Role in Keycloak

### Step 1: Create HR_OFFICER Role

1. Open Keycloak Admin Console: http://localhost:8080
2. Login as admin
3. Select Realm: **HR-System**
4. Go to **Realm Roles**
5. Click **Create Role**
6. Enter:
   - Role Name: `HR_OFFICER`
   - Description: `HR Officer - Create, Read, Update permissions`
7. Click **Save**

---

### Step 2: Assign HR_OFFICER Role to User

The user `om@fa.com` needs the HR_OFFICER role:

1. In Keycloak Admin Console
2. Go to **Users**
3. Search for: `om@fa.com`
4. Click on the user
5. Go to **Role Mapping** tab
6. Click **Assign role**
7. Select **HR_OFFICER** from the list
8. Click **Assign**

---

## 🧪 Testing HR_OFFICER Access

### Test 1: Login as HR_OFFICER

```
1. Go to: http://127.0.0.1:5000/login
2. Login with: om@fa.com
3. Expected: Redirected to Admin Dashboard ✅
```

---

### Test 2: Check Permissions

After login, open:

```
http://127.0.0.1:5000/api/check-permissions
```

**Expected Response:**

```json
{
  "status": "success",
  "user": {
    "email": "om@fa.com",
    "roles": ["HR_OFFICER"]
  },
  "permissions": {
    "can_view_admin_dashboard": true,
    "can_create": true,
    "can_read": true,
    "can_update": true,
    "can_delete": false,  ← HR_OFFICER cannot delete
    "is_admin": false,
    "is_officer": true,
    "is_employee": false
  }
}
```

---

### Test 3: Try Creating Employee (Should Work)

```
1. Login as HR_OFFICER (om@fa.com)
2. Go to: http://127.0.0.1:5000/admin/employees
3. Click "Add Employee"
4. Fill the form and submit
5. Expected: ✅ Employee created successfully
```

---

### Test 4: Try Updating Employee (Should Work)

```
1. Go to employee list
2. Click "Edit" on any employee
3. Update information
4. Expected: ✅ Employee updated successfully
```

---

### Test 5: Try Deleting Employee (Should Fail)

```
1. Go to employee list
2. Try to delete an employee
3. Expected: ❌ 403 Forbidden or button hidden
```

---

## 📋 Routes Access Control

| Route                     | HR_ADMIN | HR_OFFICER | EMPLOYEE |
| ------------------------- | -------- | ---------- | -------- |
| `/admin/dashboard`        | ✅       | ✅         | ❌       |
| `/admin/employees` (view) | ✅       | ✅         | ❌       |
| `/admin/employees/add`    | ✅       | ✅         | ❌       |
| `/admin/employees/edit`   | ✅       | ✅         | ❌       |
| `/admin/employees/delete` | ✅       | ❌         | ❌       |
| `/admin/attendance`       | ✅       | ✅         | ❌       |
| `/admin/leaves`           | ✅       | ✅         | ❌       |
| `/admin/payroll`          | ✅       | ✅         | ❌       |
| `/admin/announcements`    | ✅       | ✅         | ❌       |
| `/user/dashboard`         | ✅       | ✅         | ✅       |

---

## 🔍 How It Works

### New Decorators:

1. **@hr_management_required**
   - Allows both HR_ADMIN and HR_OFFICER
   - Used for most admin routes
2. **@admin_only_required**

   - Allows HR_ADMIN only
   - Used for delete operations

3. **@login_required**
   - Any authenticated user
   - Used for user dashboard

---

## 🎯 Permission Checks in Code

```python
# Check if user is Admin
if g.is_admin:
    # Show delete button

# Check if user is Officer
if g.is_officer:
    # Hide delete button
```

In templates:

```html
{% if g.is_admin %}
<button class="delete-btn">Delete</button>
{% endif %}
```

---

## 🔒 Security Implementation

### Login Flow:

```
1. User logs in via Keycloak
2. Token received with roles
3. Roles extracted: ['HR_OFFICER']
4. If HR_OFFICER → Redirect to /admin/dashboard
5. If EMPLOYEE → Redirect to /user/dashboard
```

### Route Protection:

```
1. User tries to access /admin/employees/delete/5
2. Decorator @admin_only_required checks roles
3. User has HR_OFFICER (not HR_ADMIN)
4. Access denied → 403 Forbidden
```

---

## 📝 Quick Commands

### Check User Roles:

```
http://127.0.0.1:5000/api/check-permissions
```

### Test All Security:

```
http://127.0.0.1:5000/api/security/test/all
```

### Who Am I:

```
http://127.0.0.1:5000/api/security/test/whoami
```

---

## ⚠️ Important Notes

1. **Make sure** to assign HR_OFFICER role in Keycloak first
2. **Logout and login again** after assigning new role
3. **Check token** has the correct roles using `/api/check-permissions`
4. **Delete operations** are protected and only work for HR_ADMIN

---

## ✅ Verification Checklist

- [ ] HR_OFFICER role created in Keycloak
- [ ] om@fa.com has HR_OFFICER role assigned
- [ ] Login as om@fa.com redirects to admin dashboard
- [ ] Can view employees list
- [ ] Can create new employee
- [ ] Can edit existing employee
- [ ] Cannot delete employee (403 or button hidden)
- [ ] Delete button only visible for HR_ADMIN

---

## 🆘 Troubleshooting

**Problem**: Still going to user dashboard instead of admin
**Solution**: Check roles in Keycloak and logout/login again

**Problem**: Can still delete as HR_OFFICER
**Solution**: Check @admin_only_required is applied to delete routes

**Problem**: Getting 403 on all admin pages
**Solution**: Make sure HR_OFFICER role is assigned in Keycloak

---

**🎉 Setup Complete! HR_OFFICER can now access admin dashboard with CRU permissions (no Delete)**
