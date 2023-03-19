from json import loads
from glob import glob
from re import match
import traceback

from logger import log

class ConfigCaller :

    def __init__(self):
        with open("/opt/bunkerweb/settings.json") as f :
            self._settings = loads(f.read())
        for plugin in glob("/opt/bunkerweb/core/*/plugin.json") + glob("/opt/bunkerweb/plugins/*/plugin.json"):
            with open(plugin) as f:
                try:
                    self._settings.update(loads(f.read())["settings"])
                except:
                    log(
                        "CONFIG",
                        "⚠️",
                        f"Exception while loading plugin metadata file at {plugin} : {traceback.format_exc()}",
                    )

    def _is_setting(self, setting) :
        return setting in self._settings

    def _is_global_setting(self, setting):
        if setting in self._settings :
            return self._settings[setting]["context"] == "global"
        if match("^.+_\d+$", setting):
            multiple_setting = "_".join(setting.split("_")[:-1])
            return multiple_setting in self._settings and self._settings[multiple_setting]["context"] == "global" and "multiple" in self._settings[multiple_setting]
        return False

    def _is_multisite_setting(self, setting):
        if setting in self._settings :
            return self._settings[setting]["context"] == "multisite"
        if match("^.+_\d+$", setting):
            multiple_setting = "_".join(setting.split("_")[:-1])
            return multiple_setting in self._settings and self._settings[multiple_setting]["context"] == "multisite" and "multiple" in self._settings[multiple_setting]
        return False
    
    def _full_env(self, env_instances, env_services):
        full_env = {k: v["default"] for k, v in self._settings.items()}
        # Replace with instances values
        for k, v in env_instances.items():
            full_env[k] = v
            if (not self._is_global_setting(k) and
                "MULTISITE" in env_instances and env_instances["MULTISITE"] == "yes" and
                "SERVER_NAME" in env_instances and env_instances["SERVER_NAME"] != ""):
                for server_name in env_instances["SERVER_NAME"].split(" "):
                    full_env[f"{server_name}_{k}"] = v
        # Replace with services values
        for k, v in env_services.items() :
            full_env[k] = v
        return full_env