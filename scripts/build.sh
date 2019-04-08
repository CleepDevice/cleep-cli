#!/bin/bash

cd ..
rm -rf dist/
python3 setup.py clean
python3 setup.py sdist bdist_wheel --universal
rm -rf cleepcli.egg-info
rm -rf build
cd -

