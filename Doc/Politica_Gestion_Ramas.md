# Política de Gestión de Ramas y Versionado

Este documento describe la estrategia de ramificación (branching) y versionado del proyecto, diseñada para garantizar un flujo de desarrollo ordenado y despliegues controlados.

---

## 1. Ramas Principales

Existen dos ramas principales con roles y restricciones específicas:

### Rama `main`
-   **Propósito**: Refleja el **código de producción**. Cada commit en `main` corresponde a una versión estable y desplegada de la aplicación.
-   **Flujo de trabajo**:
    -   **No se admiten Pull Requests directos a `main`**.
    -   Para lanzar una nueva versión, un miembro autorizado del equipo debe fusionar la rama **`Trunk`** en su copia local de **`main`** y luego empujar los cambios al repositorio remoto.
    -   Cada push a **`main`** activa el workflow automático de versionado semántico y crea una **etiqueta (tag)** y una release asociada a la versión correspondiente (ej. v1.2.3).
-   **CI/CD**: El push de una nueva etiqueta en **`main`** dispara los pipelines de CI/CD para ejecutar pruebas finales y realizar el **despliegue en el entorno de producción**.

### Rama `Trunk`
-   **Propósito**: Es la rama principal de **integración y desarrollo**. Contiene los cambios más recientes que han sido probados y están listos para ser incluidos en la próxima versión.
-   **Flujo de trabajo**:
    -   Integra los cambios provenientes de las ramas de desarrollo (`feature/Task.xyz`).
    -   La integración de ramas internas del equipo se realiza exclusivamente mediante **merges locales**, **no mediante Pull Requests**
    -   Los **Pull Requests** solo se utilizan para contribuciones externas provenientes de otros forks de **uvlhub**.
-   **CI/CD**: Cada vez que se fusiona un cambio en `Trunk`, se ejecutan automáticamente los pipelines de CI/CD que incluyen:
    -   Ejecución de pruebas unitarias y de integración.
    -   **Despliegue en el entorno de pre-producción** para validación.

---

## 2. Ramas de Desarrollo y Soporte

### Ramas de Funcionalidad (`feature`)
-   **Nomenclatura**: `feature/Task.xyz`, donde `xyz` es el identificador único del Work Item (Task) asociado.
-   **Propósito**: Desarrollar nuevas funcionalidades o tareas de forma aislada.
-   **Flujo de trabajo**:
    1.  Se crean a partir de la rama `Trunk`.
    2.  Una vez completado el desarrollo y el testing relacionado, se realizará de manera local un merge a Trunk.
    3.  Tras la fusión, la rama `feature` se elimina.

### Rama de Corrección de Emergencia (`bugfix`)
-   **Propósito**: Solucionar errores críticos detectados en el **entorno de producción**.
-   **Flujo de trabajo**:
    1.  Se actualiza a partir de la rama `main`.
    2.  Una vez aplicada la corrección, se fusiona directamente en `main` y se crea una nueva etiqueta de versión **PATCH** (ej. `v1.2.2` -> `v1.2.3`).
    3.  Inmediatamente después, la corrección **debe ser fusionada también en `Trunk`** para evitar regresiones en futuros despliegues.

---

## 3. Estrategia de Versionado

Se utiliza el **Versionado Semántico (SemVer)** con el formato `MAJOR.MINOR.PATCH`.

-   **MAJOR**: Se incrementa para cambios incompatibles con versiones anteriores (breaking changes).
-   **MINOR**: Se incrementa al añadir nuevas funcionalidades de forma compatible.
-   **PATCH**: Se incrementa para correcciones de errores compatibles con versiones anteriores.

Las versiones se gestionan mediante etiquetas (tags) de Git en la rama `main`. Cada etiqueta es inmutable y representa una instantánea exacta del código en producción.
