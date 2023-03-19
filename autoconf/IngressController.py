from traceback import format_exc
from kubernetes import client, config, watch
from kubernetes.client.exceptions import ApiException
from threading import Thread, Lock
from logger import log
from sys import exit
from time import sleep

from Controller import Controller
from ConfigCaller import ConfigCaller

class IngressController(Controller, ConfigCaller) :

    def __init__(self) :
        Controller.__init__(self, "kubernetes")
        ConfigCaller.__init__(self)
        config.load_incluster_config()
        self.__corev1 = client.CoreV1Api()
        self.__networkingv1 = client.NetworkingV1Api()
        self.__internal_lock = Lock()

    def _get_controller_instances(self):
        return [
            pod
            for pod in self.__corev1.list_pod_for_all_namespaces(watch=False).items
            if pod.metadata.annotations != None
            and "bunkerweb.io/AUTOCONF" in pod.metadata.annotations
        ]

    def _to_instances(self, controller_instance):
        health = False
        if controller_instance.status.conditions is not None :
            for condition in controller_instance.status.conditions :
                if condition.type == "Ready" and condition.status == "True" :
                    health = True
                    break
        instance = {
            "name": controller_instance.metadata.name,
            "hostname": controller_instance.status.pod_ip,
            "health": health,
            "env": {
                env.name: env.value if env.value is not None else ""
                for env in controller_instance.spec.containers[0].env
            },
        }
        for controller_service in self._get_controller_services() :
            if controller_service.metadata.annotations is not None :
                for annotation, value in controller_service.metadata.annotations.items() :
                    if not annotation.startswith("bunkerweb.io/") :
                        continue
                    variable = annotation.replace("bunkerweb.io/", "", 1)
                    if self._is_setting(variable) :
                        instance["env"][variable] = value
        return [instance]

    def _get_controller_services(self) :
        return self.__networkingv1.list_ingress_for_all_namespaces(watch=False).items

    def _to_services(self, controller_service):
        if controller_service.spec is None or controller_service.spec.rules is None :
            return []
        services = []
        # parse rules
        for rule in controller_service.spec.rules:
            if rule.host is None :
                log("INGRESS-CONTROLLER", "⚠️", "Ignoring unsupported ingress rule without host.")
                continue
            service = {"SERVER_NAME": rule.host}
            if rule.http is None :
                services.append(service)
                continue
            location = 1
            for path in rule.http.paths:
                if path.path is None :
                    log("INGRESS-CONTROLLER", "⚠️", "Ignoring unsupported ingress rule without path.")
                    continue
                if path.backend.service is None :
                    log("INGRESS-CONTROLLER", "⚠️", "Ignoring unsupported ingress rule without backend service.")
                    continue
                if path.backend.service.port is None :
                    log("INGRESS-CONTROLLER", "⚠️", "Ignoring unsupported ingress rule without backend service port.")
                    continue
                if path.backend.service.port.number is None :
                    log("INGRESS-CONTROLLER", "⚠️", "Ignoring unsupported ingress rule without backend service port number.")
                    continue
                service_list = self.__corev1.list_service_for_all_namespaces(
                    watch=False,
                    field_selector=f"metadata.name={path.backend.service.name}",
                ).items
                if len(service_list) == 0:
                    log(
                        "INGRESS-CONTROLLER",
                        "⚠️",
                        f"Ignoring ingress rule with service {path.backend.service.name} : service not found.",
                    )
                    continue
                reverse_proxy_host = f"http://{path.backend.service.name}.{service_list[0].metadata.namespace}.svc.cluster.local:{str(path.backend.service.port.number)}"
                service["USE_REVERSE_PROXY"] = "yes"
                service[f"REVERSE_PROXY_HOST_{str(location)}"] = reverse_proxy_host
                service[f"REVERSE_PROXY_URL_{str(location)}"] = path.path
                location += 1
            services.append(service)

        # parse tls
        if controller_service.spec.tls is not None :
            log("INGRESS-CONTROLLER", "⚠️", "Ignoring unsupported tls.")

        # parse annotations
        if controller_service.metadata.annotations is not None :
            for service in services :
                for annotation, value in controller_service.metadata.annotations.items() :
                    if not annotation.startswith("bunkerweb.io/") :
                        continue
                    variable = annotation.replace("bunkerweb.io/", "", 1)
                    if not variable.startswith(service["SERVER_NAME"].split(" ")[0] + "_") :
                        continue
                    variable = variable.replace(service["SERVER_NAME"].split(" ")[0] + "_", "", 1)
                    if self._is_multisite_setting(variable) :
                        service[variable] = value
        return services

    def _get_static_services(self):
        services = []
        variables = {}
        for instance in self.__corev1.list_pod_for_all_namespaces(watch=False).items:
            if (
                instance.metadata.annotations is None
                or "bunkerweb.io/AUTOCONF" not in instance.metadata.annotations
            ):
                continue
            for env in instance.spec.containers[0].env:
                variables[env.name] = "" if env.value is None else env.value
        server_names = []
        if "SERVER_NAME" in variables and variables["SERVER_NAME"] != "" :
            server_names = variables["SERVER_NAME"].split(" ")
        for server_name in server_names:
            service = {"SERVER_NAME": server_name}
            for variable, value in variables.items():
                prefix = variable.split("_")[0]
                real_variable = variable.replace(f"{prefix}_", "", 1)
                if prefix == server_name and self._is_multisite_setting(real_variable) :
                    service[real_variable] = value
            services.append(service)
        return services

    def get_configs(self):
        supported_config_types = ["http", "stream", "server-http", "server-stream", "default-server-http", "modsec", "modsec-crs"]
        configs = {config_type: {} for config_type in supported_config_types}
        for configmap in self.__corev1.list_config_map_for_all_namespaces(watch=False).items:
            if configmap.metadata.annotations is None or "bunkerweb.io/CONFIG_TYPE" not in configmap.metadata.annotations :
                continue
            config_type = configmap.metadata.annotations["bunkerweb.io/CONFIG_TYPE"]
            if config_type not in supported_config_types:
                log(
                    "INGRESS-CONTROLLER",
                    "⚠️",
                    f"Ignoring unsupported CONFIG_TYPE {config_type} for ConfigMap {configmap.metadata.name}",
                )
                continue
            if not configmap.data:
                log(
                    "INGRESS-CONTROLLER",
                    "⚠️",
                    f"Ignoring blank ConfigMap {configmap.metadata.name}",
                )
                continue
            config_site = ""
            if "bunkerweb.io/CONFIG_SITE" in configmap.metadata.annotations :
                config_site = configmap.metadata.annotations["bunkerweb.io/CONFIG_SITE"] + "/"
            for config_name, config_data in configmap.data.items() :
                configs[config_type][config_site + config_name] = config_data
        return configs

    def __watch(self, watch_type):
        w = watch.Watch()
        what = None
        if watch_type == "pod":
            what = self.__corev1.list_pod_for_all_namespaces
        elif watch_type == "ingress" :
            what = self.__networkingv1.list_ingress_for_all_namespaces
        elif watch_type == "configmap" :
            what = self.__corev1.list_config_map_for_all_namespaces
        else:
            raise Exception(f"unsupported watch_type {watch_type}")
        while True:
            locked = False
            try:
                for _ in w.stream(what):
                    self.__internal_lock.acquire()
                    locked = True
                    self._instances = self.get_instances()
                    self._services = self.get_services()
                    self._configs = self.get_configs()
                    if not self._config.update_needed(self._instances, self._services, configs=self._configs) :
                        self.__internal_lock.release()
                        locked = False
                        continue
                    log("INGRESS-CONTROLLER", "ℹ️", "Catched kubernetes event, deploying new configuration ...")
                    try:
                        if ret := self.apply_config():
                            log("INGRESS-CONTROLLER", "ℹ️", "Successfully deployed new configuration 🚀")
                        else:
                            log("INGRESS-CONTROLLER", "❌", "Error while deploying new configuration ...")
                    except :
                        log("INGRESS-CONTROLLER", "❌", "Exception while deploying new configuration :")
                        print(format_exc())
                    self.__internal_lock.release()
                    locked = False
            except ApiException as e:
                if e.status != 410:
                    log(
                        "INGRESS-CONTROLLER",
                        "❌",
                        f"Exception while reading k8s event (type = {watch_type}) : ",
                    )
                    print(format_exc())
            except:
                log(
                    "INGRESS-CONTROLLER",
                    "❌",
                    f"Unknown exception while reading k8s event (type = {watch_type}) : ",
                )
                print(format_exc())
            finally:
                if locked :
                    self.__internal_lock.release()
                log("INGRESS-CONTROLLER", "⚠️", "Got exception, retrying in 10 seconds ...")
                sleep(10)

    def apply_config(self) :
        self._config.stop_scheduler()
        ret = self._config.apply(self._instances, self._services, configs=self._configs)
        self._config.start_scheduler()
        return ret

    def process_events(self):
        watch_types = ["pod", "ingress", "configmap"]
        threads = [
            Thread(target=self.__watch, args=(watch_type,))
            for watch_type in watch_types
        ]
        for thread in threads :
            thread.start()
        for thread in threads :
            thread.join()
