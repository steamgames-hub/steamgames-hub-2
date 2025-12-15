# Convenciones para Mensajes de Commit

Este documento define las reglas para escribir mensajes de commit en este proyecto, basadas en **Conventional Commits 1.0.0**. Estas normas son aplicadas automáticamente por un hook de Git (`commit-msg`).

---

## Formato General

Cada mensaje de commit debe seguir una estructura clara para ser legible y fácil de procesar por herramientas automáticas.

### Estructura del Mensaje
```
tipo(scope opcional)!: descripción

[cuerpo opcional]

[footer opcional]
```

---

## 1. Cabecera (Primera Línea)

La primera línea del commit es la más importante y debe ser concisa y descriptiva.

**Formato:** `tipo(scope opcional)!: descripción`

-   **`tipo`**: Obligatorio. Indica la naturaleza del cambio.
-   **`scope`**: Opcional. Un sustantivo que describe la sección del código afectada (ej. `auth`, `database`, `ui`).
-   **`!`**: Opcional. Indica un **cambio rompedor (breaking change)**.
-   **`descripción`**: Obligatorio. Un resumen claro y conciso del cambio.

### Tipos Permitidos

Solo se pueden usar los siguientes tipos:

-   **feat**: Una nueva funcionalidad para el usuario.
-   **fix**: Una corrección de un error (bug).
-   **docs**: Cambios en la documentación (ej. README, guías).
-   **style**: Cambios de formato que no afectan al código (espacios, punto y coma, etc.).
-   **refactor**: Cambios en el código que no corrigen un error ni añaden una funcionalidad.
-   **perf**: Una mejora de rendimiento.
-   **test**: Añadir o corregir pruebas.
-   **build**: Cambios que afectan al sistema de build o a dependencias externas (ej. `npm`, `pip`).
-   **ci**: Cambios en los ficheros de configuración de CI (ej. GitHub Actions).
-   **chore**: Otras tareas que no modifican el código fuente o las pruebas (ej. actualización de `gitignore`).
-   **revert**: Revierte un commit anterior.

### Reglas de la Cabecera

1.  **Longitud máxima**: Se recomienda no superar los **72 caracteres**.
2.  **Sin punto final**: No debe terminar con un punto.

---

## 2. Cuerpo del Commit (Opcional)

El cuerpo se usa para explicar el **qué** y el **porqué** del cambio, no el cómo.

-   Debe estar separado de la cabecera por **una línea en blanco**.
-   Es útil para describir contextos complejos o justificar la solución elegida.

---

## 3. Footer y Breaking Changes

El footer se usa para añadir metadatos adicionales.

### Cambios Rompedores (Breaking Changes)

Si un commit introduce un cambio que rompe la compatibilidad hacia atrás, debe indicarse de dos maneras:

1.  Añadiendo un `!` después del `scope` en la cabecera.
2.  Añadiendo un bloque `BREAKING CHANGE:` en el footer que explique el cambio, cómo migrar y el motivo.

**Si se usa `!`, el footer `BREAKING CHANGE:` es obligatorio.**

---

## Excepciones

Los commits generados automáticamente por Git, como `Merge` o `Revert`, no necesitan seguir estas reglas.

---

## Ejemplos

**Commit simple (fix):**
```
fix(auth): corrige el flujo de validación de tokens JWT
```

**Commit con scope y descripción (feat):**
```
feat(search): añade la posibilidad de buscar productos por etiquetas
```

**Commit con cuerpo (refactor):**
```
refactor(core): simplifica la lógica del manejador de estado

Se elimina la gestión de estado manual en favor de una librería externa
para reducir la complejidad y mejorar la mantenibilidad.
```

**Commit con Breaking Change:**
```
refactor(api)!: elimina el endpoint obsoleto /v1/users

BREAKING CHANGE: El endpoint `/v1/users` ha sido eliminado.
Los clientes deben migrar a `/v2/accounts` para obtener la información de usuarios.
```