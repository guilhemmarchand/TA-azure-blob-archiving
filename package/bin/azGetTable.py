#!/usr/bin/env python

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys
import splunk
import splunk.entity
import time
import json
import logging
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

splunkhome = os.environ['SPLUNK_HOME']

# set logging
filehandler = logging.FileHandler(splunkhome + "/var/log/splunk/azure2blob_azgettable.log", 'a')
formatter = logging.Formatter('%(asctime)s %(levelname)s %(filename)s %(funcName)s %(lineno)d %(message)s')
filehandler.setFormatter(formatter)
log = logging.getLogger()  # root logger - Good to get it only once.
for hdlr in log.handlers[:]:  # remove the existing file handlers
    if isinstance(hdlr,logging.FileHandler):
        log.removeHandler(hdlr)
log.addHandler(filehandler)      # set the new handler
# set the log level to INFO, DEBUG as the default is ERROR
log.setLevel(logging.INFO)

sys.path.append(os.path.join(splunkhome, 'etc', 'apps', 'TA-azure-blob-archiving', 'lib'))

# import Splunk libs
from splunklib.searchcommands import dispatch, StreamingCommand, Configuration, Option, validators
from splunklib import six
import splunklib.client as client

# log the sys.path for troubleshooting purposes
logging.info("Python sys.path=\"" + str(sys.path) + "\"")

# import Azure librairies
from azure.storage.blob import BlobClient, BlobServiceClient
from azure.cosmosdb.table.tableservice import TableService
from azure.cosmosdb.table.models import Entity

from splunklib.searchcommands import dispatch, GeneratingCommand, Configuration, Option, validators
import splunklib.client as client

@Configuration(distributed=False)

class AzGetTable(GeneratingCommand):

    target_table = Option(
        doc='''
        **Syntax:** **target_table=****
        **Description:** The name of the Azure Storage Account table.''',
        require=True)

    partition_key = Option(
        doc='''
        **Syntax:** **partition_key=****
        **Description:** The value for the PartitionKey.''',
        require=True)


    def generate(self, **kwargs):

        # set loglevel
        loglevel = 'INFO'
        conf_file = "azure2blob_settings"
        confs = self.service.confs[str(conf_file)]
        for stanza in confs:
            if stanza.name == 'logging':
                for stanzakey, stanzavalue in stanza.content.items():
                    if stanzakey == "loglevel":
                        loglevel = stanzavalue
        logginglevel = logging.getLevelName(loglevel)
        log.setLevel(logginglevel)

        # Get the session key
        session_key = self._metadata.searchinfo.session_key

        # Get the current user        
        user = self._metadata.searchinfo.username

        # Get splunkd port
        entity = splunk.entity.getEntity('/server', 'settings',
                                            namespace='TA-azure-blob-archiving', sessionKey=session_key, owner='-')
        splunkd_port = entity['mgmtHostPort']

        # Get conf
        conf_file = "azure2blob_settings"
        confs = self.service.confs[str(conf_file)]
        storage_passwords = self.service.storage_passwords

        # our confs
        AZ_BLOB_CONTAINER = None
        AZ_BLOB_CONNECTION_STRING = None
        # AZ_STORAGE_TABLE_NAME = None
        # table name is argument driven

        # get
        for stanza in confs:
            if stanza.name == "azure2blob":
                for stanzakey, stanzavalue in stanza.content.items():
                    if stanzakey == "AZ_BLOB_CONTAINER":
                        AZ_BLOB_CONTAINER = stanzavalue
                    if stanzakey == "AZ_BLOB_CONNECTION_STRING":
                        AZ_BLOB_CONNECTION_STRING = stanzavalue

        # logging debug
        logging.debug("AZ_BLOB_CONTAINER is: " + str(AZ_BLOB_CONTAINER))
        logging.debug("AZ_BLOB_CONNECTION_STRING is: " + str(AZ_BLOB_CONNECTION_STRING))

        # do not proceed of the connection string is not configured yet
        if str(AZ_BLOB_CONNECTION_STRING) == 'connection_string_to_the_blob_storage':
            logging.error("The Azure connection string was not configured yet, cannot proceed.")
            sys.exit(1)

        # create the table service
        try:
            table_service = TableService(connection_string=AZ_BLOB_CONNECTION_STRING)
        except Exception as e:
            logging.error("Failed to establish the service to the Azure table with exception=" + str(e))

        #
        # Main start
        #

        if self:

            # retrieve all records
            filterStr = "PartitionKey eq \'" + str(self.partition_key) + "\'"
            tasks = table_service.query_entities(
                self.target_table, filter=filterStr)
            for task in tasks:

                record = {
                    'PartitionKey': task.get('PartitionKey'), 'RowKey': task.get('RowKey'), 'blob_name': task.get('blob_name'),
                    'bucket_id': task.get('bucket_id'), 'original_bucket_name': task.get('original_bucket_name'),
                    'original_peer_name': task.get('original_peer_name'), 'original_peer_guid': task.get('original_peer_guid'),
                    'epoch_start': task.get('epoch_start'), 'epoch_end': task.get('epoch_end'), 'size_bytes': task.get('size_bytes'),
                    'indexname': task.get('indexname'), 'clustered_flag': task.get('clustered_flag'), 'status': task.get('status')
                }

                # yield
                data = {'_time': time.time(), '_raw': json.dumps(record, indent=1)}
                yield data

        else:

            # yield
            data = {'_time': time.time(), '_raw': "{\"response\": \"" + "Error: bad request}"}
            yield data


dispatch(AzGetTable, sys.argv, sys.stdin, sys.stdout, __name__)
