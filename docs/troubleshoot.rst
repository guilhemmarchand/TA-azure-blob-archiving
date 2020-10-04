Troubleshoot
============

Manually testing archiving a bucket
-----------------------------------

**You can test manually archiving a bucket to Azure blob the following way:**

- Connect to an indexer via SSH
- Open a session as the user name owning the Splunk processes
- Identify a cold bucket you want to test for the archiving
- Use the following command to manually archive a bucket:

::

    sudo su - Splunk
    cd /opt/splunk/etc/slave-apps/TA-azure-blob-archiving/bin

*Then, make sure to export the SPLUNK_HOME variable:*

::

    export SPLUNK_HOME="/opt/splunk"

*Finally, run the Python script targetting the cold bucket path:*

::

    python3 AzFrozen2Blob.py /opt/splunk/var/lib/splunk/network/colddb/db_1601751202_1601751090_88

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

