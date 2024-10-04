#!/bin/bash

echo ""
echo "================================================="
echo "=                                               ="
echo "=      OCS Inventory Backend configuration      ="
echo "=                                               ="
echo "================================================="
echo ""

echo "Select the database engine:"
echo ""
echo "[1] PostgreSQL"
echo "[2] MySQL | MariaDB"
echo ""
read -p "Database engine [1|2]: " db_engine

case $db_engine in
    1)
        sed -i "s/DB_ENGINE=.*/DB_ENGINE='django.db.backends.postgresql'/" /usr/share/ocsinventory-backend/.env
        echo "Database engine configured for PostgreSQL"
        echo "Try to install PostgreSQL python library"
        source /usr/lib/ocsinventory-backend/venv/bin/activate
        pip3 install psycopg2-binary>=2.9.9
        deactivate
        ;;
    2)
        sed -i "s/DB_ENGINE=.*/DB_ENGINE='django.db.backends.mysql'/" /usr/share/ocsinventory-backend/.env
        echo "Database engine configured for MySQL or MariaDB"
        echo "Try to install MySQL/Mariadb python library"
        source /usr/lib/ocsinventory-backend/venv/bin/activate
        pip3 install mysqlclient>=1.4.3
        deactivate
        ;;
    *)
        echo "Invalid option, aborted configuration !"
        exit 1
        ;;
esac

read -p "Which host is running database server ?: " db_host
sed -i "s/DB_HOST=.*/DB_HOST='$db_host'/" /usr/share/ocsinventory-backend/.env

read -p "On which port is running database server ?: " db_port
sed -i "s/DB_PORT=.*/DB_PORT='$db_port'/" /usr/share/ocsinventory-backend/.env

read -p "What is the database name ?: " db_name
sed -i "s/DB_NAME=.*/DB_NAME='$db_name'/" /usr/share/ocsinventory-backend/.env

read -p "What is the database user name ?: " db_user
sed -i "s/DB_USER=.*/DB_USER='$db_user'/" /usr/share/ocsinventory-backend/.env

read -p "What is the database user password ?: " db_password
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

echo ""
echo "For more information, look at /tmp/ocsinventory-backend-configuration.log for the database migrations logs."

echo ""
echo "==========================================================="
echo "=                                                         ="
echo "=      OCS Inventory Backend successfully configured      ="
echo "=                                                         ="
echo "==========================================================="
echo ""
