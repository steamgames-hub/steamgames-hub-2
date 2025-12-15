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

## Descripción del sistema

Steamgames-Hub al haber tomado como base el proyecto de UVL-Hub, su base funcional radica de este, pero nosotros como equipo hemos mejorado el sistema añadiendo diversas features de las que se hablarán posteriormente. Steamgames-Hub esta levantado mediante el microframework de Flask y se compone además de varias API RESTs como son las correspondientes a la plataforma de repositorio abierto de Zenodo y el sistema de análisis de modelos de variabilidad (o Feature Models) Flamapy y un "local storage" con una base de datos gestionada por MariaDB. El sistema se encuentra desplegado en Docker, Vagrant, Render y por supuesto en local.

La arquitectura del sistema se dispone de forma modular y su núcleo lo conforma principalmente el módulo de dataset y el módulo de auth que controla el inicio de sesión, los roles y a que tiene acceso cada usuario, además de restringir las principales funcionalidades de los dataset si no estas registrado o has hecho login. En cuanto al funcionamiento y relación entre los distintos elementos y clases del sistema, se trabaja mediante peticiones HTTP que son procesadas por el servidor y este ejecutará las distintas funciones que posee siguiendo siempre la misma forma (independientemente del módulo ya que todos están creados con la misma plantilla): la petición HTTP se resume en una ruta o url, que proviene del html propio de la página y que será atendida por el archivo routes.py donde se recogen todas las posibles rutas a las que se puede acceder y a su vez este realizará una serie de procesos apoyados en el archivo services.py (archivo en el que se recogen una serie de funciones útiles y necesarias para el sistema) para responder a esa petición de manera satisfactoria. De la misma forma, service.py, se apoya en los archivos forms.py (archivo para el procesado de información a través de formularios) y repositories.py (archivo donde se procesan las queries y se maneja la información que le llega a la base de datos), este último sabiendo como enviar la información gracias al archivo models.py, quien es el que estructura toda la información del sistema y se encarga del manejo de las tablas de la base de datos. Tras esto podemos ver que los módulos estan organizados en 3 niveles: el nivel de vista o interfaz, que es el que recoge las peticiones mandadas por el usuario; el nivel de controladores, que son los que procesan estas peticiones y realizan las distintas funciones; y el nivel modelo, que es donde se procesan todos los datos y está directamente conectado con la base de datos.

Pasando ya la parte más específica del sistema desarrollado, veremos cúales han sido las implementaciones hechas por el grupo. Primero hablaremos de las features obligatorias y posteriormente de las seleccionadas por el equipo.

### MANDATORY FEATURES

Estas features fueron realizadas por equipo de Steamgames-Hub-1, pero son necesarias para la base del sistema:

 - **WI-103-Fakenodo - Fictitious service to simulate Zenodo**: Este work-item se trata de crear un servicio falso (un mock) que simule el comportamiento básico de la API de Zenodo para que así podamos trabajar y probar el funcionamiento de la supuesta integración de la API sin tener que depender del propio servicio de Zenodo. De manera más específica se requiere de el servicio simplemente pueda crear un registro que devuelva una supuesta respuesta diciendo que se ha subido bien, que pueda subir archivos individuales pertenecientes a los datasets y que se puedan ver las distintas versiones de los archivos. Además si se editan los metadatos de algun registro, se deberá mantener el anterior DOI, pero si se cambia o añade algún fichero y se publica, se deberá crear una nueva versión del registro.

 - **WI-104-Newdataset - Evolving uvlhub into a "[datatype]hub"**: Este work-item se trata de reestructurar el sistema de forma que ya no esté enfocado en datasets de tipo UVL, sino que ahora se admitan datasets de distintos tipos, como por ejemplo UML, BPM o el nuestro propio. Reestructurar el sistema significa cambiar los tipos de datasets y para ello se hará uso del base (BaseDataset) como guía, además para cada modelo de datos se tendrá que crear su propia lógica y cada módulo su propio workflow.

### SPECIFIC FEATURES

Las siguientes features son las elegidas por el equipo de Steamgames-Hub-2 y por tanto se decidión no realizar las mismas para tener un sistema conjunto más completo y complejo.

 - **WI-105 - Add download counter for datasets**: El objetivo de este work-item es poder ver cuantas veces ha sido descargado un dataset y para ello se deberá de aumentar en 1 el contador de descargas cada vez que se realice una. Para ello se tendrás que hacer:

    - Añadir un nuevo campo en el model de los dataset que sea el contador (incialmente a 0).
    - Incrementar el contador con cada descarga.
    - Mostrar este valor en los detalles del dataset.
    - Añadir un endpoint (/datasets/{id}/stats) que devuelva este número y otros estadísticas relevantes.

 - **WI-75 - Verification email**: Cada usuario al registrarse debe recibir un email de verificación en su cuenta para poder registrarse en el sistema. Para ello se deberá poder mandar el mensaje al correo generando un token y al verificarse, se checkeará que dicho token es correcto.

 - **WI-77 - Admin roles**: Los administradores deben de ser capaces de asignar roles a todos los usuarios para poder gestionar los permisos de la plataforma y deben poder gestionar todo el sistema. Para ello se deberá hacer:

    - Implementar los distintos roles en backend: Administrador (Acceso a todo el sistema), Curator (Notifican a los administradores de errores), Usuarios y Guests.
    - Mostrar el rol en la parte superior de la página.
    - Implementar en backend la operación de editar el perfil de un usuario.
    - Implementar en backend la operación de eliminar un dataset.
    - Implementar en frontend la operación de editar el perfil de un usuario.
    - Implementar en frontend la operación de eliminar un dataset.
    - Implementar en backend la operación de ascender o degradar los permisos de los usuarios.
    - Poder ver la lista de usuarios.
    - Implementar en backend la funcionalidad de notificar errores (Curators).
    - Implementar en frontend la funcionalidad de notificar errores (Curators).
    - Implementar en backend la funcionalidad de obtener las incidencias.
    - Implementar en frontend la funcionalidad de obtener las incidencias.
    - Implementar la funcionalidad de cerrar incidencias o reabrirlas.

 - **WI-68 - Draft dataset**: Un usuario debe poder guardar sus borradores de los datasets que quiera dejar y continuar más adelante, pero estos datasets no deben de ser visibles para el resto de usuarios. Para ello se deberá hacer:

    - En backend crear una propiedad de los datasets que nos permita saber que datasets son borradores.
    - Permitir en backend que se puedan eliminar los borradores.
    - Permitir en backend que se pueda editar un borrador.
    - Detectar en frontend que cuando se rellene un campo y abandones la pestaña actual te salte una confirmación para guardar un borrador del dataset que se esté rellenando.
    - Poder ver en un apartado la lista de borradores.
    - Crear una propiedad de los usuarios para que los borradores se guarden automáticamente y no pedir confirmación.
    - Dar la posibilidad de cambiar la preferencia de guardado automatico.
    - Crear en frontend la funcionalidad de editar los borradores y poder publicarlos.
    - Crear en frontend la funcionalidad de eliminar los borradores.

 - **WI-85 - Major versioning**: Se debe permitir realizar grandes cambios en tus datasets ya publicados, creando así una nueva versión de este y poder ver las anteriores. Para ello se deberá hacer:

    - Modificar el modelo de datos para que se admita el versionado.
    - Permitir editar tus datasets publicados.
    - Permitir añadir o quitar ficheros de un dataset publicado.
    - Permitir modificar los metadatos del dataset.
    - Conectar y trackear versiones anteriores del dataset.
    - Poder ver todas las versiones de los datasets en una timeline.

 - **WI-86 - Viewing versions of a dataset**: Se deber permitir ver a los usuarios los cambios realizados a los datasets a través de las distintas versiones, diferenciando entre versiones con cambios pequeños y grandes. Para ello se deberá hacer:

    - Crear en backend la diferenciación de versiones.
    - Ver esa diferenciación en la interfaz.
    - Crear en backend una lista de versiones.
    - Poder ver los detalles de las distintas versiones.

Con todo esto, el sistema ahora es mucho más completo, manejable y robusto.

## Visión global del proceso de desarrollo (1.500 palabras aproximadamente)

Debe dar una visión general del proceso que ha seguido enlazándolo con las herramientas que ha utilizado. Ponga un ejemplo de un cambio que se proponga al sistema y cómo abordaría todo el ciclo hasta tener ese cambio en producción. Los detalles de cómo hacer el cambio vendrán en el apartado correspondiente.

## Entorno de desarrollo (800 palabras aproximadamente)

Debe explicar cuál es el entorno de desarrollo que ha usado, cuáles son las versiones usadas y qué pasos hay que seguir para instalar tanto su sistema como los subsistemas relacionados para hacer funcionar el sistema al completo. Si se han usado distintos entornos de desarrollo por parte de distintos miembros del grupo, también debe referenciarlo aquí.

## Ejercicio de propuesta de cambio

Se presentará un ejercicio con una propuesta concreta de cambio en la que a partir de un cambio que se requiera, se expliquen paso por paso (incluyendo comandos y uso de herramientas) lo que hay que hacer para realizar dicho cambio. Debe ser un ejercicio ilustrativo de todo el proceso de evolución y gestión de la configuración del proyecto.

## Conclusiones y trabajo futuro

Se enunciarán algunas conclusiones y se presentará un apartado sobre las mejoras que se proponen para el futuro (curso siguiente) y que no han sido desarrolladas en el sistema que se entrega.