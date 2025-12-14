# Manual de instalación de SteamGamesHub

> *Compatibilidad*: guía escrita para Ubuntu 22.04 LTS o superior.<br>
> *Versión de Python recomendada*: 3.12 o superior.

## Tabla de contenidos

1. [Actualizar el sistema](#1-actualizar-el-sistema)
2. [Clonar el repositorio](#2-clonar-el-repositorio)
3. [Instalar y preparar MariaDB](#3-instalar-y-preparar-mariadb)
   1. [Instalar el paquete oficial](#31-instalar-el-paquete-oficial)
   2. [Iniciar el servicio](#32-iniciar-el-servicio)
   3. [Asegurar la instalación](#33-asegurar-la-instalación)
   4. [Crear bases de datos y usuarios](#34-crear-bases-de-datos-y-usuarios)
4. [Configurar el entorno de la aplicación](#4-configurar-el-entorno-de-la-aplicación)
   1. [Variables de entorno](#41-variables-de-entorno)
5. [Instalar dependencias](#5-instalar-dependencias)
   1. [Crear y activar un entorno virtual](#51-crear-y-activar-un-entorno-virtual)
   2. [Instalar dependencias de Python](#52-instalar-dependencias-de-python)
   3. [Instalar Rosemary en modo editable](#53-instalar-rosemary-en-modo-editable)
6. [Ejecutar la aplicación](#6-ejecutar-la-aplicación)
   1. [Aplicar migraciones](#61-aplicar-migraciones)
   2. [Sembrar datos de prueba](#62-sembrar-datos-de-prueba)
   3. [Lanzar el servidor Flask de desarrollo](#63-lanzar-el-servidor-flask-de-desarrollo)
   4. [Ejecutar con Docker Compose](#64-ejecutar-con-docker-compose)
   5. [Ejecutar con Vagrant](#65-ejecutar-con-vagrant)

---

## 1. Actualizar el sistema

Asegúrate de que los paquetes del sistema estén al día antes de instalar dependencias.

```bash
sudo apt update -y
sudo apt upgrade -y
```

## 2. Clonar el repositorio

Si trabajas sobre tu propio fork (recomendado para contribuciones), clónalo mediante SSH:

```bash
git clone git@github.com:steamgames-hub/steamgames-hub-1.git
cd steamgames-hub-1
```

Para clonar el repositorio oficial través de HTTPS:

```bash
git clone https://github.com/steamgames-hub/steamgames-hub-1.git
cd steamgames-hub-1
```

## 3. Instalar y preparar MariaDB

SteamGamesHub necesita una base de datos relacional. Usaremos MariaDB.

### 3.1. Instalar el paquete oficial

```bash
sudo apt install mariadb-server -y
```

### 3.2. Iniciar el servicio

```bash
sudo systemctl start mariadb
```

### 3.3. Asegurar la instalación

Ejecuta el script de endurecimiento inicial y responde siguiendo los valores sugeridos:

```bash
sudo mysql_secure_installation
```

Valores recomendados:

- Enter current password for root (enter for none): Enter
- Switch to unix_socket authentication [Y/n]: y
- Change the root password? [Y/n]: y
  - New password: uvlhubdb_root_password
  - Re-enter new password: uvlhubdb_root_password
- Remove anonymous users? [Y/n]: y
- Disallow root login remotely? [Y/n]: y
- Remove test database and access to it? [Y/n]: y
- Reload privilege tables now? [Y/n]: y

> Puedes cambiar estas credenciales si lo deseas; recuerda mantener los mismos valores en tu archivo .env.

### 3.4. Crear bases de datos y usuarios

Ingresa a la consola de MariaDB e introduce la contraseña configurada en el paso anterior (uvlhubdb_root_password por defecto):

```bash
sudo mysql -u root -p
```

Dentro de la consola, crea las bases de datos y el usuario de desarrollo utilizados por SteamGamesHub:

```sql
CREATE DATABASE steamgameshub1db;
CREATE DATABASE steamgameshub1db_test;
CREATE USER 'steamgameshub1db_user'@'localhost' IDENTIFIED BY 'steamgameshub1db_password';
GRANT ALL PRIVILEGES ON steamgameshub1db.* TO 'steamgameshub1db_user'@'localhost';
GRANT ALL PRIVILEGES ON steamgameshub1db_test.* TO 'steamgameshub1db_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

## 4. Configurar el entorno de la aplicación

### 4.1. Variables de entorno

Copia el archivo de ejemplo y personaliza las variables según tu entorno (dominio, contraseñas, claves de AWS/SENDGRID si corresponde, etc.).

```bash
cp .env.local.example .env
```

Ajusta especialmente las variables relacionadas con MariaDB (MARIADB_HOSTNAME, MARIADB_DATABASE, MARIADB_USER, MARIADB_PASSWORD, MARIADB_ROOT_PASSWORD). De forma predeterminada, coinciden con los valores definidos en el script SQL anterior.

### 4.2. Ignorar modulo webhook

El módulo de webhook solo tiene sentido en una implementación que use Docker y en un entorno de preproducción. Para evitar problemas, indicamos que este módulo debe ser ignorado en la carga inicial de módulos añadiendo el nombre al archivo .moduleignore:

```bash
echo "webhook" > .moduleignore
```

## 5. Instalar dependencias

### 5.1. Crear y activar un entorno virtual

Instala el paquete de venv si aún no lo tienes y crea un entorno virtual basado en Python 3.12:

```bash
sudo apt install python3.12-venv -y
python3.12 -m venv venv
source venv/bin/activate
```

### 5.2. Instalar dependencias de Python

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 5.3. Instalar Rosemary en modo editable

Rosemary es la CLI incluida en este repositorio para automatizar tareas de desarrollo. Instálala en modo editable para que los cambios en rosemary/ se reflejen de inmediato:

```bash
pip install -e ./
```

Para comprobar la instalación:

```bash
rosemary
```

Deberías ver el listado de comandos disponibles (por ejemplo, db:seed).

## 6. Ejecutar la aplicación

### 6.1. Aplicar migraciones

```bash
flask db upgrade
```

### 6.2. Sembrar datos de prueba

```bash
rosemary db:seed
```

### 6.3. Lanzar el servidor Flask de desarrollo

```bash
flask run
```

Si todo ha ido bien, podrás acceder a SteamGamesHub en [http://localhost:5000](http://localhost:5000).

### 6.4. Ejecutar con Docker Compose

Docker Compose permite levantar la aplicación y sus dependencias (base de datos, Nginx, Selenium, etc.) de forma orquestada en contenedores.

#### 6.4.1. Variables de entorno para Docker

Antes de usar Docker, asegúrate de trabajar con las variables de entorno adecuadas:

```bash
cp .env.docker.example .env
```

#### 6.4.2. Instalar Docker y Docker Compose (Ubuntu)

En Ubuntu, puedes instalar Docker Engine y Docker Compose (como plugin de la CLI) con:

```bash
sudo apt update
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
   | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" \
   | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce

sudo usermod -aG docker ${USER}
mkdir -p ~/.docker/cli-plugins/

LATEST_VERSION=$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')

curl -SL "https://github.com/docker/compose/releases/download/${LATEST_VERSION}/docker-compose-$(uname -s)-$(uname -m)" \
   -o ~/.docker/cli-plugins/docker-compose

chmod +x ~/.docker/cli-plugins/docker-compose
```

> Tras ejecutar sudo usermod -aG docker ${USER}, cierra sesión y vuelve a entrar (o reinicia) para que se apliquen los cambios de grupo.

#### 6.4.3. Workflow principal con Docker Compose

Desde la raíz del proyecto, el flujo habitual de trabajo con Docker Compose es:

1. Parar cualquier servicio local que pueda estar usando el mismo puerto que la base de datos (típicamente MariaDB en 3306):

   ```bash
   sudo systemctl stop mariadb
   ```

2. Asegurarte de que no quedan contenedores en ejecución de una sesión previa:

   ```bash
   docker compose -f docker/docker-compose.dev.yml down
   ```

3. (Opcional) Eliminar el volumen de base de datos si quieres un entorno limpio de datos:

   ```bash
   docker volume rm docker_db_data
   ``` 

    Úsalo solo cuando quieras borrar todos los datos persistidos en la base de datos.

4. Levantar la pila completa en segundo plano, reconstruyendo las imágenes si es necesario:

   ```bash
   docker compose -f docker/docker-compose.dev.yml up -d --build
   ``` 

   Si no quieres reconstruir las imagenes (--build) ni lanzar en segundo plano (-d) puedes usar:
   ```bash
   docker compose -f docker/docker-compose.dev.yml up
   ``` 


5. Acceder a la aplicación a través de Nginx en [http://localhost](http://localhost).

6. Para detener todo y liberar recursos:

   ```bash
   docker compose -f docker/docker-compose.dev.yml down
   ``` 
Para ver contenedores en ejecución:

   ```bash
   docker ps
   ```
   
### 6.5. Ejecutar con Vagrant

El repositorio incluye un entorno Vagrant basado en Ubuntu 22.04 y provisionado con Ansible.
#### 6.5.1. Instalación de Vagrant, VirtualBox y Ansible

Instrucciones para instalar Vagrant, VirtualBox y Ansible sobre Ubuntu 22.04 (Jammy Jellyfish):

```bash
# Actualizar la lista de paquetes
sudo apt update

# Instalar vagrant, ansible y virtualbox
sudo apt install vagrant ansible virtualbox -y
```

Si el paquete `vagrant` no está disponible en los repositorios oficiales de Ubuntu, tendrás que añadir manualmente el repositorio oficial de HashiCorp y su clave GPG:

```bash
wget -O - https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install vagrant ansible virtualbox -y
```

#### 6.5.2. Configurar las variables de entorno

Antes de iniciar la máquina virtual, copia el archivo de variables de entorno específico para Vagrant:

```bash
cp .env.vagrant.example .env
```

#### 6.5.3. Iniciar la máquina virtual

Inicia la máquina virtual desde el subdirectorio `vagrant`:

```bash
cd vagrant
vagrant up
```

#### 6.5.4. Ejecutar comandos dentro de la VM

Para ejecutar comandos adicionales dentro de la VM:

```bash
vagrant ssh
```

#### 6.5.5. Acceder a la aplicación

La app expone el puerto 5000 al host (ver `Vagrantfile`), por lo que podrás acceder en [http://localhost:5000](http://localhost:5000).

#### 6.5.6. Apagar o eliminar la VM

Para apagar o limpiar el entorno:

```bash
vagrant halt    # Apagar manteniendo la VM
vagrant destroy # Eliminar la VM y sus discos
```
