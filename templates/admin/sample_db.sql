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

-- 14/12 edit 
-- ==================================================
-- -- STEP 1: Add status column to payroll table
-- -- ==================================================
-- ALTER TABLE `payroll` 
-- ADD COLUMN `status` ENUM('pending', 'processing', 'paid') DEFAULT 'pending' AFTER `pay_date`;

-- -- ==================================================
-- -- STEP 2: Add more sample users (password: employee123)
-- -- ==================================================
-- INSERT INTO `users` (`first_name`, `last_name`, `email`, `phone`, `password`, `role_id`) VALUES
-- ('Ahmed', 'Hassan', 'ahmed.hassan@company.com', '+20 100 111 2222', 'scrypt:32768:8:1$pVZ8xYq7fKxJgB4K$6d3e8a7f3d9c2b4e5a6f7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b', 1),
-- ('Fatma', 'Ali', 'fatma.ali@company.com', '+20 100 222 3333', 'scrypt:32768:8:1$pVZ8xYq7fKxJgB4K$6d3e8a7f3d9c2b4e5a6f7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b', 1),
-- ('Mohamed', 'Ibrahim', 'mohamed.ibrahim@company.com', '+20 100 333 4444', 'scrypt:32768:8:1$pVZ8xYq7fKxJgB4K$6d3e8a7f3d9c2b4e5a6f7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b', 1),
-- ('Sara', 'Mohamed', 'sara.mohamed@company.com', '+20 100 444 5555', 'scrypt:32768:8:1$pVZ8xYq7fKxJgB4K$6d3e8a7f3d9c2b4e5a6f7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b', 1),
-- ('Omar', 'Khaled', 'omar.khaled@company.com', '+20 100 555 6666', 'scrypt:32768:8:1$pVZ8xYq7fKxJgB4K$6d3e8a7f3d9c2b4e5a6f7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b', 1),
-- ('Nour', 'Ahmed', 'nour.ahmed@company.com', '+20 100 666 7777', 'scrypt:32768:8:1$pVZ8xYq7fKxJgB4K$6d3e8a7f3d9c2b4e5a6f7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b', 1),
-- ('Youssef', 'Mahmoud', 'youssef.mahmoud@company.com', '+20 100 777 8888', 'scrypt:32768:8:1$pVZ8xYq7fKxJgB4K$6d3e8a7f3d9c2b4e5a6f7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b', 1),
-- ('Hana', 'Salah', 'hana.salah@company.com', '+20 100 888 9999', 'scrypt:32768:8:1$pVZ8xYq7fKxJgB4K$6d3e8a7f3d9c2b4e5a6f7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b', 1);

-- -- ==================================================
-- -- STEP 3: Add employees for the new users
-- -- ==================================================
-- INSERT INTO `employees` (`user_id`, `department_id`, `job_title_id`, `hire_date`, `status`) VALUES
-- (2, 1, 1, '2024-03-15', 'active'),  -- Ahmed Hassan - Engineering - Software Engineer
-- (3, 2, 4, '2024-02-20', 'active'),  -- Fatma Ali - HR - HR Specialist
-- (4, 3, 6, '2024-04-10', 'active'),  -- Mohamed Ibrahim - Marketing - Marketing Specialist
-- (5, 4, 8, '2024-05-01', 'active'),  -- Sara Mohamed - Sales - Sales Representative
-- (6, 5, 9, '2024-03-25', 'active'),  -- Omar Khaled - Finance - Financial Analyst
-- (7, 1, 2, '2024-01-15', 'active'),  -- Nour Ahmed - Engineering - Senior Software Engineer
-- (8, 6, 11, '2024-06-01', 'active'), -- Youssef Mahmoud - Product - Product Manager
-- (9, 7, 12, '2024-04-20', 'active'); -- Hana Salah - Design - UX Designer

-- -- ==================================================
-- -- STEP 4: Add payroll records for December 2025
-- -- ==================================================
-- INSERT INTO `payroll` (`employee_id`, `basic_salary`, `bonus`, `deductions`, `pay_date`, `status`) VALUES
-- (1, 8000.00, 1000.00, 500.00, '2025-12-01', 'paid'),      -- Admin User
-- (2, 5500.00, 500.00, 350.00, '2025-12-01', 'paid'),       -- Ahmed Hassan
-- (3, 4800.00, 300.00, 280.00, '2025-12-01', 'paid'),       -- Fatma Ali
-- (4, 5200.00, 400.00, 320.00, '2025-12-01', 'processing'), -- Mohamed Ibrahim
-- (5, 4500.00, 200.00, 250.00, '2025-12-01', 'pending'),    -- Sara Mohamed
-- (6, 6200.00, 800.00, 420.00, '2025-12-01', 'paid'),       -- Omar Khaled
-- (7, 7000.00, 900.00, 450.00, '2025-12-01', 'processing'), -- Nour Ahmed
-- (8, 7500.00, 1000.00, 500.00, '2025-12-01', 'pending'),   -- Youssef Mahmoud
-- (9, 5800.00, 600.00, 380.00, '2025-12-01', 'paid');       -- Hana Salah

-- -- ==================================================
-- -- STEP 5: Add payroll records for November 2025
-- -- ==================================================
-- INSERT INTO `payroll` (`employee_id`, `basic_salary`, `bonus`, `deductions`, `pay_date`, `status`) VALUES
-- (1, 8000.00, 900.00, 500.00, '2025-11-01', 'paid'),
-- (2, 5500.00, 450.00, 350.00, '2025-11-01', 'paid'),
-- (3, 4800.00, 250.00, 280.00, '2025-11-01', 'paid'),
-- (4, 5200.00, 350.00, 320.00, '2025-11-01', 'paid'),
-- (5, 4500.00, 150.00, 250.00, '2025-11-01', 'paid'),
-- (6, 6200.00, 750.00, 420.00, '2025-11-01', 'paid');

-- ****************trial adds***********************
-- -- Add holidays table
-- CREATE TABLE `holidays` (
--   `holiday_id` int(11) NOT NULL AUTO_INCREMENT,
--   `name` varchar(100) NOT NULL,
--   `date` date NOT NULL,
--   PRIMARY KEY (`holiday_id`)
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -- Add notifications table
-- CREATE TABLE `notifications` (
--   `notification_id` int(11) NOT NULL AUTO_INCREMENT,
--   `user_id` int(11) NOT NULL,
--   `text` varchar(255) NOT NULL,
--   `created_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
--   PRIMARY KEY (`notification_id`),
--   KEY `user_id` (`user_id`),
--   CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`)
-- ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -- Insert sample holidays
-- INSERT INTO `holidays` (`name`, `date`) VALUES
-- ('Christmas Day', '2025-12-25'),
-- ('New Year\'s Day', '2026-01-01'),
-- ('Republic Day', '2026-01-26');