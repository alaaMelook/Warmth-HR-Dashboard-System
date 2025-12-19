# 🔥 Warmth HR Dashboard - Keycloak Theme

A custom Keycloak theme designed for the Warmth HR Dashboard system with modern styling, warm orange branding, and a professional look.

## 📁 Theme Structure

```
warmth-hr-theme/
├── login/                          # Login page theme
│   ├── theme.properties            # Theme configuration
│   ├── resources/
│   │   ├── css/
│   │   │   └── styles.css          # Custom login styles
│   │   └── img/
│   │       └── logo.svg            # Logo image
│   └── messages/
│       └── messages_en.properties  # Custom text/labels
├── account/                        # Account management theme
│   ├── theme.properties
│   └── resources/
│       ├── css/
│       │   └── styles.css
│       └── img/
│           └── logo.svg
├── email/                          # Email notification theme
│   ├── theme.properties
│   └── html/
│       └── template.ftl            # Email HTML template
└── META-INF/
    └── keycloak-themes.json        # Theme registration
```

## 🎨 Brand Colors

| Color | Hex Code | Usage |
|-------|----------|-------|
| Primary Orange | `#FF6B35` | Buttons, links, accents |
| Primary Hover | `#E85A2B` | Hover states |
| Secondary Teal | `#4ECDC4` | Secondary elements |
| Dark Background | `#1A1A2E` | Login page background |
| Text Dark | `#2C3E50` | Main text |
| Text Muted | `#6C757D` | Secondary text |

## 🚀 Deployment Instructions

### Option 1: Direct Deployment (Standalone Keycloak)

1. Copy the `warmth-hr-theme` folder to your Keycloak themes directory:
   ```bash
   cp -r warmth-hr-theme <KEYCLOAK_HOME>/themes/
   ```

2. Restart Keycloak to detect the new theme.

### Option 2: Docker Volume Mount

Add this to your `docker-compose.yml`:

```yaml
services:
  keycloak:
    image: quay.io/keycloak/keycloak:latest
    volumes:
      - ./keycloak-themes/warmth-hr-theme:/opt/keycloak/themes/warmth-hr-theme
    environment:
      - KC_SPI_THEME_CACHE_THEMES=false  # Disable cache for development
    # ... other configurations
```

### Option 3: Build into Docker Image

Create a custom Dockerfile:

```dockerfile
FROM quay.io/keycloak/keycloak:latest
COPY warmth-hr-theme /opt/keycloak/themes/warmth-hr-theme
```

## ⚙️ Activate Theme for Your Realm

1. **Login to Keycloak Admin Console**
   - URL: `http://localhost:8080/admin` (or your Keycloak URL)
   - Login with admin credentials

2. **Select Your Realm**
   - Click on the realm dropdown (top-left)
   - Select your HR realm (e.g., `hr-realm`)

3. **Navigate to Realm Settings**
   - Go to **Realm Settings** in the left sidebar

4. **Configure Themes Tab**
   - Click on the **Themes** tab
   - Set the following:
     - **Login Theme**: `warmth-hr-theme`
     - **Account Theme**: `warmth-hr-theme`
     - **Email Theme**: `warmth-hr-theme`

5. **Save Changes**
   - Click **Save** button

## 🔄 Development Mode

To see changes immediately without restarting Keycloak, add this environment variable:

```bash
KC_SPI_THEME_CACHE_THEMES=false
KC_SPI_THEME_CACHE_TEMPLATES=false
KC_SPI_THEME_STATIC_MAX_AGE=-1
```

Or in docker-compose:

```yaml
environment:
  - KC_SPI_THEME_CACHE_THEMES=false
  - KC_SPI_THEME_CACHE_TEMPLATES=false
```

## 🖼️ Preview

The theme features:
- 🔥 Fire icon logo with "Warmth HR Dashboard" branding
- 🎨 Warm orange gradient color scheme
- 🌙 Dark gradient background for login page
- ✨ Modern card design with shadows and rounded corners
- 📱 Fully responsive design
- 🔘 Animated buttons with hover effects
- 📧 Branded email templates

## 📝 Customization

### Change Colors
Edit the CSS variables in `login/resources/css/styles.css`:

```css
:root {
    --warmth-primary: #FF6B35;      /* Change primary color */
    --warmth-secondary: #4ECDC4;    /* Change secondary color */
    --warmth-bg-dark: #1A1A2E;      /* Change background */
}
```

### Change Logo
Replace the SVG files in:
- `login/resources/img/logo.svg`
- `account/resources/img/logo.svg`

### Change Text/Messages
Edit `login/messages/messages_en.properties`:

```properties
loginTitleHtml=Your Company Name
loginTitle=Your Company Name
```

## ❓ Troubleshooting

### Theme not appearing in dropdown
- Ensure the folder is in `<KEYCLOAK_HOME>/themes/`
- Check `keycloak-themes.json` is properly formatted
- Restart Keycloak

### Styles not loading
- Clear browser cache
- Disable theme caching (development mode)
- Check for CSS syntax errors

### Logo not showing
- Verify the path in `theme.properties`
- Check image file exists
- Ensure correct file permissions

---

**Created for:** Warmth HR Dashboard System  
**Keycloak Version:** 20.x+  
**Last Updated:** December 2025
