# Diario del Equipo

#### Versión 1.0 del documento

|                |                                         |
| -------------- | --------------------------------------- |
| **Asignatura** | Evolución y Gestión de la Configuración |
| **Curso**      | 2025/2026                               |
| **Proyecto**   | steamgames-hub-2                        |

| **Integrantes**               | **Correo**            |
| ----------------------------- | --------------------- |
| Julia Virginia Ángeles Burgos | julangbur@alum.us.es  |
| Manuel Jesús Benito Merchán   | manbenmer1@alum.us.es |
| Francisco Fernández Noguerol  | frafernog@alum.us.es  |
| Beatriz Gutiérrez Arazo       | beagutara@alum.us.es  |
| José Javier Morán Corbacho    | josmorcor3@alum.us.es |
| Alba Ramos Vargas             | albramvar1@alum.us.es |

<br>

## Resumen de total de reuniones empleadas en el equipo

- Total de reuniones: 3 reuniones
- Total de reuniones presenciales: 3 reuniones presenciales
- Total de reuniones virtuales: 0 reuniones virtuales
- Total de tiempo empleado en reuniones presenciales: 100 min
- Total de tiempo empleado en reuniones virtuales: 0 min

## Actas de acuerdos de las reuniones en las que se tomaron decisiones importantes

### ACTA 2025-01

- Asistentes: Julia Virginia Ángeles, Manuel Jesús Benito, Francisco Fernández, Beatriz Gutiérrez, Javier Morán y Alba Ramos.  

- Acuerdos tomados:

    - Acuerdo 2025-01-01:

        Se ha decidido actualizar nuestro repositorio mediante la estrategia cherry-pick para recibir los últimos cambios del fork de la asignatura. De esta manera, evitamos tener que volver a limpiar el historial de commits. Más aun cuando el número de commits que debemos recibir es solamente uno.

### ACTA 2025-02

- Asistentes: Julia Virginia Ángeles, Manuel Jesús Benito, Francisco Fernández, Beatriz Gutiérrez, Javier Morán y Alba Ramos.
- Acuerdos tomados:

    - Acuerdo 2025-02-01:
    
        Se ha decidido realizar un repositorio padre en la organización steamgames-hub que aúne los cambios de steamgames-hub-1 y steamgames-hub-2. De esto modo, el proyecto que entregemos por parte de los 2 equipos constará de las mismas funcionalidades y constituirá un único producto final.


### ACTA 2025-03

- Asistentes: Alba Ramos y Javier Morán.
- Acuerdos tomados:

    - Acuerdo 2025-03-01:
        
        Se han planificado y repartido las tareas para abordar los Work Items 85 y 86 de la siguiente manera:
        1. [**Francisco Fernández**] Modificar el modelo de dataset para que admita versiones.
        2. [**Alba Ramos**] Al crear un dataset que le asocie una version y comprobar inconsistencias. También que la ultima version de de un dataset tenga un conceptual doi y las anteriores un specific doi. Un conceptual doi seria el doi del dataset tal cual está ahora y el specific doi seria el doi más la version del dataset.
        3. [**Manuel Jesús Benito**] Interfaz para hacer nueva version. Hacer una nueva version de un dataset consiste en editar un dataset ya existente y añadirle ficheros o quitarle. Ademas se deben poder cambiar metadatos como la fecha y más cosas (ver la issue del wi en si para saber esto al completo). Por ultimo, poner un boton para dar a elegir al usuario si considera que los cambios que ha hecho son significativos para hacer una nueva version.
        4. [**Beatriz Gutiérrez**] Interfaz de historial de versiones y enlaces entre versiones, vista especifica (en forma de árbol).
        5. [**Julia Virginia Ángeles**] Frontend de listado de versiones en la vista del dataset.
        6. [**Javier Morán**] Rollback tanto en frontend como en backend. Esto es que exista la posibilidad de volver a la version anterior de un dataset.

        Así pues, tambíen se ha decidido que, como los Work Items 85 y 86 son muy parecidos en cuanto a la funcionalidad a desarrollar, se van a desarrollar como si se tratasen de un mismo Work Item.