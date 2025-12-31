#!/bin/bash

kubectl exec -it -n garage garage-0 -- ./garage $@
