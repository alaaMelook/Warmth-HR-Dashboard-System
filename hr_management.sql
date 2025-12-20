-- phpMyAdmin SQL Dump
-- version 5.2.1
-- https://www.phpmyadmin.net/
--
-- Host: 127.0.0.1
-- Generation Time: Dec 20, 2025 at 03:09 AM
-- Server version: 10.4.32-MariaDB
-- PHP Version: 8.2.12

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `hr_management`
--

-- --------------------------------------------------------

--
-- Table structure for table `attendance`
--

CREATE TABLE `attendance` (
  `attendance_id` int(11) NOT NULL,
  `employee_id` int(11) NOT NULL,
  `attendance_date` date NOT NULL,
  `check_in` time DEFAULT NULL,
  `check_out` time DEFAULT NULL,
  `status` enum('present','absent','leave') DEFAULT 'present'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `attendance`
--

INSERT INTO `attendance` (`attendance_id`, `employee_id`, `attendance_date`, `check_in`, `check_out`, `status`) VALUES
(1, 3, '2025-12-15', '22:02:22', NULL, 'present'),
(2, 4, '2025-12-15', '22:08:03', NULL, 'present'),
(4, 4, '2025-12-16', '00:43:28', '01:28:21', 'present'),
(7, 8, '2025-12-16', '01:31:39', NULL, 'present'),
(8, 3, '2025-12-19', '20:38:09', '21:05:50', 'present'),
(9, 3, '2025-12-20', '03:18:25', '03:18:32', 'present'),
(11, 11, '2025-12-20', '03:24:37', '03:24:43', 'present');

-- --------------------------------------------------------

--
-- Table structure for table `departments`
--

CREATE TABLE `departments` (
  `department_id` int(11) NOT NULL,
  `department_name` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `departments`
--

INSERT INTO `departments` (`department_id`, `department_name`) VALUES
(13, 'Administration'),
(10, 'Customer Service'),
(7, 'Design'),
(1, 'Engineering'),
(5, 'Finance'),
(2, 'Human Resources'),
(8, 'Information Technology'),
(12, 'Legal'),
(3, 'Marketing'),
(9, 'Operations'),
(6, 'Product'),
(11, 'Research & Development'),
(4, 'Sales');

-- --------------------------------------------------------

--
-- Table structure for table `employees`
--

CREATE TABLE `employees` (
  `employee_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `department_id` int(11) DEFAULT NULL,
  `job_title_id` int(11) DEFAULT NULL,
  `hire_date` date DEFAULT NULL,
  `status` enum('active','inactive') DEFAULT 'active'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `employees`
--

INSERT INTO `employees` (`employee_id`, `user_id`, `department_id`, `job_title_id`, `hire_date`, `status`) VALUES
(3, 2, NULL, NULL, '2025-12-15', 'active'),
(4, 4, 5, 10, '2025-12-15', 'active'),
(8, 8, 1, 17, '2025-12-16', 'active'),
(10, 10, NULL, NULL, '2025-12-19', 'active'),
(11, 11, NULL, NULL, '2025-12-20', 'active');

-- --------------------------------------------------------

--
-- Table structure for table `holidays`
--

CREATE TABLE `holidays` (
  `holiday_id` int(11) NOT NULL,
  `title` varchar(255) NOT NULL,
  `holiday_date` date NOT NULL,
  `description` text DEFAULT NULL,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `created_by` int(11) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `holidays`
--

INSERT INTO `holidays` (`holiday_id`, `title`, `holiday_date`, `description`, `created_at`, `created_by`) VALUES
(16, 'Christmas', '2025-12-25', 'Merry Christmas', '2025-12-15 23:22:23', 3),
(17, 'New year', '2025-12-31', NULL, '2025-12-15 23:25:21', 3),
(23, 'Champion', '2025-12-27', NULL, '2025-12-20 01:48:35', 10);

-- --------------------------------------------------------

--
-- Table structure for table `job_titles`
--

CREATE TABLE `job_titles` (
  `job_title_id` int(11) NOT NULL,
  `title_name` varchar(100) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `job_titles`
--

INSERT INTO `job_titles` (`job_title_id`, `title_name`) VALUES
(10, 'Accountant'),
(24, 'Administrative Assistant'),
(27, 'Business Analyst'),
(14, 'Chief Executive Officer'),
(16, 'Chief Financial Officer'),
(15, 'Chief Technology Officer'),
(21, 'Customer Service Manager'),
(20, 'Customer Service Representative'),
(18, 'Data Analyst'),
(17, 'DevOps Engineer'),
(9, 'Financial Analyst'),
(3, 'HR Manager'),
(4, 'HR Specialist'),
(23, 'Legal Advisor'),
(5, 'Marketing Manager'),
(6, 'Marketing Specialist'),
(25, 'Office Manager'),
(19, 'Operations Manager'),
(11, 'Product Manager'),
(26, 'Project Manager'),
(28, 'Quality Assurance Engineer'),
(22, 'Research Scientist'),
(7, 'Sales Manager'),
(8, 'Sales Representative'),
(2, 'Senior Software Engineer'),
(1, 'Software Engineer'),
(13, 'UI Designer'),
(12, 'UX Designer');

-- --------------------------------------------------------

--
-- Table structure for table `leaves`
--

CREATE TABLE `leaves` (
  `leave_id` int(11) NOT NULL,
  `employee_id` int(11) NOT NULL,
  `leave_type` enum('sick','vacation','unpaid') NOT NULL,
  `start_date` date NOT NULL,
  `end_date` date NOT NULL,
  `reason` text DEFAULT NULL,
  `status` enum('pending','approved','rejected') DEFAULT 'pending'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `leaves`
--

INSERT INTO `leaves` (`leave_id`, `employee_id`, `leave_type`, `start_date`, `end_date`, `reason`, `status`) VALUES
(6, 3, 'sick', '2025-12-18', '2025-12-27', 'sick', 'approved'),
(7, 3, '', '2025-12-16', '2025-12-17', NULL, 'approved'),
(10, 4, 'vacation', '2025-12-24', '2025-12-27', NULL, 'approved'),
(11, 11, 'vacation', '2025-12-27', '2025-12-31', 'تعبان جدا', 'approved'),
(12, 3, 'sick', '2025-12-30', '2025-12-31', NULL, 'approved'),
(13, 3, 'sick', '2026-01-01', '2026-01-02', NULL, 'approved'),
(14, 3, 'vacation', '2026-02-19', '2026-02-20', NULL, 'rejected'),
(15, 3, 'unpaid', '2026-03-20', '2026-03-21', NULL, 'rejected'),
(16, 3, 'vacation', '2026-05-20', '2026-05-22', NULL, 'rejected');

-- --------------------------------------------------------

--
-- Table structure for table `notifications`
--

CREATE TABLE `notifications` (
  `notification_id` int(11) NOT NULL,
  `title` varchar(255) NOT NULL,
  `message` text NOT NULL,
  `notification_type` enum('info','warning','success','urgent') DEFAULT 'info',
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `created_by` int(11) DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT 1
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Dumping data for table `notifications`
--

INSERT INTO `notifications` (`notification_id`, `title`, `message`, `notification_type`, `created_at`, `created_by`, `is_active`) VALUES
(1, 'Welcome to HR System', 'Welcome to the new HR Management System. Please update your profile information.', 'info', '2025-12-15 23:22:23', 3, 1),
(6, 'انا هتجوز', 'كلكم معزومين', 'info', '2025-12-15 23:26:12', 3, 1),
(7, 'goooooooooooooooal', 'goal', 'info', '2025-12-20 01:50:38', 4, 1);

-- --------------------------------------------------------

--
-- Table structure for table `payroll`
--

CREATE TABLE `payroll` (
  `payroll_id` int(11) NOT NULL,
  `employee_id` int(11) NOT NULL,
  `basic_salary` decimal(10,2) NOT NULL,
  `bonus` decimal(10,2) DEFAULT 0.00,
  `deductions` decimal(10,2) DEFAULT 0.00,
  `pay_date` date NOT NULL,
  `status` enum('pending','processing','paid') DEFAULT 'pending'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `payroll`
--

INSERT INTO `payroll` (`payroll_id`, `employee_id`, `basic_salary`, `bonus`, `deductions`, `pay_date`, `status`) VALUES
(2, 3, 3500.00, 1000.00, 0.00, '2025-12-01', 'paid'),
(3, 4, 2000.00, 500.00, 100.00, '2025-12-01', 'paid'),
(6, 8, 10000.00, 1000.00, 0.00, '2025-12-01', 'paid'),
(7, 10, 7000.00, 500.00, 0.00, '2025-12-01', 'pending');

-- --------------------------------------------------------

--
-- Table structure for table `roles`
--

CREATE TABLE `roles` (
  `role_id` int(11) NOT NULL,
  `role_name` varchar(50) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `roles`
--

INSERT INTO `roles` (`role_id`, `role_name`) VALUES
(2, 'admin'),
(1, 'user');

-- --------------------------------------------------------

--
-- Table structure for table `users`
--

CREATE TABLE `users` (
  `user_id` int(11) NOT NULL,
  `first_name` varchar(100) NOT NULL,
  `last_name` varchar(100) NOT NULL,
  `email` varchar(150) NOT NULL,
  `phone` varchar(20) DEFAULT NULL,
  `address` varchar(255) DEFAULT NULL,
  `emergency_name` varchar(100) DEFAULT NULL,
  `emergency_relationship` varchar(50) DEFAULT NULL,
  `emergency_phone` varchar(20) DEFAULT NULL,
  `password` varchar(255) NOT NULL,
  `role_id` int(11) DEFAULT 1,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

--
-- Dumping data for table `users`
--

INSERT INTO `users` (`user_id`, `first_name`, `last_name`, `email`, `phone`, `address`, `emergency_name`, `emergency_relationship`, `emergency_phone`, `password`, `role_id`, `created_at`) VALUES
(2, 'mahmoud', 'fahmy', 'ma@mo.com', '0109643479', 'egypt', 'Jane Doe', 'Spouse', '01096434798', 'scrypt:32768:8:1$KHnu8bApk7oToIXE$af201dd9aa8693568b1eb05e9cd6fe550d81ed65f69d0a069199e8d42f027862cbe237f19d272ffc388a692937e4238cf97ae8871b002ab0f5e6d598c440be31', 1, '2025-12-15 02:01:47'),
(3, 'Admin', 'System', 'admin@hr.com', '01234567890', 'Main Office', 'Emergency Contact', 'HR Manager', '01111111111', 'scrypt:32768:8:1$L5tkdrLMjeZILNzg$69d9b5fe267ddd1110ac747e6eb1829b173f0f294ed318c402a4bd2a91881c7cf261287709b12fa03152b9ac039e7d33f0a33deb4191e72a6579aff7834081ab', 2, '2025-12-15 16:02:13'),
(4, 'omar', 'farg', 'om@fa.com', '01234567890', 'None', 'Jane Doe', 'Spouse', '+1 (555) 123-0000', 'scrypt:32768:8:1$P0SgkzQY2f9yXKEb$ff06a47adc69523d092afc9e633c09652fda1ae2c6408331bc52beea88c3e609ef62f1fec71cf38278fba50e17459927f6bbcdc178d1bf9a9c8271f385b25e76', 1, '2025-12-15 18:31:28'),
(8, 'تيسير', 'فهمي', 'tyser@fa.com', '123456789', NULL, NULL, NULL, NULL, 'scrypt:32768:8:1$sYqMEDxXBY9wP2Wq$cc9c995dcd172b9b5fcfdc747a2623ebae36b1e31750445d3200c8e17623ef118976ce2cbd439c66c9104f0201d3ae5044a6220244a249175319e325ee4492a7', 1, '2025-12-15 23:30:33'),
(10, 'HR', 'Admin', 'hr-admin@hr.com', '01000000000', NULL, NULL, NULL, NULL, 'dummy-password-not-used', 2, '2025-12-19 15:20:34'),
(11, 'john', 'User', 'john@jo.com', 'None', NULL, NULL, NULL, NULL, 'scrypt:32768:8:1$HY4DVOzerEucE2V8$009e2ee79a5080d36de4d8edc6ef80f4f75dc33b5bdc7b16a52c66fa6c7380f8d381eb6cd39e83ce2b628d815d55a77b236ab8e34787399724af098a58065d62', 1, '2025-12-20 00:08:37');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `attendance`
--
ALTER TABLE `attendance`
  ADD PRIMARY KEY (`attendance_id`),
  ADD KEY `employee_id` (`employee_id`);

--
-- Indexes for table `departments`
--
ALTER TABLE `departments`
  ADD PRIMARY KEY (`department_id`),
  ADD UNIQUE KEY `department_name` (`department_name`);

--
-- Indexes for table `employees`
--
ALTER TABLE `employees`
  ADD PRIMARY KEY (`employee_id`),
  ADD UNIQUE KEY `uniq_user_id` (`user_id`),
  ADD KEY `user_id` (`user_id`),
  ADD KEY `department_id` (`department_id`),
  ADD KEY `job_title_id` (`job_title_id`);

--
-- Indexes for table `holidays`
--
ALTER TABLE `holidays`
  ADD PRIMARY KEY (`holiday_id`),
  ADD KEY `created_by` (`created_by`);

--
-- Indexes for table `job_titles`
--
ALTER TABLE `job_titles`
  ADD PRIMARY KEY (`job_title_id`),
  ADD UNIQUE KEY `title_name` (`title_name`);

--
-- Indexes for table `leaves`
--
ALTER TABLE `leaves`
  ADD PRIMARY KEY (`leave_id`),
  ADD KEY `employee_id` (`employee_id`);

--
-- Indexes for table `notifications`
--
ALTER TABLE `notifications`
  ADD PRIMARY KEY (`notification_id`),
  ADD KEY `created_by` (`created_by`);

--
-- Indexes for table `payroll`
--
ALTER TABLE `payroll`
  ADD PRIMARY KEY (`payroll_id`),
  ADD KEY `employee_id` (`employee_id`);

--
-- Indexes for table `roles`
--
ALTER TABLE `roles`
  ADD PRIMARY KEY (`role_id`),
  ADD UNIQUE KEY `role_name` (`role_name`);

--
-- Indexes for table `users`
--
ALTER TABLE `users`
  ADD PRIMARY KEY (`user_id`),
  ADD UNIQUE KEY `email` (`email`),
  ADD KEY `role_id` (`role_id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `attendance`
--
ALTER TABLE `attendance`
  MODIFY `attendance_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=12;

--
-- AUTO_INCREMENT for table `departments`
--
ALTER TABLE `departments`
  MODIFY `department_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=14;

--
-- AUTO_INCREMENT for table `employees`
--
ALTER TABLE `employees`
  MODIFY `employee_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=14;

--
-- AUTO_INCREMENT for table `holidays`
--
ALTER TABLE `holidays`
  MODIFY `holiday_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=25;

--
-- AUTO_INCREMENT for table `job_titles`
--
ALTER TABLE `job_titles`
  MODIFY `job_title_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=29;

--
-- AUTO_INCREMENT for table `leaves`
--
ALTER TABLE `leaves`
  MODIFY `leave_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=17;

--
-- AUTO_INCREMENT for table `notifications`
--
ALTER TABLE `notifications`
  MODIFY `notification_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=9;

--
-- AUTO_INCREMENT for table `payroll`
--
ALTER TABLE `payroll`
  MODIFY `payroll_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=8;

--
-- AUTO_INCREMENT for table `roles`
--
ALTER TABLE `roles`
  MODIFY `role_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=3;

--
-- AUTO_INCREMENT for table `users`
--
ALTER TABLE `users`
  MODIFY `user_id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=14;

--
-- Constraints for dumped tables
--

--
-- Constraints for table `attendance`
--
ALTER TABLE `attendance`
  ADD CONSTRAINT `attendance_ibfk_1` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`employee_id`);

--
-- Constraints for table `employees`
--
ALTER TABLE `employees`
  ADD CONSTRAINT `employees_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`user_id`),
  ADD CONSTRAINT `employees_ibfk_2` FOREIGN KEY (`department_id`) REFERENCES `departments` (`department_id`),
  ADD CONSTRAINT `employees_ibfk_3` FOREIGN KEY (`job_title_id`) REFERENCES `job_titles` (`job_title_id`);

--
-- Constraints for table `holidays`
--
ALTER TABLE `holidays`
  ADD CONSTRAINT `holidays_ibfk_1` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL;

--
-- Constraints for table `leaves`
--
ALTER TABLE `leaves`
  ADD CONSTRAINT `leaves_ibfk_1` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`employee_id`);

--
-- Constraints for table `notifications`
--
ALTER TABLE `notifications`
  ADD CONSTRAINT `notifications_ibfk_1` FOREIGN KEY (`created_by`) REFERENCES `users` (`user_id`) ON DELETE SET NULL;

--
-- Constraints for table `payroll`
--
ALTER TABLE `payroll`
  ADD CONSTRAINT `payroll_ibfk_1` FOREIGN KEY (`employee_id`) REFERENCES `employees` (`employee_id`);

--
-- Constraints for table `users`
--
ALTER TABLE `users`
  ADD CONSTRAINT `users_ibfk_1` FOREIGN KEY (`role_id`) REFERENCES `roles` (`role_id`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
