# HazeBot Admin Panel Setup Guide

This guide covers setting up the Flask API backend and Flutter web/mobile interface for managing HazeBot.

> **⚠️ Prerequisites:** HazeBot Discord bot must be set up first! See **[Bot Setup Guide](BOT_SETUP.md)** for complete instructions.

## Architecture Overview

```
┌─────────────────┐
│  Flutter Web/   │
│  Android App    │
└────────┬────────┘
         │ HTTP/REST
         │
┌────────▼────────┐
│   Flask API     │
└────────┬────────┘
         │ Python Import
         │
┌────────▼────────┐
│   Config.py     │
│   (HazeBot)     │
└─────────────────┘
```

## Prerequisites

1. **Python 3.9+** - For the Flask API
2. **Flutter 3.0+** - For the web/Android interface
3. **HazeBot** - The bot should be set up and configured

## Part 1: Flask API Setup

### Step 1: Install API Dependencies

```bash
pip install -r api_requirements.txt
```

This installs:
- Flask - Web framework
- Flask-CORS - Cross-origin resource sharing
- PyJWT - JSON Web Token authentication

### Step 2: Configure Environment Variables

Add these to your `.env` file:

```env
# API Configuration
API_PORT=5000
API_SECRET_KEY=your-very-secret-key-here-change-this
API_ADMIN_USER=admin
API_ADMIN_PASS=your-secure-password-here
```

**Security Note:** Always use strong, unique values in production!

### Step 3: Run the API Server

```bash
cd api
python app.py
```

The API will be available at `http://localhost:5000`

### Step 4: Test the API

```bash
# Health check
curl http://localhost:5000/api/health

# Login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your-password"}'
```

## Part 2: Flutter App Setup

### Step 1: Install Flutter

If you haven't installed Flutter yet:

**Linux/macOS:**
```bash
git clone https://github.com/flutter/flutter.git -b stable
export PATH="$PATH:`pwd`/flutter/bin"
flutter doctor
```

**Windows:**
Download from: https://docs.flutter.dev/get-started/install/windows

### Step 2: Install Dependencies

```bash
cd hazebot_admin
flutter pub get
```

### Step 3: Configure API URL

Edit `lib/services/api_service.dart` and update the base URL:

For local development:
```dart
// Web
static const String baseUrl = 'http://localhost:5000/api';

// Android Emulator
static const String baseUrl = 'http://10.0.2.2:5000/api';

// Android Device (replace with your computer's IP)
static const String baseUrl = 'http://192.168.1.100:5000/api';
```

For production:
```dart
static const String baseUrl = 'https://your-domain.com/api';
```

### Step 4: Run the Web Interface

```bash
flutter run -d chrome
```

Or build for production:
```bash
flutter build web
# Files will be in build/web/
```

### Step 5: Run on Android

**Using Android Emulator:**
```bash
# Start emulator from Android Studio or:
flutter emulators --launch <emulator_id>

# Run app
flutter run
```

**Using Physical Device:**
```bash
# Enable USB debugging on your device
# Connect via USB
flutter devices  # Check device is detected
flutter run
```

**Build APK:**
```bash
flutter build apk --release
# APK will be in build/app/outputs/flutter-apk/
```

## Part 3: Production Deployment

### API Deployment

#### Option 1: Traditional Server

1. Install dependencies:
```bash
pip install -r requirements.txt -r api_requirements.txt
```

2. Use a production WSGI server:
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 api.app:app
```

3. Set up systemd service (Linux):
```ini
[Unit]
Description=HazeBot API
After=network.target

[Service]
User=hazebot
WorkingDirectory=/path/to/HazeBot
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 api.app:app

[Install]
WantedBy=multi-user.target
```

4. Configure nginx reverse proxy:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location /api {
        proxy_pass http://localhost:5000/api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

#### Option 2: Cloud Platforms

**Railway:**
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

**Heroku:**
```bash
# Create Procfile
echo "web: gunicorn api.app:app" > Procfile

# Deploy
heroku create hazebot-api
git push heroku main
```

**Docker:**
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt api_requirements.txt ./
RUN pip install -r requirements.txt -r api_requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "api.app:app"]
```

### Web Interface Deployment

#### Option 1: Static Hosting

```bash
flutter build web --release
```

Deploy `build/web/` to:
- **Firebase Hosting:**
  ```bash
  firebase init hosting
  firebase deploy
  ```

- **GitHub Pages:**
  ```bash
  # Push build/web contents to gh-pages branch
  ```

- **Netlify/Vercel:**
  - Drag and drop `build/web` folder
  - Or connect GitHub repo

#### Option 2: Docker

```dockerfile
FROM nginx:alpine
COPY build/web /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Android App Deployment

#### Google Play Store

1. **Sign your app:**
```bash
keytool -genkey -v -keystore ~/hazebot-release-key.jks -keyalg RSA -keysize 2048 -validity 10000 -alias hazebot
```

2. **Configure signing in `android/app/build.gradle`:**
```gradle
android {
    signingConfigs {
        release {
            storeFile file("/path/to/hazebot-release-key.jks")
            storePassword "your-password"
            keyAlias "hazebot"
            keyPassword "your-password"
        }
    }
    buildTypes {
        release {
            signingConfig signingConfigs.release
        }
    }
}
```

3. **Build App Bundle:**
```bash
flutter build appbundle --release
```

4. **Upload to Play Console:**
   - Create app in Google Play Console
   - Upload `build/app/outputs/bundle/release/app-release.aab`

#### Direct APK Distribution

```bash
flutter build apk --release
# Share build/app/outputs/flutter-apk/app-release.apk
```

## Part 4: Usage

### Default Login

- Username: `admin` (or value from `API_ADMIN_USER`)
- Password: `changeme` (or value from `API_ADMIN_PASS`)

**Change these immediately in production!**

### Configuration Categories

1. **General** - Bot name, prefix, cooldowns
2. **Channels** - Discord channel IDs
3. **Roles** - Discord role IDs
4. **Memes** - Subreddit and Lemmy configuration
5. **Rocket League** - RL integration settings
6. **Welcome** - Welcome messages and rules

### Making Changes

1. Login to the interface
2. Navigate to the configuration category
3. Update the fields
4. Click "Save Configuration"
5. Changes are applied immediately

## Troubleshooting

### API Issues

**Problem:** `Connection refused`
- Ensure Flask API is running
- Check firewall allows port 5000
- Verify correct IP address

**Problem:** CORS errors
- CORS is enabled by default
- Check Flask-CORS is installed
- Verify API URL in Flutter app

### Flutter Issues

**Problem:** Dependencies won't install
```bash
flutter clean
flutter pub get
```

**Problem:** Android build fails
```bash
cd android
./gradlew clean
cd ..
flutter build apk
```

**Problem:** Web build errors
```bash
flutter clean
flutter pub get
flutter build web
```

### Android Device Testing

**Problem:** Can't connect to API
- Use your computer's local IP (not localhost)
- Ensure both devices on same network
- Check firewall allows connections
- For HTTP, configure network security config

## Security Checklist

- [ ] Changed default API credentials
- [ ] Using HTTPS in production
- [ ] Strong API secret key
- [ ] Firewall configured properly
- [ ] API rate limiting enabled (recommended)
- [ ] Regular security updates
- [ ] Secure storage of .env file
- [ ] Android app signed properly

## Next Steps

1. Test the interface thoroughly
2. Configure all bot settings
3. Set up production deployment
4. Enable HTTPS
5. Configure Android signing
6. Deploy to Play Store (optional)

## Support

For issues or questions:
- Check the logs (Flask and Flutter)
- Review API responses
- Test API endpoints directly
- Check Flutter console for errors

## Additional Resources

- Flask Documentation: https://flask.palletsprojects.com/
- Flutter Documentation: https://docs.flutter.dev/
- Discord.py Documentation: https://discordpy.readthedocs.io/
- JWT: https://jwt.io/
