# 🎨 Warmth HR Dashboard System
> A modern, elegant, and user-friendly HR Management System interface designed with warmth and professionalism in mind.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Status](https://img.shields.io/badge/status-active-success.svg)

---

## ✨ Features

### 🔐 Admin Panel
- **Dashboard Overview** - Quick stats cards (employees, attendance, leaves, payroll)
- **Employee Management** - Full CRUD operations with data tables
- **Leave Requests** - Review and approve/reject employee requests
- **Attendance Logs** - Track and filter attendance records
- **Reports & Analytics** - Generate insights and export data
- **System Settings** - Configure system preferences

### 👤 Employee Portal
- **Personal Dashboard** - View attendance status and leave balance
- **Leave Management** - Submit and track leave requests
- **Attendance History** - Calendar and list view of attendance
- **Salary Slips** - View and download monthly payslips
- **Profile Management** - Update personal information
- **Notifications** - Stay updated with company announcements

---

## 🎨 Color Palette

The UI is built around a warm, elegant color scheme:

| Color | Hex Code | Usage |
|-------|----------|-------|
| Primary | `#957C62` | Headers, primary buttons, sidebar highlights |
| Secondary | `#E2B59A` | Cards, backgrounds, secondary elements |
| Accent | `#FFE1AF` | Highlights, notifications, badges |
| Alert | `#B77466` | Important actions, warnings, delete buttons |

---

## 🔐 Keycloak Setup (Docker + Realm Import)

To run the project with authentication using Keycloak:

### 1️⃣ Prerequisites

* Install **Docker Desktop** and ensure it is running
* Port `8080` should be free (for Keycloak)

### 2️⃣ Run Keycloak Container

```powershell
docker run --name keycloak -p 8080:8080 `
  -e KEYCLOAK_ADMIN=admin `
  -e KEYCLOAK_ADMIN_PASSWORD=admin `
  quay.io/keycloak/keycloak:22.0.1 start-dev
```

**Access the Admin Console:**
* URL: http://localhost:8080
* Login credentials:
  * **Username:** `admin`
  * **Password:** `admin`

### 3️⃣ Import Pre-configured Realm

1. Place the `hr-realm.json` file in your project folder
2. Run the import command:

```powershell
docker run --name keycloak -p 8080:8080 `
  -v ${PWD}:/opt/keycloak/data/import `
  -e KEYCLOAK_ADMIN=admin `
  -e KEYCLOAK_ADMIN_PASSWORD=admin `
  quay.io/keycloak/keycloak:22.0.1 start-dev --import-realm
```

This will import the **HR-System Realm** with all clients, roles, and basic configuration.

## OR  3. Start Keycloak
```bash
docker-compose up -d
```

## 4. Import Configuration
1. Open: http://localhost:8080/admin
2. Login: admin/admin
3. Create Realm → Import `keycloak-config/HR-System-realm.json`


### 4️⃣ Optional: Export Realm (Backup)

If you want to back up the current Realm:

```powershell
docker exec keycloak /opt/keycloak/bin/kc.sh export --realm HR-System --file /tmp/hr-realm.json
docker cp keycloak:/tmp/hr-realm.json .
```

> **Note:** Replace `keycloak` with your actual container name if different.

### 5️⃣ Access Keys for Frontend / Backend

* **Frontend Client:** `hr-frontend` (OpenID Connect)
* **Backend Client:** `hr-backend` (OpenID Connect, secret enabled)
* Use the credentials from the imported Realm JSON

---

## 🚀 Project Status

🔨 **Currently in development** - UI Design Phase

This project is in its early stages. The structure and implementation details will be updated as development progresses.

---

## 📸 Preview

*UI screenshots and previews will be added soon*

---

## 🎯 Design Principles

- **Minimalism** - Clean layouts with purposeful whitespace
- **Consistency** - Unified design language across all pages
- **Accessibility** - WCAG compliant color contrasts
- **Responsiveness** - Mobile-first approach
- **User-Centric** - Intuitive navigation and clear hierarchy

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👥 Authors

- **Alaa Hassn Melook** - *Initial Design* - [@alaaMelook](https://github.com/alaaMelook)
- **Nadine Rasmy** - *Initial Design* - [@nadine-rasmy23](https://github.com/nadine-rasmy23)
- **Yumna Medhat Anter** - *Initial Design* - [@YUMNAANTER0099](https://github.com/YUMNAANTER0099)
- **Manar Ahmed** - *Initial Design* - [@Manarelmaradny](https://github.com/Manarelmaradny)
- **Mahmoud zaghloula** - *Initial Design* - [@zaghloula](https://github.com/zaghloula)
- **Abdelrahman Elmoghazy** - *Initial Design* - [@abdelrahman-elmoghazy](https://github.com/abdelrahman-elmoghazy)

---

## 🙏 Acknowledgments

- Inspired by modern HR management systems
- Color palette designed for warmth and professionalism
- Built with attention to user experience

---

---

<p align="center">Made with ❤️ for better HR management</p>