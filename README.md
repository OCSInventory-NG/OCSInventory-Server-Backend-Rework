# OCSInventory-Server-Rework

Rework of the OCS Inventory project server

# Getting started


Install basic requirements using pip

```bash
pip install -r requirements.txt
```

In case python-ldap brings an error, check the following link : <https://www.python-ldap.org/en/python-ldap-3.4.3/installing.html>

Depending on the database system you plan to use:

```bash
pip install -r requirements_psql.txt # For postgresql
pip install -r requirements_mysql.txt # For mysql 
```

Copy the `.env-sample` to `.env` :

```bash
cp .env-sample .env
```

Note : database and user creation won't be described in this readme, please refer to your database system documentation

Using your favorite editor, edit the file with the correct database connection info :

```bash
DEBUG=False
SECRET_KEY='a-not-secure-key'
DB_ENGINE='django.db.backends.postgresql' # django.db.backends.mysql for Mysql / Mariadb
DB_NAME='dbname'
DB_USER='user'
DB_PASSWORD='pass'
DB_HOST='localhost'
DB_PORT='5432'
```

For more details : <https://docs.djangoproject.com/en/5.2/ref/databases/>
