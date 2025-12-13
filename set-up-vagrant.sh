#! /bin/bash
echo "Starting vagrant set-up"

echo ""
echo ""echo "Please, enter your sudo password to continue."
sudo -v

echo ""
echo "This script asumes you have VirtualBox, Ansible and Vagrant already installed. If not, please install them before running this script."
read -p "Proceed? (y/n): " response
if [ "$response" == "n" ]
then
    echo "See you soon!"
    sleep 1s
    exit 0
fi

# asks the user if the .env file is configured correctly
echo ""
echo "Make sure you have the correct .env.vagrant.example file, if not, the application will not start correctly (or at all)."
read -p "Proceed? (y/n): " response
if [ "$response" == "n" ]
then
    echo "Please configure the .env file before running this script."
    sleep 1s
    exit 0
fi

# configuring environment
echo ""
echo "Configuring environment..."
cp .env.vagrant.example .env
sudo modprobe -r kvm_intel
sudo systemctl stop mariadb

# start application
echo ""
echo "Starting the application using Vagrant..."
cd vagrant
read -p "Do you want to build anew the machine? (y/n): " response
if [ "$response" == "n" ]
then
    vagrant up
else
    vagrant up --provision
fi
