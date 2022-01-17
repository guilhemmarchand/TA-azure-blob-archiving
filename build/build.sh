#!/usr/bin/env bash
# set -x

# for Mac OS X
export COPYFILE_DISABLE=true

PWD=$(pwd)
OUTPUT="../output"
app="TA-azure-blob-archiving"
version=$(grep 'version =' ../$app/default/app.conf | head -1 | awk '{print $3}' | sed 's/\.//g')

rm -f *.tgz ${app}
cp -a ../${app} .
tar -czf ../output/${app}_${version}.tgz --exclude=${app}/local --exclude=${app}/metadata/local.meta ${app}
echo "Wrote: ${app}_${version}.tgz"

exit 0
