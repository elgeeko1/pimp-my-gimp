#!/bin/bash

echo PWD=$PWD 

source {{ gimp_path }}/venv/bin/activate
sudo -E env PATH=$PATH python {{ gimp_path }}/pimp-my-gimp.py
