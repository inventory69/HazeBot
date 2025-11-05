# HazeBot Admin - Flutter Application

Modern web and Android interface for configuring the HazeBot Discord bot.

## Features

- 🌐 Cross-platform: Web and Android support
- 🎨 Modern Material Design UI
- 🔐 Secure JWT authentication
- ⚙️ Full bot configuration management
- 📱 Responsive design for all screen sizes
- 🌙 Dark mode support

## Prerequisites

- Flutter SDK (3.0.0 or higher)
- Dart SDK (3.0.0 or higher)
- For Android: Android Studio with Android SDK
- Running HazeBot API server

## Installation

### 1. Install Flutter

Follow the official Flutter installation guide:
- https://docs.flutter.dev/get-started/install

### 2. Install Dependencies

```bash
cd hazebot_admin
flutter pub get
```

### 3. Configuration

Update the API base URL in `lib/services/api_service.dart`:

```dart
static const String baseUrl = 'http://your-api-server:5000/api';
```

For local development, use:
- Web: `http://localhost:5000/api`
- Android emulator: `http://10.0.2.2:5000/api`
- Android device: `http://YOUR_COMPUTER_IP:5000/api`

## Running the Application

### Web

```bash
flutter run -d chrome
```

Or build for production:

```bash
flutter build web
```

The built files will be in `build/web/` directory.

### Android

```bash
# Run in debug mode
flutter run

# Build APK
flutter build apk

# Build App Bundle for Play Store
flutter build appbundle
```

## Project Structure

```
hazebot_admin/
├── lib/
│   ├── main.dart                 # App entry point
│   ├── models/                   # Data models
│   ├── services/                 # API and business logic
│   │   ├── api_service.dart      # REST API client
│   │   ├── auth_service.dart     # Authentication
│   │   └── config_service.dart   # Configuration management
│   ├── screens/                  # UI screens
│   │   ├── login_screen.dart     # Login page
│   │   ├── home_screen.dart      # Main dashboard
│   │   └── config/               # Configuration screens
│   │       ├── general_config_screen.dart
│   │       ├── channels_config_screen.dart
│   │       ├── roles_config_screen.dart
│   │       ├── meme_config_screen.dart
│   │       ├── rocket_league_config_screen.dart
│   │       └── welcome_config_screen.dart
│   └── widgets/                  # Reusable UI components
├── pubspec.yaml                  # Dependencies
└── README.md                     # This file
```

## Features Overview

### Dashboard
- Overview of bot configuration
- Quick status indicators
- Configuration categories

### General Configuration
- Bot name and command prefix
- Presence update interval
- Message cooldown settings
- Fuzzy matching threshold

### Channels Configuration
- Configure Discord channel IDs
- Log channel, changelog channel
- Meme channel, welcome channels
- Ticket system channels

### Roles Configuration
- Admin, moderator, and member roles
- Interest roles
- Special feature roles

### Meme Configuration
- Reddit subreddits
- Lemmy communities
- Meme sources (Reddit/Lemmy)
- Template cache duration

### Rocket League Configuration
- Rank check interval
- Cache TTL settings

### Welcome Configuration
- Server rules text
- Welcome messages
- Button reply messages

## Development

### Hot Reload

Flutter supports hot reload during development:
- Press `r` in the terminal to hot reload
- Press `R` to hot restart
- Press `q` to quit

### Debugging

```bash
flutter run --debug
flutter logs
```

### Building for Production

#### Web
```bash
flutter build web --release
```

#### Android
```bash
# Release APK
flutter build apk --release

# Split APKs by architecture
flutter build apk --split-per-abi --release
```

## Deployment

### Web Deployment

The web build can be deployed to any static hosting service:

```bash
flutter build web --release
# Deploy the build/web directory
```

Supported platforms:
- Firebase Hosting
- GitHub Pages
- Netlify
- Vercel
- AWS S3
- Any static web server

### Android Deployment

1. Sign your app (required for Play Store):
   - Create a keystore
   - Configure signing in `android/app/build.gradle`
   - Build signed APK or App Bundle

2. Deploy to:
   - Google Play Store (recommended)
   - Direct APK distribution
   - Internal testing channels

## Security Notes

- Change default API credentials
- Use HTTPS in production
- Implement proper API authentication
- Store sensitive data securely
- Enable ProGuard for Android release builds

## Troubleshooting

### CORS Issues (Web)
If you encounter CORS errors, ensure the Flask API has CORS properly configured.

### Android Network Issues
- Check AndroidManifest.xml for internet permission
- For HTTP (non-HTTPS) connections, configure network security

### Connection Refused
- Verify API server is running
- Check firewall settings
- Use correct IP address for device testing

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly (web and Android)
5. Submit a pull request

## License

Same as HazeBot main project (MIT License)
