from __future__ import absolute_import, division, print_function, unicode_literals

import os, sys
import splunk
import splunk.entity
import splunk.Intersplunk
import json
import uuid
import time
import subprocess
import tarfile
import logging
from urllib.parse import urlencode

splunkhome = os.environ['SPLUNK_HOME']

# set logging
logger = logging.getLogger(__name__)
filehandler = logging.FileHandler(splunkhome + "/var/log/splunk/azure2blob_rest_handler_restore.log", 'a')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(filename)s %(funcName)s %(lineno)d %(message)s')
filehandler.setFormatter(formatter)
log = logging.getLogger()
for hdlr in log.handlers[:]:
    if isinstance(hdlr,logging.FileHandler):
        log.removeHandler(hdlr)
log.addHandler(filehandler)
log.setLevel(logging.DEBUG)

# append libs, handle if the app is running a standalone instance or clustered
if os.path.exists(os.path.join(splunkhome, 'etc', 'apps', 'TA-azure-blob-archiving', 'lib')):
    sys.path.append(os.path.join(splunkhome, 'etc', 'apps', 'TA-azure-blob-archiving', 'lib'))
elif os.path.exists(os.path.join(splunkhome, 'etc', 'slave-apps', 'TA-azure-blob-archiving', 'lib')):
    sys.path.append(os.path.join(splunkhome, 'etc', 'slave-apps', 'TA-azure-blob-archiving', 'lib'))

import azure2blob_rest_handler
import splunklib.client as client

# import Azure libs
from azure.storage.blob import BlobClient, BlobServiceClient

class AzRestore_v1(azure2blob_rest_handler.RESTHandler):
    def __init__(self, command_line, command_arg):
        super(AzRestore_v1, self).__init__(command_line, command_arg, logger)

    # Request a bucket restore operation
    def post_ta_azure_blob_archiving_v1_restore(self, request_info, **kwargs):

        # vars
        describe = False
        splunk_rebuild = None
        blob_name = None
        target_directory = None

        # Retrieve from data
        try:
            resp_dict = json.loads(str(request_info.raw_args['payload']))
        except Exception as e:
            resp_dict = None

        if resp_dict is not None:
            try:
                describe = resp_dict['describe']
                if describe in ("true", "True"):
                    describe = True
            except Exception as e:
                describe = False
            if not describe:
                splunk_rebuild = resp_dict['splunk_rebuild']
                if splunk_rebuild in ('true', 'True', 'TRUE'):
                    splunk_rebuild = True
                else:
                    splunk_rebuild = False
                blob_name = resp_dict['blob_name']
                target_directory = resp_dict['target_directory']

        else:
            # body is required in this endpoint, if not submitted describe the usage            
            describe = True

        if describe:

            response = {
                "describe": "This endpoint will restore a bucket from Azure Blob storage, it requires a POST call with the following information:",
                "options": [ {
                    "splunk_rebuild": "If the bucket should be rebuilt upon its extraction, valid options are: true | false",
                    "blob_name": "The blob name of the bucket, as stored in Azure",
                    "target_directory": "The Splunk Thawte target directory",
                }]
            }

            return {
                "payload": json.dumps(response, indent=1),
                'status': 200 # HTTP status code
            }

        else:
        
            # Get splunkd port
            entity = splunk.entity.getEntity('/server', 'settings',
                                                namespace='TA-azure-blob-archiving', sessionKey=request_info.session_key, owner='-')
            splunkd_port = entity['mgmtHostPort']

            # Get service
            service = client.connect(
                owner="nobody",
                app="TA-azure-blob-archiving",
                port=splunkd_port,
                token=request_info.session_key
            )

            # set loglevel
            loglevel = 'INFO'
            conf_file = "azure2blob_settings"
            confs = service.confs[str(conf_file)]
            for stanza in confs:
                if stanza.name == 'logging':
                    for stanzakey, stanzavalue in stanza.content.items():
                        if stanzakey == "loglevel":
                            loglevel = stanzavalue
            logginglevel = logging.getLevelName(loglevel)
            log.setLevel(logginglevel)

            # retrieve conf
            for stanza in confs:
                if stanza.name == "azure2blob":
                    for stanzakey, stanzavalue in stanza.content.items():
                        if stanzakey == "AZ_BLOB_CONTAINER":
                            AZ_BLOB_CONTAINER = stanzavalue
                        if stanzakey == "AZ_BLOB_CONNECTION_STRING":
                            AZ_BLOB_CONNECTION_STRING = stanzavalue

            # do not proceed of the connection string is not configured yet
            if str(AZ_BLOB_CONNECTION_STRING) == 'connection_string_to_the_blob_storage':
                logging.error("The Azure connection string was not configured yet, cannot proceed.")
                msg = {
                    "response": "The Azure connection string was not configured yet, cannot proceed.",
                }
                return {
                    "payload": json.dumps(msg, indent=1),
                    'status': 500 # HTTP status code
                }

            # Create the BlobServiceClient object which will be used to create a container client
            blob_service_client = BlobServiceClient.from_connection_string(AZ_BLOB_CONNECTION_STRING)

            try:

                container_client = blob_service_client.get_container_client(AZ_BLOB_CONTAINER)
                blob_client = container_client.get_blob_client(blob_name)

                # compose the taget_file
                if ('/') in blob_name:
                    target_file = str(target_directory) + str(blob_name.split("/")[-1])
                else:
                    target_file = str(target_directory) + str(blob_name)

                # Download the blob file
                logging.info("Attempting to download blob file=" + str(blob_name) + " target_file=" + str(target_file))
                with open(target_file, "wb") as my_blob:
                    download_stream = blob_client.download_blob()
                    my_blob.write(download_stream.readall())

                # Retrieve the size of the tgz archive
                size_bytes = 'unknown'
                if os.path.exists(target_file):
                    size_bytes = os.path.getsize(target_file)
                    logging.info("blob file successfully downloaded to " + str(target_file) +  " size_bytes=" + str(size_bytes))

                try:
                    # Get archive content and extract
                    archive_content = 'unknown'
                    tar = tarfile.open(target_file, 'r')
                    archive_content = tar.getnames()
                    archive_top_directory = archive_content[0]
                    directory_onfilesystem = str(target_directory) + '/' + str(archive_top_directory)
                    for item in tar:
                        tar.extract(item, target_directory)
                    # Remove the tgz
                    if os.path.exists(target_file):
                        os.remove(target_file)

                    #
                    # Archive was downloaded and extracted successfully, we can proceed to rebuild
                    #

                    if splunk_rebuild:

                        # for logging and output purposes
                        splunk_rebuild_action = 'True'

                        process = subprocess.Popen(['/opt/splunk/bin/splunk', 'rebuild', str(directory_onfilesystem)],
                                            stdout=subprocess.PIPE, 
                                            stderr=subprocess.PIPE)
                        stdout, stderr = process.communicate()
                        logging.info(stdout)
                        if stderr:
                            logging.info(stderr)

                    else:
                        # for logging and output purposes
                        splunk_rebuild_action = 'False'

                    msg = {
                        "blob_name": str(blob_name),
                        "size_bytes" : str(size_bytes),
                        "archive_content": str(archive_content),
                        "archive_topdirectory": str(archive_top_directory),
                        "directory_onfilesystem": str(directory_onfilesystem),
                        "target_directory": str(target_directory),
                        "splunk_rebuild_action": str(splunk_rebuild_action),                      
                        "status": "success",
                    }

                    logging.info(msg)
                    return {
                        "payload": json.dumps(msg, indent=1),
                        'status': 200 # HTTP status code
                    }

                except Exception as e:
                    logging.error("failed to extract the file target_file=" + str(target_file) + " in target_directory=" + str(target_directory) + " with exception=" + str(e))
                    # Remove the tgz
                    if os.path.exists(target_file):
                        os.remove(target_file)

                    msg = {
                        "blob_name": str(blob_name),
                        "size_bytes" : str(size_bytes),
                        "archive_content": str(archive_content),
                        "target_directory": str(target_directory),                        
                        "status": "failure",
                        "exception": str(e),
                    }

                    logging.info(msg)
                    return {
                        "payload": json.dumps(msg, indent=1),
                        'status': 500 # HTTP status code
                    }

            except Exception as e:

                msg = {
                    "blob_name": str(blob_name),
                    "target_directory": str(target_directory),
                    "status": "failure",
                    "exception": str(e),
                }

                logging.error(msg)
                return {
                    "payload": json.dumps(msg, indent=1),
                    'status': 500 # HTTP status code
                }
