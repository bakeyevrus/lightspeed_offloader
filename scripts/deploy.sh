#!/bin/bash

if [ -z "$1" ]
  then
    echo "Please, provide an absoulte path to the application as an argument!"
    exit 1
fi

if ! command -v python3 &>/dev/null; then
  echo "ERROR: Python 3 is not isntalled for the current system"
  exit 1
fi


if ! command python3 -m pip --version &>/dev/null; then
  echo "ERROR: pip is not installed for the current system"
  exit 1
fi

echo "Installing app dependencies..."
python3 -m pip install -r ../requirements.txt
if [ $? -ne 0 ]; then
  echo "ERROR: Failed to install app dependencies"
  exit 1
fi

echo "Creating logs directory..."
mkdir ../logs &>/dev/null

echo "Checking crontab service installed..."
service cron status &>/dev/null
if [ $? -ne 0 ]; then
  echo "ERROR: Crontab service either doesn't exist or isn't running"
  exit 1
fi

PY_PATH=`which python3`
CRONTAB_FILE=crontab.tmp
echo "Creating crontab..."
echo "0 8,10,12,14,16,18,20 * * * cd $1 && $PY_PATH -m lightspeed_offloader -c config/application.yaml -l config/logging.yaml >> logs/stacktrace.log 2>&1" >> ${CRONTAB_FILE}
echo "5 8,10,12,14,16,18,20 * * * cd $1 && $PY_PATH -m status_checker -c config/application.yaml -l config/logging.yaml >> logs/stacktrace.log 2>&1" >> ${CRONTAB_FILE}
crontab ${CRONTAB_FILE}
if [ $? -ne 0 ]
then
  echo "ERROR: Cannot install crontab file"
  exit 1
else
  echo "Crontab has been successfully installed!"
fi

rm ${CRONTAB_FILE}