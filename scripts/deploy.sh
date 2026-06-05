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
# Ensure all files and directories are owned by ec2-user (fixes permission errors if previously run as root)
sudo chown -R ec2-user:ec2-user /home/ec2-user/rag_project_system
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

# 5. Configure Nginx reverse proxy for portfolio.piyushjoshi.space if not already present
echo "Configuring Nginx reverse proxy..."
if ! command -v nginx &> /dev/null; then
    echo "Installing Nginx..."
    sudo dnf install -y nginx || sudo yum install -y nginx
fi

if [ ! -f /etc/nginx/conf.d/rag_portfolio.conf ]; then
    echo "Creating new Nginx configuration file..."
    sudo tee /etc/nginx/conf.d/rag_portfolio.conf > /dev/null << 'EOF'
server {
    listen 80;
    server_name portfolio.piyushjoshi.space;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
    sudo systemctl enable nginx --now
    sudo systemctl restart nginx
else
    echo "Nginx configuration already exists. Skipping recreation to preserve SSL/custom settings."
fi

echo "Deployment completed successfully!"
