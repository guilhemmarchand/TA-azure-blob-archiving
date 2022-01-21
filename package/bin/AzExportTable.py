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
filehandler = logging.FileHandler(splunkhome + "/var/log/splunk/azure2blob_azexporttable.log", 'a')
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

@Configuration()
class AzExportToTable(StreamingCommand):

    table_target = Option(
        doc='''
        **Syntax:** **table_target=****
        **Description:** The name of the Azure Storage table target.''',
        require=True)

    field_storage_account = Option(
        doc='''
        **Syntax:** **field_storage_account=****
        **Description:** field name containing the value for StorageAccount.''',
        require=True)

    field_table = Option(
        doc='''
        **Syntax:** **field_table=****
        **Description:** field name containing the value for Table.''',
        require=True)

    field_partitionkey = Option(
        doc='''
        **Syntax:** **field_partitionkey=****
        **Description:** field name containing the value for PartitionKey.''',
        require=True)

    field_row_key = Option(
        doc='''
        **Syntax:** **field_row_key=****
        **Description:** field name containing the value for the value for RowKey.''',
        require=True)

    field_timestamp = Option(
        doc='''
        **Syntax:** **field_timestamp=****
        **Description:** field name containing the value for the value for Timestamp.''',
        require=True)

    field_blob_name = Option(
        doc='''
        **Syntax:** **field_blob_name=****
        **Description:** field name containing the value for blob_name.''',
        require=True)

    field_bucket_id = Option(
        doc='''
        **Syntax:** **field_bucket_id=****
        **Description:** field name containing the value for bucket_id.''',
        require=True)

    field_original_bucket_name = Option(
        doc='''
        **Syntax:** **field_original_bucket_name=****
        **Description:** field name containing the value for original_bucket_name.''',
        require=True)

    field_original_peer_name = Option(
        doc='''
        **Syntax:** **field_original_peer_name=****
        **Description:** field name containing the value for original_peer_name.''',
        require=True)

    field_original_peer_guid = Option(
        doc='''
        **Syntax:** **field_original_peer_guid=****
        **Description:** field name containing the value for original_peer_guid.''',
        require=True)

    field_epoch_start = Option(
        doc='''
        **Syntax:** **field_epoch_start=****
        **Description:** field name containing the value for epoch_start.''',
        require=True)

    field_epoch_end = Option(
        doc='''
        **Syntax:** **field_epoch_end=****
        **Description:** field name containing the value for epoch_start.''',
        require=True)

    field_indexname = Option(
        doc='''
        **Syntax:** **field_indexname=****
        **Description:** field name containing the value for indexname.''',
        require=True)

    field_size_bytes = Option(
        doc='''
        **Syntax:** **field_size_bytes=****
        **Description:** field name containing the value for size_bytes.''',
        require=True)

    field_clustered_flag = Option(
        doc='''
        **Syntax:** **field_clustered_flag=****
        **Description:** field name containing the value for clustered_flag.''',
        require=True)

    # status will be statically defined as imported

    def stream(self, records):

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

        # create the service to the Azure table
        try:
            table_service = TableService(connection_string=AZ_BLOB_CONNECTION_STRING)
        except Exception as e:
            logging.error("Failed to establish the service to the Azure table with exception=" + str(e))

        # empty array to store our processed records
        records_list = []

        # Loop in the results
        records_count = 0
        for splrecord in records:

            # increment
            records_count +=1

            # get fields and values
            StorageAccount = str(splrecord[self.field_storage_account])
            Table = str(splrecord[self.field_table])
            PartitionKey = str(splrecord[self.field_partitionkey])
            RowKey = str(splrecord[self.field_row_key])
            Timestamp = str(splrecord[self.field_timestamp])
            blob_name = str(splrecord[self.field_blob_name])
            bucket_id = str(splrecord[self.field_bucket_id])
            original_bucket_name = str(splrecord[self.field_original_bucket_name])
            original_peer_name = str(splrecord[self.field_original_peer_name])
            original_peer_guid = str(splrecord[self.field_original_peer_guid])
            epoch_start = str(splrecord[self.field_epoch_start])
            epoch_end = str(splrecord[self.field_epoch_end])
            indexname = str(splrecord[self.field_indexname])
            size_bytes = str(splrecord[self.field_size_bytes])
            clustered_flag = str(splrecord[self.field_clustered_flag])
            status = 'imported'

            # Create the record to be added to our array of processed events
            record = {
                        "StorageAccount": str(StorageAccount),
                        "Table": str(Table),
                        "PartitionKey": str(PartitionKey),
                        "RowKey": str(RowKey),
                        "Timestamp": str(Timestamp),
                        "blob_name": str(blob_name),
                        "bucket_id": str(bucket_id),
                        "original_bucket_name": str(original_bucket_name),
                        "original_peer_name": str(original_peer_name),
                        "original_peer_guid": str(original_peer_guid),
                        "epoch_start": str(epoch_start),
                        "epoch_end": str(epoch_end),
                        "indexname": str(indexname),
                        "size_bytes": str(size_bytes),
                        "clustered_flag": str(clustered_flag),
                        "status": str(status),
                        }
                
            # logging debug
            logging.debug("downstream record=\"" + json.dumps(record, indent=1) + "\"")

            # Append to the records array
            records_list.append(record)

        ################################
        # Export to the table by chunk #
        ################################

        # total number of messages to be processed
        results_count = len(records_list)
        logging.info("There are " + str(results_count) + " records to be processed into the Azure table")

        # to report processed messages
        processed_count = 0

        # process by chunk
        chunks = [records_list[i:i + 500] for i in range(0, len(records_list), 500)]
        for chunk in chunks:
            chunk_len = len(chunk)

            for subrecord in chunk:
                # Insert the record in table
                try:
                    logging.debug("Inserting record in table=\"" + str(json.dumps(subrecord, indent=1)))
                    table_service.insert_entity(self.table_target, subrecord)

                except Exception as e:
                    logging.error("Error inserting record in table with exception: " + str(e))
                    sys.exit(1)

            # processed count
            processed_count = processed_count + chunk_len

        # final
        raw = {
            "results_count": str(results_count),
            "processed_count": str(processed_count),
            "user": str(user)
        }

        raw_kv_message = 'results_count=\"' + str(results_count) \
            + '\", processed_count=\"' + str(processed_count) \
            + '\", user=\"' + str(user) + '\"'
        logging.info(raw_kv_message)
        yield {'_time': time.time(), '_raw': json.dumps(raw, indent=4)}

dispatch(AzExportToTable, sys.argv, sys.stdin, sys.stdout, __name__)
