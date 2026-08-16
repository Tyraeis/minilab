#!/bin/bash
set -eu

namespace=$1
pvc=$2
pod=pvc-inspector-$pvc

kubectl apply -f - <<EOF
apiVersion: v1
kind: Pod
metadata:
  name: $pod
  namespace: $namespace
spec:
  containers:
  - image: busybox
    name: pvc-inspector
    command: ["tail"]
    args: ["-f", "/dev/null"]
    volumeMounts:
    - mountPath: /pvc
      name: pvc-mount
  volumes:
  - name: pvc-mount
    persistentVolumeClaim:
      claimName: $pvc
EOF
kubectl wait --for=condition=Ready pod/$pod --timeout=-1s
kubectl exec -it -n $namespace $pod -- sh
kubectl delete pod -n $namespace $pod
