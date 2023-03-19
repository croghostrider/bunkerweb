#!/usr/bin/python3

import sys, os, traceback

sys.path.append("/opt/bunkerweb/deps/python")
sys.path.append("/opt/bunkerweb/utils")

import logger, jobs, requests, ipaddress

def check_line(kind, line):
    if kind == "IP":
        try:
            if "/" in line:
                ipaddress.ip_network(line)
            else:
                ipaddress.ip_address(line)
            return True, line
        except :
            pass
        return False, ""
    elif kind == "RDNS" :
        if re.match(r"^(\.?[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$", line) :
            return True, line.lower()
        return False, ""
    elif kind == "ASN" :
        real_line = line.replace("AS", "")
        if re.match(r"^\d+$", real_line) :
            return True, real_line
    elif kind == "USER_AGENT" :
        return True, line.replace("\\ ", " ").replace("\\.", "%.").replace("\\\\", "\\").replace("-", "%-")
    elif kind == "URI" :
        if re.match(r"^/", line) :
            return True, line
    return False, ""

status = 0

try:

    # Check if at least a server has Greylist activated
    greylist_activated = False
    # Multisite case
    if os.getenv("MULTISITE") == "yes":
        for first_server in os.getenv("SERVER_NAME").split(" "):
            if (
                os.getenv(
                    f"{first_server}_USE_GREYLIST", os.getenv("USE_GREYLIST")
                )
                == "yes"
            ):
                greylist_activated = True
                break
    elif os.getenv("USE_GREYLIST") == "yes" :
        greylist_activated = True
    if not greylist_activated :
        logger.log("GREYLIST", "ℹ️", "Greylist is not activated, skipping downloads...")
        os._exit(0)

    # Create directories if they don't exist
    os.makedirs("/opt/bunkerweb/cache/greylist", exist_ok=True)
    os.makedirs("/opt/bunkerweb/tmp/greylist", exist_ok=True)

    # Our urls data
    urls = {
        "IP": [],
        "RDNS": [],
        "ASN" : [],
        "USER_AGENT": [],
        "URI": []
    }

    # Don't go further if the cache is fresh
    kinds_fresh = {
        "IP": True,
        "RDNS": True,
        "ASN" : True,
        "USER_AGENT": True,
        "URI": True
    }
    all_fresh = True
    for kind in kinds_fresh:
        if not jobs.is_cached_file(
            f"/opt/bunkerweb/cache/greylist/{kind}.list", "hour"
        ):
            kinds_fresh[kind] = False
            all_fresh = False
            logger.log(
                "GREYLIST",
                "ℹ️",
                f"Greylist for {kind} is not cached, processing downloads...",
            )
        else:
            logger.log(
                "GREYLIST",
                "ℹ️",
                f"Greylist for {kind} is already in cache, skipping downloads...",
            )
    if all_fresh :
        os._exit(0)

    # Get URLs
    urls = {
        "IP": [],
        "RDNS": [],
        "ASN" : [],
        "USER_AGENT": [],
        "URI": []
    }
    for kind, value in urls.items():
        for url in os.getenv(f"GREYLIST_{kind}_URLS", "").split(" "):
            if url != "" and url not in value:
                urls[kind].append(url)

    # Loop on kinds
    for kind, urls_list in urls.items():
        if kinds_fresh[kind] :
            continue
        # Write combined data of the kind to a single temp file
        for url in urls_list:
            try:
                logger.log("GREYLIST", "ℹ️", f"Downloading greylist data from {url} ...")
                resp = requests.get(url, stream=True)
                if resp.status_code != 200 :
                    continue
                i = 0
                with open(f"/opt/bunkerweb/tmp/greylist/{kind}.list", "w") as f:
                    for line in resp.iter_lines(decode_unicode=True) :
                        line = line.strip()
                        if kind != "USER_AGENT" :
                            line = line.strip().split(" ")[0]
                        if line == "" or line.startswith("#") or line.startswith(";") :
                            continue
                        ok, data = check_line(kind, line)
                        if ok :
                            f.write(data + "\n")
                            i += 1
                logger.log("GREYLIST", "ℹ️", f"Downloaded {str(i)} bad {kind}")
                # Check if file has changed
                file_hash = jobs.file_hash(f"/opt/bunkerweb/tmp/greylist/{kind}.list")
                cache_hash = jobs.cache_hash(f"/opt/bunkerweb/cache/greylist/{kind}.list")
                if file_hash == cache_hash:
                    logger.log(
                        "GREYLIST",
                        "ℹ️",
                        f"New file {kind}.list is identical to cache file, reload is not needed",
                    )
                else:
                    logger.log(
                        "GREYLIST",
                        "ℹ️",
                        f"New file {kind}.list is different than cache file, reload is needed",
                    )
                    # Put file in cache
                    cached, err = jobs.cache_file(
                        f"/opt/bunkerweb/tmp/greylist/{kind}.list",
                        f"/opt/bunkerweb/cache/greylist/{kind}.list",
                        file_hash,
                    )
                    if not cached:
                        logger.log("GREYLIST", "❌", f"Error while caching greylist : {err}")
                        status = 2
                    if status != 2 :
                        status = 1
            except:
                status = 2
                logger.log("GREYLIST", "❌", f"Exception while getting greylist from {url} :")
                print(traceback.format_exc())

except :
    status = 2
    logger.log("GREYLIST", "❌", "Exception while running greylist-download.py :")
    print(traceback.format_exc())

sys.exit(status)
