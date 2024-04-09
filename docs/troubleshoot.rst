Troubleshoot
============

Manually testing archiving a bucket
-----------------------------------

**You can test manually archiving a bucket to Azure blob the following way:**

- Connect to an indexer via SSH
- Open a session as the user name owning the Splunk processes
- Identify a cold bucket you want to test for the archiving
- Use the following command to manually archive a bucket: (note: unless you manually set SPLUNK_HOME, to run an archiving manually you need to use the shell wrapper)

::

    sudo su - Splunk
    /opt/splunk/bin/splunk cmd /opt/splunk/etc/peer-apps/TA-azure-blob-archiving/bin/AzFrozen2Blob.sh /opt/splunk/var/lib/splunk/network/colddb/db_1601751202_1601751090_88

*Example of results:*

::

    bucket is /opt/splunk/var/lib/splunk/network/colddb/db_1601751202_1601751090_88
    idx_struct is <re.Match object; span=(0, 69), match='/opt/splunk/var/lib/splunk/network/colddb/db_1601>
    indexname is network
    is it gz? True
    is it zst? False
    Archiving bucket: /opt/splunk/var/lib/splunk/network/colddb/db_1601751202_1601751090_88
    /opt/splunk/var/lib/splunk/network/colddb/db_1601751202_1601751090_88/Strings.data
    /opt/splunk/var/lib/splunk/network/colddb/db_1601751202_1601751090_88/bloomfilter
    /opt/splunk/var/lib/splunk/network/colddb/db_1601751202_1601751090_88/Sources.data
    /opt/splunk/var/lib/splunk/network/colddb/db_1601751202_1601751090_88/optimize.result
    /opt/splunk/var/lib/splunk/network/colddb/db_1601751202_1601751090_88/bucket_info.csv
    /opt/splunk/var/lib/splunk/network/colddb/db_1601751202_1601751090_88/SourceTypes.data
    /opt/splunk/var/lib/splunk/network/colddb/db_1601751202_1601751090_88/.rawSize
    /opt/splunk/var/lib/splunk/network/colddb/db_1601751202_1601751090_88/1601751202-1601751090-14340990455171772002.tsidx
    /opt/splunk/var/lib/splunk/network/colddb/db_1601751202_1601751090_88/Hosts.data
    peer_name is ip-10-0-0-75
    bucket_name is db_1601751202_1601751090_88
    bucket_epoch_start is 1601751090
    bucket_epoch_end is 1601751202
    bucket_id_list is ['88']
    # This means it's a non replicated bucket, so need to grab the GUID from instance.cfg
    original_peer_guid is 9C5BADFD-7FB3-4142-A3E6-548F9C0316C1
    bucket_id is network_9C5BADFD-7FB3-4142-A3E6-548F9C0316C1_88
    This bucket has not been archived yet, proceed to archiving now
    the peer name is ip-10-0-0-75
    Archive upload to Azure blob storage successful for bucket /opt/splunk/var/lib/splunk/network/colddb/db_1601751202_1601751090_88

Any error will be clearly exposed in the output of the script.

If the archive operation is successful, the bucket tgz will be visible in the Azure portal, and a new record will have been created in the Azure table.

Investigating BuckerMover logs
------------------------------

**Splunk traces the BucketMover logs in the _internal, as follows:**

::

    index=_internal sourcetype=splunkd BucketMover

**Successful archiving appears as:**

::

    10-04-2020 13:38:41.653 +0000 INFO  BucketMover - will attempt to freeze bkt="/opt/splunk/var/lib/splunk/linux_amer/colddb/db_1601744221_1601743940_85" reason=" maxTotalDataSize=104857600 bytes, diskSize=104902656 bytes"
    10-04-2020 13:38:47.248 +0000 INFO  BucketMover - AsyncFreezer freeze succeeded for bkt='/opt/splunk/var/lib/splunk/linux_amer/colddb/db_1601744221_1601743940_85'

**If there are any failures from the Python backend, Splunk will log every trace from stderr, example:**

*Splunk search*

::

    index=_internal sourcetype=splunkd bucketmover error

*Example of failure main message*

::

    10-04-2020 13:18:55.260 +0000 ERROR BucketMover - coldToFrozenScript cmd='"/opt/splunk_72/splunk/etc/apps/TA-azure-blob-archiving/bin/AzFrozen2Blob.sh" /opt/splunk_72/splunk/var/lib/splunk/network/colddb/db_1601796404_1601795154_4' exited with non-zero status='exited with code 1'

*For example if you attempt to run directly the Python backend on Splunk prior to Splunk 8.0, the following message would be visible:*

::

    10-04-2020 13:18:55.257 +0000 ERROR BucketMover - coldToFrozenScript ImportError: This package should not be accessible on Python 3. Either you are trying to run from the python-future src folder or your installation of python-future is corrupted.

The front-end part of the application provides buit-in dashboards and reports for this purpose.