<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: 'Segoe UI', Arial, sans-serif;
            background-color: #F8F9FA;
            margin: 0;
            padding: 20px;
        }
        .email-container {
            max-width: 600px;
            margin: 0 auto;
            background-color: #FFFFFF;
            border-radius: 16px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            overflow: hidden;
        }
        .email-header {
            background: linear-gradient(135deg, #FF6B35 0%, #E85A2B 100%);
            padding: 30px;
            text-align: center;
        }
        .email-header h1 {
            color: #FFFFFF;
            margin: 0;
            font-size: 24px;
        }
        .email-header .logo {
            font-size: 36px;
            margin-bottom: 10px;
        }
        .email-body {
            padding: 40px 30px;
            color: #2C3E50;
            line-height: 1.6;
        }
        .email-body h2 {
            color: #FF6B35;
            margin-top: 0;
        }
        .email-button {
            display: inline-block;
            background: linear-gradient(135deg, #FF6B35 0%, #E85A2B 100%);
            color: #FFFFFF !important;
            text-decoration: none;
            padding: 14px 32px;
            border-radius: 10px;
            font-weight: 600;
            margin: 20px 0;
        }
        .email-footer {
            background-color: #F8F9FA;
            padding: 20px 30px;
            text-align: center;
            color: #6C757D;
            font-size: 12px;
        }
        .email-footer a {
            color: #FF6B35;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <div class="email-container">
        <div class="email-header">
            <div class="logo">🔥</div>
            <h1>Warmth HR Dashboard</h1>
        </div>
        <div class="email-body">
            ${body}
        </div>
        <div class="email-footer">
            <p>This email was sent by Warmth HR Dashboard</p>
            <p><a href="${realmUrl}">Visit Warmth HR Dashboard</a></p>
        </div>
    </div>
</body>
</html>
