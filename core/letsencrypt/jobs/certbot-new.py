#!/usr/bin/python3

import sys, os, subprocess, traceback

sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/utils")

import logger

def certbot_new(first_domain, domains, email):
    cmd = f"/opt/bunkerweb/deps/python/bin/certbot certonly --manual --preferred-challenges=http --manual-auth-hook /opt/bunkerweb/core/letsencrypt/jobs/certbot-auth.py --manual-cleanup-hook /opt/bunkerweb/core/letsencrypt/jobs/certbot-cleanup.py -n -d {domains} --email {email} --agree-tos"
    if os.getenv("USE_LETS_ENCRYPT_STAGING") == "yes" :
        cmd += " --staging"
    os.environ["PYTHONPATH"] = "/opt/bunkerweb/deps/python"
    proc = subprocess.run(cmd.split(" "), stdin=subprocess.DEVNULL, stderr=subprocess.STDOUT, env=os.environ)
    return proc.returncode

status = 0

try:

    # Multisite case
    if os.getenv("MULTISITE") == "yes":
        for first_server in os.getenv("SERVER_NAME").split(" "):
            if (
                os.getenv(
                    f"{first_server}_AUTO_LETS_ENCRYPT",
                    os.getenv("AUTO_LETS_ENCRYPT"),
                )
                != "yes"
            ):
                continue
            if first_server == "" :
                continue
            real_server_name = os.getenv(f"{first_server}_SERVER_NAME", first_server)
            domains = real_server_name.replace(" ", ",")
            if os.path.exists(
                f"/etc/letsencrypt/live/{first_server}/cert.pem"
            ):
                logger.log(
                    "LETS-ENCRYPT",
                    "ℹ️",
                    f"Certificates already exists for domain(s) {domains}",
                )
                continue
            real_email = os.getenv(
                f"{first_server}_EMAIL_LETS_ENCRYPT",
                os.getenv("EMAIL_LETS_ENCRYPT", f"contact@{first_server}"),
            )
            if real_email == "":
                real_email = f"contact@{first_server}"
            logger.log(
                "LETS-ENCRYPT",
                "ℹ️",
                f"Asking certificates for domains : {domains} (email = {real_email}) ...",
            )
            if certbot_new(first_server, domains, real_email) != 0:
                status = 1
                logger.log(
                    "LETS-ENCRYPT",
                    "❌",
                    f"Certificate generation failed for domain(s) {domains} ...",
                )
            else:
                logger.log(
                    "LETS-ENCRYPT",
                    "ℹ️",
                    f"Certificate generation succeeded for domain(s) : {domains}",
                )

    elif os.getenv("AUTO_LETS_ENCRYPT") == "yes" and os.getenv("SERVER_NAME") != "":
        first_server = os.getenv("SERVER_NAME").split(" ")[0]
        domains = os.getenv("SERVER_NAME").replace(" ", ",")
        if os.path.exists(f"/etc/letsencrypt/live/{first_server}/cert.pem"):
            logger.log(
                "LETS-ENCRYPT",
                "ℹ️",
                f"Certificates already exists for domain(s) {domains}",
            )
        else:
            real_email = os.getenv("EMAIL_LETS_ENCRYPT", f"contact@{first_server}")
            if real_email == "":
                real_email = f"contact@{first_server}"
            logger.log(
                "LETS-ENCRYPT",
                "ℹ️",
                f"Asking certificates for domain(s) : {domains} (email = {real_email}) ...",
            )
            if certbot_new(first_server, domains, real_email) != 0:
                status = 2
                logger.log(
                    "LETS-ENCRYPT",
                    "❌",
                    f"Certificate generation failed for domain(s) : {domains}",
                )
            else:
                logger.log(
                    "LETS-ENCRYPT",
                    "ℹ️",
                    f"Certificate generation succeeded for domain(s) : {domains}",
                )

except :
    status = 1
    logger.log("LETS-ENCRYPT", "❌", "Exception while running certbot-new.py :")
    print(traceback.format_exc())

sys.exit(status)
