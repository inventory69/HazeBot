# Quick Start Guide - HazeBot Web Interface

This guide will get you up and running with the HazeBot web interface in 5 minutes.

## Prerequisites

- Python 3.9+ installed
- HazeBot already set up
- Terminal/command line access

## Step 1: Install API Dependencies (1 minute)

```bash
pip install flask flask-cors pyjwt
```

Or use the requirements file:
```bash
pip install -r api_requirements.txt
```

## Step 2: Configure Environment (1 minute)

Add these lines to your `.env` file:

```env
API_PORT=5000
API_SECRET_KEY=my-super-secret-key-12345
API_ADMIN_USER=admin
API_ADMIN_PASS=mySecurePassword123
API_DEBUG=false
```

**Important:** Change the password and secret key!

## Step 3: Start the API (30 seconds)

```bash
cd api
python app.py
```

You should see:
```
Starting HazeBot Configuration API on port 5000
 * Running on http://0.0.0.0:5000
```

## Step 4: Access the Web Interface (30 seconds)

### Option A: Use Flutter Web (Recommended)

1. Install Flutter: https://docs.flutter.dev/get-started/install
2. Run the app:
```bash
cd hazebot_admin
flutter pub get
flutter run -d chrome
```

### Option B: Use a simple HTML test page

Create `test.html`:
```html
<!DOCTYPE html>
<html>
<head>
    <title>HazeBot Config Test</title>
</head>
<body>
    <h1>HazeBot Configuration</h1>
    <button onclick="testAPI()">Test API Connection</button>
    <pre id="output"></pre>
    
    <script>
    async function testAPI() {
        // Login
        const loginRes = await fetch('http://localhost:5000/api/auth/login', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                username: 'admin',
                password: 'mySecurePassword123'
            })
        });
        const {token} = await loginRes.json();
        
        // Get config
        const configRes = await fetch('http://localhost:5000/api/config', {
            headers: {'Authorization': `Bearer ${token}`}
        });
        const config = await configRes.json();
        
        document.getElementById('output').textContent = 
            JSON.stringify(config, null, 2);
    }
    </script>
</body>
</html>
```

Open `test.html` in your browser and click "Test API Connection".

## Step 5: Login (30 seconds)

- Open the web interface
- Enter username: `admin`
- Enter password: `mySecurePassword123` (or what you set)
- Click Login

## You're Done! 🎉

You can now:
- View all bot configuration in the dashboard
- Edit general settings (bot name, prefix, cooldowns)
- Update channel IDs
- Modify role configurations
- Configure meme sources
- Adjust Rocket League settings
- Customize welcome messages

## Common Issues

### "Connection refused"
- Make sure the API is running (`python api/app.py`)
- Check the port (default: 5000)

### "Invalid credentials"
- Check your .env file
- Make sure API_ADMIN_USER and API_ADMIN_PASS match

### CORS errors (web)
- Flask-CORS should handle this automatically
- If issues persist, check Flask-CORS is installed

### Can't install Flutter
- You can use the HTML test page above
- Or access the API directly with curl/Postman

## API Quick Reference

### Login
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"mySecurePassword123"}'
```

### Get Configuration (need token from login)
```bash
curl http://localhost:5000/api/config \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Update General Settings
```bash
curl -X PUT http://localhost:5000/api/config/general \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -H "Content-Type: application/json" \
  -d '{"bot_name":"My New Bot Name"}'
```

## Next Steps

1. **Secure your installation:**
   - Change default password
   - Use strong API_SECRET_KEY
   - Set API_DEBUG=false (default)

2. **For production:**
   - See SETUP_GUIDE.md for deployment instructions
   - Use HTTPS (not HTTP)
   - Configure firewall
   - Use gunicorn instead of Flask dev server

3. **For Android:**
   - Follow SETUP_GUIDE.md to build APK
   - Update API URL in Flutter app
   - Sign the APK for distribution

## Help

- Full documentation: See SETUP_GUIDE.md
- API reference: See api/README.md
- Flutter docs: See hazebot_admin/README.md

## Security Reminder

⚠️ **Always change default credentials in production!**
⚠️ **Never use debug mode in production!**
⚠️ **Use HTTPS for production deployments!**

---

Enjoy managing your HazeBot through the web interface! 🌿
