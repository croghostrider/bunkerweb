#!/bin/bash

# Function to run a command and check its return code
function do_and_check_cmd() {
    output=$("$@" 2>&1)
    ret="$?"
    if [ $ret -ne 0 ] ; then
        echo "❌ Error from command : $*"
        echo "$output"
        exit $ret
    else
        echo "✔️ Success: $*"
        echo "$output"
    fi
    return 0
}

#Start the nginx service if it is not already running
if ! systemctl is-active nginx; then
    echo "Starting nginx service..."
    do_and_check_cmd systemctl start nginx
fi

#Give all the permissions to the nginx user
echo "Setting ownership for all necessary directories to nginx user and group..."
do_and_check_cmd chown -R nginx:nginx /usr/share/bunkerweb /var/cache/bunkerweb /var/lib/bunkerweb /etc/bunkerweb /var/tmp/bunkerweb

#Start bunkerweb service as nginx user and enable it to start on boot
echo "Enabling and starting bunkerweb service..."
do_and_check_cmd systemctl enable bunkerweb
do_and_check_cmd systemctl start bunkerweb

#Start and enable bunkerweb-ui service
echo "Enabling and starting bunkerweb-ui service..."
do_and_check_cmd systemctl enable bunkerweb-ui
do_and_check_cmd systemctl start bunkerweb-ui

# Copy old line from environment file to new one
# Check if old environment file exists
if [ -f /var/tmp/variables.env ]; then
    echo "Old environment file found!"
    echo "Copying old line from environment file to new one..."
    while read line; do
        echo "$line" >> /etc/bunkerweb/variables.env
    done < /var/tmp/variables.env
    # Remove old environment files
    echo "Removing old environment files..."
    do_and_check_cmd rm -f /var/tmp/variables.env
else
    echo "Old environment file not found!"
    exit 0
fi

# Copy old line from ui environment file to new one
# Check if old environment file exists
if [ -f /var/tmp/ui.env ]; then
    echo "Old ui environment file found!"
    echo "Copying old line from ui environment file to new one..."
    while read line; do
        echo "$line" >> /etc/bunkerweb/ui.env
    done < /var/tmp/ui.env
    # Remove old environment files
    echo "Removing old environment files..."
    do_and_check_cmd rm -f /var/tmp/ui.env
else
    echo "Old ui environment file not found!"
    exit 0
fi

# Check if old db.sqlite3 file exists
if [ -f /var/tmp/bunkerweb/db.sqlite3 ]; then
    echo "Old db.sqlite3 file found!"
    do_and_check_cmd cp /var/tmp/bunkerweb/db.sqlite3 /var/lib/bunkerweb/db.sqlite3
    do_and_check_cmd rm -f /var/lib/bunkerweb/db.sqlite3
else
    echo "Old db.sqlite3 file not found!"
    exit 0
fi

echo "All services started and enabled successfully!"