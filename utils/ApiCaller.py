from io import BytesIO
import tarfile

from logger import log

class ApiCaller :

    def __init__(self, apis=[]) :
        self.__apis = apis

    def _set_apis(self, apis) :
        self.__apis = apis

    def _get_apis(self) :
        return self.__apis

    def _send_to_apis(self, method, url, files=None, data=None, response=False):
        ret = True
        for api in self.__apis:
            if files is not None :
                for file, buffer in files.items() :
                    buffer.seek(0, 0)
            sent, err, status, resp = api.request(method, url, files=files, data=data)
            if not sent:
                ret = False
                log("API", "❌", f"Can't send API request to {api.get_endpoint()}{url} : {err}")
            elif status == 200:
                log("API", "ℹ️", f"Successfully sent API request to {api.get_endpoint()}{url}")
            else:
                ret = False
                log(
                    "API",
                    "❌",
                    f"Error while sending API request to {api.get_endpoint()}{url} : status = "
                    + resp["status"]
                    + ", msg = "
                    + resp["msg"],
                )
        if response:
            return (ret, resp) if isinstance(resp, dict) else (ret, resp.json())
        return ret

    def _send_files(self, path, url):
        tgz = BytesIO()
        with tarfile.open(mode="w:gz", fileobj=tgz) as tf :
            tf.add(path, arcname=".")
        tgz.seek(0, 0)
        files = {"archive.tar.gz": tgz}
        ret = bool(self._send_to_apis("POST", url, files=files))
        tgz.close()
        return ret
