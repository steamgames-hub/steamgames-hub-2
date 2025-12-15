#! /bin/bash
echo "Starting docker set-up"

echo ""
echo ""echo "Please, enter your sudo password to continue."
sudo -v

echo ""
echo "This script asumes you have Docker and Docker Compose already installed. If not, please install them before running this script."
echo "Make sure you have the correct .env.docker.example file, if not, the application will not start correctly (or at all)."
read -p "Proceed? (y/n): " response
if [ "$response" == "n" ]
then
    echo "See you soon!"
    sleep 1s
    exit 0
fi

# configuring environment
echo ""
echo "Configuring environment..."
cp .env.docker.example .env
sudo systemctl stop mariadb

# start application
echo ""
echo "Starting the application using Docker..."
read -p "Do you want to build anew the machine? (y/n): " response
if [ "$response" == "n" ]
then
    docker compose -f docker/docker-compose.dev.yml up
    exit 0
else
    docker compose -f docker/docker-compose.dev.yml up --build -d
    exit 0
fi
