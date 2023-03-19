import traceback, json, hashlib
from os import path, remove
from shutil import copy
from datetime import datetime


"""
{
    "date": timestamp,
    "checksum": sha512
}
"""

def is_cached_file(file, expire):
        is_cached = False
        try:
                if not path.isfile(file) :
                    return False
                if not path.isfile(f"{file}.md"):
                        return False
                cached_time = 0
                with open(f"{file}.md", "r") as f:
                        cached_time = json.loads(f.read())["date"]
                current_time = datetime.timestamp(datetime.now())
                if current_time < cached_time :
                    return False
                diff_time = current_time - cached_time
                if expire == "day":
                        is_cached = diff_time < 86400
                elif expire == "hour":
                        is_cached = diff_time < 3600
                elif expire == "month":
                        is_cached = diff_time < 2592000
        except :
            is_cached = False
        return is_cached

def file_hash(file):
        sha512 = hashlib.sha512()
        with open(file, "rb") as f:
                while True:
                        if data := f.read(1024):
                                sha512.update(data)
                        else:
                                break
        return sha512.hexdigest()

def cache_hash(cache):
        try:
                with open(f"{cache}.md", "r") as f:
                        return json.loads(f.read())["checksum"]
        except :
            pass
        return None

def cache_file(file, cache, _hash):
        ret, err = True, "success"
        try:
                copy(file, cache)
                remove(file)
                with open(f"{cache}.md", "w") as f:
                        md = {
                            "date": datetime.timestamp(datetime.now()),
                            "checksum": _hash
                        }
                        f.write(json.dumps(md))
        except:
                return False, f"exception : {traceback.format_exc()}"
        return ret, err
