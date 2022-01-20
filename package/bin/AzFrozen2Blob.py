#!/usr/bin/env python3

# Purpose:
# This is a frozen script for Splunk which purpose is to archive frozen buckets in Azure blob storage
# In addition with the archiving itself, the framework is built on top of Azure storage tables which are used
# to store statuses of the buckets that were archived and define if an indexer needs to archive a bucket or not
# In a context of clustered indexers, this avoids archiving buckets that were archived by another peer already due to bucket replication

# To use this script you need to configure in a local/azure2blob.conf the following information:
# AZ_BLOB_CONTAINER = name of the container to be used for achiving, this value is used as the value for paritionkey in the Azure storage table too
# AZ_BLOB_CONNECTION_STRING = The connection string that provides us access to the blob storage and the Azure storage table
# AZ_STORAGE_TABLE_NAME = The name for the Azure storage to be used, will be created automatically if does not exist

# exit code:
# exit 0 if upload to blob storage was successfull, Splunk proceed to the purge of the frozen bucket
# exit 1 if upload has failed, Splunk will re-attempt continously to achive the bucket

import sys, os, gzip, shutil, subprocess, random, re, platform, time
import tarfile
import socket
import configparser
import contextlib
import datetime
import json
import logging

# Verify SPLUNK_HOME environment variable is available, the script is expected to be launched by Splunk which
#  will set this for debugging or manual run, please set this variable manually
try:
    os.environ["SPLUNK_HOME"]
except KeyError:
    print('The environment variable SPLUNK_HOME could not be verified, if you want to run this script '
                  'manually you need to export it before processing')
    sys.exit(1)
SPLUNK_HOME = os.environ['SPLUNK_HOME']

# append libs
sys.path.append(os.path.join(SPLUNK_HOME, 'etc', 'apps', 'TA-azure-blob-archiving', 'lib'))

# import Azure libs
from azure.storage.blob import BlobClient, BlobServiceClient
from azure.cosmosdb.table.tableservice import TableService
from azure.cosmosdb.table.models import Entity

# set logging
filehandler = logging.FileHandler(SPLUNK_HOME + "/var/log/splunk/azure2blob_azfrozen2blob.log", 'a')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(filename)s %(funcName)s %(lineno)d %(message)s')
filehandler.setFormatter(formatter)
log = logging.getLogger()  # root logger - Good to get it only once.
for hdlr in log.handlers[:]:  # remove the existing file handlers
    if isinstance(hdlr,logging.FileHandler):
        log.removeHandler(hdlr)
log.addHandler(filehandler)      # set the new handler
# set the log level to INFO, DEBUG as the default is ERROR
log.setLevel(logging.INFO)

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
    logging.error(msg)
    sys.exit(1)

# Get config
config = configparser.RawConfigParser()
if is_windows:
    default_app_settings_initfile = APP + "\\default\\azure2blob_settings.conf"
    local_app_settings_initfile = APP + "\\default\\azure2blob_settings.conf"
else:
    default_app_settings_initfile = APP + "/default/azure2blob_settings.conf"
    local_app_settings_initfile = APP + "/local/azure2blob_settings.conf"

# First read default config
config.read(default_app_settings_initfile)

# Get default values
AZ_BLOB_CONNECTION_STRING = config.get("azure2blob", "AZ_BLOB_CONNECTION_STRING")
AZ_STORAGE_TABLE_NAME = config.get("azure2blob", "AZ_STORAGE_TABLE_NAME")
AZ_BLOB_CONTAINER = config.get("azure2blob", "AZ_BLOB_CONTAINER")
AZ_BLOB_STRUCTURE = config.get("azure2blob", "AZ_BLOB_STRUCTURE")
AZ_LOGGING_LEVEL = config.get("logging", "loglevel")

# Check config exists
if not os.path.isfile(local_app_settings_initfile):
    msg = 'Please configure your Azure blob settings by creating and configuring a local/azblobconfig_settings.conf.'
    logging.error(msg)
    sys.exit(1)    

# If app has a local setting file, try to read logging
if os.path.isfile(local_app_settings_initfile):
    config.read(local_app_settings_initfile)

    try:
        AZ_BLOB_CONNECTION_STRING = config.get("azure2blob", "AZ_BLOB_CONNECTION_STRING")
    except Exception as e:
        AZ_BLOB_CONNECTION_STRING = AZ_BLOB_CONNECTION_STRING

    try:
        AZ_STORAGE_TABLE_NAME = config.get("azure2blob", "AZ_STORAGE_TABLE_NAME")
    except Exception as e:
        AZ_STORAGE_TABLE_NAME = AZ_STORAGE_TABLE_NAME

    try:
        AZ_BLOB_CONTAINER = config.get("azure2blob", "AZ_BLOB_CONTAINER")
    except Exception as e:
        AZ_BLOB_CONTAINER = AZ_BLOB_CONTAINER

    try:
        AZ_BLOB_STRUCTURE = config.get("azure2blob", "AZ_BLOB_STRUCTURE")
    except Exception as e:
        AZ_BLOB_STRUCTURE = AZ_BLOB_STRUCTURE

    try:
        AZ_LOGGING_LEVEL = config.get("logging", "loglevel")
    except Exception as e:
        AZ_LOGGING_LEVEL = AZ_LOGGING_LEVEL


# finally set logging level
log.setLevel(AZ_LOGGING_LEVEL)

# do not proceed of the connection string is not configured yet
if str(AZ_BLOB_CONNECTION_STRING) == 'connection_string_to_the_blob_storage':
    logging.error("The Azure connection string was not configured yet, cannot proceed.")
    sys.exit(1)
elif not AZ_BLOB_CONNECTION_STRING:
    logging.error('The environment variable AZ_BLOB_CONNECTION_STRING could not be verified, this variable is required '
                  'and needs to contain the Azure blob connection string')
    sys.exit(1)

# Verify AZ_BLOB_CONTAINER env variable, this is the blob container value
if not AZ_BLOB_CONTAINER:
    logging.error('The environment variable AZ_BLOB_CONTAINER could not be verified, this variable is required '
                  'and needs to contain the value for Azure blob container')
    sys.exit(1)

# Attempt creating the blob container if does not exist already

# Create the BlobServiceClient object which will be used to create a container client
blob_service_client = BlobServiceClient.from_connection_string(AZ_BLOB_CONNECTION_STRING)

# Create the Azure blob container if required
container_was_created = False
try:
    container_client = blob_service_client.create_container(AZ_BLOB_CONTAINER)
    container_was_created = True
except:
    container_was_created = False

if container_was_created:
    logging.info("The Azure blob container " + str(AZ_BLOB_CONTAINER) + " has been created.")

# Create the AZ table service
table_service = TableService(connection_string=AZ_BLOB_CONNECTION_STRING)

#
# FUNCTIONS
#


def getHostName():
    # Get the local hostname from the networking stack.
    localHostname = socket.gethostname()

    # gethostname() can either return just the host component or the FQDN.  This behaviour cannot be predicted
    # and can change between invocations on the same host.  To ensure we are putting archive buckets in the same
    # location for the specific host, we'll strip the domain portion off if it exists
    domainCheck = re.compile(r'.*\..*')
    if domainCheck.match(localHostname):
        localHostname = localHostname.split(".")[0]

    return localHostname


def make_tarfile(output_filename, source_dir):
    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir))


# For new style buckets (v4.2+), we can remove all files except for the rawdata.
# We can later rebuild all metadata and tsidx files with "splunk rebuild"
def handleNewBucket(base, files):
    logging.info('Archiving bucket: ' + base)
    # the only non file is the rawdata folder, which we want to archive
    for f in files:
        full = os.path.join(base, f)
        if os.path.isfile(full):
            logging.info(full)
            os.remove(full)


# For buckets created before 4.2, simply gzip the tsidx files
# To thaw these buckets, be sure to first unzip the tsidx files
def handleOldBucket(base, files):
    logging.info('Archiving old-style bucket: ' + base)
    for f in files:
        full = os.path.join(base, f)
        if os.path.isfile(full) and (f.endswith('.tsidx') or f.endswith('.data')):
            fin = open(full, 'rb')
            fout = gzip.open(full + '.gz', 'wb')
            fout.writelines(fin)
            fout.close()
            fin.close()
            os.remove(full)


# This function is not called, but serves as an example of how to do
# the previous "flatfile" style export. This method is still not
# recommended as it is resource intensive
def handleOldFlatfileExport(base, files):
    command = ['exporttool', base, os.path.join(base, 'index.export'), 'meta::all']
    retcode = subprocess.call(command)
    if retcode != 0:
        sys.exit('exporttool failed with return code: ' + str(retcode))

    for f in files:
        full = os.path.join(base, f)
        if os.path.isfile(full):
            os.remove(full)
        elif os.path.isdir(full):
            shutil.rmtree(full)
        else:
            logging.warn('Warning: found irregular bucket file: ' + full)

#
# PROGRAM START
#

if __name__ == "__main__":
    searchable = False
    if len(sys.argv) != 2:
        sys.exit('usage: python3 AzFrozen2Blob.py <bucket_dir_to_archive>')

    bucket = sys.argv[1]
    logging.info("bucket is %s"%bucket)

    if bucket.endswith('/'):
        logging.debug("the bucket name ends with a / %s" % bucket)
        bucket = bucket[:-1]

    idx_struct = re.search(r'(.*)\/(colddb|db)\/(.*)', bucket, re.MULTILINE)
    logging.debug("idx_struct is %s" % idx_struct)

    if idx_struct is None:
        indexname = os.path.basename(os.path.dirname(bucket))
        logging.debug("indexname is %s" % indexname)
    else:
        indexname = os.path.basename(os.path.dirname(os.path.dirname(bucket)))
        logging.debug("indexname is %s" % indexname)

    if not os.path.isdir(bucket):
        logging.error('Given bucket is not a valid directory: ' + bucket)
        sys.exit(1)

    rawdatadir = os.path.join(bucket, 'rawdata')
    if not os.path.isdir(rawdatadir):
        logging.error('No rawdata directory, given bucket is likely invalid: ' + bucket)
        sys.exit(1)

    files = os.listdir(bucket)
    journal_gz = os.path.join(rawdatadir, 'journal.gz')
    journal_zst = os.path.join(rawdatadir, 'journal.zst')
    logging.debug("is it gz? %s" % os.path.isfile(journal_gz))
    logging.debug("is it zst? %s" % os.path.isfile(journal_zst))
    if os.path.isfile(journal_zst) or os.path.isfile(journal_gz):
        handleNewBucket(bucket, files)
    else:
        handleOldBucket(bucket, files)

    peer_name = getHostName()
    logging.debug("peer_name is %s" % peer_name)

    bucket_name = bucket.split("/")[-1]
    logging.debug("bucket_name is %s" % bucket_name)

    # Get bucket UTC epoch start and UTC epoch end
    buckets_info = bucket_name.split('_')
    bucket_epoch_start, bucket_epoch_end = "null", "null"
    bucket_epoch_end = buckets_info[1]
    bucket_epoch_start = buckets_info[2]
    logging.debug("bucket_epoch_start is %s" % bucket_epoch_start)
    logging.debug("bucket_epoch_end is %s" % bucket_epoch_end)    

    bucket_id_list = bucket_name.split("_")[3:]
    logging.debug("bucket_id_list is %s" % bucket_id_list)
    if len(bucket_id_list) == 1:
        clustered_flag = "0"
        # This means it's a non replicated bucket, so need to grab the GUID from instance.cfg
        logging.debug("# This means it's a non replicated bucket, so need to grab the GUID from instance.cfg")
        with open(SPLUNK_HOME + "/etc/instance.cfg", "r") as f:
            read_data = f.read()
            match = re.search(r'^guid = (.*)', read_data, re.MULTILINE)
            original_peer_guid = match.group(1)
            logging.debug("original_peer_guid is %s" % original_peer_guid)
        bucket_id = indexname + "_" + original_peer_guid + "_" + bucket_id_list[0]
    else:
        logging.debug("# This means it's a replicated bucket, we'll grab the GUID from the b name")
        # This means it's a replicated bucket, we'll grab the GUID from the b name
        clustered_flag = "1"
        bucket_id = indexname+"_"+bucket_id_list[1]+"_"+bucket_id_list[0]
        original_peer_guid = bucket_id_list[1]

    # print the bucket_id
    logging.debug("bucket_id is %s" % bucket_id)

    # define the bucket tgz file path
    bucket_tgz = bucket + '.tgz'

    # Research in the Azure Table if this entity exists and if its archiving status is success
    # If the entity complies with this, archiving is not required and this bucket_id was already archived on this peer or another peer
    # Otherwise, continue.

    bucket_is_archived = False
    record_found = False
    record_status = None

    try:
        with contextlib.redirect_stderr(None):
            record = table_service.get_entity(AZ_STORAGE_TABLE_NAME, AZ_BLOB_CONTAINER, bucket_id, select='status', timeout=60)
            record_status = record.status
            record_found = True
    except Exception as e:
        record_found = False

    if record_found and record_status in "success":
        bucket_is_archived = True
    else:
        bucket_is_archived = False

    if bucket_is_archived:
        logging.info("The bucket " + bucket_id + " has been archived already, nothing to do and will exit 0")        
        sys.exit(0)
    else:
        logging.info("The bucket " + bucket_id + " has not been archived yet, proceed to archiving now")

    # Create a tgz from tbe bucket, and sleep a few seconds to let time for the file closure
    make_tarfile(bucket_tgz, bucket)
    time.sleep(5)

    # Get tgz size in bytes
    try : 
        size = os.path.getsize(bucket_tgz) 
    
    except OSError : 
        logging.error("Path '%s' does not exists or is inaccessible" %bucket_tgz) 
        sys.exit() 
    
    # Print the size (in bytes) 
    # of specified path  
    logging.debug("Size (In bytes) of '% s':" % bucket_tgz, size)    

    # Print the peer name
    logging.debug("the peer name is %s" %peer_name)

    # Define the blob structure and name
    if AZ_BLOB_STRUCTURE == 'index':
        blob_name = indexname + "/" + bucket_id + ".tgz"
    elif AZ_BLOB_STRUCTURE == 'index_year':
        blob_name = indexname + "/" + str(datetime.datetime.now().date().strftime("%Y")) + "/" + bucket_id + ".tgz"
    elif AZ_BLOB_STRUCTURE == 'index_year_month':
        blob_name = indexname + "/" + str(datetime.datetime.now().date().strftime("%Y")) + "/" + str(datetime.datetime.now().date().strftime("%m")) + "/" + bucket_id + ".tgz"
    else:
        blob_name = indexname + "/" + bucket_id + ".tgz"

    blob = BlobClient.from_connection_string(conn_str=AZ_BLOB_CONNECTION_STRING, container_name=AZ_BLOB_CONTAINER, blob_name=blob_name)

    # Finally upload to the blob storage, return the results and exit with the error code
    az_upload_success = False

    with open(bucket_tgz, "rb") as data:
        try:
            blob.upload_blob(data)
            az_upload_success = True
        except:
            az_upload_success = False

    if az_upload_success:
        logging.info('Archive upload to Azure blob storage successful for bucket ' + bucket_id)
        logging.info('The bucket ' + bucket_id + ' has been archived successfully, sending an exit code 0 to Splunk now')
        if os.path.isfile(bucket_tgz):
            os.remove(bucket_tgz)
        # Create the record and update the AZ Storage table only if the upload was successful
        record = {'PartitionKey': AZ_BLOB_CONTAINER, 'RowKey': bucket_id, 'blob_name': blob_name,                
                'bucket_id': bucket_id, 'original_bucket_name': bucket_name,
                'original_peer_name': peer_name, 'original_peer_guid': original_peer_guid,
                'epoch_start': bucket_epoch_start, 'epoch_end': bucket_epoch_end, 'size_bytes': size,
                'indexname': indexname, 'clustered_flag': clustered_flag, 'status': 'success'}
        table_service.insert_entity(AZ_STORAGE_TABLE_NAME, record)
        sys.exit(0)
    else:
        logging.error('Archive upload to Azure blob storage has failed for bucket ' + bucket_id)
        print(sys.exc_info()[1])
        if os.path.isfile(bucket_tgz):
            os.remove(bucket_tgz)
        sys.exit(1)
