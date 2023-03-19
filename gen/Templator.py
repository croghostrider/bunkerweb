import jinja2, glob, importlib, os, pathlib, copy, string, random

class Templator :

    def __init__(self, templates, core, plugins, output, target, config) :
        self.__templates = templates
        self.__core = core
        self.__plugins = plugins
        self.__output = output
        if not self.__output.endswith("/") :
            self.__output += "/"
        self.__target = target
        if not self.__target.endswith("/") :
            self.__target += "/"
        self.__config = config
        self.__jinja_env = self.__load_jinja_env()

    def render(self) :
        self.__render_global()
        servers = [self.__config["SERVER_NAME"]]
        if self.__config["MULTISITE"] == "yes" :
            servers = self.__config["SERVER_NAME"].split(" ")
        for server in servers :
            self.__render_server(server)

    def __load_jinja_env(self):
        searchpath = [self.__templates]
        searchpath.extend(
            f"{subpath}/confs"
            for subpath in glob.glob(f"{self.__core}/*")
            + glob.glob(f"{self.__plugins}/*")
            if os.path.isdir(subpath)
        )
        return jinja2.Environment(loader=jinja2.FileSystemLoader(searchpath=searchpath), lstrip_blocks=True, trim_blocks=True)

    def __find_templates(self, contexts):
        templates = []
        for template in self.__jinja_env.list_templates():
            if "global" in contexts and "/" not in template :
                templates.append(template)
                continue
            templates.extend(
                template
                for context in contexts
                if template.startswith(f"{context}/")
            )
        return templates

    def __write_config(self, subpath=None, config=None):
        real_path = self.__output
        if subpath != None:
            real_path += f"{subpath}/"
        real_path += "variables.env"
        real_config = config if config != None else self.__config
        pathlib.Path(os.path.dirname(real_path)).mkdir(parents=True, exist_ok=True)
        with open(real_path, "w") as f:
            for k, v in real_config.items():
                f.write(f"{k}={v}" + "\n")

    def __render_global(self) :
        self.__write_config()
        templates = self.__find_templates(["global", "http", "stream", "default-server-http"])
        for template in templates :
            self.__render_template(template)

    def __render_server(self, server):
        templates = self.__find_templates(["modsec", "modsec-crs", "server-http", "server-stream"])
        if self.__config["MULTISITE"] == "yes":
            config = copy.deepcopy(self.__config)
            for variable, value in self.__config.items():
                if variable.startswith(f"{server}_"):
                    config[variable.replace(f"{server}_", "", 1)] = value
            self.__write_config(subpath=server, config=config)
        for template in templates:
            subpath = None
            config = None
            if self.__config["MULTISITE"] == "yes":
                subpath = server
                config = copy.deepcopy(self.__config)
                for variable, value in self.__config.items():
                    if variable.startswith(f"{server}_"):
                        config[variable.replace(f"{server}_", "", 1)] = value
                config["NGINX_PREFIX"] = self.__target + server + "/"
                server_key = f"{server}_SERVER_NAME"
                if server_key not in self.__config :
                    config["SERVER_NAME"] = server
            root_confs = ["server.conf", "access-lua.conf", "init-lua.conf", "log-lua.conf", "set-lua.conf"]
            name = next(
                (
                    os.path.basename(template)
                    for root_conf in root_confs
                    if template.endswith(f"/{root_conf}")
                ),
                None,
            )
            self.__render_template(template, subpath=subpath, config=config, name=name)

    def __render_template(self, template, subpath=None, config=None, name=None):
        # Get real config and output folder in case it's a server config and we are in multisite mode
        real_config = copy.deepcopy(self.__config)
        if config :
            real_config = copy.deepcopy(config)
        real_config["all"] = copy.deepcopy(real_config)
        real_config["import"] = importlib.import_module
        real_config["is_custom_conf"] = Templator.is_custom_conf
        real_config["has_variable"] = Templator.has_variable
        real_config["random"] = Templator.random
        real_config["read_lines"] = Templator.read_lines
        real_output = self.__output
        if subpath:
            real_output += f"/{subpath}/"
        real_name = template
        if name :
            real_name = name
        jinja_template = self.__jinja_env.get_template(template)
        pathlib.Path(os.path.dirname(real_output + real_name)).mkdir(parents=True, exist_ok=True)
        with open(real_output + real_name, "w") as f :
            f.write(jinja_template.render(real_config))

    def is_custom_conf(self):
        return glob.glob(f"{self}/*.conf")
    
    def has_variable(self, variable, value):
        if variable in self and self[variable] == value:
            return True
        if self["MULTISITE"] == "yes":
            for server_name in self["SERVER_NAME"].split(" "):
                if (
                    f"{server_name}_{variable}" in self
                    and self[f"{server_name}_{variable}"] == value
                ):
                    return True
        return False
    
    def random(self):
        characters = string.ascii_letters + string.digits
        return "".join(random.choice(characters) for _ in range(nb))
    
    def read_lines(self):
        try:
            with open(self, "r") as f:
                return f.readlines()
        except :
            return []
