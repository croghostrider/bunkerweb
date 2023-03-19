#!/usr/bin/python3

import sys, os, traceback

sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/utils")
sys.path.append("/opt/bunkerweb/api")

from logger import log
from API import API

status = 0

try:
    # Get env vars
    is_kubernetes_mode = os.getenv("KUBERNETES_MODE") == "yes"
    is_swarm_mode = os.getenv("SWARM_MODE") == "yes"
    is_autoconf_mode = os.getenv("AUTOCONF_MODE") == "yes"
    token = os.getenv("CERTBOT_TOKEN")
    validation = os.getenv("CERTBOT_VALIDATION")

    # Cluster case
    if is_kubernetes_mode or is_swarm_mode or is_autoconf_mode:
        for variable, value in os.environ.items():
            if not variable.startswith("CLUSTER_INSTANCE_") :
                continue
            endpoint = value.split(" ")[0]
            host = value.split(" ")[1]
            api = API(endpoint, host=host)
            sent, err, status, resp = api.request("POST", "/lets-encrypt/challenge", data={"token": token, "validation": validation})
            if not sent:
                status = 1
                log(
                    "LETS-ENCRYPT",
                    "❌",
                    f"Can't send API request to {api.get_endpoint()}/lets-encrypt/challenge : {err}",
                )
            elif status == 200:
                log(
                    "LETS-ENCRYPT",
                    "ℹ️",
                    f"Successfully sent API request to {api.get_endpoint()}/lets-encrypt/challenge",
                )

            else:
                status = 1
                log(
                    "LETS-ENCRYPT",
                    "❌",
                    f"Error while sending API request to {api.get_endpoint()}/lets-encrypt/challenge : status = "
                    + resp["status"]
                    + ", msg = "
                    + resp["msg"],
                )
    else:
        root_dir = "/opt/bunkerweb/tmp/lets-encrypt/.well-known/acme-challenge/"
        os.makedirs(root_dir, exist_ok=True)
        with open(root_dir + token, "w") as f :
            f.write(validation)
except :
    status = 1
    log("LETS-ENCRYPT", "❌", "Exception while running certbot-auth.py :")
    print(traceback.format_exc())

sys.exit(status)
