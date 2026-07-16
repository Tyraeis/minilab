#!/bin/bash
kubeseal -f secrets/headplane-cookie-secret.yaml -w templates/secrets/headplane-cookie-secret.yaml
kubeseal -f secrets/headplane-oidc-secret.yaml -w templates/secrets/headplane-oidc-secret.yaml
kubeseal -f secrets/headscale-oidc-secret.yaml -w templates/secrets/headscale-oidc-secret.yaml
