# Instructions

The Azure SDK libs are retrieved automatically by ucc-gen via the requirements:

```
azure-core>=1.21.1
azure-storage-blob>=12.9.0
azure-common>=1.1.27
azure-nspkg>=3.0.2
azure-cosmosdb-nspkg>=2.0.2
azure-cosmosdb-table>=1.0.6
```

Some librairies are required for the advanced part of the integration, these libs need to be complied for the running OS and the right version of Python.
At the time of this writting, Splunk is running Py 3.7

https://pypi.org/project/cffi
https://pypi.org/project/cryptography
