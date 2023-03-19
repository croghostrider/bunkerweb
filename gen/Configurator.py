import sys, json, glob, re, os, traceback

sys.path.append("/opt/bunkerweb/utils")

from logger import log

class Configurator :

    def __init__(self, settings, core, plugins, variables) :
        self.__settings = self.__load_settings(settings)
        self.__core = core
        self.__plugins = self.__load_plugins(plugins)
        self.__variables = self.__load_variables(variables)
        self.__multisite = False
        if "MULTISITE" in self.__variables and self.__variables["MULTISITE"] == "yes" :
            self.__multisite = True
        self.__servers = self.__map_servers()
        
    def __map_servers(self):
        if not self.__multisite or "SERVER_NAME" not in self.__variables:
            return {}
        servers = {}
        for server_name in self.__variables["SERVER_NAME"].split(" "):
            if not re.search(self.__settings["SERVER_NAME"]["regex"], server_name):
                log(
                    "GENERATOR",
                    "⚠️",
                    f"Ignoring server name {server_name} because regex is not valid",
                )
                continue
            names = [server_name]
            if f"{server_name}_SERVER_NAME" in self.__variables:
                if not re.search(
                    self.__settings["SERVER_NAME"]["regex"],
                    self.__variables[f"{server_name}_SERVER_NAME"],
                ):
                    log(
                        "GENERATOR",
                        "⚠️",
                        f"Ignoring {server_name}_SERVER_NAME because regex is not valid",
                    )
                else:
                    names = self.__variables[f"{server_name}_SERVER_NAME"].split(" ")
            servers[server_name] = names
        return servers
    
    def __load_settings(self, path) :
        with open(path) as f :
            return json.loads(f.read())
    
    def __load_plugins(self, path):
        plugins = {}
        files = glob.glob(f"{path}/*/plugin.json")
        for file in files:
            try:
                with open(file) as f:
                    plugins |= json.loads(f.read())["settings"]
            except:
                log("GENERATOR", "❌", f"Exception while loading JSON from {file} :")
                print(traceback.format_exc())

        return plugins
    
    def __load_variables(self, path):
        variables = {}
        with open(path) as f:
            lines = f.readlines()
            for line in lines:
                line = line.strip()
                if line.startswith("#") or line == "" or "=" not in line:
                    continue
                var = line.split("=")[0]
                value = line[len(var)+1:]
                variables[var] = value
        return variables

    def get_config(self):
        config = {}
        # Extract default settings
        default_settings = [self.__settings, self.__core, self.__plugins]
        for settings in default_settings :
            for setting, data in settings.items() :
                config[setting] = data["default"]
        # Override with variables
        for variable, value in self.__variables.items():
            ret, err = self.__check_var(variable)
            if ret:
                config[variable] = value
            else:
                log("GENERATOR", "⚠️", f"Ignoring variable {variable} : {err}")
        # Expand variables to each sites if MULTISITE=yes and if not present
        if config["MULTISITE"] == "yes":
            for server_name in config["SERVER_NAME"].split(" "):
                if server_name == "" :
                    continue
                for settings in default_settings:
                    for setting, data in settings.items():
                        if data["context"] == "global" :
                            continue
                        key = f"{server_name}_{setting}"
                        if setting == "SERVER_NAME" and key not in config:
                            config[key] = server_name
                            continue
                        if key not in config :
                            config[key] = config[setting]
        return config

    def __check_var(self, variable):
        value = self.__variables[variable]
        # MULTISITE=no
        if not self.__multisite:
            where, real_var = self.__find_var(variable)
            if not where:
                return False, f"variable name {variable} doesn't exist"
            if "regex" not in where[real_var]:
                return False, f"missing regex for variable {variable}"
            return (
                (True, "ok")
                if re.search(where[real_var]["regex"], value)
                else (
                    False,
                    f"value {value} doesn't match regex "
                    + where[real_var]["regex"],
                )
            )
        # MULTISITE=yes
        prefixed, real_var = self.__var_is_prefixed(variable)
        where, real_var = self.__find_var(real_var)
        if not where:
            return False, f"variable name {variable} doesn't exist"
        if prefixed and where[real_var]["context"] != "multisite":
            return False, f"context of {variable} isn't multisite"
        return (
            (True, "ok")
            if re.search(where[real_var]["regex"], value)
            else (
                False,
                f"value {value} doesn't match regex " + where[real_var]["regex"],
            )
        )
        
    def __find_var(self, variable):
        targets = [self.__settings, self.__core, self.__plugins]
        for target in targets:
            if variable in target :
                return target, variable
            for real_var, settings in target.items():
                if "multiple" in settings and re.search(
                    f"^{real_var}_[0-9]+$", variable
                ):
                    return target, real_var
        return False, variable
        
    def __var_is_prefixed(self, variable):
        return next(
            (
                (True, variable.replace(f"{server}_", "", 1))
                for server in self.__servers
                if variable.startswith(f"{server}_")
            ),
            (False, variable),
        )