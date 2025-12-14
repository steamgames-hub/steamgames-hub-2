# Manual de despliegue de SteamGamesHub en Render

Render.com es una plataforma moderna de hosting y despliegue que abstrae la gestión de servidores. Permite ejecutar aplicaciones web, APIs, bases de datos y servicios estáticos con CI/CD integrado, escalado automático y certificados SSL gratuitos. Este documento describe cómo desplegar SteamGamesHub utilizando Render para la aplicación y Filess.io para la base de datos.

> **Resumen**
>
> - **Base de datos**: se despliega en Filess.io porque Render solo ofrece PostgreSQL sin costo.
> - **Aplicación**: se despliega en Render mediante la imagen Docker definida en `docker/images/Dockerfile.render`.

## Tabla de contenidos

1. [Parte 1: base de datos en Filess.io](#parte-1-base-de-datos-en-filessio)
   1. [Crear cuenta y servicio](#11-crear-cuenta-y-servicio)
   2. [Configurar parámetros](#12-configurar-parámetros)
2. [Parte 2: aplicación en Render](#parte-2-aplicación-en-render)
   1. [Acceder a Render](#21-acceder-a-render)
   2. [Crear el servicio web](#22-crear-el-servicio-web)
      1. [Opciones básicas](#221-opciones-básicas)
      2. [Configurar variables de entorno](#222-configurar-variables-de-entorno)
   3. [Verificar el despliegue](#23-verificar-el-despliegue)

---

## Parte 1: base de datos en Filess.io

Render solo ofrece soporte gratuito para PostgreSQL; para MariaDB utilizamos [Filess.io](https://filess.io/) como proveedor gestionado.

### 1.1. Crear cuenta y servicio

1. Regístrate o inicia sesión en Filess.io.
2. Haz clic en **+ New Database**.
3. Selecciona **MariaDB** como motor.
4. Escoge un nombre fácil de reconocer, por ejemplo `steamgameshubdb`.

Una vez creada la base de datos, podemos acceder a informaciondetallada sobre la misma

Anota la información de conexión (Connection Information). Será necesaria al definir las variables de entorno en Render.

> **Sugerencia**: crea una segunda base de datos para pruebas (por ejemplo `steamgameshub1db_test`) si planeas ejecutar migraciones o seeders diferenciados.

## Parte 2: aplicación en Render

### 2.1. Acceder a Render

1. Entra a [https://render.com](https://render.com) y haz clic en **Sign in**.
2. Se recomienda utilizar la cuenta de GitHub para enlazar fácilmente el repositorio.

### 2.2. Crear el servicio web

SteamGamesHub requiere una imagen Docker personalizada incluida en este repositorio.

#### 2.2.1. Opciones básicas

1. Desde el panel de Render selecciona **Dashboard → New → Web Service**.
2. En **Git Provider**, pega la URL del repositorio que deseas desplegar (tu fork o el oficial `https://github.com/steamgames-hub/steamgames-hub-1.git`). Si no aparece, ve a **Credentials → Configure GitHub** y otorga permisos.
3. Pulsa **Connect**.
4. Asigna un nombre con el formato `steamgameshub-<alias>` (por ejemplo, `steamgameshub-alicia`).
5. En **Project** puedes reutilizar uno existente o crear uno nuevo (por ejemplo, `steamgameshub`).
6. Selecciona **Docker** como lenguaje/plataforma.
7. Elige la región **Frankfurt (Central EU)** u otra cercana a tus usuarios.
8. Define la rama como `main`, salvo que quieras desplegar otra rama.
9. En **Dockerfile Path** indica `docker/images/Dockerfile.render`.
10. Para **Instance Type** puedes empezar con el plan **Free**.

#### 2.2.2. Configurar variables de entorno

Para evitar introducir variables una por una, Render permite cargarlas desde un archivo `.env`.

1. Dentro del apartado **Environment Variables**, elige **Add from .env**.
2. Copia y pega el siguiente bloque y luego reemplaza los valores marcados:

```env
FLASK_APP_NAME="SteamGamesHub.IO"
FLASK_ENV=production
FLASK_APP=app
SECRET_KEY=steamgameshub_dev_key_1234567890
DOMAIN=steamgameshub-<alias>.onrender.com
MARIADB_HOSTNAME=<HOST_DE_FILESS>
MARIADB_DATABASE=<DB_DE_FILESS>
MARIADB_USER=<USUARIO_DE_FILESS>
MARIADB_PORT=<PUERTO_DE_FILESS>
MARIADB_PASSWORD=<PASSWORD_DE_FILESS>
MARIADB_ROOT_PASSWORD=<PASSWORD_DE_FILESS>
WORKING_DIR=/app/
```

- Sustituye `<alias>` por tu identificador (por ejemplo, tu usuario de GitHub).
- Los valores `<HOST_DE_FILESS>`, `<DB_DE_FILESS>`, etc., provienen del panel de Filess.io.
- Si tus módulos añaden variables adicionales (AWS, SendGrid, etc.), inclúyelas manualmente, ya que en producción no estará disponible la CLI Rosemary ni el comando `rosemary compose:env`.

Cuando termines, haz clic en **Deploy Web Service**.

### 2.3. Verificar el despliegue

1. Render mostrará los logs del build y del arranque. Vigila la salida por si aparece algún error (dependencias, conexión a MariaDB, migraciones, etc.).
2. Una vez finalizado, deberías poder acceder a `https://steamgameshub-<alias>.onrender.com`.
3. El primer despliegue puede tardar hasta 5 minutos.

> Si el servicio no puede conectarse a MariaDB, revisa que la IP pública de Render esté autorizada en Filess.io (algunos planes requieren habilitar acceso desde cualquier origen o añadir la IP manualmente).
