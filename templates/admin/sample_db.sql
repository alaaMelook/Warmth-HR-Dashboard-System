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


-- -- إضافة جدول إعدادات الشركة
CREATE TABLE IF NOT EXISTS `company_settings` (
  `setting_id` int(11) NOT NULL AUTO_INCREMENT,
  `company_name` varchar(200) DEFAULT 'TechCorp Inc.',
  `industry` varchar(100) DEFAULT 'Technology',
  `employee_count` int(11) DEFAULT 248,
  `timezone` varchar(50) DEFAULT 'UTC-5',
  `date_format` varchar(20) DEFAULT 'MM/DD/YYYY',
  `language` varchar(10) DEFAULT 'en',
  `currency` varchar(10) DEFAULT 'USD',
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`setting_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- إضافة جدول إعدادات الإشعارات
CREATE TABLE IF NOT EXISTS `notification_settings` (
  `setting_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) DEFAULT NULL,
  `email_notifications` tinyint(1) DEFAULT 1,
  `leave_alerts` tinyint(1) DEFAULT 1,
  `attendance_reminders` tinyint(1) DEFAULT 0,
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`setting_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `notification_settings_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- إضافة جدول إعدادات الأمان
CREATE TABLE IF NOT EXISTS `security_settings` (
  `setting_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `two_factor_enabled` tinyint(1) DEFAULT 0,
  `two_factor_secret` varchar(255) DEFAULT NULL,
  `login_alerts` tinyint(1) DEFAULT 0,
  `last_password_change` timestamp NULL DEFAULT NULL,
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp(),
  PRIMARY KEY (`setting_id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `security_settings_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- إدخال بيانات افتراضية لإعدادات الشركة
INSERT INTO `company_settings` (`company_name`, `industry`, `employee_count`, `timezone`, `date_format`, `language`, `currency`) 
VALUES ('TechCorp Inc.', 'Technology', 248, 'UTC-5', 'MM/DD/YYYY', 'en', 'USD')
ON DUPLICATE KEY UPDATE `setting_id` = `setting_id`;

-- إضافة أعمدة إضافية لجدول departments إذا لزم الأمر
ALTER TABLE `departments` 
ADD COLUMN IF NOT EXISTS `description` text DEFAULT NULL,
ADD COLUMN IF NOT EXISTS `manager_id` int(11) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS `created_at` timestamp NOT NULL DEFAULT current_timestamp();

-- إضافة أعمدة إضافية لجدول job_titles إذا لزم الأمر
ALTER TABLE `job_titles` 
ADD COLUMN IF NOT EXISTS `description` text DEFAULT NULL,
ADD COLUMN IF NOT EXISTS `salary_range_min` decimal(10,2) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS `salary_range_max` decimal(10,2) DEFAULT NULL,
ADD COLUMN IF NOT EXISTS `created_at` timestamp NOT NULL DEFAULT current_timestamp();

-- إضافة بعض البيانات التجريبية للأقسام
INSERT INTO `departments` (`department_name`, `description`) VALUES
('Engineering', 'Software development and technical operations'),
('Product', 'Product management and strategy'),
('Design', 'UI/UX design and creative services'),
('Human Resources', 'HR operations and employee management'),
('Marketing', 'Marketing and brand management'),
('Sales', 'Sales and business development')
ON DUPLICATE KEY UPDATE `department_name` = VALUES(`department_name`);

-- إضافة بعض البيانات التجريبية للوظائف
INSERT INTO `job_titles` (`title_name`, `description`) VALUES
('Software Engineer', 'Develops and maintains software applications'),
('Senior Developer', 'Leads technical projects and mentors junior developers'),
('Product Manager', 'Manages product roadmap and strategy'),
('UI/UX Designer', 'Designs user interfaces and experiences'),
('HR Manager', 'Manages HR operations and policies'),
('Marketing Specialist', 'Executes marketing campaigns and strategies'),
('Sales Representative', 'Manages client relationships and sales')
ON DUPLICATE KEY UPDATE `title_name` = VALUES(`title_name`);