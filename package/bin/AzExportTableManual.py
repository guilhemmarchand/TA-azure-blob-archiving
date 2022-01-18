#!/usr/bin/env python3

# Purpose:
# Download a blob from a container

# usage: python3 AzDownloadBlob.oy <container_name> <blob_name> <target_file>

import sys, os, gzip, shutil, subprocess, random, re, platform, time
import tarfile
import socket
import datetime
import configparser
import contextlib
import csv
import json

# import Az libs
from azure.storage.blob import BlobClient, BlobServiceClient
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
    msg = 'The Application root directory could not be found, is the TA-azure-blob-cold2frozen installed ? We tried: ' + \
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

# Create the AZ table service
table_service = TableService(connection_string=AZ_BLOB_CONNECTION_STRING)

if __name__ == "__main__":
    searchable = False
    
    table_target = sys.argv[1]
    print("container is %s"%table_target)

    input_csv = sys.argv[2]
    print("input_csv is %s"%input_csv)

    # open and read the csv file

    # the csv file requires the following fields:
    # StorageAccount, Table, PartitionKey, RowKey, Timestamp, blob_name, bucket_id, original_bucket_name, original_peer_name, original_peer_guid, epoch_start, epoch_end, indexname, size_bytes, clustered_flag, status

    # Use a Splunk search, define a value for each and export to CSV
    #
    # Then run:
    # argument 1 is the name of the Az Table
    # argument 2 is the name of the CSV file in input
    # /usr/bin/python3 /opt/splunk/etc/apps/TA-azure-blob-archiving/bin/AzExportTableManual.py testexport test.csv

    with open(input_csv) as csv_file:
        readCSV = csv.DictReader(csv_file, delimiter=',')
        line_count = 0
        for row in readCSV:
            record = {
                    'PartitionKey': str(row['PartitionKey']), 'RowKey': str(row['RowKey']), 'blob_name': str(row['blob_name']),
                    'bucket_id': str(row['bucket_id']), 'original_bucket_name': str(row['original_bucket_name']),
                    'original_peer_name': str(row['original_peer_name']), 'original_peer_guid': str(row['original_peer_guid']),
                    'epoch_start': str(row['epoch_start']), 'epoch_end': str(row['epoch_end']), 'size_bytes': str(row['size_bytes']),
                    'indexname': str(row['indexname']), 'clustered_flag': str(row['clustered_flag']), 'status': 'imported'
                    }
            
            # Insert the record
            try:
                print("Inserting record in table=\"" + str(json.dumps(record, indent=1)))
                table_service.insert_entity(table_target, record)

            except Exception as e:
                print("Error with exception: " + str(e))
                sys.exit(1)
