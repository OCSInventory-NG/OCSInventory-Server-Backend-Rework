#!/bin/bash

echo ""
echo "================================================="
echo "=                                               ="
echo "=      OCS Inventory Backend configuration      ="
echo "=                                               ="
echo "================================================="
echo ""

if [[ ! -w "/usr/share/ocsinventory-backend/.env" ]]; then
    echo "Your user doesn't have sufficient rights to allow the configuration of OCS Inventory Backend."
    exit 1
fi

# remove default Nginx configuration
if [ -f /etc/nginx/sites-enabled/default ]; then
    echo "Removing default Nginx configuration..."
    rm /etc/nginx/sites-enabled/default
    echo "Default Nginx configuration removed."
fi

echo "Select the database engine:"
echo ""
echo "[1] PostgreSQL"
echo "[2] MySQL | MariaDB"
echo ""
read -r -p "Database engine [1|2]: " db_engine

case $db_engine in
    1)
        sed -i "s/DB_ENGINE=.*/DB_ENGINE='django.db.backends.postgresql'/" /usr/share/ocsinventory-backend/.env
        echo "Database engine configured for PostgreSQL"
        echo "Try to install PostgreSQL python library"
        source /usr/lib/ocsinventory-backend/venv/bin/activate
        pip3 install -r /usr/share/ocsinventory-backend/requirements_psql.txt
        deactivate
        ;;
    2)
        sed -i "s/DB_ENGINE=.*/DB_ENGINE='django.db.backends.mysql'/" /usr/share/ocsinventory-backend/.env
        echo "Database engine configured for MySQL or MariaDB"
        echo "Try to install MySQL/Mariadb python library"
        source /usr/lib/ocsinventory-backend/venv/bin/activate
        pip3 install -r /usr/share/ocsinventory-backend/requirements_mysql.txt
        deactivate
        ;;
    *)
        echo "Invalid option, aborted configuration !"
        exit 1
        ;;
esac

read -r -p "Which host is running database server ?: " db_host
sed -i "s/DB_HOST=.*/DB_HOST='$db_host'/" /usr/share/ocsinventory-backend/.env

read -r -p "On which port is running database server ?: " db_port
sed -i "s/DB_PORT=.*/DB_PORT='$db_port'/" /usr/share/ocsinventory-backend/.env

read -r -p "What is the database name ?: " db_name
sed -i "s/DB_NAME=.*/DB_NAME='$db_name'/" /usr/share/ocsinventory-backend/.env

read -r -p "What is the database user name ?: " db_user
sed -i "s/DB_USER=.*/DB_USER='$db_user'/" /usr/share/ocsinventory-backend/.env

read -r -p "What is the database user password ?: " db_password
sed -i "s/DB_PASSWORD=.*/DB_PASSWORD='$db_password'/" /usr/share/ocsinventory-backend/.env

echo "Configuration completed !"
echo "Now, running database migrations..."

source /usr/lib/ocsinventory-backend/venv/bin/activate

if python3 /usr/share/ocsinventory-backend/manage.py migrate > /tmp/ocsinventory-backend-configuration.log 2>&1; then
    echo "Database migrations successfully applied !"
    deactivate
else
    echo "Error during database migrations, please check /tmp/ocsinventory-backend-configuration.log for more information."
    deactivate
    exit 1
fi

# restart uWSGI service
echo "Restarting uWSGI and Nginx services..."
systemctl restart uwsgi
if [ $? -eq 0 ]; then
    echo "uWSGI service restarted successfully."
else
    echo "Error restarting uWSGI service. Please check the service status manually."
    exit 1
fi

systemctl restart nginx
if [ $? -eq 0 ]; then
    echo "Nginx service restarted successfully."
else
    echo "Error restarting Nginx service. Please check the service status manually."
    exit 1
fi

echo ""
echo "For more information, look at /tmp/ocsinventory-backend-configuration.log for the database migrations logs."

echo ""
echo "==========================================================="
echo "=                                                         ="
echo "=      OCS Inventory Backend successfully configured      ="
echo "=                                                         ="
echo "==========================================================="
echo ""
