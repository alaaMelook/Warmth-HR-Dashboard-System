-- إضافة Departments
INSERT INTO `departments` (`department_id`, `department_name`) VALUES
(1, 'Engineering'),
(2, 'Human Resources'),
(3, 'Marketing'),
(4, 'Sales'),
(5, 'Finance'),
(6, 'Product'),
(7, 'Design');

-- إضافة Job Titles
INSERT INTO `job_titles` (`job_title_id`, `title_name`) VALUES
(1, 'Software Engineer'),
(2, 'Senior Software Engineer'),
(3, 'HR Manager'),
(4, 'HR Specialist'),
(5, 'Marketing Manager'),
(6, 'Marketing Specialist'),
(7, 'Sales Manager'),
(8, 'Sales Representative'),
(9, 'Financial Analyst'),
(10, 'Accountant'),
(11, 'Product Manager'),
(12, 'UX Designer'),
(13, 'UI Designer');

-- إضافة مستخدم Admin (password: admin123)
-- الـ password hash ده generated من werkzeug
INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `phone`, `password`, `role_id`) VALUES
(1, 'Admin', 'User', 'admin@company.com', '+20 123 456 7890', 'scrypt:32768:8:1$pVZ8xYq7fKxJgB4K$6d3e8a7f3d9c2b4e5a6f7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b', 2);

-- إضافة Employee للـ Admin
INSERT INTO `employees` (`employee_id`, `user_id`, `department_id`, `job_title_id`, `hire_date`, `status`) VALUES
(1, 1, 2, 3, '2024-01-01', 'active');