#!/bin/bash

# purpose: easy peasy migrate existing local archives to Azure

# Example of usage:
# bash bash /opt/splunk/etc/slave-apps/TA-azure-blob-archiving/bin/shell_tools/AzMigrateLocalArchive.sh --target="/opt/splunk/var/lib/splunk" --frozen_dirname="frozen" --remove=true --splunk_home="/opt/splunk"
#

# set TERM
export TERM=xterm

# life needs some colors
red=" \x1b[31m "
green=" \x1b[32m "
yellow=" \x1b[33m "
blue=" \x1b[34m "
reset=" \x1b[0m "

# show usage
show_usage() {
    echo -e "${blue}\n\nUsage: ${0} --splunk_home=<SPLUNK_HOME variable> --target=<The local file-system path containing the indexes, example: /opt/splunk/var/lib/splunk> --frozen_dirname<The name of the directory containing the frozen buckets within each directory in target, example: frozen> --remove=<when the upload is complete and if the backend returns an exit code 0, remote the bucket from the file-system>\n\n${reset}"
}

# get arguments
while [ "$1" != "" ]; do
    PARAM=$(echo "$1" | awk -F= '{print $1}')
    VALUE=$(echo "$1" | awk -F= '{print $2}')
    case $PARAM in
    -h | --help)
        show_usage
        exit
        ;;
    --splunk_home)
        splunk_home=$VALUE
        export SPLUNK_HOME=$VALUE
        ;;
    --target)
        target=$VALUE
        ;;
    --frozen_dirname)
        frozen_dirname=$VALUE
        ;;
    --remove)
        remove=$VALUE
        ;;
    *)
        echo -e "${red}ERROR:${reset} unknown parameter \"$PARAM\""
        show_usage
        exit 1
        ;;
    esac
    shift
done

# simple argument verification
if [ -z "$splunk_home" ]; then
    echo -e "${red}\nERROR: splunk_home is not set${reset}\n"
    show_usage
    exit 100
fi

# simple argument verification
if [ -z "$target" ]; then
    echo -e "${red}\nERROR: target is not set${reset}\n"
    show_usage
    exit 100
fi

if [ -z "$frozen_dirname" ]; then
    echo -e "${red}\nERROR: frozen_dirname is not set${reset}\n"
    show_usage
    exit 100
fi

if [ -z "$remove" ]; then
    echo -e "${red}\nERROR: remove is not set${reset}\n"
    show_usage
    exit 100
fi

#
# START PROGRAM
#

if [ ! -d "$target" ]; then
    echo -e "${red}\nERROR: the directory target $target does not exist${reset}\n"
    exit 100
fi

case "$remove" in
"true" | "True")
    echo -e "${blue}Buckets will be removed automatically if the upload to Azure was successful.${reset}"
    remove_bool=1
    ;;
"false" | "False")
    echo -e "${blue}Buckets will be not be removed automatically after the upload, whatever the status is.${reset}"
    remove_bool=0
    ;;
*)
    echo -e "${red}\nERROR: remove argument is invalid${reset}\n"
    show_usage
    exit 100
    ;;
esac

PWD=$(pwd)

cd "$target"
echo ""
echo -e "${yellow}Azure to blob local archiving program start${reset}"
echo ""

cd "$target"

# loop through the indexes
for indexdir in $(ls -d *); do

    if [ -d "${indexdir}" ]; then

        echo -e "${blue}Processing index=${indexdir} ${reset}"

        if [ -d $indexdir/$frozen_dirname ]; then
            cd $indexdir/$frozen_dirname

            find . -maxdepth 1 -mindepth 1 -name "db_*" -type d -printf '%f\n' | while read bucket; do

                if [ -d ${bucket} ] && [ -d ${bucket}/rawdata ]; then

                    bucket_fullpath="${target}/${indexdir}/$frozen_dirname/${bucket}"

                    echo -e "${blue}Processing bucket=${bucket_fullpath} ${reset}"
                    "$SPLUNK_HOME/etc/slave-apps/TA-azure-blob-archiving/bin/AzFrozen2Blob.sh" "${bucket_fullpath}"
                    if [ $? -eq 0 ]; then
                        if [ $remove_bool -eq 1 ]; then
                            echo -e "${green}bucket=${bucket} was successfully archived to Azure, removing the bucket from the file-system${reset}"
                            rm -rf "${bucket}"
                        else
                            echo -e "${green}bucket=${bucket} was successfully archived to Azure, it has not been removed from the file-system as per your request${reset}"
                        fi
                    else
                        echo -e "${red}bucket=${bucket} failure to achive to Azure, consult the logs for more information${reset}"
                    fi

                fi

            done

            find . -maxdepth 1 -mindepth 1 -name "rb_*" -type d -printf '%f\n' | while read bucket; do

                if [ -d ${bucket} ] && [ -d ${bucket}/rawdata ]; then

                    bucket_fullpath="${target}/${indexdir}/$frozen_dirname/${bucket}"

                    echo -e "${blue}Processing bucket=${bucket_fullpath} ${reset}"
                    "$SPLUNK_HOME/etc/slave-apps/TA-azure-blob-archiving/bin/AzFrozen2Blob.sh" "${bucket_fullpath}"
                    if [ $? -eq 0 ]; then
                        if [ $remove_bool -eq 1 ]; then
                            echo -e "${green}bucket=${bucket} was successfully archived to Azure, removing the bucket from the file-system${reset}"
                            rm -rf "${bucket}"
                        else
                            echo -e "${green}bucket=${bucket} was successfully archived to Azure, it has not been removed from the file-system as per your request${reset}"
                        fi
                    else
                        echo -e "${red}bucket=${bucket} failure to achive to Azure, consult the logs for more information${reset}"
                    fi

                fi

            done

            # go back
            cd "$target"

        fi

    fi

done

cd $PWD
echo ""
echo -e "${yellow}Azure to blob local archiving program end${reset}"
echo ""
exit 0
