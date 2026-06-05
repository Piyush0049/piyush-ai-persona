#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting deployment steps..."

# 1. Check if virtual environment exists, if not, create it
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# 2. Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# 3. Upgrade pip and install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# 4. Reload systemd and restart the service
echo "Restarting application service..."
sudo systemctl daemon-reload
sudo systemctl restart rag_portfolio.service

echo "Deployment completed successfully!"
