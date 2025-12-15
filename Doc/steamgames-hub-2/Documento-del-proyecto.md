# Steamgames-hub-2

- **Grupo:** 3 (tarde)
- **Curso escolar:** 2025/2026
- **Asignatura:** Evolución y gestión de la configuración

## Miembros del equipo

Escala 1–10 de esfuerzo/implicación (10 = mayor implicación)

| Miembro                                                                 | Implicación |
| ----------------------------------------------------------------------- | ----------- |
| [Angeles Burgos, Julia Virginia](https://github.com/Juliangeles)        | 10          |
| [Benito Merchán, Manuel Jesús](https://github.com/ManuelJBM)            | 10          |
| [Fernández Noguerol, Francisco](https://github.com/FranciscoFernandezN) | 10          |
| [Gutiérrez Arazo, Beatriz](https://github.com/BPP4634)                  | 10          |
| [Morán Corbacho, José Javier](https://github.com/josmorcor3)            | 10          |
| [Ramos Vargas, Alba](https://github.com/albramvar1)                     | 10          |

## Enlaces de interés

- [Repositorio de código](https://github.com/steamgames-hub/steamgames-hub-2/)
- [Sistema desplegado](https://steamgames-hub-2.onrender.com/)

## Enlace a la documentación

- [Documentación principal]()
- [Gestión del código fuente](https://github.com/steamgames-hub/steamgames-hub-2/blob/trunk/Doc/steamgames-hub-2/Gesti%C3%B3n_del_c%C3%B3digo_fuente.md)
- [Documentación Workflows CI/CD](https://github.com/steamgames-hub/steamgames-hub-2/blob/trunk/Doc/steamgames-hub-2/Workflows_CI_CD.md)

## Indicadores del Proyecto

(debe dejar enlaces a evidencias que permitan de una forma sencilla analizar estos indicadores, con gráficas y/o con enlaces)

| Miembro del equipo | Horas | Commits | LoC | Test | Issues | Work Item         | Dificultad      |
| ------------------ | ----- | ------- | --- | ---- | ------ | ----------------- | --------------- |
| Apellidos, nombre  | HH    | XX      | YY  | ZZ   | II     | Descripción breve | H/M/L           |
| Apellidos, nombre  | HH    | XX      | YY  | ZZ   | II     | Descripción breve | H/M/L           |
| Apellidos, nombre  | HH    | XX      | YY  | ZZ   | II     | Descripción breve | H/M/L           |
| Apellidos, nombre  | HH    | XX      | YY  | ZZ   | II     | Descripción breve | H/M/L           |
| Apellidos, nombre  | HH    | XX      | YY  | ZZ   | II     | Descripción breve | H/M/L           |
| Apellidos, nombre  | HH    | XX      | YY  | ZZ   | II     | Descripción breve | H/M/L           |
| TOTAL              | tHH   | tXX     | tYY | tZZ  | tII    | Descripción breve | H (X)/M(Y)/L(Z) |

La tabla contiene la información de cada miembro del proyecto y el total de la siguiente forma:

- **Horas:** número de horas empleadas en el proyecto
- **Commits:** solo contar los commits hechos por miembros del equipo, no lo commits previos
- **LoC (líneas de código):** solo contar las líneas producidas por el equipo y no las que ya existían o las que se producen al incluir código de terceros
- **Test:** solo contar los test realizados por el equipo nuevos
- **Issues:** solo contar las issues gestionadas dentro del proyecto y que hayan sido gestionadas por el equipo
- **Work Item:** principal WI del que se ha hecho cargo el miembro del proyecto
- **Dificultad:** señalar el grado de dificultad en cada caso. Además, en los totales, poner cuántos se han hecho de cada grado de dificultad entre paréntesis.

## Integración con otros equipos

Equipos con los que se ha integrado y los motivos por lo que lo ha hecho y lugar en el que se ha dado la integración:

- Nombre-del-equipo: breve descripción de la integración
- Nombre-del-equipo: breve descripción de la integración
- Nombre-del-equipo: breve descripción de la integración

## Resumen ejecutivo (800 palabras aproximadamente)

Se sintetizará de un vistazo lo hecho en el trabajo y los datos fundamentales. Se usarán palabras para resumir el proyecto presentado.

## Descripción del sistema (1.500 palabras aproximadamente)

Se explicará el sistema desarrollado desde un punto de vista funcional y arquitectónico. Se hará una descripción tanto funcional como técnica de sus componentes y su relación con el resto de subsistemas. Habrá una sección que enumere explícitamente cuáles son los cambios que se han desarrollado para el proyecto.

## Visión global del proceso de desarrollo (1.500 palabras aproximadamente)

Debe dar una visión general del proceso que ha seguido enlazándolo con las herramientas que ha utilizado. Ponga un ejemplo de un cambio que se proponga al sistema y cómo abordaría todo el ciclo hasta tener ese cambio en producción. Los detalles de cómo hacer el cambio vendrán en el apartado correspondiente.

## Entorno de desarrollo

### Configuración principal del equipo

Este proyecto puede funcionar en diversos entornos debido a la flexibilidad que proporciona, pero los miembros de este equipo han usado la siguiente configuración para su uso en local:

1. Un sistema operativo basado en Linux, en este caso, todo el equipo ha usado Ubuntu, entre las versiones 24.04.1 y 24.04.03 (última en el momento de la redacción de este documento)
2. Un IDE moderno, como es Visual Studio Code, en su versión `1.105.1`, junto con las extensiones que cada uno haya deseado. Debido a que ninguna extensión es **ESTRICTAMENTE NECESARIA**, no se detallarán en este apartado. Además, también se necesita acceso a una consola o CLI.
3. Una configuración de variables de entorno adecuadas para el funcionamiento en local, lo que **DEBE INCLUIR**:
- El nombre de la aplicación: `Steamgameshub.IO` en `FLASK_APP_NAME` y demás variables de entorno necesarias para una aplicación de flask, como son `FLASK_APP` y `FLASK_ENV`, en este caso con `app` y `development`, respectivamente.
- El dominio a usar cuando la aplicación arranque: `localhost:5000` en `DOMAIN`
- La configuración para conectarse con la base de datos de mariadb: puerto, nombre de la base de datos, usuario y contraseña. Estas variables se detallarán en el siguiente apartado.
- Una url ficticia para fakenodo en `FAKENODO_URL`, donde se ha usado `fakenodo.org`
- Las credenciales necesarias para poder enviar correos tanto para el 2FA como para la verificación del email y para almacenar ficheros en remoto en AWS (aunque esto último **NO INFLUYE PARA EL DESPLIGUE EN LOCAL**).
4. Una instalación limpia de Python 3.12.3, con su posterior instalación de dependencias con `pip install -r requirements.txt`
5. Una instalación y puesta en marcha del servicio de MariaDB consecuentes con las variables de entorno elegidas.

Una vez ejecutado todo este proceso, el equipo de trabajo ha trabajado en el proyecto siguiendo una serie de pasos:

1. Ejecutar migraciones (si existieran) con el servicio de MariaDB activado: `flask db upgrade`
2. Limpiar y poblar la base de datos: `rosemary db:reset` y `rosemary db:seed`
3. Arrancar la aplicación con `flask run --host=0.0.0.0 --debug --reload` y acceder a la url configurada en las variables de entorno.

### Correcto funcionamiento de la base de datos

Debido a que el sistema requiere una base de datos de MariaDB para funcionar en un sistema local, todo el equipo se ha instalado este servicio, configurándolo según la guía de [UVLHub](https://docs.uvlhub.io/installation/manual_installation), aunque a posteriori se le han hecho modificaciones en los nombres de las bases de datos para que sean `steamgameshubdb` y `steamgameshubdb_test` y por tanto, incluido esto en las variables de entorno de `MARIADB_DATABASE` y `MARIADB_TEST_DATABASE` respectivamente. El resto de variables de entorno y configuraciones se han dejado por defecto tal y como se dice en la guía.

### Otras configuraciones (con Docker y Vagrant)

Además, algunos integrantes del equipo han usado Docker para su entorno de desarrollo. Para esto, únicamente es necesario tener instalado Docker y corroborar que exista una variable de nombre `WORKING_DIR` apuntando a la carpeta `/app/` y quqe el nombre de la base de datos se llame `db`. Esto es debido a como están diseñados los Dockerfile del proyecto.

Una vez se verifique lo anterior, se puede arrancar el proyecto con Docker de la siguiente manera: `docker compose -f docker/docker-compose.dev.yml up -d `.

A su vez, el proyecto también se puede usar con una máquina virtual (Vagrant), pero ningún miembro la ha usado activamente. De todas formas, la configuración para poder usar Vagrant en muy sencilla, únicamente hay que verificar que la variable de entorno `WORKING_DIR` apunte a la carpeta `/vagrant/`. 

Una vez hecho esto, suponiendo que se tiene instalado Vagrant, Ansible y VirtualBox, un simple comando dentro de la carpeta `/vagrant/` arranca automaticamente la máquina virtual: `vagrant up`.

### API keys necesarias

Si bien el proyecto proporciona una serie de variables de entorno que en principio debieran ser "Plug-and-Play" en la raíz, el proyecto, tal y como se ha mencionado antes, requiere de API keys para funcionar, estas API keys (se incluyen en [este enlace](https://uses0-my.sharepoint.com/:f:/r/personal/albramvar1_alum_us_es/Documents/steamgames-hub-env?csf=1&web=1&e=SuQXbM) ya que no se pueden subir directamente a GitHub). Estas API keys son las siguientes:

- `AWS_ACCESS_KEY_ID` y `AWS_SECRET_ACCESS_KEY`, correspondientes con la conexión de AWS S3 para almacenar ficheros, siempre y cuando no se trate de un despliegue local. Claves que se complementan con `S3_BUCKET` y `S3_REGION`. 

- Para el email, las variables de entorno necesarias son:
    #### Para el 2FA
    - `FROM_EMAIL`, `MAIL_DEFAULT_SENDER` y `MAIL_USER`, con el correo usado como remitente, en este caso `noreply.steamgameshub@gmail.com`.
    - `MAIL_PASSWORD` y `MAIL_USERNAME`, con las claves necesarias para iniciar sesión en el correo anterior.
    - `MAIL_PORT`, `MAIL_USE_TLS` y `MAIL_PORT`

    #### Para la verficación del email
    - `SECRET_KEY`, `SECURITY_PASSWORD_SALT` y `SENDGRID_API_KEY`, con los valores que proporciona Sendgrid para poder enviar emails.

    Estas variables son muchas debido a que cada grupo ha integrado de una manera distinta el envío de correos.

### Puesta en marcha mejorada

Debido a que este proceso puede llegar a ser engorroso y, sobre todo, repetitivo si se instala en varias máquinas, se ha desarrollado una serie de scripts que facilitan y automatizan este proceso. Estos scripts son los denominados como `set-up-local.sh`, `set-up-docker.sh` y `set-up-vagrant.sh`. 

## Ejercicio de propuesta de cambio

Se presentará un ejercicio con una propuesta concreta de cambio en la que a partir de un cambio que se requiera, se expliquen paso por paso (incluyendo comandos y uso de herramientas) lo que hay que hacer para realizar dicho cambio. Debe ser un ejercicio ilustrativo de todo el proceso de evolución y gestión de la configuración del proyecto.

## Conclusiones y trabajo futuro

### Conclusiones
- El proyecto ha alcanzado los objetivos funcionales planteados: gestión de usuarios, subida y descarga de ficheros, gestión de datasets y mecanismos básicos de verificación y 2FA. Las funcionalidades implementadas son coherentes con los requisitos y han sido validadas mediante tests unitarios e integración.
- La arquitectura modular facilita la extensión y el mantenimiento: cada módulo (auth, dataset, hubfile, profile, etc.) está claramente separado y documentado, lo que ha permitido trabajar en paralelo en varias partes del sistema.
- Se ha logrado un nivel de automatización (scripts de arranque, seeds, y pruebas locales) que acelera la puesta en marcha del entorno de desarrollo y unos workflows que permiten detectar bugs y errores temprano.
- La integración entre equipos ha sido complicada, sobre todo, por no tener claro desde el principio la manera de proceder entre nosotros.

### Trabajo futuro
- Calidad y pruebas: aumentar la cobertura de tests (unitarios, selenium, carga, etc.).
- Mejorar la interfaz gŕafica de la aplicación y unificar el estilo.
- CI/CD: añadir nuevos workflows y mejorar aquellos existentes, workflows de integración y despliegue automatizados.
- Rendimiento y escalabilidad: optimizar manejo de ficheros grandes (streaming, chunked uploads), mejorar cache y consultas a la base de datos, y añadir métricas.
- Robustez y experiencia de usuario: mejorar validaciones en formularios, mensajes de error más bonitos, accesibilidad y añadir idiomas (i18n).
- Documentación y onboarding: añadir guías más completas y mejorar el README.md

Estas propuestas priorizan la estabilidad, la seguridad y la facilidad de mantenimiento, dejando más de lado el aumento de las funcionalidades para el siguiente curso de desarrollo.