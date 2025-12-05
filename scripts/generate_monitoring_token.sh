#!/bin/bash
# ============================================================================
# HazeBot - Monitoring Token Generator
# ============================================================================
# Dieses Script generiert einen JWT Token für Uptime Kuma Monitoring
#
# Usage:
#   ./generate_monitoring_token.sh
#
# Requirements:
#   - curl
#   - jq (optional, für pretty output)
#   - API_MONITORING_SECRET muss gesetzt sein
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
API_URL="${API_URL:-https://api.haze.pro}"
OUTPUT_FILE="${OUTPUT_FILE:-monitoring_token.txt}"

echo -e "${BLUE}============================================${NC}"
echo -e "${BLUE}🔐 HazeBot Monitoring Token Generator${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""

# Check if API_MONITORING_SECRET is set
if [ -z "$API_MONITORING_SECRET" ]; then
    echo -e "${RED}❌ ERROR: API_MONITORING_SECRET environment variable not set${NC}"
    echo ""
    echo "Please set the secret first:"
    echo "  export API_MONITORING_SECRET='your-secret-here'"
    echo ""
    echo "Generate a strong secret with:"
    echo "  openssl rand -hex 32"
    exit 1
fi

echo -e "${GREEN}✅ API_MONITORING_SECRET found${NC}"
echo -e "📡 API URL: ${YELLOW}${API_URL}${NC}"
echo ""

# Check if curl is installed
if ! command -v curl &> /dev/null; then
    echo -e "${RED}❌ ERROR: curl is not installed${NC}"
    exit 1
fi

echo "🔄 Requesting monitoring token..."
echo ""

# Make API request
RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${API_URL}/api/auth/monitoring-token" \
    -H "Content-Type: application/json" \
    -d "{\"secret\": \"${API_MONITORING_SECRET}\"}")

# Extract HTTP status code and body
HTTP_CODE=$(echo "$RESPONSE" | tail -n 1)
BODY=$(echo "$RESPONSE" | head -n -1)

# Check HTTP status
if [ "$HTTP_CODE" != "200" ]; then
    echo -e "${RED}❌ ERROR: API request failed with status code ${HTTP_CODE}${NC}"
    echo ""
    echo "Response:"
    echo "$BODY" | (command -v jq &> /dev/null && jq '.' || cat)
    echo ""
    
    if [ "$HTTP_CODE" == "401" ]; then
        echo -e "${YELLOW}💡 Hint: Check if your API_MONITORING_SECRET is correct${NC}"
    elif [ "$HTTP_CODE" == "500" ]; then
        echo -e "${YELLOW}💡 Hint: Make sure API_MONITORING_SECRET is configured on the API server${NC}"
    fi
    
    exit 1
fi

echo -e "${GREEN}✅ Token successfully generated!${NC}"
echo ""

# Parse response (with or without jq)
if command -v jq &> /dev/null; then
    TOKEN=$(echo "$BODY" | jq -r '.token')
    EXPIRES=$(echo "$BODY" | jq -r '.expires')
    EXPIRES_DAYS=$(echo "$BODY" | jq -r '.expires_in_days')
    
    echo -e "${BLUE}============================================${NC}"
    echo -e "${GREEN}📋 Token Details${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
    echo -e "${YELLOW}Token:${NC}"
    echo "$TOKEN"
    echo ""
    echo -e "${YELLOW}Expires:${NC} $EXPIRES (in $EXPIRES_DAYS days)"
    echo ""
    echo -e "${YELLOW}Permissions:${NC} health_check, ping, analytics_read"
    echo ""
else
    # Fallback without jq
    TOKEN=$(echo "$BODY" | grep -o '"token":"[^"]*"' | cut -d'"' -f4)
    
    echo -e "${BLUE}============================================${NC}"
    echo -e "${GREEN}📋 Token Details${NC}"
    echo -e "${BLUE}============================================${NC}"
    echo ""
    echo -e "${YELLOW}Token:${NC}"
    echo "$TOKEN"
    echo ""
    echo "Full Response:"
    echo "$BODY"
    echo ""
fi

# Save to file
echo "$TOKEN" > "$OUTPUT_FILE"
echo -e "${GREEN}✅ Token saved to: ${YELLOW}${OUTPUT_FILE}${NC}"
echo ""

# Usage instructions
echo -e "${BLUE}============================================${NC}"
echo -e "${GREEN}🎯 Next Steps${NC}"
echo -e "${BLUE}============================================${NC}"
echo ""
echo "1. Copy the token above"
echo "2. In Uptime Kuma, create a new HTTP(s) monitor"
echo "3. Add a header:"
echo "   Name: Authorization"
echo "   Value: Bearer ${TOKEN:0:20}..."
echo ""
echo "Example monitors to create:"
echo "  • ${YELLOW}${API_URL}/api/health${NC} (no auth required)"
echo "  • ${YELLOW}${API_URL}/api/ping${NC} (requires token)"
echo "  • ${YELLOW}${API_URL}/api/tickets${NC} (requires token)"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT:${NC}"
echo "  • Store this token securely"
echo "  • Token expires in 90 days"
echo "  • Generate new token before expiry"
echo ""
echo -e "${GREEN}📖 Full documentation: docs/UPTIME_KUMA_SETUP.md${NC}"
echo ""

# Security reminder
echo -e "${RED}🔒 Security Reminder:${NC}"
echo "  • Do NOT commit this token to git"
echo "  • Do NOT share this token publicly"
echo "  • Rotate token every 60-90 days"
echo ""

echo -e "${GREEN}✨ Done!${NC}"
