from Test import Test
from os.path import isdir, join, isfile
from os import chown, walk, getenv, listdir, mkdir, chmod
from shutil import copytree, rmtree
from traceback import format_exc
from subprocess import run
from time import sleep
from logger import log

class LinuxTest(Test) :

    def __init__(self, name, timeout, tests, distro):
        super().__init__(name, "linux", timeout, tests)
        self._domains = {
            r"www\.example\.com": getenv("TEST_DOMAIN1"),
            r"auth\.example\.com": getenv("TEST_DOMAIN1"),
            r"app1\.example\.com": getenv("TEST_DOMAIN1_1"),
            r"app2\.example\.com": getenv("TEST_DOMAIN1_2"),
            r"app3\.example\.com": getenv("TEST_DOMAIN1_3")
        }
        if distro not in ["ubuntu", "debian", "fedora", "centos"]:
            raise Exceptions(f"unknown distro {distro}")
        self.__distro = distro

    def init(self):
        try:
            if not Test.init() :
                return False
            # TODO : find the nginx uid/gid on Docker images
            # proc = run("sudo chown -R root:root /tmp/bw-data", shell=True)
            # if proc.returncode != 0 :
            #     raise(Exception("chown failed (autoconf stack)"))
            # if isdir("/tmp/linux") :
            #     rmtree("/tmp/linux")
            # mkdir("/tmp/linux")
            # chmod("/tmp/linux", 0o0777)
            cmd = f"docker run -p 80:80 -p 443:443 --rm --name linux-{self} -d --tmpfs /tmp --tmpfs /run --tmpfs /run/lock -v /sys/fs/cgroup:/sys/fs/cgroup:rw --cgroupns=host --tty local/bw-{self}:latest"
            proc = run(cmd, shell=True)
            if proc.returncode != 0 :
                raise(Exception("docker run failed (linux stack)"))
            if self in ["ubuntu", "debian"]:
                cmd = "apt install -y /opt/\$(ls /opt | grep deb)"
            elif self in ["centos", "fedora"]:
                cmd = "dnf install -y /opt/\$(ls /opt | grep rpm)"
            proc = LinuxTest.docker_exec(self, cmd)
            if proc.returncode != 0 :
                raise(Exception("docker exec apt install failed (linux stack)"))
            proc = LinuxTest.docker_exec(self, "systemctl start bunkerweb")
            if proc.returncode != 0 :
                raise(Exception("docker exec systemctl start failed (linux stack)"))
            # cp_dirs = {
            #     "/tmp/bw-data/letsencrypt": "/etc/letsencrypt",
            #     "/tmp/bw-data/cache": "/opt/bunkerweb/cache"
            # }
            # for src, dst in cp_dirs.items() :
            #     proc = LinuxTest.docker_cp(distro, src, dst)
            #     if proc.returncode != 0 :
            #         raise(Exception("docker cp failed for " + src + " (linux stack)"))
            #     proc = LinuxTest.docker_exec(distro, "chown -R nginx:nginx " + dst + "/*")
            #     if proc.returncode != 0 :
            #         raise(Exception("docker exec failed for directory " + src + " (linux stack)"))
            if self in ["ubuntu", "debian"]:
                LinuxTest.docker_exec(
                    self,
                    "DEBIAN_FRONTEND=noninteractive apt-get install -y php-fpm unzip",
                )
                if self == "ubuntu":
                    LinuxTest.docker_cp(
                        self,
                        "./tests/www-deb.conf",
                        "/etc/php/8.1/fpm/pool.d/www.conf",
                    )
                    LinuxTest.docker_exec(
                        self,
                        "systemctl stop php8.1-fpm ; systemctl start php8.1-fpm",
                    )
                elif self == "debian":
                    LinuxTest.docker_cp(
                        self,
                        "./tests/www-deb.conf",
                        "/etc/php/7.4/fpm/pool.d/www.conf",
                    )
                    LinuxTest.docker_exec(
                        self,
                        "systemctl stop php7.4-fpm ; systemctl start php7.4-fpm",
                    )
            elif self in ["centos", "fedora"]:
                LinuxTest.docker_exec(self, "dnf install -y php-fpm unzip")
                LinuxTest.docker_cp(self, "./tests/www-rpm.conf", "/etc/php-fpm.d/www.conf")
                LinuxTest.docker_exec(
                    self,
                    "mkdir /run/php ; chmod 777 /run/php ; systemctl stop php-fpm ; systemctl start php-fpm",
                )
            sleep(60)
        except :
            log("LINUX", "❌", "exception while running LinuxTest.init()\n" + format_exc())
            return False
        return True

    def end(self):
        ret = True
        try:
            if not Test.end() :
                return False
            proc = run(f"docker kill linux-{self}", shell=True)
            if proc.returncode != 0 :
                ret = False
        except :
            log("LINUX", "❌", "exception while running LinuxTest.end()\n" + format_exc())
            return False
        return ret

    def _setup_test(self):
        try:
            super()._setup_test()
            test = f"/tmp/tests/{self._name}"
            for ex_domain, test_domain in self._domains.items() :
                Test.replace_in_files(test, ex_domain, test_domain)
                Test.rename(test, ex_domain, test_domain)
            Test.replace_in_files(test, "example.com", getenv("ROOT_DOMAIN"))
            proc = LinuxTest.docker_cp(self.__distro, test, f"/opt/{self._name}")
            if proc.returncode != 0 :
                raise(Exception("docker cp failed (test)"))
            setup = f"{test}/setup-linux.sh"
            if isfile(setup):
                proc = LinuxTest.docker_exec(
                    self.__distro, f"cd /opt/{self._name} && ./setup-linux.sh"
                )
                if proc.returncode != 0 :
                    raise(Exception("docker exec setup failed (test)"))
            proc = LinuxTest.docker_exec(
                self.__distro, f"cp /opt/{self._name}/variables.env /opt/bunkerweb"
            )
            if proc.returncode != 0 :
                raise(Exception("docker exec cp variables.env failed (test)"))
            proc = LinuxTest.docker_exec(self.__distro, "echo '' >> /opt/bunkerweb/variables.env ; echo 'USE_LETS_ENCRYPT_STAGING=yes' >> /opt/bunkerweb/variables.env ; echo 'DISABLE_DEFAULT_SERVER=no' >> /opt/bunkerweb/variables.env")
            if proc.returncode != 0 :
                raise(Exception("docker exec append variables.env failed (test)"))
            proc = LinuxTest.docker_exec(self.__distro, "systemctl stop bunkerweb ; systemctl start bunkerweb")
            if proc.returncode != 0 :
                raise(Exception("docker exec systemctl restart failed (linux stack)"))
        except :
            log("LINUX", "❌", "exception while running LinuxTest._setup_test()\n" + format_exc())
            self._debug_fail()
            self._cleanup_test()
            return False
        return True

    def _cleanup_test(self):
        try:
            proc = LinuxTest.docker_exec(
                self.__distro,
                f"cd /opt/{self._name} ; ./cleanup-linux.sh ; rm -rf /opt/bunkerweb/www/* ; rm -rf /opt/bunkerweb/configs/* ; rm -rf /opt/bunkerweb/plugins/*",
            )
            if proc.returncode != 0 :
                raise(Exception("docker exec rm failed (cleanup)"))
            super()._cleanup_test()
        except :
            log("DOCKER", "❌", "exception while running LinuxTest._cleanup_test()\n" + format_exc())
            return False
        return True

    def _debug_fail(self) :
        LinuxTest.docker_exec(self.__distro, "cat /var/log/nginx/access.log ; cat /var/log/nginx/error.log ; journalctl -u bunkerweb --no-pager")
    
    def docker_exec(self, cmd_linux):
        return run(
            f"docker exec linux-{self}" + " /bin/bash -c \"" + cmd_linux + "\"",
            shell=True,
        )

    def docker_cp(self, src, dst):
        return run(f"docker cp {src} linux-{self}:{dst}", shell=True)