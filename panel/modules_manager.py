import shutil
import subprocess
import os
import re
import logging
import traceback


class PHP:
    def __init__(self, php_path, project_path):
        self.php_path = php_path
        self.project_path = project_path
        self.php_version_major = self._extract_php_major_version()

        self.log_dir = os.path.join(project_path, "userdata", "logs")
        os.makedirs(self.log_dir, exist_ok=True)

        self.php_log = os.path.join(self.log_dir, "php.log")

        logging.basicConfig(
            filename=os.path.join(self.log_dir, "server.log"),
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.setup_php_ini()

    def _extract_php_major_version(self):
        match = re.search(r'(\d+)\.\d+\.\d+', os.path.basename(self.php_path))
        if match:
            return match.group(1)
        raise ValueError(f"Не удалось определить версию PHP из пути: {self.php_path}")

    def setup_php_ini(self):
        php_ini_path = os.path.join(self.php_path, "php.ini")
        if not os.path.exists(php_ini_path):
            dev_ini = os.path.join(self.php_path, "php.ini-development")
            prod_ini = os.path.join(self.php_path, "php.ini-production")
            if os.path.exists(dev_ini):
                shutil.copy(dev_ini, php_ini_path)
                logging.info(f"Скопирован php.ini-development в {php_ini_path}")
            elif os.path.exists(prod_ini):
                shutil.copy(prod_ini, php_ini_path)
                logging.info(f"Скопирован php.ini-production в {php_ini_path}")
            else:
                logging.error("Не найден php.ini, php.ini-development или php.ini-production")
                raise FileNotFoundError("Не найден php.ini, php.ini-development или php.ini-production")

    def run_php(self):
        command = rf'"{self.php_path}\php-cgi.exe" -b 127.0.0.1:9000'
        print(command)
        self._execute_command(command, f"PHP {self.php_version_major} запущен.", log_file=self.php_log, wait=False)

    @staticmethod
    def stop_php():
        try:
            command = rf'taskkill /F /IM php-cgi.exe /T /FI "STATUS eq RUNNING"'
            subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logging.info("PHP остановлен.")
        except Exception as e:
            logging.error(f"Ошибка при остановке PHP: {e}")

    def restart_php(self):
        self.stop_php()
        self.run_php()
        logging.info(f"PHP {self.php_version_major} перезапущен.")

    def _execute_command(self, command, success_message, log_file, wait=True):
        try:
            with open(log_file, "a") as log_output:
                if wait:
                    process = subprocess.run(command, shell=True, stdout=log_output, stderr=log_output, text=True)
                    if process.returncode == 0:
                        logging.info(success_message)
                        return True
                    else:
                        logging.error(f"Ошибка выполнения: смотри {log_file}")
                        return False
                else:
                    subprocess.Popen(command, shell=True, stdout=log_output, stderr=log_output)
                    logging.info(success_message)
                    return True
        except:
            logging.error(f"Ошибка: {traceback.format_exc()}")
            return False


class ApachePHP(PHP):
    def __init__(self, apache_path, php_path, project_path):
        super().__init__(php_path, project_path)
        self.apache_path = apache_path
        self.php_path = php_path
        self.project_path = project_path

        self.php_version_major = self._extract_php_major_version()

        self.module_log_dir = os.path.normpath(os.path.join(self.project_path, "userdata", "modules_logs"))
        self.log_dir = os.path.join(project_path, "userdata", "logs")
        os.makedirs(self.log_dir, exist_ok=True)

        self.apache_log = os.path.join(self.log_dir, "apache.log")
        self.php_log = os.path.join(self.log_dir, "php.log")

        logging.basicConfig(
            filename=os.path.join(self.log_dir, "server.log"),
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.setup_php_ini()

    def configure_apache(self):
        conf_path = os.path.join(self.apache_path, "conf", "httpd.conf")
        php_e = "" if self.php_version_major == "8" else "7"
        apache_dll_path = os.path.join(self.php_path, f"php{self.php_version_major}apache2_4.dll")
        authz_core_module = os.path.join(self.apache_path, "modules", "mod_authz_core.so")
        mod_authz_host = os.path.join(self.apache_path, "modules", "mod_authz_host.so")
        mod_mime = os.path.join(self.apache_path, "modules", "mod_mime.so")
        config = f"""
        ServerRoot "{self.apache_path}"
        Listen 80
        DocumentRoot "{self.project_path}/sites"
        <Directory "{self.project_path}/sites">
            Options Indexes FollowSymLinks
            AllowOverride All
            Require all granted
        </Directory>
        
        ErrorLog "{self.module_log_dir}/apache_error.log"
        CustomLog "{self.module_log_dir}/apache_access.log" common

        LoadModule authz_core_module {authz_core_module}
        LoadModule authz_host_module {mod_authz_host}
        LoadModule mime_module {mod_mime}
        LoadModule php{php_e}_module "{apache_dll_path}"
        AddHandler application/x-httpd-php .php
        PHPIniDir "{self.php_path}"
        """
        with open(conf_path, "w", encoding="utf-8") as conf_file:
            conf_file.write(config)

        logging.info(f"Apache сконфигурирован с PHP {self.php_version_major} из {self.php_path}")

    def run_apache(self):

        self.configure_apache()
        command = rf'"{self.apache_path}\bin\httpd.exe"'
        self._execute_command(command, "Apache запущен.", log_file=self.apache_log, wait=False)

    def stop_apache(self):
        try:
            command = rf'taskkill /F /IM httpd.exe /T /FI "STATUS eq RUNNING"'
            self._execute_command(command, "Apache остановлен.", log_file=self.apache_log, wait=False)
        except:
            pass

    def restart_apache(self):
        self.stop_apache()
        self.run_apache()
        logging.info("Apache перезапущен.")

    def run(self):
        self.run_php()
        self.run_apache()

    def stop(self):
        self.stop_apache()
        self.stop_php()

    def restart(self):
        self.stop()
        self.run()


class NginxPHP(PHP):
    def __init__(self, nginx_path, php_path, project_path):
        super().__init__(php_path, project_path)
        self.nginx_path = os.path.normpath(nginx_path)
        self.php_path = php_path
        self.project_path = project_path

        self.conf_path = os.path.normpath(os.path.join(self.nginx_path, "conf", "nginx.conf"))
        self.module_log_dir = os.path.normpath(os.path.join(self.project_path, "userdata", "modules_logs"))
        self.sites_path = os.path.join(self.project_path, "sites")

        self.log_dir = os.path.join(self.project_path, "userdata", "logs")
        os.makedirs(self.log_dir, exist_ok=True)

        self.nginx_log = os.path.join(self.log_dir, "nginx.log")
        self.php_log = os.path.join(self.log_dir, "php.log")
        logging.basicConfig(
            filename=os.path.join(self.log_dir, "server.log"),
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )
        self.setup_php_ini()

    def configure_nginx(self):
        config = f"""
        worker_processes  1;
        events {{
            worker_connections  1024;
        }}
        http {{
            include       mime.types;
            default_type  application/octet-stream;
            sendfile        on;
            keepalive_timeout  65;
            
            error_log  {self.module_log_dir}/nginx_error.log;
            access_log {self.module_log_dir}/nginx_access.log;
                
            server {{
                listen 80;
                server_name localhost;
                root {self.sites_path};
                index index.php index.html;
                
                error_log  {self.module_log_dir}/nginx_error.log;
                access_log {self.module_log_dir}/nginx_access.log;
            
                location / {{
                    try_files $uri $uri/ =404;
                }}

                location ~ \\.php$ {{
                    include fastcgi_params;
                    fastcgi_pass 127.0.0.1:9000;
                    fastcgi_index index.php;
                    fastcgi_param SCRIPT_FILENAME $document_root$fastcgi_script_name;
                    fastcgi_param PATH_TRANSLATED $document_root$fastcgi_script_name;
                    fastcgi_param QUERY_STRING $query_string;
                    fastcgi_param REQUEST_METHOD $request_method;
                    fastcgi_param CONTENT_TYPE $content_type;
                    fastcgi_param CONTENT_LENGTH $content_length;
                    fastcgi_param SCRIPT_NAME $fastcgi_script_name;
                    fastcgi_param REQUEST_URI $request_uri;
                    fastcgi_param DOCUMENT_URI $document_uri;
                    fastcgi_param DOCUMENT_ROOT $document_root;
                    fastcgi_param SERVER_PROTOCOL $server_protocol;
                    fastcgi_param REMOTE_ADDR $remote_addr;
                    fastcgi_param REMOTE_PORT $remote_port;
                    fastcgi_param SERVER_ADDR $server_addr;
                    fastcgi_param SERVER_PORT $server_port;
                    fastcgi_param SERVER_NAME $server_name;
                    
                }}
            }}
        }}
        """

        with open(self.conf_path, "w", encoding="utf-8") as conf_file:
            conf_file.write(config)

        logging.info(f"Nginx сконфигурирован для папки сайтов: {self.sites_path}")

    def run_nginx(self):
        self.configure_nginx()
        command = rf'''"{self.nginx_path.replace("\\", "/")}/nginx.exe" -c "{self.conf_path.replace("\\", "/")}" -p "{self.nginx_path.replace("\\", "/")}"'''
        self._execute_command(command, "Nginx запущен.", log_file=self.nginx_log, wait=False)

    def stop_nginx(self):
        command = rf'"{self.nginx_path}\nginx.exe" -s stop -c "{self.conf_path.replace("\\", "/")}" -p "{self.nginx_path.replace("\\", "/")}"'
        self._execute_command(command, "Nginx остановлен.", log_file=self.nginx_log)

    def restart_nginx(self):
        self.stop_nginx()
        self.run_nginx()
        logging.info("Nginx перезапущен.")

    def run(self):
        self.run_php()
        self.run_nginx()

    def stop(self):
        self.stop_nginx()
        self.stop_php()

    def restart(self):
        self.stop()
        self.run()


class HybridServer(PHP):
    def __init__(self, apache_path, nginx_path, php_path, project_path):
        super().__init__(php_path, project_path)

        self.module_log_dir = self.module_log_dir = os.path.normpath(os.path.join(self.project_path, "userdata", "modules_logs"))
        self.apache_path = apache_path
        self.nginx_path = nginx_path
        self.php_path = php_path
        self.project_path = project_path
        self.sites_path = os.path.join(self.project_path, "sites")
        self.conf_nginx_path = os.path.normpath(os.path.join(self.nginx_path, "conf", "nginx.conf"))



        self.log_dir = os.path.join(self.project_path, "userdata", "logs")
        os.makedirs(self.log_dir, exist_ok=True)

        self.apache_log = os.path.join(self.log_dir, "apache.log")
        self.nginx_log = os.path.join(self.log_dir, "nginx.log")
        self.php_log = os.path.join(self.log_dir, "php.log")

        logging.basicConfig(
            filename=os.path.join(self.log_dir, "server.log"),
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )

        self.setup_php_ini()

    def configure_apache(self):
        conf_path = os.path.join(self.apache_path, "conf", "httpd.conf")

        sites_path = os.path.join(self.project_path, "sites")
        php_e = "" if self.php_version_major == "8" else "7"
        apache_dll_path = os.path.join(self.php_path, f"php{self.php_version_major}apache2_4.dll")
        authz_core_module = os.path.join(self.apache_path, "modules", "mod_authz_core.so")
        mod_authz_host = os.path.join(self.apache_path, "modules", "mod_authz_host.so")
        mod_mime = os.path.join(self.apache_path, "modules", "mod_mime.so")

        config = f"""
        Listen 8080
        <VirtualHost *:8080>
            ServerName site1.su
            DocumentRoot "{sites_path}/site1"
            <Directory "{sites_path}/site1">
                AllowOverride All
                Require all granted
            </Directory>
        </VirtualHost>
        
        <VirtualHost *:8080>
            ServerName localhost
            DocumentRoot "{sites_path}/site2"
            <Directory "{sites_path}/site2">
                AllowOverride All
                Require all granted
            </Directory>
        </VirtualHost>
        
        ErrorLog "{self.module_log_dir}/apache_error.log"

        LoadModule authz_core_module {authz_core_module}
        LoadModule authz_host_module {mod_authz_host}
        LoadModule mime_module {mod_mime}
        LoadModule php{php_e}_module "{apache_dll_path}"
        AddHandler application/x-httpd-php .php
        PHPIniDir "{self.php_path}"
        """

        with open(conf_path, "w", encoding="utf-8") as conf_file:
            conf_file.write(config)

        logging.info(f"Apache сконфигурирован для работы на порту 8080 с PHP из {self.php_path}")

    def configure_nginx(self):
        conf_path = os.path.join(self.nginx_path, "conf", "nginx.conf")

        config = f"""
        worker_processes  1;
        events {{
            worker_connections  1024;
        }}
        http {{
            include       mime.types;
            default_type  application/octet-stream;
            sendfile        on;
            keepalive_timeout  65;
            
            error_log  {self.module_log_dir}/nginx_error.log;
            access_log {self.module_log_dir}/nginx_access.log;
                server {{
                    listen 80;
                    server_name site1.su;
                
                    # Либо отдаём статику прямо, а PHP/другое проксируем.
                    location / {{
                        proxy_pass http://127.0.0.1:8080;
                        proxy_set_header Host $host;
                        proxy_set_header X-Real-IP $remote_addr;
                        # и другие нужные заголовки
                    }}
                }}
                
                # Для site2.ru
                server {{
                    listen 80;
                    server_name site2.ru;
                
                    location / {{
                        proxy_pass http://127.0.0.1:8080;
                        proxy_set_header Host $host;
                        proxy_set_header X-Real-IP $remote_addr;
                    }}
                }}
        }}
        """

        with open(conf_path, "w", encoding="utf-8") as conf_file:
            conf_file.write(config)

        logging.info(f"Nginx сконфигурирован как реверс-прокси для Apache (порт 8080)")

    def run_apache(self):

        self.configure_apache()
        command = rf'"{self.apache_path}\bin\httpd.exe"'
        self._execute_command(command, "Apache запущен.", log_file=self.apache_log, wait=False)

    def stop_apache(self):
        try:
            command = rf'taskkill /F /IM httpd.exe /T /FI "STATUS eq RUNNING"'
            self._execute_command(command, "Apache остановлен.", log_file=self.apache_log, wait=False)
        except:
            pass

    def restart_apache(self):
        self.stop_apache()
        self.run_apache()
        logging.info("Apache перезапущен.")

    def run_nginx(self):
        self.configure_nginx()
        command = rf'''"{self.nginx_path.replace("\\", "/")}/nginx.exe" -c "{self.conf_nginx_path.replace("\\", "/")}" -p "{self.nginx_path.replace("\\", "/")}"'''
        self._execute_command(command, "Nginx запущен.", log_file=self.nginx_log, wait=False)

    def stop_nginx(self):
        command = rf'"{self.nginx_path}\nginx.exe" -s stop -c "{self.conf_nginx_path.replace("\\", "/")}" -p "{self.nginx_path.replace("\\", "/")}"'
        self._execute_command(command, "Nginx остановлен.", log_file=self.nginx_log)

    def restart_nginx(self):
        self.stop_nginx()
        self.run_nginx()
        logging.info("Nginx перезапущен.")

    def run(self):
        self.run_php()
        self.run_apache()
        self.run_nginx()

    def stop(self):
        self.stop_nginx()
        self.stop_apache()
        self.stop_php()

    def restart(self):
        self.stop()
        self.run()


class Postgresql:
    def __init__(self, postgresql_path, project_path):
        self.is_running = False
        self.path = postgresql_path

        self.log_dir = os.path.join(project_path, "userdata", "logs")
        os.makedirs(self.log_dir, exist_ok=True)

        self.log_file = os.path.join(self.log_dir, "postgresql.log")
        logging.basicConfig(
            filename=self.log_file,
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )
        logging.info("Postgresql initialized")

    def run(self):
        if self.is_running:
            logging.info("PostgreSQL уже запущен.")
            return
        command = rf'"{self.path}\bin\pg_ctl.exe" start -D "{self.path}\data" -l "{self.log_file}"'
        self._execute_command(command, "PostgreSQL запущен.", wait=False)
        self.is_running = True

    def stop(self):
        if not self.is_running:
            logging.info("PostgreSQL уже остановлен.")
            return
        command = rf'"{self.path}\bin\pg_ctl.exe" stop -D "{self.path}\data"'
        success = self._execute_command(command, "PostgreSQL остановлен.")
        if success:
            self.is_running = False

    def restart(self):
        command = rf'"{self.path}\bin\pg_ctl.exe" restart -D "{self.path}\data" -l "{self.log_file}"'
        success = self._execute_command(command, "PostgreSQL перезапущен.")
        if success:
            self.is_running = True

    def run_pgadmin(self):
        command = rf'"{self.path}\pgAdmin 4\bin\pgAdmin4.exe"'
        self._execute_command(command, "pgAdmin 4 запущен.", wait=False)

    def _execute_command(self, command, success_message, wait=True):
        try:
            log_output = open(self.log_file, "a")
            if wait:
                process = subprocess.run(command, shell=True, stdout=log_output, stderr=log_output, text=True)
                log_output.close()
                if process.returncode == 0:
                    logging.info(success_message)
                    print(success_message)
                    return True
                else:
                    logging.error(f"Ошибка выполнения: {self.log_file}")
                    return False
            else:
                subprocess.Popen(command, shell=True, stdout=log_output, stderr=log_output)
                log_output.close()
                logging.info(success_message)
                return True
        except Exception as e:
            logging.error(f"Ошибка: {e}")
            print(f"Ошибка: {e}")
            return False


class MySQL:
    def __init__(self, mysql_path, project_path):
        self.is_running = False
        self.path = mysql_path

        self.log_dir = os.path.join(project_path, "userdata", "logs")
        os.makedirs(self.log_dir, exist_ok=True)

        self.log_file = os.path.join(self.log_dir, "mysql.log")
        logging.basicConfig(
            filename=self.log_file,
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )
        logging.info("MySQL initialized")

    def run(self):
        if self.is_running:
            logging.info("MySQL уже запущен.")
            return
        command = rf'"{self.path}\bin\mysqld.exe" --defaults-file="{self.path}\my.ini" --console'
        self._execute_command(command, "MySQL запущен.", wait=False)
        self.is_running = True

    def stop(self):
        if not self.is_running:
            logging.info("MySQL уже остановлен.")
            return
        command = rf'"{self.path}\bin\mysqladmin.exe" -u root shutdown'
        success = self._execute_command(command, "MySQL остановлен.")
        if success:
            self.is_running = False

    def restart(self):
        self.stop()
        self.run()
        logging.info("MySQL перезапущен.")

    def _execute_command(self, command, success_message, wait=True):
        try:
            log_output = open(self.log_file, "a")
            if wait:
                process = subprocess.run(command, shell=True, stdout=log_output, stderr=log_output, text=True)
                log_output.close()
                if process.returncode == 0:
                    logging.info(success_message)
                    print(success_message)
                    return True
                else:
                    logging.error(f"Ошибка выполнения: {self.log_file}")
                    return False
            else:
                subprocess.Popen(command, shell=True, stdout=log_output, stderr=log_output)
                log_output.close()
                logging.info(success_message)
                return True
        except Exception as e:
            logging.error(f"Ошибка: {e}")
            print(f"Ошибка: {e}")
            return False


class Redis:
    def __init__(self, redis_path, project_path):
        self.is_running = False
        self.path = redis_path

        self.log_dir = os.path.join(project_path, "userdata", "logs")
        os.makedirs(self.log_dir, exist_ok=True)

        self.log_file = os.path.join(self.log_dir, "redis.log")
        logging.basicConfig(
            filename=self.log_file,
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s"
        )
        logging.info("Redis initialized")

    def run(self):
        if self.is_running:
            logging.info("Redis уже запущен.")
            return
        command = rf'"{self.path}\redis-server.exe" "{self.path}\redis.conf"'
        self._execute_command(command, "Redis запущен.", wait=False)
        self.is_running = True

    def stop(self):
        if not self.is_running:
            logging.info("Redis уже остановлен.")
            return
        command = rf'"{self.path}\redis-cli.exe" shutdown'
        success = self._execute_command(command, "Redis остановлен.")
        if success:
            self.is_running = False

    def restart(self):
        self.stop()
        self.run()
        logging.info("Redis перезапущен.")

    def _execute_command(self, command, success_message, wait=True):
        try:
            log_output = open(self.log_file, "a")
            if wait:
                process = subprocess.run(command, shell=True, stdout=log_output, stderr=log_output, text=True)
                log_output.close()
                if process.returncode == 0:
                    logging.info(success_message)
                    print(success_message)
                    return True
                else:
                    logging.error(f"Ошибка выполнения: смотри {self.log_file}")
                    return False
            else:
                subprocess.Popen(command, shell=True, stdout=log_output, stderr=log_output)
                log_output.close()
                logging.info(success_message)
                return True
        except Exception as e:
            logging.error(f"Ошибка: {e}")
            print(f"Ошибка: {e}")
            return False
