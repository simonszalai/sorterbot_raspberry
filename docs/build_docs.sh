#!/bin/bash

# Construct script path from script file location
SCRIPT_PATH=$(cd "$(dirname "${BASH_SOURCE[0]}")" ; pwd -P )

# Make html
make -C $SCRIPT_PATH/src html

# Move files to docs folder
mv $SCRIPT_PATH/html/* $SCRIPT_PATH/

# Rename folders starting with _
mv $SCRIPT_PATH/_static $SCRIPT_PATH/static
mv $SCRIPT_PATH/_sources $SCRIPT_PATH/sources

# Replace references for the renamed folders
perl -i -pe's/_static/static/g' genindex.html
perl -i -pe's/_static/static/g' py-modindex.html
perl -i -pe's/_static/static/g' search.html
perl -i -pe's/_static/static/g' index.html
perl -i -pe's/_sources/sources/g' index.html

# Remove html folder
rm -r html
