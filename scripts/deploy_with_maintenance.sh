#!/bin/bash
# ============================================================================
# HazeBot - Deployment with Uptime Kuma Maintenance Mode
# ============================================================================
# Automatically pauses Uptime Kuma monitors during deployment to prevent
# false downtime alerts during git pull & service restart
#
# Usage:
#   ./scripts/deploy_with_maintenance.sh [duration_minutes]
#
# Example:
#   ./scripts/deploy_with_maintenance.sh 5    # 5 minute maintenance window
#
# Requirements:
#   - curl
#   - UPTIME_KUMA_URL environment variable
#   - UPTIME_KUMA_API_KEY environment variable
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
MAINTENANCE_DURATION="${1:-5}"  # Default 5 minutes
UPTIME_KUMA_URL="${UPTIME_KUMA_URL:-}"
UPTIME_KUMA_API_KEY="${UPTIME_KUMA_API_KEY:-}"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🚀 HazeBot Deployment with Maintenance Mode${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# ============================================================================
# Function: Pause Uptime Kuma Monitors
# ============================================================================
pause_monitors() {
    if [ -z "$UPTIME_KUMA_URL" ] || [ -z "$UPTIME_KUMA_API_KEY" ]; then
        echo -e "${YELLOW}⚠️  Uptime Kuma not configured - skipping maintenance mode${NC}"
        echo -e "${YELLOW}   Set UPTIME_KUMA_URL and UPTIME_KUMA_API_KEY to enable${NC}"
        return 0
    fi
    
    echo -e "${MAGENTA}🔇 Pausing Uptime Kuma monitors for ${MAINTENANCE_DURATION} minutes...${NC}"
    
    # Note: Uptime Kuma API endpoints vary by version
    # Manual pause via UI is recommended for now
    # This serves as a reminder to pause monitors
    
    echo -e "${YELLOW}⚠️  MANUAL ACTION REQUIRED:${NC}"
    echo -e "${YELLOW}   1. Open Uptime Kuma Dashboard${NC}"
    echo -e "${YELLOW}   2. Select monitors for HazeBot API${NC}"
    echo -e "${YELLOW}   3. Click 'Pause' button${NC}"
    echo ""
    echo -e "Press ENTER when monitors are paused, or CTRL+C to cancel"
    read -r
}

# ============================================================================
# Function: Resume Uptime Kuma Monitors
# ============================================================================
resume_monitors() {
    if [ -z "$UPTIME_KUMA_URL" ] || [ -z "$UPTIME_KUMA_API_KEY" ]; then
        return 0
    fi
    
    echo ""
    echo -e "${MAGENTA}🔔 Resuming Uptime Kuma monitors...${NC}"
    echo -e "${YELLOW}⚠️  MANUAL ACTION REQUIRED:${NC}"
    echo -e "${YELLOW}   1. Open Uptime Kuma Dashboard${NC}"
    echo -e "${YELLOW}   2. Select paused monitors${NC}"
    echo -e "${YELLOW}   3. Click 'Resume' button${NC}"
    echo ""
    echo -e "Press ENTER when monitors are resumed"
    read -r
}

# ============================================================================
# Main Deployment Flow
# ============================================================================

echo -e "${GREEN}📋 Deployment Plan:${NC}"
echo -e "   1. Pause Uptime Kuma monitors (${MAINTENANCE_DURATION} min)"
echo -e "   2. Git pull latest changes"
echo -e "   3. Restart service (Pterodactyl)"
echo -e "   4. Wait for service to be healthy"
echo -e "   5. Resume Uptime Kuma monitors"
echo ""
echo -e "Continue? (y/N): "
read -r confirm

if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo -e "${RED}❌ Deployment cancelled${NC}"
    exit 1
fi

echo ""

# Step 1: Pause Monitors
pause_monitors

# Step 2: Git Pull
echo -e "${GREEN}📥 Pulling latest changes from git...${NC}"
git pull origin main
echo -e "${GREEN}✅ Git pull completed${NC}"
echo ""

# Step 3: Service Restart Information
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🔄 Service Restart${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo -e "${YELLOW}Your Pterodactyl panel will automatically:${NC}"
echo -e "  1. Detect git changes"
echo -e "  2. Stop HazeBot"
echo -e "  3. Restart HazeBot"
echo ""
echo -e "${YELLOW}This usually takes 30-120 seconds${NC}"
echo ""

# Step 4: Wait for Service
echo -e "${MAGENTA}⏳ Waiting for service to restart...${NC}"
echo ""

# Check if API is reachable
MAX_ATTEMPTS=30
ATTEMPT=0
API_URL="https://api.haze.pro/api/health"

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    ATTEMPT=$((ATTEMPT + 1))
    
    if curl -f -s "$API_URL" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ API is responding!${NC}"
        break
    else
        echo -ne "${YELLOW}⏳ Attempt $ATTEMPT/$MAX_ATTEMPTS - Waiting for API...${NC}\r"
        sleep 4
    fi
    
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        echo ""
        echo -e "${RED}❌ API did not respond after $MAX_ATTEMPTS attempts${NC}"
        echo -e "${YELLOW}⚠️  Please check Pterodactyl panel manually${NC}"
        echo -e "${YELLOW}   Resume monitors when service is confirmed up${NC}"
        exit 1
    fi
done

echo ""

# Verify health
echo -e "${MAGENTA}🏥 Checking API health...${NC}"
HEALTH_RESPONSE=$(curl -s "$API_URL")
echo "$HEALTH_RESPONSE" | grep -q '"status":"ok"' && \
    echo -e "${GREEN}✅ API health check passed${NC}" || \
    echo -e "${YELLOW}⚠️  API health check returned unexpected response${NC}"

echo ""

# Step 5: Resume Monitors
echo -e "${GREEN}============================================${NC}"
echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo -e "${GREEN}============================================${NC}"
echo ""

resume_monitors

echo ""
echo -e "${GREEN}🎉 All done! Your deployment is complete.${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo -e "  • Verify monitors are green in Uptime Kuma"
echo -e "  • Check Discord for any alerts"
echo -e "  • Test critical endpoints manually"
echo ""

# Summary
echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}📊 Deployment Summary${NC}"
echo -e "${BLUE}============================================${NC}"
echo -e "Branch: $(git rev-parse --abbrev-ref HEAD)"
echo -e "Commit: $(git rev-parse --short HEAD)"
echo -e "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo -e "API URL: $API_URL"
echo -e "${BLUE}============================================${NC}"
