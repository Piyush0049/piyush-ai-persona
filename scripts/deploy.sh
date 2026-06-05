#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

echo "Starting deployment steps..."

# Ensure git, python3, and pip are installed (compatible with Amazon Linux dnf/yum)
if ! command -v git &> /dev/null; then
    echo "git not found. Installing git..."
    sudo dnf install -y git || sudo yum install -y git
fi

if ! command -v python3 &> /dev/null; then
    echo "python3 not found. Installing python3..."
    sudo dnf install -y python3 || sudo yum install -y python3
fi

if ! python3 -c "import venv" &> /dev/null; then
    echo "venv module not found. Installing python3-pip and virtualenv support..."
    sudo dnf install -y python3-pip || sudo yum install -y python3-pip
fi

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

# 4. Configure systemd service if not present, reload, and restart
echo "Configuring and restarting application service..."
sudo cp rag_portfolio.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable rag_portfolio.service
sudo systemctl restart rag_portfolio.service

echo "Deployment completed successfully!"
