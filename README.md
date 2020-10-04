# Cold to Frozen framework for Splunk to archive buckets in Azure blob storage

| branch | build status |
| ---    | ---          |
| master | [![master status](https://circleci.com/gh/guilhemmarchand/TA-azure-blob-archiving/tree/master.svg?style=svg)](https://circleci.com/gh/guilhemmarchand/TA-azure-blob-archiving/tree/master)

## Introduction

**This Add-on provides a robust and smart archiving framefork solution for Splunk Enterprise and Azure blob storage.**

It relies on the Splunk built-in archiving capabilities and Azure blob storage and tables via the usage of the Python SDK for Azure:

*Splunk Documentation links:*

- https://docs.splunk.com/Documentation/Splunk/latest/Indexer/Automatearchiving
- https://docs.splunk.com/Documentation/Splunk/latest/Indexer/Setaretirementandarchivingpolicy

*Azure links:*

- https://azure.github.io/azure-sdk/releases/latest/python.html
- https://docs.microsoft.com/en-us/python/api/?view=azure-python
- https://docs.microsoft.com/en-us/azure/storage/blobs/storage-quickstart-blobs-portal

**The framework and concept can be summarised the following way:**

- Splunk automatically calls the AzFrozen2Blob.py Python script when a bucket is frozen from cold storage (assuming archiving is enabled on the index)
- The Python script accesses an Azure storage account and verifies in a pre-defined Azure storage table if that bucket ID has been archived already (management of buckets replication for Splunk indexers in cluster)
- If the bucket has not been archived yet, a tgz archive of the bucket is created and uploaded to the pre-defined container in Azure blob
- If the upload to blob is successful, the Python script inserts a new record in the Azure storage table with all the useful information related to this bucket
- If the upload is successful, the script exists with an error code=0 which instructs Splunk that the bucket can be frozen, otherwise the script exit=1 and a new attempt will be made automatically by Splunk

**Analytic, management and reporting:**

Use the Splunk Add-on for Microsoft Cloud Services to monitor and index automatically records created in the Azure storage table:

- https://splunkbase.splunk.com/app/3110/
- https://docs.splunk.com/Documentation/AddOns/released/MSCloudServices/Configureinputs4

This application provides a dashboard and logic based on a KVstore collection that is automatically feed by the records indexed, which allows you to the power of Splunk language to review buckets that were achived, search for any information based on the rich information stored in the Azure table, or provide analytic reporting.

![screenshot1](./docs/img/az_screen.png)

![screenshot2](./docs/img/az_screen2.png)

![screenshot3](./docs/img/splunk_ui_main.png)

![screenshot4](./docs/img/splunk_ui_main2.png)


**See the documentation on readthedocs.org:**

https://ta-azure-blob-archiving.readthedocs.io/en/latest/