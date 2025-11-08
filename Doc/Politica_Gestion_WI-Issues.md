# Política de Gestión de Work Items (WI) / Issues

Este documento establece las directrices para la creación, gestión y cierre de Work Items (WIs) e Issues en el proyecto, asegurando un flujo de trabajo claro y una asignación de responsabilidades definida.

---

## 1. Creación y Asignación

### Creación de un WI/Issue
-   **Título Claro y Específico**: Debe resumir el objetivo de la tarea o el problema a resolver.
-   **Descripción Detallada**: Incluir contexto, y requisitos. Si es un bug, añadir pasos para reproducirlo.

### Asignación de Roles
-   A cada WI/Issue se le asignarán **dos miembros** del equipo:
    1.  **Responsable (Developer)**: La persona que implementará la solución o desarrollará la funcionalidad.
    2.  **Revisor (Tester)**: La persona que validará y probará la implementación antes de su cierre.

### Tipos de WI/Issue
Se deben utilizar las siguientes etiquetas para clasificar el trabajo:
-   `feature`: Una nueva funcionalidad.
-   `task`: Una tarea específica que no es una `feature` ni un `bug`.
-   `bug`: Un error o fallo en el código existente.
-   `docs`: Tareas relacionadas con la documentación.

### Etiquetas de Dificultad
La prioridad y el esfuerzo se definen con las siguientes etiquetas:
-   `difficulty: mandatory`: Tarea obligatoria para cumplir con los requisitos del hito y de alta prioridad.
-   `difficulty: high`: Tarea de alta complejidad.
-   `difficulty: medium`: Tarea de dificultad media.
-   `difficulty: low`: Tarea de menor impacto.

---

## 2. Flujo de Trabajo

Los WIs/Issues seguirán un flujo de trabajo con cuatro estados principales:

1.  **`ToDo`**
    -   **Significado**: La tarea está definida y asignada, pero el desarrollo aún no ha comenzado.
    -   **Acción**: El responsable puede empezar a trabajar en ella cuando esté listo.

2.  **`In Progress`**
    -   **Significado**: El **responsable (developer)** está trabajando activamente en la implementación.
    -   **Acción**: El desarrollador crea una rama `feature/Task.xyz` y empieza a codificar.

3.  **`In Review`**
    -   **Significado**: El desarrollo ha finalizado y la tarea está lista para ser validada por el **revisor (tester)**.
    -   **Acción**: El desarrollador abre un Pull Request a `Trunk`. El revisor clona la rama, realiza las pruebas necesarias y verifica que se cumplen los requisitos.

4.  **`Closed`**
    -   **Significado**: La tarea ha sido implementada, probada y el código correspondiente se ha fusionado en la rama `Trunk`.
    -   **Acción**: El estado se actualiza automáticamente.

---

## 3. Cierre de Issues

-   **Cierre Automático**: Un WI/Issue se cierra automáticamente cuando un commit que contiene la palabra clave `closes` seguida de la referencia del issue (ej. `closes #123`) se fusiona en la rama `Trunk`.
-   **Ejemplo de Mensaje de Commit**:
    ```
    feat(profile): añade la subida de avatares de usuario

    Implementa la funcionalidad para que los usuarios puedan subir
    y cambiar su imagen de perfil.

    closes #45
    ```
-   **Responsabilidad**: Es responsabilidad del **tester** incluir el mensaje de cierre en el commit final.