#!/bin/bash

# Fixed download URL for the console
fixed_console_url="https://present-files-1317479375.cos.ap-guangzhou.myqcloud.com/console.tar.gz"
package_name="console.tar.gz"

LOG_WARN()
{
    local content=${1}
    echo -e "\033[31m[WARN] ${content}\033[0m"
}

LOG_INFO()
{
    local content=${1}
    echo -e "\033[32m[INFO] ${content}\033[0m"
}

help() {
    echo "
Usage:
    -h Help
e.g
    $0
"
exit 0
}

parse_params(){
    # Only keep -h flag for help, remove all versioning flags
    while getopts "h" option;do
        case $option in
        h) help;;
        *) help;;
        esac
    done
}

download_console(){
    LOG_INFO "Downloading console from ${fixed_console_url}"
    # Directly download from the fixed URL
    curl -#LO "${fixed_console_url}"
    
    if [ $? -eq 0 ];then
        LOG_INFO "Download console successfully"
    else
        LOG_WARN "Download console failed, please switch to better network and try again!"
        exit 1 # Exit on download failure
    fi
    
    # Extract and make scripts executable
    tar -zxf ${package_name} && chmod +x console*/*.sh
    if [ $? -eq 0 ];then
        LOG_INFO "Unzip console successfully"
    else
        LOG_WARN "Unzip console failed, please try again!"
        exit 1 # Exit on extraction failure
    fi 
}

# Parse command line arguments
parse_params "$@"

# Since we only download the console, call download_console directly
download_console
