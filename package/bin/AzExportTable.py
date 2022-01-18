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

@Configuration()
class AzExportToTable(StreamingCommand):

    table_target = Option(
        doc='''
        **Syntax:** **table_target=****
        **Description:** The name of the Azure Storage table target.''',
        require=True)

    field_partitionkey = Option(
        doc='''
        **Syntax:** **field_partitionkey=****
        **Description:** field name containing the value for the partition key.''',
        require=True)

    field_blob_name = Option(
        doc='''
        **Syntax:** **field_blob_name=****
        **Description:** field name containing the value for the blob_name.''',
        require=True)

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
        # table name is argument driven

        # get
        for stanza in confs:
            if stanza.name == "azure2blob":
                for stanzakey, stanzavalue in stanza.content.items():
                    if stanzakey == "AZ_BLOB_CONTAINER":
                        AZ_BLOB_CONTAINER = stanzavalue
                    if stanzakey == "AZ_BLOB_CONNECTION_STRING":
                        AZ_BLOB_CONNECTION_STRING = stanzavalue








        # empty array to store our processed records
        records_list = []

        # Loop in the results
        records_count = 0
        for splrecord in records:

            # increment
            records_count +=1

            # get fields and values
            partitionkey = str(splrecord[self.field_partitionkey])
            blob_name = str(splrecord[self.field_blob_name])

            # Create the record to be added to our array of processed events
            record = {
                        "partitionkey": str(partitionkey),
                        "blob_name": str(blob_name),
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

        # to report processed messages
        processed_count = 0

        # process by chunk
        chunks = [records_list[i:i + 500] for i in range(0, len(records_list), 500)]
        for chunk in chunks:

            chunk_len = len(chunk)

            # TBD

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
        yield {'_time': time.time(), '_raw': json.dumps(raw, indent=4), 'result_count': str(results_count), 'process_count': str(processed_count)}

dispatch(AzExportToTable, sys.argv, sys.stdin, sys.stdout, __name__)
