#!/bin/bash

# Update backup-status project script
echo "Starting backup-status project update..."

# Navigate to project directory
cd /var/www/backup-status

# Change ownership to adminlocal for git operations
echo "Changing ownership to adminlocal..."
sudo chown -R adminlocal:adminlocal /var/www/backup-status

# Pull latest changes from git
echo "Pulling latest changes..."
git pull

# Change ownership back to www-data for web server
echo "Changing ownership to www-data..."
sudo chown -R www-data:www-data /var/www/backup-status

# Restart the service
echo "Restarting backup_status service..."
sudo systemctl restart backup_status.service

echo "Update completed successfully!"
