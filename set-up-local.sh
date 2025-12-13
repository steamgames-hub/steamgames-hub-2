#! /bin/bash
echo "Starting local set-up"

echo ""
echo "Please, enter your sudo password to continue."
sudo -v

# asks the user if python is configured correctly
echo ""
echo "This script asumes you have Python already installed. If not, please install them before running this script."
read -p "Proceed? (y/n): " response
if [ "$response" == "n" ]
then
    echo "See you soon!"
    sleep 1s
    exit 0
fi

# asks the user if python is configured correctly
echo ""
echo "This script asumes you have Python already installed. If not, please install them before running this script."
read -p "Proceed? (y/n): " response
if [ "$response" == "n" ]
then
    echo "See you soon!"
    sleep 1s
    exit 0
fi

# asks the user if the .env file is configured correctly
echo ""
echo "Make sure you have the correct .env.local.example file, if not, the application will not start correctly (or at all)."
read -p "Proceed? (y/n): " response
if [ "$response" == "n" ]
then
    echo "Please configure the .env file before running this script."
    sleep 1s
    exit 0
fi

# update and upgrade system
echo ""
echo "Updating and upgrading the system..."
sudo apt -qq update -y
sudo apt -qq upgrade -y

# mariadb setup
echo ""
read -p "Do you have mariadb already installed and configured as required? (y/n): " response
if [ "$response" == "n" ]
then
    echo "Installing and configuring mariadb..."
    sudo apt install mariadb-server -y
    sudo mysql_secure_installation
fi

# create database and user
echo ""
echo "Creating databases and user..."
sudo systemctl start mariadb
sudo mysql -e "CREATE DATABASE IF NOT EXISTS steamgameshubdb;"
sudo mysql -e "CREATE DATABASE IF NOT EXISTS steamgameshubdb_test;"
sudo mysql -e "CREATE USER IF NOT EXISTS 'steamgameshubdb_user'@'localhost' IDENTIFIED BY 'steamgameshubdb_password';"
sudo mysql -e "GRANT ALL PRIVILEGES ON steamgameshubdb.* TO 'steamgameshubdb_user'@'localhost';"
sudo mysql -e "GRANT ALL PRIVILEGES ON steamgameshubdb_test.* TO 'steamgameshubdb_user'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"

# configure .env
echo ""
echo "Configuring environment..."
cp .env.local.example .env
echo "webhook" > .moduleignore

# install dependencies
echo ""
echo "Installing dependencies..."
sudo apt install python3.12-venv
sudo python3.12 -m venv venv

echo ""
echo "Activating virtual environment..."
. ./venv/bin/activate
sudo rm -rf rosemary.egg-info
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet
pip install -e ./ --quiet

# initialize database
echo ""
echo "Initializing database..."
flask db upgrade
rosemary db:seed --reset -y

# run the application
echo ""
echo "Starting the application..."
flask run --host=0.0.0.0 --reload --debug
