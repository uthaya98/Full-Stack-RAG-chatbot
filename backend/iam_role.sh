#!/usr/bin/env bash
set -euo pipefail

# ============================
# CONFIGURATION
# ============================
PROJECT_NAME="zuscoffee-chatbot"            
ROLE_NAME="zuscoffee-lambda-role"
REGION="ap-southeast-2"                     
ACCOUNT_ID=$(aws sts get-caller-identity --query "Account" --output text)

# ============================
# STEP 1: Verify IAM Role (optional)
# ============================
echo "🧾 Checking IAM role: $ROLE_NAME"
ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query "Role.Arn" --output text 2>/dev/null || true)
if [ -z "$ROLE_ARN" ]; then
  echo "❌ IAM role not found. Create it manually if needed."
else
  echo "✅ IAM role exists: $ROLE_ARN"
fi

echo "🎉 Script setup complete!"
