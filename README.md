# OCS Inventory Server Backend

Welcome to the new backend application for OCS Inventory.

## Table of Contents
- [Introduction](#introduction)
- [Production Use](#production-use)
- [Development Setup](#development-setup)

## Introduction

This repository hosts the backend application for the OCS Inventory Server. It aims to provide a modern REST API for managing IT assets, deployments, and administrative tasks.

## Production Use

To deploy and use the backend in production, or to find resources related to OCS Inventory, refer to the following official links:
- [OCS Inventory Prerequisites](https://documentation.ocsinventory-ng.org/administrator-docs/system-requirements) - Requirements needed to install the solution
- [OCS Inventory Server Setup](https://documentation.ocsinventory-ng.org/administrator-docs/server-setup) - Complete installation guide for OCS Inventory Server (backend and frontend component)
- [OCS Inventory Documentation Wiki](https://documentation.ocsinventory-ng.org/) - Official guides on installation, configuration, and administration.

## Development Setup

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
