#!/usr/bin/env python3

# README: 
# - Use this Python script to create the Azure table to be used to store bucket archiving information
# - To run:
# export SPLUNK_HOME="/opt/splunk"
# python3 /opt/splunk/etc/apps/TA-azure-blob-archiving/bin/AzCreateTable.py

import sys, os, gzip, shutil, subprocess, random, re, platform, time
import configparser
from azure.cosmosdb.table.tableservice import TableService
from azure.cosmosdb.table.models import Entity

# Verify SPLUNK_HOME environment variable is available, the script is expected to be launched by Splunk which
#  will set this for debugging or manual run, please set this variable manually
try:
    os.environ["SPLUNK_HOME"]
except KeyError:
    print('The environment variable SPLUNK_HOME could not be verified, if you want to run this script '
                  'manually you need to export it before processing')
    sys.exit(1)
SPLUNK_HOME = os.environ['SPLUNK_HOME']

# Guest Operation System type
ostype = platform.system().lower()

# If running Windows OS (used for directory identification)
is_windows = re.match(r'^win\w+', (platform.system().lower()))

# Discover app path
# app name
appname = "TA-azure-blob-archiving"

if is_windows:
    TA_APP = SPLUNK_HOME + '\\etc\\apps\\' + appname
else:
    TA_APP = SPLUNK_HOME + '/etc/apps/' + appname

if is_windows:
    TA_APP_CLUSTERED = SPLUNK_HOME + '\\etc\\slave-apps\\' + appname
else:
    TA_APP_CLUSTERED = SPLUNK_HOME + '/etc/slave-apps/' + appname

# Empty APP
APP = ''

# Verify APP exist
if os.path.exists(TA_APP):
    APP = TA_APP
elif os.path.exists(TA_APP_CLUSTERED):
    APP = TA_APP_CLUSTERED
else:
    msg = 'The Application root directory could not be found, is the TA-azure-blob-archiving installed ? We tried: ' + \
          str(TA_APP) + ' ' + str(TA_APP_CLUSTERED)
    print(msg)
    sys.exit(1)

# Get config
config = configparser.RawConfigParser()
if is_windows:
    default_config_inifile = APP + "\\default\\azure2blob.conf"
    config_inifile = APP + "\\local\\azure2blob.conf"
else:
    default_config_inifile = APP + "/default/azure2blob.conf"
    config_inifile = APP + "/local/azure2blob.conf"

# First read default config
config.read(default_config_inifile)

# Get default allowed custom values
AZ_STORAGE_TABLE_NAME_DEFAULT = config.get("azure2blob", "AZ_STORAGE_TABLE_NAME")
AZ_BLOB_CONTAINER_DEFAULT = config.get("azure2blob", "AZ_BLOB_CONTAINER")

# Check config exists
if not os.path.isfile(config_inifile):
    msg = 'Please configure your Azure blob settings by creating and configuring a local/azblobconfig.conf.'
    print(msg)
    sys.exit(1)    

# Then read local config
config.read(config_inifile)

# Handles values
AZ_BLOB_CONTAINER_LOCAL = config.get("azure2blob", "AZ_BLOB_CONTAINER")
AZ_BLOB_CONNECTION_STRING = config.get("azure2blob", "AZ_BLOB_CONNECTION_STRING")
AZ_STORAGE_TABLE_NAME_LOCAL = config.get("azure2blob", "AZ_STORAGE_TABLE_NAME")

# Handle allowed custom values

# AZ storage table name
if AZ_STORAGE_TABLE_NAME_LOCAL:
    AZ_STORAGE_TABLE_NAME = AZ_STORAGE_TABLE_NAME_LOCAL
else:
    AZ_STORAGE_TABLE_NAME = AZ_STORAGE_TABLE_NAME_DEFAULT

# AZ blob container
if AZ_BLOB_CONTAINER_LOCAL:
    AZ_BLOB_CONTAINER = AZ_BLOB_CONTAINER_LOCAL
else:
    AZ_BLOB_CONTAINER = AZ_BLOB_CONTAINER_DEFAULT

# Verify AZ_BLOB_CONNECTION_STRING env variable, this is the SAS connection string to the Azure Blob storage
if not AZ_BLOB_CONNECTION_STRING:
    print('The environment variable AZ_BLOB_CONNECTION_STRING could not be verified, this variable is required '
                  'and needs to contain the Azure blob connection string')
    sys.exit(1)

# Verify AZ_BLOB_CONTAINER env variable, this is the blob container value
if not AZ_BLOB_CONTAINER:
    print('The environment variable AZ_BLOB_CONTAINER could not be verified, this variable is required '
                  'and needs to contain the value for Azure blob container')
    sys.exit(1)

# Create the table via SDK
table_service = TableService(connection_string=AZ_BLOB_CONNECTION_STRING)
table_service.create_table(AZ_STORAGE_TABLE_NAME)
