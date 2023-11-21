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

splunkhome = os.environ["SPLUNK_HOME"]

# set logging
filehandler = logging.FileHandler(
    splunkhome + "/var/log/splunk/azure2blob_azpurgeblob.log", "a"
)
formatter = logging.Formatter(
    "%(asctime)s %(levelname)s %(filename)s %(funcName)s %(lineno)d %(message)s"
)
filehandler.setFormatter(formatter)
log = logging.getLogger()  # root logger - Good to get it only once.
for hdlr in log.handlers[:]:  # remove the existing file handlers
    if isinstance(hdlr, logging.FileHandler):
        log.removeHandler(hdlr)
log.addHandler(filehandler)  # set the new handler
# set the log level to INFO, DEBUG as the default is ERROR
log.setLevel(logging.INFO)

sys.path.append(
    os.path.join(splunkhome, "etc", "apps", "TA-azure-blob-archiving", "lib")
)

# import Splunk libs
from splunklib.searchcommands import (
    dispatch,
    StreamingCommand,
    Configuration,
    Option,
    validators,
)
from splunklib import six
import splunklib.client as client

# log the sys.path for troubleshooting purposes
logging.info('Python sys.path="' + str(sys.path) + '"')

# import Azure librairies
from azure.storage.blob import BlobClient, BlobServiceClient
from azure.cosmosdb.table.tableservice import TableService
from azure.cosmosdb.table.models import Entity


@Configuration()
class AzPurgeBlob(StreamingCommand):
    mode = Option(
        doc="""
        **Syntax:** **mode=****
        **Description:** The run mode of the command, by safety it defaults to simulate, valid options are: simulate|live.""",
        require=True,
        validate=validators.Match("mode", r"^(simulate|live)$"),
    )

    update_table = Option(
        doc="""
        **Syntax:** **update_table=****
        **Description:** Specify if the table entity status field will be updated, requires table fields to be provided, defaults to true""",
        require=True,
        default="true",
        validate=validators.Match("mode", r"^(true|false)$"),
    )

    field_storage_account = Option(
        doc="""
        **Syntax:** **field_storage_account=****
        **Description:** field name containing the value for StorageAccount.""",
        require=True,
    )

    field_blob_name = Option(
        doc="""
        **Syntax:** **field_blob_name=****
        **Description:** field name containing the value for blob_name.""",
        require=True,
    )

    # table information are optional, if all are sets, the command will attempt to alter the entity record in the table

    field_table = Option(
        doc="""
        **Syntax:** **field_table=****
        **Description:** field name containing the value for Table.""",
        require=False,
        default="None",
    )

    field_partitionkey = Option(
        doc="""
        **Syntax:** **field_partitionkey=****
        **Description:** field name containing the value for PartitionKey.""",
        require=False,
        default="None",
    )

    field_row_key = Option(
        doc="""
        **Syntax:** **field_row_key=****
        **Description:** field name containing the value for the value for RowKey.""",
        require=False,
        default="None",
    )

    # status will be statically defined as deleted

    def stream(self, records):
        # set loglevel
        loglevel = "INFO"
        conf_file = "azure2blob_settings"
        confs = self.service.confs[str(conf_file)]
        for stanza in confs:
            if stanza.name == "logging":
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
        entity = splunk.entity.getEntity(
            "/server",
            "settings",
            namespace="TA-azure-blob-archiving",
            sessionKey=session_key,
            owner="-",
        )
        splunkd_port = entity["mgmtHostPort"]

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
        logging.debug('AZ_BLOB_CONTAINER="{}"'.format(str(AZ_BLOB_CONTAINER)))

        # do not proceed of the connection string is not configured yet
        if str(AZ_BLOB_CONNECTION_STRING) == "connection_string_to_the_blob_storage":
            logging.error(
                "The Azure connection string was not configured yet, cannot proceed."
            )
            sys.exit(1)

        # if update_table is set to true, we need values for the table Metadatas
        if self.update_table == "true":
            if (
                not self.field_table
                or not self.field_partitionkey
                or not self.field_row_key
            ):
                logging.error(
                    "update_table is set to true, but the table metadata fields have not been provided"
                )
                sys.exit(1)

        # create the service to the Azure table
        if self.update_table == "true":
            try:
                table_service = TableService(
                    connection_string=AZ_BLOB_CONNECTION_STRING
                )
            except Exception as e:
                logging.error(
                    'Failed to establish the service to the Azure table with exception="{}"'.format(
                        str(e)
                    )
                )

        # empty array to store our processed records
        records_list = []

        # Loop in the results
        records_count = 0
        for splrecord in records:
            # increment
            records_count += 1

            # get fields and values
            StorageAccount = str(splrecord[self.field_storage_account])
            Table = str(splrecord[self.field_table])
            PartitionKey = str(splrecord[self.field_partitionkey])
            RowKey = str(splrecord[self.field_row_key])
            blob_name = str(splrecord[self.field_blob_name])
            status = "deleted"

            # Create the record to be added to our array of processed events
            record = {
                "StorageAccount": str(StorageAccount),
                "Table": str(Table),
                "PartitionKey": str(PartitionKey),
                "RowKey": str(RowKey),
                "blob_name": str(blob_name),
                "status": str(status),
            }

            # logging debug
            logging.debug('downstream record="{}"'.format(json.dumps(record, indent=1)))

            # Append to the records array
            records_list.append(record)

        ################################
        # Export to the table by chunk #
        ################################

        # total number of messages to be processed
        results_count = len(records_list)
        logging.info(
            'record_count="{}" records to be processed into the Azure table'.format(
                str(results_count)
            )
        )

        # to report processed messages
        processed_count = 0

        # to report purged count
        purged_count = 0

        # process by chunk
        chunks = [records_list[i : i + 500] for i in range(0, len(records_list), 500)]
        for chunk in chunks:
            chunk_len = len(chunk)

            for subrecord in chunk:
                # Process to the blob file purge

                # get the blob_file
                subrecord_blob_file = subrecord.get("blob_name")
                subrecord_StorageAccount = subrecord.get("StorageAccount")
                subrecord_Table = subrecord.get("Table")
                subrecord_PartitionKey = subrecord.get("PartitionKey")
                subrecord_RowKey = subrecord.get("RowKey")

                # boolean
                wasPurged = False

                #
                # simulation
                #
                if self.mode == "simulate":
                    logging.info(
                        'Simulation of blob file purge, record="{}"'.format(
                            json.dumps(subrecord, indent=1)
                        )
                    )
                    logging.debug(
                        'blob file to be purged, blob_name="{}"'.format(
                            str(subrecord_blob_file)
                        )
                    )

                #
                # live
                #
                elif self.mode == "live":
                    logging.info(
                        'Attempting to purge the blob file, record="{}"'.format(
                            json.dumps(subrecord, indent=1)
                        )
                    )
                    logging.debug(
                        'blob file to be purged, blob_name="{}"'.format(
                            str(subrecord_blob_file)
                        )
                    )

                    try:
                        # the container name is the PartitionKey
                        blob_service_client = BlobServiceClient.from_connection_string(
                            conn_str=AZ_BLOB_CONNECTION_STRING
                        )
                        container_client = blob_service_client.get_container_client(
                            subrecord_PartitionKey
                        )
                        blob_list = [subrecord_blob_file]
                        container_client.delete_blobs(*blob_list)

                        # increment
                        purged_count += 1

                        # log
                        logging.info(
                            'blob="{}" was successfully purged'.format(
                                str(subrecord_blob_file)
                            )
                        )

                        wasPurged = True

                    except Exception as e:
                        logging.error(
                            'Error while performing the blob file purge with exception="{}"'.format(
                                str(e)
                            )
                        )

                    # if the blob was successfully purged, attempt to update the table
                    if wasPurged and self.update_table == "true":
                        logging.debug(
                            "Attempting to retrieve the record in the Azure table"
                        )
                        try:
                            table_record = table_service.get_entity(
                                subrecord_Table,
                                subrecord_PartitionKey,
                                subrecord_RowKey,
                                timeout=60,
                            )
                            logging.debug(
                                'In table record="{}"'.format(str(table_record))
                            )

                            # Set the new record
                            table_record_update = {
                                "PartitionKey": table_record.get("PartitionKey"),
                                "RowKey": table_record.get("RowKey"),
                                "blob_name": table_record.get("blob_name"),
                                "bucket_id": table_record.get("bucket_id"),
                                "original_bucket_name": table_record.get(
                                    "original_bucket_name"
                                ),
                                "original_peer_name": table_record.get(
                                    "original_peer_name"
                                ),
                                "original_peer_guid": table_record.get(
                                    "original_peer_guid"
                                ),
                                "epoch_start": table_record.get("epoch_start"),
                                "epoch_end": table_record.get("epoch_end"),
                                "size_bytes": table_record.get("size_bytes"),
                                "indexname": table_record.get("indexname"),
                                "clustered_flag": table_record.get("clustered_flag"),
                                "status": "deleted",
                            }

                            # Attempt to update the table record
                            try:
                                table_service.update_entity(
                                    subrecord_Table, table_record_update, timeout=60
                                )
                                logging.debug(
                                    "record in Azure storage table was successfully updated"
                                )
                            except Exception as e:
                                logging.error(
                                    'Error while attempting to update the table record with exception="{}"'.format(
                                        str(e)
                                    )
                                )

                        except Exception as e:
                            logging.error(
                                'Error while retrieving the table record with exception="{}"'.format(
                                    str(e)
                                )
                            )

            # processed count
            processed_count = processed_count + chunk_len

        # final
        raw = {
            "results_count": str(results_count),
            "processed_count": str(processed_count),
            "purged_count": str(purged_count),
            "user": str(user),
        }

        raw_kv_message = (
            'results_count="'
            + str(results_count)
            + '", processed_count="'
            + str(processed_count)
            + '", user="'
            + str(user)
            + '"'
        )
        logging.info(raw_kv_message)
        yield {
            "_time": time.time(),
            "_raw": json.dumps(raw, indent=4),
            "result_count": str(results_count),
            "process_count": str(processed_count),
        }


dispatch(AzPurgeBlob, sys.argv, sys.stdin, sys.stdout, __name__)
