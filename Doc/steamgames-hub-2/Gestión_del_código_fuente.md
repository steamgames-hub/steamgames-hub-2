# Política de gestión del código fuente

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

## Gestión de commits
 
Para este proyecto se ha decidido seguir las siguientes pautas en cuanto a a la gestión de los commits se refiere.

En primer lugar, para escribir los mensajes de commits vamos a emplear la especificación conventional commits. De este modo, los mensajes de commits deben seguir la siguiente estructura.

```markdown
    <tipo>: <descripción>
    <cuerpo>
```

El campo tipo debe comenzar obligatoriamente por uno de los siguientes prefijos: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore` o `revert`. Además, el cuerpo debe finalizar con uno de los siguientes prefijos: `Refs:`, `Closes:`, `Fixes:` seguido de #xx, siendo xx el número de la issue a la que está vinculado el commit. Todo esto se valida automáticamente mediante un hook que hemos configurado.

Por último, siempre que sea posible la fusión de ramas se realizará mediante fast-forward. Si existen conflictos o la rama de destino tiene commits adicionales, se realizará una fusión generando un commit de merge.

## Gestión de ramas

La gestión de ramas sigue el modelo propuesto en la asignatura, conocido como E.G.C. flow. En él distinguimos cuatro tipos de ramas:

1. Rama `main` <br> Rama principal y única en el repositorio que solo será actulizada desde la rama trunk con el objetivo de lanzar una nueva versión de la aplicación. La versión contará con una tag y una release.

2. Rama `trunk` <br> Actúa como rama de preproducción. Recibe todo el desarrollo procedente de las ramas feature task. Se actualiza de forma continua cada vez que finalizamos una tarea.

3. Ramas `feature task` <br> Son ramas específicas para el desarrollo de nuevas funcionalidades o tareas concretas. Cada nueva tarea parte desde trunk y vuelve a integrarse en ella una vez completada.

4. Rama `bugfix` <br> Existe una única rama de este tipo, destinada exclusivamente a corregir errores detectados en la rama trunk. Su objetivo es centralizar y simplificar la gestión de arreglos.

## Gestión de incidencias

Cuando se recibe una incidencia, Beatriz Gutiérrez y Javier Morán, como coordinadores del equipo, se encargan de evaluarla y planificar el trabajo necesario para su resolución. Para ello, crean una tarea de trabajo no planificada y la asignan a cualquier miembro del equipo que pueda dedicar tiempo a resolverla en ese momento.

Además, el equipo ha implementado un sistema de priorización para identificar qué tareas requieren mayor atención. En este sentido, se utilizan etiquetas de prioridad: alta, media y baja, que permiten gestionar de forma eficiente los esfuerzos del equipo y asegurar que las incidencias más críticas se resuelvan primero.
