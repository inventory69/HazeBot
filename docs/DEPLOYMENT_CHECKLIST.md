# Deployment Checklist - HazeBot Web Interface

Use this checklist to ensure a smooth deployment of the HazeBot web interface and API.

## Pre-Deployment

### Security Configuration
- [ ] Changed default API admin password (`API_ADMIN_PASS`)
- [ ] Generated strong API secret key (`API_SECRET_KEY`)
- [ ] Set `API_DEBUG=false` in production
- [ ] Reviewed all environment variables in `.env`
- [ ] Removed any test/debug credentials

### API Setup
- [ ] Installed all API dependencies: `pip install -r api_requirements.txt`
- [ ] Tested API locally: `python api/app.py`
- [ ] Verified health endpoint: `curl http://localhost:5000/api/health`
- [ ] Tested authentication: `curl -X POST http://localhost:5000/api/auth/login ...`
- [ ] Confirmed all endpoints work

### Flutter App
- [ ] Updated API base URL in `lib/services/api_service.dart`
- [ ] Tested web build: `flutter build web`
- [ ] Tested Android build (if needed): `flutter build apk`
- [ ] Verified login works with production credentials

## Production Deployment

### Server Setup
- [ ] Server has Python 3.9+ installed
- [ ] Created dedicated user for the application
- [ ] Set up virtual environment: `python -m venv venv`
- [ ] Installed dependencies in venv
- [ ] Configured firewall rules (allow API port)

### API Deployment
- [ ] Installed production WSGI server (gunicorn/uwsgi)
- [ ] Created systemd service file (or equivalent)
- [ ] Configured reverse proxy (nginx/apache)
- [ ] Set up SSL/TLS certificate (Let's Encrypt)
- [ ] Tested HTTPS access
- [ ] Configured automatic startup
- [ ] Set up logging

### Web Interface
- [ ] Built production web bundle: `flutter build web --release`
- [ ] Deployed to static hosting (or served via nginx)
- [ ] Configured correct API URL
- [ ] Tested HTTPS access
- [ ] Verified CORS works

### Android App (Optional)
- [ ] Created keystore for signing
- [ ] Configured signing in `android/app/build.gradle`
- [ ] Built signed APK/bundle: `flutter build appbundle --release`
- [ ] Tested on physical device
- [ ] Uploaded to Play Store (or distributed APK)

## Post-Deployment

### Testing
- [ ] Can access web interface via HTTPS
- [ ] Login works with production credentials
- [ ] Can view bot configuration
- [ ] Can update configuration
- [ ] Changes persist after API restart
- [ ] Error messages are appropriate (no stack traces)
- [ ] Mobile/responsive layout works

### Monitoring
- [ ] Set up log monitoring
- [ ] Configured error alerting
- [ ] Set up uptime monitoring
- [ ] Verified backup strategy

### Documentation
- [ ] Updated team documentation with access URLs
- [ ] Documented credentials location (secure)
- [ ] Created runbook for common issues
- [ ] Informed relevant team members

## Security Hardening

### API Server
- [ ] Firewall configured (only necessary ports open)
- [ ] Rate limiting configured (recommended)
- [ ] HTTPS only (no HTTP)
- [ ] Strong password policy enforced
- [ ] Regular security updates scheduled
- [ ] Logs reviewed regularly
- [ ] Fail2ban or similar configured (optional)

### Application
- [ ] JWT secret is strong and random
- [ ] Tokens expire appropriately
- [ ] Input validation working
- [ ] No sensitive data in logs
- [ ] Error messages don't leak information

### Server
- [ ] SSH key-only authentication
- [ ] Updated system packages
- [ ] Disabled root login
- [ ] Configured automatic security updates
- [ ] Set up backup strategy
- [ ] Tested backup restore process

## Maintenance Plan

### Regular Tasks
- [ ] Weekly: Review logs for errors
- [ ] Monthly: Check for dependency updates
- [ ] Monthly: Verify backups are working
- [ ] Quarterly: Security audit
- [ ] Quarterly: Review and rotate credentials

### Update Process
- [ ] Test updates in staging environment
- [ ] Create backup before updates
- [ ] Update dependencies: `pip install -U -r api_requirements.txt`
- [ ] Update Flutter: `flutter upgrade`
- [ ] Rebuild and redeploy
- [ ] Verify everything works

## Rollback Plan

In case of issues:
1. [ ] Have previous version backed up
2. [ ] Document rollback steps
3. [ ] Test rollback procedure
4. [ ] Keep old credentials available

## Emergency Contacts

- Admin: _________________
- Developer: _________________
- Server host support: _________________

## Notes

Deployment date: _______________
Deployed by: _______________
Server: _______________
URL: _______________

Additional notes:
_________________________________
_________________________________
_________________________________

---

## Quick Commands Reference

### Start API (Development)
```bash
cd api
python app.py
```

### Start API (Production)
```bash
gunicorn -w 4 -b 0.0.0.0:5000 api.app:app
```

### Build Flutter Web
```bash
cd hazebot_admin
flutter build web --release
```

### Build Android APK
```bash
cd hazebot_admin
flutter build apk --release
```

### Check API Status
```bash
curl https://your-domain.com/api/health
```

### View Logs
```bash
# Systemd service
journalctl -u hazebot-api -f

# Direct logs
tail -f /var/log/hazebot-api.log
```

### Restart API
```bash
sudo systemctl restart hazebot-api
```

---

**Security Reminder:** Never commit credentials to version control!
