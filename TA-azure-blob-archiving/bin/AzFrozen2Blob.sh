#!/bin/bash

# For Splunk instance prior to Python 3, the PYTHONPATH may refer to Python 2 can cause failures during the import of modules
unset PYTHONPATH

# Retrieve the first argument that is the bucket name
bucket=$1

# Check SPL_HOME variable is defined, this should be the case when launched by Splunk scheduler
if [ -z "${SPLUNK_HOME}" ]; then
        echo "ERROR, SPLUNK_HOME variable is not defined, please set SPLUNK_HOME to run this script manually"
        exit 1
fi

# Discover APP directory
APP_ROOT="TA-azure-blob-archiving"

if [ -d "$SPLUNK_HOME/etc/apps/${APP_ROOT}" ]; then
        APP=$SPLUNK_HOME/etc/apps/${APP_ROOT}

elif [ -d "$SPLUNK_HOME/etc/slave-apps/${APP_ROOT}" ];then
        APP=$SPLUNK_HOME/etc/slave-apps/${APP_ROOT}

else
        echo "ERROR, the APP directory could not be defined, is the ${APP_ROOT} installed ?"
        exit 1
fi

# Run
/usr/bin/python3 ${APP}/bin/AzFrozen2Blob.py $bucket