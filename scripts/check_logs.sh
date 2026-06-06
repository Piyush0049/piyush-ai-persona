#!/bin/bash
# Script to check application logs on AWS EC2

echo "=== Checking RAG Portfolio Service Logs ==="
echo ""
echo "Last 50 lines of application logs:"
echo "-----------------------------------"
sudo journalctl -u rag_portfolio.service -n 50 --no-pager

echo ""
echo "=== To follow logs in real-time, run: ==="
echo "sudo journalctl -u rag_portfolio.service -f"
echo ""
echo "=== To check service status: ==="
echo "sudo systemctl status rag_portfolio.service"
