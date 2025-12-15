# steamgames-hub-1

## Información del proyecto

- **Nombre del proyecto:** steamgames-hub-1
- **Grupo:** 3
- **Curso escolar:** 2025/2026
- **Asignatura:** Evolución y gestión de la configuración

---

## Miembros del equipo


| Nombre completo |
|-----------------|
| Artero Bellido, Manuel |
| Calderón Rodríguez, Manuel María |
| Jiménez Lara, Raimundo |
| Luque Buzón, Álvaro |
| Márquez Gutiérrez, José Manuel |
| Salazar Caballero, Alberto |

---

## Resumen de reuniones

| Concepto | Valor |
|----------|-------|
| **Total de reuniones (TR)** | 9 |
| **Total de reuniones presenciales (TRP)** | 4 |
| **Total de reuniones virtuales (TRV)** | 5 |
| **Total de tiempo empleado en reuniones presenciales (TTRP)** | 6 horas |
| **Total de tiempo empleado en reuniones virtuales (TTRV)** | 7.5 horas |

---

## Actas de acuerdos

### ACTA 2025-01 (Acta Fundacional)

**Fecha:** 18 de octubre de 2025  
**Modalidad:** Presencial  
**Duración:** 2 horas

**Asistentes:**
- Manuel Artero Bellido
- Manuel María Calderón Rodríguez
- Raimundo Jiménez Lara
- Álvaro Luque Buzón
- José Manuel Márquez Gutiérrez
- Alberto Salazar Caballero

**Acuerdos tomados:**

| Acuerdo | Descripción |
|---------|-------------|
| **2025-01-01** | Se establece el nombre del proyecto como "steamgames-hub-1" |
| **2025-01-02** | Se define la política de gestión de ramas: trunk-based development con ramas feature/, bugfix/ y hotfix/ |
| **2025-01-03** | Se adopta la convención de commits semántica (feat:, fix:, docs:, chore:, refactor:, test:) |
| **2025-01-04** | Se establece el uso de GitHub Projects para la gestión de Work Items e Issues |
| **2025-01-05** | Se acuerda realizar reuniones semanales de seguimiento |
| **2025-01-06** | Se define el stack tecnológico: Flask, MariaDB, Selenium para tests E2E |
| **2025-01-07** | Se establece el flujo de CI/CD con GitHub Actions para tests unitarios, de integración y Selenium |

---

### ACTA 2025-02

**Fecha:** 25 de octubre de 2025  
**Modalidad:** Virtual  
**Duración:** 1.5 horas

**Asistentes:**
- Manuel Artero Bellido
- Manuel María Calderón Rodríguez
- Raimundo Jiménez Lara
- Álvaro Luque Buzón
- José Manuel Márquez Gutiérrez
- Alberto Salazar Caballero

**Acuerdos tomados:**

| Acuerdo | Descripción |
|---------|-------------|
| **2025-02-01** | Se asignan los módulos principales: dataset, auth, explore, community, profile, team |
| **2025-02-02** | Se implementará autenticación con verificación de email y 2FA opcional |
| **2025-02-03** | Se establece la estructura de la base de datos con migraciones Alembic |
| **2025-02-04** | Se acuerda documentar los workflows de CI/CD |

---

### ACTA 2025-03

**Fecha:** 1 de noviembre de 2025  
**Modalidad:** Virtual  
**Duración:** 1.5 horas

**Asistentes:**
- Manuel Artero Bellido
- Manuel María Calderón Rodríguez
- Raimundo Jiménez Lara
- Álvaro Luque Buzón
- José Manuel Márquez Gutiérrez
- Alberto Salazar Caballero

**Acuerdos tomados:**

| Acuerdo | Descripción |
|---------|-------------|
| **2025-03-01** | Se implementa el módulo de datasets con funcionalidad de upload y versionado |
| **2025-03-02** | Se añade integración con Fakenodo para simular la API de Zenodo |
| **2025-03-03** | Se crean tests unitarios y de integración para el módulo dataset |
| **2025-03-04** | Se implementa el historial de versiones de datasets (commit: `5cc58e9`) |

---

### ACTA 2025-04

**Fecha:** 8 de noviembre de 2025  
**Modalidad:** Presencial  
**Duración:** 1.5 horas

**Asistentes:**
- Manuel Artero Bellido
- Manuel María Calderón Rodríguez
- Raimundo Jiménez Lara
- Álvaro Luque Buzón
- José Manuel Márquez Gutiérrez
- Alberto Salazar Caballero

**Acuerdos tomados:**

| Acuerdo | Descripción |
|---------|-------------|
| **2025-04-01** | Se añade visualización de versiones en el detalle del dataset |
| **2025-04-02** | Se crea funcionalidad de rollback a versiones anteriores |
| **2025-04-03** | Se mejora la UI del módulo public con CTAs adaptadas a SteamGamesHub |
| **2025-04-04** | Se implementan tests de Selenium para el módulo public y datasets relacionados |
| **2025-04-05** | Se añade workflow de GitHub Actions para tests de Selenium |

---

### ACTA 2025-05

**Fecha:** 15 de noviembre de 2025  
**Modalidad:** Virtual  
**Duración:** 1.5 horas

**Asistentes:**
- Manuel Artero Bellido
- Manuel María Calderón Rodríguez
- Raimundo Jiménez Lara
- Álvaro Luque Buzón
- José Manuel Márquez Gutiérrez
- Alberto Salazar Caballero

**Acuerdos tomados:**

| Acuerdo | Descripción |
|---------|-------------|
| **2025-05-01** | Se implementa creación, edición y borrado de draft-datasets |
| **2025-05-02** | Se añaden tests de carga con Locust para profile y fakenodo |
| **2025-05-03** | Se mejora la funcionalidad de trending datasets |
| **2025-05-04** | Se refactoriza feature model a dataset file |
| **2025-05-05** | Se implementa búsqueda por comunidades en el módulo explore |

---

### ACTA 2025-06

**Fecha:** 22 de noviembre de 2025  
**Modalidad:** Virtual  
**Duración:** 1.5 horas

**Asistentes:**
- Manuel Artero Bellido
- Manuel María Calderón Rodríguez
- Raimundo Jiménez Lara
- Álvaro Luque Buzón
- José Manuel Márquez Gutiérrez
- Alberto Salazar Caballero

**Acuerdos tomados:**

| Acuerdo | Descripción |
|---------|-------------|
| **2025-06-01** | Se añaden tests de integración para hubfile y dataset |
| **2025-06-02** | Se implementa funcionalidad completa de rollback de versiones de datasets |
| **2025-06-03** | Se corrigen errores de traducción (español a inglés) |
| **2025-06-04** | Se actualizan los tests de Selenium afectados por los cambios de idioma |

---

### ACTA 2025-07

**Fecha:** 29 de noviembre de 2025  
**Modalidad:** Presencial  
**Duración:** 1.5 horas

**Asistentes:**
- Manuel Artero Bellido
- Manuel María Calderón Rodríguez
- Raimundo Jiménez Lara
- Álvaro Luque Buzón
- José Manuel Márquez Gutiérrez
- Alberto Salazar Caballero

**Acuerdos tomados:**

| Acuerdo | Descripción |
|---------|-------------|
| **2025-07-01** | Se crea nueva pantalla de edición de datasets |
| **2025-07-02** | Se implementa integración con el equipo steamgameshub-2 |
| **2025-07-03** | Se documentan los manuales de instalación y despliegue |
| **2025-07-04** | Se corrigen bugs de versionado tras integración con equipos |
| **2025-07-05** | Se mejora la visualización de DOIs conceptuales y específicos |

---

### ACTA 2025-08

**Fecha:** 6 de diciembre de 2025  
**Modalidad:** Virtual  
**Duración:** 1.5 horas

**Asistentes:**
- Manuel Artero Bellido
- Manuel María Calderón Rodríguez
- Raimundo Jiménez Lara
- Álvaro Luque Buzón
- José Manuel Márquez Gutiérrez
- Alberto Salazar Caballero

**Acuerdos tomados:**

| Acuerdo | Descripción |
|---------|-------------|
| **2025-08-01** | Se introducen datasets de prueba con versiones para testing |
| **2025-08-02** | Se corrigen botones de timeline y rollback |
| **2025-08-03** | Se añade variable de entorno TWO_FACTOR_ENABLED |
| **2025-08-04** | Se corrigen todos los tests unitarios rotos |
| **2025-08-05** | Se arreglan tests de Selenium del módulo dataset |

---

### ACTA 2025-09

**Fecha:** 15 de diciembre de 2025  
**Modalidad:** Presencial  
**Duración:** 1 hora

**Asistentes:**
- Manuel Artero Bellido
- Manuel María Calderón Rodríguez
- Raimundo Jiménez Lara
- Álvaro Luque Buzón
- José Manuel Márquez Gutiérrez
- Alberto Salazar Caballero

**Acuerdos tomados:**

| Acuerdo | Descripción |
|---------|-------------|
| **2025-09-01** | Se realiza merge final de la rama bugfix a trunk |
| **2025-09-02** | Se verifican todos los workflows de CI/CD funcionando correctamente |
| **2025-09-03** | Se prepara el entorno para el despliegue en Render |
| **2025-09-04** | Se da por finalizado el desarrollo del proyecto |
| **2025-09-05** | Se documenta el resumen de reuniones y actas |
| **2025-09-06** | Se prepara la entrega final con toda la documentación |

---

## Resumen de funcionalidades implementadas

Basado en el historial de commits del proyecto (770 commits totales):

| Módulo | Funcionalidades principales |
|--------|----------------------------|
| **Dataset** | Upload, versionado, historial, rollback, edición, draft-datasets, trending |
| **Auth** | Login, registro, verificación de email, 2FA, cambio de contraseña |
| **Explore** | Búsqueda, filtros por comunidad, datasets relacionados |
| **Community** | Gestión de comunidades, asignación de datasets |
| **Profile** | Perfil de usuario, métricas personales |
| **Team** | Gestión de equipos |
| **Hubfile** | Gestión de archivos, metadata, versiones |
| **Fakenodo** | Simulación de API Zenodo para desarrollo |

## Infraestructura y CI/CD

- Workflows de GitHub Actions para tests unitarios
- Workflows para tests de integración
- Workflows para tests de Selenium
- Despliegue configurado para Docker y Render
- Configuración de Vagrant para desarrollo local

