#!/usr/bin/env python

from __future__ import absolute_import, division, print_function, unicode_literals

import os
import sys
from textwrap import indent
import splunk
import splunk.entity
import time
import re
import json
import socket
import requests
from requests.auth import HTTPBasicAuth
import logging
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

splunkhome = os.environ["SPLUNK_HOME"]

# set logging
filehandler = logging.FileHandler(
    splunkhome + "/var/log/splunk/azure2blob_azrestorebatch.log", "a"
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


@Configuration()
class AzRestoreBatch(StreamingCommand):
    splunk_rebuild = Option(
        doc="""
        **Syntax:** **splunk_rebuild=****
        **Description:** Run the Splunk rebuild upon restoration of the bucket.""",
        require=False,
        default=True,
        validate=validators.Match("dedup", r"^(True|False)$"),
    )

    chunk_size = Option(
        doc="""
        **Syntax:** **chunk_size=****
        **Description:** Specify the number of buckets to be concurrently restored, defaults to 10.""",
        require=False,
        default=10,
        validate=validators.Match("dedup", r"^\d*$"),
    )

    field_blob_name = Option(
        doc="""
        **Syntax:** **field_blob_name=****
        **Description:** field name containing the value for blob_name.""",
        require=True,
    )

    field_target_directory = Option(
        doc="""
        **Syntax:** **field_blob_name=****
        **Description:** field name containing the value for target_directory.""",
        require=True,
    )

    field_target_peer = Option(
        doc="""
        **Syntax:** **field_target_peer=****
        **Description:** field name containing the value for target_peer.""",
        require=True,
    )

    # status will be statically defined as imported

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
        remote_username = None
        remote_password = None
        for stanza in confs:
            if stanza.name == "azure2blob":
                for stanzakey, stanzavalue in stanza.content.items():
                    if stanzakey == "remote_username":
                        remote_username = stanzavalue

        credential_realm = "__REST_CREDENTIAL__#TA-azure-blob-archiving#configs/conf-azure2blob_settings"
        remote_password_rawvalue = ""

        for credential in storage_passwords:
            if credential.content.get("realm") == str(credential_realm):
                remote_password_rawvalue = remote_password_rawvalue + str(
                    credential.content.clear_password
                )

        # extract a clean json object
        remote_password_rawvalue_match = re.search(
            '\{"remote_password":\s*"(.*)"\}', remote_password_rawvalue
        )
        if remote_password_rawvalue_match:
            remote_password = remote_password_rawvalue_match.group(1)
        else:
            remote_password = None

        # host_local
        host_local = socket.gethostname()

        # empty array to store our processed records
        records_list = []

        # Loop in the results
        records_count = 0
        for splrecord in records:
            # increment
            records_count += 1

            # get fields and values
            blob_name = str(splrecord[self.field_blob_name])
            target_directory = str(splrecord[self.field_target_directory])
            target_peer = str(splrecord[self.field_target_peer])

            # Create the record to be added to our array of processed events
            record = {
                "splunk_rebuild": str(self.splunk_rebuild),
                "blob_name": str(blob_name),
                "target_directory": str(target_directory),
                "target_peer": str(target_peer),
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
            'Number of buckets to restored, buckets_count="{}"'.format(
                str(results_count)
            )
        )

        # to report processed messages
        processed_count = 0
        successes_count = 0
        failures_count = 0

        # process by chunk
        chunks = [
            records_list[i : i + int(self.chunk_size)]
            for i in range(0, len(records_list), int(self.chunk_size))
        ]
        for chunk in chunks:
            chunk_len = len(chunk)

            for subrecord in chunk:
                # Request the restore endpoint
                try:
                    logging.debug(
                        'Processing to restore request="{}"'.format(
                            str(json.dumps(subrecord, indent=1))
                        )
                    )

                    # Define if the request will be local or remote
                    remote_request = False

                    # Get the specified target peer
                    subrecord_target_peer = subrecord.get("target_peer")

                    # handle
                    if str(subrecord_target_peer) != str(host_local):
                        logging.debug(
                            'Target peer="{}" differs from the local host="{}" assuming remote restore requested'.format(
                                str(subrecord_target_peer), str(host_local)
                            )
                        )
                        remote_request = True
                    else:
                        logging.debug(
                            "Target peer is local host, restore will be attempted locally"
                        )

                    # Perform the restore request
                    if remote_request:
                        endpointUrl = (
                            "https://"
                            + str(subrecord_target_peer)
                            + ":"
                            + str(splunkd_port)
                            + "/services/ta_azure_blob_archiving/v1/restore"
                        )
                        headers = {
                            "Authorization": "Splunk %s" % session_key,
                            "Content-Type": "application/json",
                        }
                        request_data = {
                            "splunk_rebuild": subrecord.get("splunk_rebuild"),
                            "blob_name": subrecord.get("blob_name"),
                            "target_directory": subrecord.get("target_directory"),
                        }
                        logging.debug(
                            'request_data="{}"'.format(
                                json.dumps(request_data, indent=1)
                            )
                        )
                        response = requests.post(
                            endpointUrl,
                            auth=HTTPBasicAuth(remote_username, remote_password),
                            data=json.dumps(request_data, indent=1),
                            verify=False,
                        )
                        if response.status_code not in (200, 201, 204):
                            logging.error(
                                "Restore operation has failed!. url={}, data={}, HTTP Error={}, "
                                "content={}".format(
                                    endpointUrl,
                                    record,
                                    response.status_code,
                                    response.text,
                                )
                            )
                            failures_count += 1
                        else:
                            logging.info(
                                "Restore operation was successful. url={}, data={}, HTTP Error={}, "
                                "content={}".format(
                                    endpointUrl,
                                    record,
                                    response.status_code,
                                    response.text,
                                )
                            )
                            successes_count += 1

                    else:
                        endpointUrl = (
                            "https://localhost:"
                            + str(splunkd_port)
                            + "/services/ta_azure_blob_archiving/v1/restore"
                        )
                        headers = {
                            "Authorization": "Splunk %s" % session_key,
                            "Content-Type": "application/json",
                        }
                        request_data = {
                            "splunk_rebuild": subrecord.get("splunk_rebuild"),
                            "blob_name": subrecord.get("blob_name"),
                            "target_directory": subrecord.get("target_directory"),
                        }
                        logging.debug(
                            'request_data="{}"'.format(
                                json.dumps(request_data, indent=1)
                            )
                        )
                        response = requests.post(
                            endpointUrl,
                            headers=headers,
                            data=json.dumps(request_data, indent=1),
                            verify=False,
                        )
                        if response.status_code not in (200, 201, 204):
                            logging.error(
                                "Restore operation has failed!. url={}, data={}, HTTP Error={}, "
                                "content={}".format(
                                    endpointUrl,
                                    record,
                                    response.status_code,
                                    response.text,
                                )
                            )
                            failures_count += 1
                        else:
                            logging.info(
                                "Restore operation was successful. url={}, data={}, HTTP Error={}, "
                                "content={}".format(
                                    endpointUrl,
                                    record,
                                    response.status_code,
                                    response.text,
                                )
                            )
                            successes_count += 1

                except Exception as e:
                    logging.error(
                        'Error while processing restore request with exception="{}"'.format(
                            str(e)
                        )
                    )
                    sys.exit(1)

            # processed count
            processed_count = processed_count + chunk_len

        # final
        raw = {
            "results_count": str(results_count),
            "processed_count": str(processed_count),
            "successes_count": str(successes_count),
            "failures_count": str(failures_count),
            "user": str(user),
        }

        raw_kv_message = (
            'results_count="'
            + str(results_count)
            + '", processed_count="'
            + str(processed_count)
            + '", successes_count="'
            + str(successes_count)
            + '", failures_count="'
            + str(failures_count)
            + '", user="'
            + str(user)
            + '"'
        )
        logging.info(raw_kv_message)
        yield {"_time": time.time(), "_raw": json.dumps(raw, indent=4)}


dispatch(AzRestoreBatch, sys.argv, sys.stdin, sys.stdout, __name__)
