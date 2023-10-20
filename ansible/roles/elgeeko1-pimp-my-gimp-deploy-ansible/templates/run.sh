#!/bin/bash

echo PWD=$PWD 

source {{ gimp_path }}/venv/bin/activate
sudo -E env PATH=$PATH python -u {{ gimp_path }}/pimp-my-gimp.py
