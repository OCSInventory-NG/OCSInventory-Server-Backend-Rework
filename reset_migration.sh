#/bin/bash

find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
find . -path "*/migrations/*.pyc"  -delete
git checkout auth config user inventory automation dashboard group #inventory/category
