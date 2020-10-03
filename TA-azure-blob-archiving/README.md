# Cold to Frozen framework for Splunk to archive buckets in Azure blob storage

## Dependencies

pip install azure-storage-blob
pip install azure-cosmosdb-table

See:
https://pypi.org/project/azure-cosmosdb-table/

## Howto:

1. Create a storage account in Azure if you do not have one yet

2. Collect the required information, you need to know the Azure blob connection URL and the connection string

2. Create a local directory in the application root directory

5. Copy the default/azure2blob.conf to local/

6. Edit local/azure2blob.conf and configure

7. Copy or move your package to the cluster master ($SPLUNK_HOME/etc/master-apps) and publish the cluster-bundle

8. Finally edit your indexes.conf to enable the cold2frozen framework, example:

[firewall_emea]
coldToFrozenScript = "/usr/bin/python3" "$SPLUNK_HOME/etc/slave-apps/TA-azure-blob-cold2frozen/bin/AzFrozen2Blob.py"
python.version = python3
