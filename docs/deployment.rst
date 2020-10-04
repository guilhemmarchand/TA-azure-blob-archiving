Deployment
##########

Deployment matrix
=================

+----------------------+---------------------+
| Splunk roles         | required            |
+======================+=====================+
| Search head          |   yes               |
+----------------------+---------------------+
| Indexer tiers        |   Yes               |
+----------------------+---------------------+

If Splunk search heads are running in Search Head Cluster (SHC), the Splunk application must be deployed by the SHC deployer.

For Splunk indexers in cluster, the Splunk application must be deployed via the Splunk Cluster Master.

Dependencies
============

Search Head(s)
--------------

**The front-end part of the application relies on indexing the content of the Azure storage tables via the Splunk Add-on for Microsoft Cloud Services:**

- https://splunkbase.splunk.com/app/3110/
- https://docs.splunk.com/Documentation/AddOns/released/MSCloudServices/Configureinputs4

Search head(s) do not have direct interractions with Azure storage blob or tables, and do not need to satisfy any additional dependencies.

Indexer(s)
----------

**Azure blob storage archiving and table interractions happen on the indexer level, each indexer needs to have the following dependencies satisfied:**

- A Python 3 interpreter must be available on the Operating Systen level (Out of Splunk space, the Add-on does not use the embedded Python interpreter that comes with Splunk)
- Azure SDK for Python must be deployed and available to the user name owning the Splunk processed (usually named splunk)

Azure SDK for Python
^^^^^^^^^^^^^^^^^^^^

**There are two SDKs used by the Addon:**

- https://pypi.org/project/azure-storage-blob/
- https://pypi.org/project/azure-cosmosdb-table/

**You can install the SDKs via pip:**

::
    sudo su - splunk
    pip3 install azure-storage-blob
    pip3 install azure-cosmosdb-table

**Once you installed the Azure SDKs, you can very easily verify that the modules can be imported successfully:**

*Connect to an indexer via SSH:*

::

    ubuntu@mylab:~$ sudo su - splunk
    splunk@mylab:~$ which python3
    /usr/bin/python3
    splunk@mylab:~$ python3
    Python 3.8.2 (default, Jul 16 2020, 14:00:26)
    [GCC 9.3.0] on linux
    Type "help", "copyright", "credits" or "license" for more information.
    >>> from azure.storage.blob import BlobClient, BlobServiceClient
    >>> from azure.cosmosdb.table.tableservice import TableService    
    >>>

If the import is successful as the example above, the dependencies are statisfied successfully.

Initial deployment
==================

**The deployment of the Splunk application follows the usual process:**

- By using the application manager in Splunk Web (Settings / Manages apps) for standalone instances

- Or by extracting the content of the tgz archive in the "apps" directory of Splunk

- For SHC configurations (Search Head Cluster), extract the tgz content in the SHC deployer and publish the SHC bundle

- For indexer in cluster deployment, extract the tgz content in the cluster master in master-apps and pubish the cluster bundle

Upgrades
========

Upgrading the Splunk application is the same operation than the initial deployment, extracting from a new release tgz will override any component that is built-in into the application.
