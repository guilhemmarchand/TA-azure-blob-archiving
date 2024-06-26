Deployment
##########

Deployment matrix
=================

+----------------------+---------------------+
| Splunk roles         | required            |
+======================+=====================+
| Search head          |   yes*              |
+----------------------+---------------------+
| Indexer tiers        |   Yes               |
+----------------------+---------------------+

*Search Head deployment is only required if you intend to use the front-end part of the application*

If Splunk search heads are running in Search Head Cluster (SHC), the Splunk application must be deployed by the SHC deployer.

For Splunk indexers in cluster, the Splunk application must be deployed via the Splunk Cluster Master.

Dependencies
============

Search Head(s)
--------------

**The front-end part of the application essentially relies on indexing the content of the Azure storage tables via the Splunk Add-on for Microsoft Cloud Services:**

- https://splunkbase.splunk.com/app/3110/
- https://docs.splunk.com/Documentation/AddOns/released/MSCloudServices/Configureinputs4

Search head(s) do not have direct interractions with Azure storage blob or tables, and do not need to satisfy any additional dependencies.

In a distributed deployment content, you would most likely deploy the Splunk Add-on for Microsoft Services on a heavy forwarder layer that you use for data collection purposes.

**There are also some interactions with the cosmosdb which require Azure SDK for Python, it needs to be installed on the Search Head(s) and within Splunk environment:**

::

    sudo su - splunk
    /opt/splunk/bin/splunk cmd python -m pip install azure-storage-blob
    /opt/splunk/bin/splunk cmd python -m pip install azure-cosmosdb-table

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

    sudo pip3 install azure-storage-blob
    sudo pip3 install azure-cosmosdb-table

Depending on the context, you may prefer to run the pip module installation only for the user that owns the Splunk processes:

::

    sudo su - splunk
    pip3 install azure-storage-blob
    pip3 install azure-cosmosdb-table

*In some systens, you may need to install the modules with root permissions, see the first option.*

*You may as well install manually the Python modules instead of using pip if you cannot use it (but pip is strongly recommended), follow the PYpi links, download the packages, and run the installer as the splunk user.*

**Once you installed the Azure SDKs, you can very easily verify that the modules can be imported successfully:**

- Open a Python3 interpreter
- Verify that you can import the Azure SDK modules:

``from azure.storage.blob import BlobClient, BlobServiceClient``

``from azure.cosmosdb.table.tableservice import TableService``

**See bellow:**

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

Do not continue if you are failing to import any of the two modules, until you fix the issue.

Initial deployment
==================

**The deployment of the Splunk application follows the usual process:**

- By using the application manager in Splunk Web (Settings / Manages apps) for standalone instances

- Or by extracting the content of the tgz archive in the "apps" directory of Splunk

- For SHC configurations (Search Head Cluster), extract the tgz content in the SHC deployer and publish the SHC bundle

- For indexer in cluster deployment, extract the tgz content in the cluster master in manager-apps and pubish the cluster bundle

Upgrades
========

Upgrading the Splunk application is the same operation than the initial deployment, extracting from a new release tgz will override any component that is built-in into the application.
