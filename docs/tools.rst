Tools
=====

**Additional command line tools are provided:**

List blobs from containers
--------------------------

**You can use the builtin Python script AzListBlob.py to list all blobs available in a container, run this command from any of the indexers:**

``AzListBlob.py``

::

    sudo su - splunk
    cd /opt/splunk/etc/slaves-apps/TA-azure-blob-archiving/bin
    export SPLUNK_HOME="/opt/splunk"
    python3 AzListBlob.py

*usage is returned:*

::

    usage: python3 AzListBlob.py <container_name>

*Example of usage:*

::

    python3 AzListBlob.py splunk-local-lab-archives

    #### Listing blobs... ####

    linux_emea/linux_emea_F3AFBA7F-A0A7-4A91-97D0-753F5828B8BE_12.tgz
    linux_emea/linux_emea_F3AFBA7F-A0A7-4A91-97D0-753F5828B8BE_15.tgz
    ...

Download blobs from containers (restore buckets)
------------------------------------------------

**You can use the builtin Python script AzDownloadBlob.py to retrieve and download a blob file from a container, which means retrieving the tgz archive of a bucket that was previously archived:**

``AzDownloadBlob.py``

::

    sudo su - splunk
    cd /opt/splunk/etc/slaves-apps/TA-azure-blob-archiving/bin
    export SPLUNK_HOME="/opt/splunk"
    python3 AzDownloadBlob.py

*usage is returned:*

::

    usage: python3 AzDownloadBlob.oy <container_name> <blob_name> <target_file>

*Example of usage:*

::

    python3 AzDownloadBlob.py splunk-local-lab-archives linux_emea/linux_emea_F3AFBA7F-A0A7-4A91-97D0-753F5828B8BE_12.tgz /tmp/linux_emea_F3AFBA7F-A0A7-4A91-97D0-753F5828B8BE_12.tgz
    container is splunk-local-lab-archives
    blob_name is linux_emea/linux_emea_F3AFBA7F-A0A7-4A91-97D0-753F5828B8BE_12.tgz
    target_file is /tmp/linux_emea_F3AFBA7F-A0A7-4A91-97D0-753F5828B8BE_12.tgz

    Downloading blob to 
            /tmp/linux_emea_F3AFBA7F-A0A7-4A91-97D0-753F5828B8BE_12.tgz

**Once you have downloaded the blob, you can proceed to the extraction of the bucket in the thaweddb to restore the required data:**

- https://docs.splunk.com/Documentation/Splunk/latest/Indexer/Restorearchiveddata
