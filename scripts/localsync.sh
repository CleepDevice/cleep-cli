#!/bin/bash

CCLI_INSTALL_DIR=`pip show cleepcli | grep Location | awk -F ": " '{ print($2) }'`
CLEEPCLI_BIN_PATH=`which cleep-cli`
CCLI_BIN_PATH=`which ccli`
if [ -d "cleepcli" ]; then
    SOURCES=cleepcli
    BIN=bin
else
    SOURCES=../cleepcli
    BIN=../bin
fi
echo $SOURCES

echo "Syncing sources..."
echo cp -af $SOURCES"/*.py" $CCLI_INSTALL_DIR"/cleepcli/"
ls -la $SOURCES/*.py
cp -af $SOURCES/*.py $CCLI_INSTALL_DIR/cleepcli/
echo "Syncing binaries..."
cp -a $BIN"/cleep-cli" $CLEEPCLI_BIN_PATH
cp -a $BIN"/cleep-cli" $CCLI_BIN_PATH
echo "Done"
