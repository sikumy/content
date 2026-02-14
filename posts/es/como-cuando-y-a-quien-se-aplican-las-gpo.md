---
id: "como-cuando-y-a-quien-se-aplican-las-gpo"
title: "Cómo, cuándo y a quién se aplican las GPO"
author: "juan-antonio-gonzalez-mena"
publishedDate: 2026-02-14
updatedDate: 2026-02-14
image: "https://cdn.deephacking.tech/i/posts/como-cuando-y-a-quien-se-aplican-las-gpo/como-cuando-y-a-quien-se-aplican-las-gpo-0.webp"
description: "Descubre cómo funcionan las políticas de grupo (GPO) en Active Directory: orden de procesamiento LSDOU, herencia, filtrado de seguridad, preferencias y contexto de ejecución."
categories:
  - "active-directory"
draft: false
featured: false
lang: "es"
---

En el anterior artículo vimos un pequeño vistazo a las políticas de grupo. Hablamos de sus componentes como de sus atributos. Si no has leído el artículo, puedes echarle un vistazo en el siguiente enlace:

- [Introducción a las Políticas de Grupo (GPO) en Active Directory](https://blog.deephacking.tech/es/posts/introduccion-a-las-politicas-de-grupo-gpo-active-directory/)

Hoy vamos a profundizar un poco más y resolver algunas dudas importantes, como por ejemplo:

- ¿Cómo, cuándo, a quién y en qué orden se aplican las GPO?
- ¿Qué ocurre si un contenedor tiene aplicada más de una GPO?
- Si estas GPO se superponen en sus configuraciones, ¿qué sucede?
- Si una GPO heredada de un contenedor superior establece una configuración y otra GPO aplicada directamente indica lo contrario, ¿cuál prevalece?
- ¿Existe alguna manera de filtrar a quién se le aplica una GPO? Es decir, que no afecte a todo el contenedor, sino solo a determinados equipos o usuarios.
- ¿En qué contexto se ejecutan los procesos que aplican las GPO?

Vamos al lío, prepárate un colacaíto para lo que se viene.

- [Flujo de aplicación de las políticas de grupo](#flujo-de-aplicación-de-las-políticas-de-grupo)
  - [Herencia de las políticas de grupo](#herencia-de-las-políticas-de-grupo)
    - [Múltiples GPO en el mismo contenedor](#múltiples-gpo-en-el-mismo-contenedor)
    - [Romper o forzar la herencia](#romper-o-forzar-la-herencia)
  - [Filtrado de las políticas de grupo](#filtrado-de-las-políticas-de-grupo)
    - [Filtrado de seguridad (Security Filtering)](#filtrado-de-seguridad-security-filtering)
    - [Filtrado WMI (WMI Filtering)](#filtrado-wmi-wmi-filtering)
    - [Orden de aplicación de una GPO](#orden-de-aplicación-de-una-gpo)
  - [Preferencias de directiva de grupo (GPP)](#preferencias-de-directiva-de-grupo-gpp)
  - [Cuándo y cómo se procesan las GPO](#cuándo-y-cómo-se-procesan-las-gpo)
    - [Foreground - Procesamiento inicial](#foreground---procesamiento-inicial)
    - [Background - Refresco periódico](#background---refresco-periódico)
    - [Contexto de ejecución (client-side)](#contexto-de-ejecución-client-side)
- [Conclusión](#conclusión)
- [Referencias](#referencias)

## Flujo de aplicación de las políticas de grupo

Vamos a comenzar hablando del flujo que se sigue cuando una GPO se aplica. Cuando se configura una GPO, es tan simple como nosotros establecer la configuración que queremos, decir a quién queremos aplicarla y olvidarnos; el resto del proceso se hace automáticamente. Cuando un ordenador o un usuario que está afectado por la GPO que acabamos de crear se conecta a la red, automáticamente recibirá esta nueva configuración y la aplicará.

Sobre ese proceso no hace falta que ahora mismo entendamos tampoco mucho, pero lo que sí es verdaderamente importante es entender los niveles de procesamiento y precedencia de las GPO.

Existen 4 niveles de jerarquía en las políticas de grupo:
- Local
- Sitio
- Dominio
- OU

Estos niveles de jerarquía definen dónde se puede aplicar una GPO. Como puedes observar, en un directorio activo puedes aplicar una GPO a sitios, dominios o unidades organizativas y, luego, por otro lado, está la política de grupo local de cada Windows.

Al mismo tiempo que estos son los 4 niveles de jerarquía, también son el orden de procesamiento, se le suele llamar `LSDOU`. La primera política que será procesada es la política local, y la última, la política de la unidad organizativa. Que la política local sea la primera en procesarse no significa que tenga mayor prioridad. De hecho, ocurre al contrario: en caso de conflicto, prevalece la última política procesada. En el orden `LSDOU`, la política aplicada a la unidad organizativa tiene mayor prioridad porque es la más cercana al objeto.

Entender esto es importante sobre todo cuando hay conflictos entre políticas; imagina que una política local le dice a un objeto lo contrario que lo que le dice la política de la unidad organizativa, ¿a quién tendrá que hacer caso? Pues lo hará a la política considerada más cercana, la de la unidad organizativa.

El siguiente diagrama permite visualizar de manera mucho más sencilla lo que acabo de explicar:

![Diagrama del orden de procesamiento LSDOU de las GPO](https://cdn.deephacking.tech/i/posts/como-cuando-y-a-quien-se-aplican-las-gpo/como-cuando-y-a-quien-se-aplican-las-gpo-1.avif)

Este orden de precedencia es el más común porque es el predeterminado, aunque existe la posibilidad de modificar el orden. En cualquier caso, de estos niveles de jerarquía existentes podemos sacar algunas conclusiones que nos ayudan a entender mejor todo esto:
- Como la política local se procesa primero, cualquier configuración dentro de una política de directorio activo tiene el potencial de modificar o anular esa configuración local.
- Las políticas a nivel de sitio que recibe un equipo cambiarán en función de la ubicación física a la que esté conectado, por lo que esta configuración puede ser variable. En un directorio activo, los sitios se definen mediante rangos de direcciones IP o subredes, lo que permite asociar los equipos a un sitio concreto en función de dónde se conecten.
- Cualquier configuración de política a nivel de dominio prevalecerá sobre cualquier política de sitio, en caso de que haya conflictos.
- La política vinculada a la unidad organizativa prevalecerá siempre (en condiciones normales).

Ahora bien, ¿qué ocurre si hay varias políticas de grupo vinculadas a una misma unidad organizativa, dominio o sitio y existen conflictos entre ellas? ¿Qué puede ocurrir también si existen unidades organizativas dentro de otras unidades organizativas y entre sí se causan conflictos? En estos casos, ¿qué prevalece?

Pues para entender estos casos más complejos debemos hablar de la herencia.

### Herencia de las políticas de grupo

Por defecto, las políticas de grupo son heredadas. Esto significa que una GPO vinculada a un contenedor superior (sitio, dominio u OU) se aplica automáticamente a todos los objetos (usuarios y equipos) de los contenedores inferiores. Esto permite que una definición en un nivel alto de la cadena llegue abajo del todo sin repetir esfuerzo. Además, el orden de procesamiento y precedencia ya lo conocemos, sigue el modelo `LSDOU`. 

En los casos donde hay unidades organizativas anidadas, el modelo se ampliaría de manera recursiva a lo siguiente:
- Local
- Sitio
- Dominio
- OU (padre)
- OU hija
- OU nieta (y así sucesivamente)

En caso de conflicto entre configuraciones de diferentes niveles, siempre prevalece la que está más cercana al objeto (usuario o equipo). Por ejemplo:
- Una GPO vinculada al dominio bloquea los dispositivos USB.
- Otra GPO vinculada a la OU "IT" los permite.

Los equipos de IT podrán usar USB, porque la GPO de la OU se procesa después y sobreescribe la del dominio. 

#### Múltiples GPO en el mismo contenedor

En el caso de que haya varias GPO vinculadas a una misma OU, sitio o dominio, estas aparecerán en una lista ordenada que se puede consultar en el _Group Policy Management (GPMC)_:

<figure>

![Pestaña Linked Group Policy Objects de la OU Crownlands](https://cdn.deephacking.tech/i/posts/como-cuando-y-a-quien-se-aplican-las-gpo/como-cuando-y-a-quien-se-aplican-las-gpo-2.avif)

<figcaption>

Pestaña Linked Group Policy Objects de la OU Crownlands

</figcaption>

</figure>

Las GPO se procesan de abajo hacia arriba, es decir, la GPO con el orden de enlace (_link order_) más bajo (normalmente la que está más arriba, con número 1) es la última en aplicarse y, por tanto, la que gana en caso de conflicto.

Puedes cambiar el orden manualmente con las flechas ↑ ↓. Esto es precisamente lo que permite modificar la precedencia por defecto dentro del mismo nivel.

#### Romper o forzar la herencia

A veces la herencia por defecto no encaja con los requisitos de la organización. Por ejemplo:
- Una OU necesita configuraciones muy específicas y no debe verse afectada por políticas heredadas innecesarias.
- Aplicar muchas GPO heredadas aumenta el tiempo de procesamiento.
- Si los requisitos se cubren con GPO vinculadas directamente, es más eficiente evitar las heredadas.

En estos casos, existen dos mecanismos clave: **Block Inheritance** y **Enforced**. Ambos se controlan a través de atributos específicos en los objetos contenedores de Directorio Activo.

##### 1. Block Inheritance (Bloquear herencia)

Se activa a nivel de contenedor (OU o dominio, aunque en el dominio raíz es poco común). Cuando está marcado, ese contenedor y sus descendientes ignoran todas las GPO heredadas de niveles superiores; solo se aplican las vinculadas directamente y las marcadas como **Enforced**.

Esta característica se controla a través del atributo `gpOptions`. Sus dos posibles valores son los siguientes:

| Valor | Significado |
|-------|-------------|
| `0`   | Herencia habilitada (valor por defecto). |
| `1`   | Herencia bloqueada (*Block Inheritance*): las GPO de contenedores superiores no se aplican, salvo las marcadas como forzadas. |

##### 2. Enforced (Forzar / No Override)

Se activa a nivel de **vínculo**, no de la GPO en sí. Esto significa que una misma GPO puede estar forzada en un contenedor y no forzada en otro. Un vínculo marcado como **Enforced**:
- Se aplica siempre, incluso si el contenedor de destino tiene **Block Inheritance** activado.
- Tiene mayor precedencia que cualquier GPO no forzada, independientemente de su posición en la jerarquía.

El atributo utilizado para controlar este mecanismo es `gpLink`. Este atributo lo mencionamos en el artículo anterior, voy a recuperar el mismo ejemplo:

```plaintext
[LDAP://CN={A1B2C3D4-1111-2222-3333-ABCDEF123456},CN=Policies,CN=System,DC=sevenkingdoms,DC=local;0]
[LDAP://CN={B2C3D4E5-4444-5555-6666-123456ABCDEF},CN=Policies,CN=System,DC=sevenkingdoms,DC=local;2]
```

Este atributo está presente en dominios, sitios y unidades organizativas. Define las GPO vinculadas al contenedor y cómo se aplican. Si del ejemplo de arriba seleccionamos una línea y la separamos por punto y coma, obtenemos dos partes:
- **La GPO vinculada**, identificada por su DN:
  - `LDAP://CN={A1B2C3D4-...},CN=Policies,CN=System,DC=sevenkingdoms,DC=local`
- **El estado del vínculo**, representado por un valor numérico:
  - `0`

Además, la posición de cada entrada dentro del atributo determina su **orden de precedencia**. Las entradas se procesan secuencialmente: la primera se aplica primero y la última se aplica en último lugar. En caso de conflicto, la última entrada sobrescribe a las anteriores, por lo que tiene **mayor prioridad**.

El estado del vínculo es lo que establece si una GPO está forzada en un contenedor o no. Sus posibles valores son:

| Valor | Significado |
|-------|-------------|
| `0`   | Vínculo habilitado. |
| `1`   | Vínculo deshabilitado. |
| `2`   | Vínculo habilitado y forzado (*Enforced*). |
| `3`   | Vínculo deshabilitado y forzado. |


---

En el siguiente diagrama se puede observar un ejemplo del comportamiento de ambos conceptos:

<figure>

![Diagrama de Block Inheritance y Enforced en GPO](https://cdn.deephacking.tech/i/posts/como-cuando-y-a-quien-se-aplican-las-gpo/como-cuando-y-a-quien-se-aplican-las-gpo-3.avif)

<figcaption>

Inspirado en el diagrama del artículo _[A Red Teamer's Guide to GPOs and OUs](https://wald0.com/?p=179)_ de wald0

</figcaption>

</figure>

La GPO `Custom Password Policy` está vinculada al objeto de dominio. En este caso, esta GPO está forzada, por lo que aplicará a todos los objetos hijos sin importar que la OU `Sysadmins` tenga el bloqueo de herencia. Asimismo, a la OU `Sysadmins` únicamente aplicará aquellas GPO que se hereden desde arriba y estén forzadas y, asimismo, las propias GPO que estén vinculadas directamente a su unidad organizativa.

En resumen, el bloqueo de herencia te aísla, pero si una GPO está forzada, no importa el aislamiento: siempre llega. Esta combinación es la que permite controlar con precisión qué políticas llegan (o no) a cada rincón del dominio.

- ¿Y qué pasa si hay varias GPO forzadas con configuraciones en conflicto?

Todas las GPO forzadas se procesan al final del todo, después de las GPO normales. Dentro de las forzadas, el orden es el siguiente:
- Entre diferentes niveles: Funciona al revés que en las GPO normales, se aplican de abajo hacia arriba en la jerarquía (primero OU hija, luego OU padre, dominio y sitio). Por eso, la GPO forzada de nivel más alto (dominio o sitio) prevalece siempre.
- Dentro del mismo nivel: Igual que en las GPO normales, la de orden de enlace más bajo (la que está más arriba en la lista) gana.

### Filtrado de las políticas de grupo

Hasta ahora hemos visto cómo la herencia, el orden de enlaces, **Block Inheritance** y **Enforced** deciden qué GPO llegan a un contenedor completo (sitio, dominio u OU).

Pero ¿qué pasa si dentro de la misma OU tienes usuarios o equipos que necesitan reglas diferentes? Moverlos a otra OU es una opción, pero a veces no es práctica o rompe la estructura lógica del dominio.

En este escenario entran los filtros. Veamos las dos maneras existentes para afinar quién recibe realmente una GPO, incluso dentro del mismo contenedor.

#### Filtrado de seguridad (Security Filtering)

Por defecto, cualquier GPO vinculada a un sitio, dominio u OU se aplica a todos los objetos autenticados en ese contenedor gracias al grupo especial `Authenticated Users`, que tiene permisos `Read` y `Apply Group Policy`.

![Filtrado de seguridad predeterminado con Authenticated Users](https://cdn.deephacking.tech/i/posts/como-cuando-y-a-quien-se-aplican-las-gpo/como-cuando-y-a-quien-se-aplican-las-gpo-4.avif)

Para restringir la GPO a ciertos objetos:
1. Eliminar `Authenticated Users` del filtrado de seguridad.
2. Añadir los objetos (usuarios, equipos o grupos) a los que sí se quiera aplicar la GPO.
3. En la pestaña `Delegation`, asegurarse de que `Authenticated Users` (o `Domain Computers`) conserva el permiso `Read`, pero **no** tiene `Apply Group Policy`.

El paso 3 es necesario a raíz del parche `MS16-072`: desde entonces, las GPO se leen en el contexto de la cuenta de equipo, por lo que el equipo debe poder leer la GPO aunque no se le aplique directamente.

![Pestaña Delegation con permisos Apply Group Policy](https://cdn.deephacking.tech/i/posts/como-cuando-y-a-quien-se-aplican-las-gpo/como-cuando-y-a-quien-se-aplican-las-gpo-5.avif)

> En caso de que se quiera excluir solo ciertos objetos, se puede dejar el filtrado por defecto (`Authenticated Users`) y en la pestaña `Delegation` añadir el grupo u objeto a excluir y denegarle el permiso `Apply Group Policy`.

#### Filtrado WMI (WMI Filtering)

Este filtro se **evalúa en el equipo** mediante consultas WMI (*Windows Management Instrumentation*). Si la condición no se cumple, **toda la GPO se descarta** (tanto la configuración de equipo como la de usuario). Esto permite filtrar por versión del sistema operativo, arquitectura, valores del registro, etc. Un ejemplo:

```sql
SELECT * FROM Win32_OperatingSystem WHERE Version LIKE "10.%" AND OSArchitecture = "64-bit"
```

Como dato, un mismo filtro WMI se puede asociar a muchas GPO, pero una GPO solo puede tener un filtro WMI.

#### Orden de aplicación de una GPO

Después de todo lo visto, cuando un equipo o usuario procesa una GPO, los filtros se evalúan en este orden:
1. **LSDOU + herencia + Link Order + Block/Enforced**: determina qué GPO llegan al contenedor.
2. **Security Filtering**: si el objeto no tiene permisos `Read` y `Apply Group Policy` → la GPO se descarta.
3. **WMI Filtering**: si la consulta WMI no se cumple en el equipo, la GPO se descarta.

En definitiva:
- El **filtrado de seguridad** controla **a quién** se aplica: usuarios, equipos o grupos específicos.
- El **filtrado WMI** controla **bajo qué condiciones** se aplica: versión del sistema operativo, arquitectura, etc.

### Preferencias de directiva de grupo (GPP)

Hasta ahora hemos visto dos niveles de control:
1. **Las políticas** deciden **qué configuración** se aplica (y la fuerzan: el usuario no puede cambiarla mientras esté activa).
2. **Los filtros** (seguridad y WMI) deciden **a quién** y **bajo qué condiciones** se aplica esa configuración.

Pero hay un problema práctico: imagina que necesitas mapear una unidad de red a todos los usuarios de una OU, excepto a los del departamento de finanzas, que necesitan otra unidad distinta. Con las herramientas que ya conoces, tus opciones son:
- Crear otra OU solo para finanzas (rompe la estructura si no tiene sentido organizativo).
- Crear otra GPO con filtrado de seguridad (funciona, pero multiplicas GPOs por cada caso particular).

Las **Preferencias de directiva de grupo** (*Group Policy Preferences* o *GPP*) resuelven este tipo de situaciones. Se configuran dentro de la misma GPO, en las secciones `Preferences` de `Configuración de equipo` y `Configuración de usuario`:

![Menú de preferencias de GPO](https://cdn.deephacking.tech/i/posts/como-cuando-y-a-quien-se-aplican-las-gpo/como-cuando-y-a-quien-se-aplican-las-gpo-6.avif)

La diferencia fundamental con las políticas clásicas es doble:

| | Políticas clásicas | Preferencias (GPP) |
|---|---|---|
| **Comportamiento** | Fuerzan un valor; el usuario no puede cambiarlo mientras la política esté aplicada. | Establecen un valor inicial; el usuario puede modificarlo después (aunque se reaplica en el siguiente refresco). |
| **Granularidad del filtrado** | Se filtra a nivel de **toda la GPO** (Security Filtering, WMI). | Cada preferencia individual tiene su propio filtrado mediante **Item-Level Targeting**. |

El **Item-Level Targeting** permite que, dentro de una misma GPO, cada elemento (una unidad mapeada, una impresora, un acceso directo...) tenga sus propias condiciones de aplicación, combinables con AND/OR: grupo de seguridad, subred IP, versión del SO, nombre del equipo, etc.

Volviendo al ejemplo anterior: en lugar de crear otra OU o multiplicar GPOs, puedes tener una sola GPO con dos preferencias de mapeo de unidad, cada una con su propio _Item-Level Targeting_ apuntando a un grupo de seguridad distinto. Todo dentro del mismo contenedor y la misma GPO.

En muchos entornos, las GPP se usan para tareas cotidianas (mapeo de unidades, impresoras, accesos directos, variables de entorno, claves del registro, etc.) que las políticas clásicas no cubren bien o que requerirían una estructura de OUs y GPOs innecesariamente compleja.

> **Nota:** Puede que las GPP te suenen porque antiguamente se almacenaban credenciales en ellas (atributo `cPassword`). Estaban cifradas con AES, hasta que Microsoft publicó accidentalmente la clave. La vulnerabilidad se parcheó con **MS14-025**, pero aún es posible encontrar `cPasswords` en entornos legacy.

### Cuándo y cómo se procesan las GPO

Llegados a este punto, sabemos de sobra qué GPO se aplican y en qué orden; también es importante entender cuándo, cómo y en qué contexto se procesan.

Las GPO se dividen en dos categorías principales:
- **Configuración de equipo** (*Computer Configuration*): se procesa al arranque del equipo.
- **Configuración de usuario** (*User Configuration*): se procesa al inicio de sesión del usuario.

![Configuración de equipo y usuario en GPO](https://cdn.deephacking.tech/i/posts/como-cuando-y-a-quien-se-aplican-las-gpo/como-cuando-y-a-quien-se-aplican-las-gpo-7.avif)

Cada GPO puede contener distintos tipos de configuración (registro, seguridad, scripts, redirección de carpetas, etc.). En el lado del cliente, cada tipo lo gestiona una **Client-Side Extension (CSE)**: una DLL especializada que sabe cómo aplicar ese tipo concreto de configuración. El motor central que orquesta todo el proceso se llama **GP Core**, y es quien decide qué CSE invocar en cada momento. Veremos ambos componentes en más detalle al final de esta sección.

Hay dos modos principales de procesamiento:

#### Foreground - Procesamiento inicial

Ocurre en los siguientes momentos:
- Al encender el equipo (configuración de equipo).
- Cuando el usuario inicia sesión (configuración de usuario).

Dentro del procesamiento en primer plano (_foreground_), hay dos submodos:
- **Síncrono:** El sistema espera a que todas las GPO terminen de aplicarse antes de mostrar el escritorio. Es más lento, pero todo está aplicado desde el primer momento. Era el modo predeterminado en **Windows 2000**.
- **Asíncrono:** Modo predeterminado desde **Windows XP / Server 2003**. El sistema no espera: el escritorio aparece rápidamente mientras las GPO se aplican en paralelo. Esto acelera los inicios de sesión, pero implica que algunas configuraciones pueden necesitar **dos ciclos de procesamiento en primer plano** (un reinicio + un inicio de sesión) para aplicarse completamente. Este comportamiento se conoce como **Fast Logon Optimization**.

Ciertas CSE, como la **instalación de software** y la **redirección de carpetas**, requieren procesamiento síncrono. Cuando detectan cambios pendientes, desactivan temporalmente _Fast Logon Optimization_ para garantizar que se aplican antes de que el usuario acceda al escritorio.

#### Background - Refresco periódico

Una vez arrancado el equipo e iniciada la sesión del usuario, las GPO se vuelven a procesar periódicamente:
- **Clientes:** cada **90 minutos**, con un **offset aleatorio de hasta 30 minutos** para evitar saturar el controlador de dominio (los refrescos se distribuyen entre 90 y 120 minutos).
- **Controladores de dominio:** cada **5 minutos**, sin offset aleatorio.

Durante el refresco, el cliente compara el **número de versión** de cada GPO (almacenado en el GPC del directorio y en el GPT de SYSVOL). Si detecta un cambio, reprocesa las CSE afectadas. Si no hay cambios, la mayoría de CSE se saltan el reprocesamiento.

Esto tiene una implicación importante desde el punto de vista ofensivo: si alguien modifica localmente una configuración que controla una GPO, pero la GPO no ha sido modificada en el directorio, el siguiente refresco no detectará cambios y **no revertirá la modificación local**.

Esto hace que las GPO sean vulnerables cuando los usuarios tienen privilegios de administrador local: un administrador local puede deshacer casi cualquier configuración de GPO de forma persistente, hasta que algo fuerce una reaplicación completa.

Para forzar la reaplicación, basta con realizar cualquier cambio en la GPO (incluso trivial), lo que incrementa su número de versión y hace que todos los equipos la reprocesen en el siguiente ciclo.

- **Excepción: Security Client-Side Extension**

No todas las CSE dependen del cambio de versión. La **Security CSE** reaplica todas las configuraciones de seguridad cada **16 horas** por defecto (controlado por `MaxNoGPOListChangesInterval`), independientemente de si la GPO ha cambiado o no.

Esta es una medida de seguridad intencional: garantiza que ajustes críticos como políticas de contraseñas, configuración del firewall, auditoría o derechos de usuario se restablezcan automáticamente si alguien con acceso local los ha manipulado. De esta forma, aunque un atacante modifique temporalmente una configuración de seguridad, como máximo 16 horas después la GPO la volverá a imponer.

Este intervalo viene activado por defecto, pero se puede modificar o desactivar.

#### Contexto de ejecución (client-side)

Todo el procesamiento de las GPO es una operación estrictamente del lado del cliente: el equipo consulta al controlador de dominio, determina las políticas aplicables y las aplica localmente.

En este proceso intervienen dos componentes principales:
- **GP Core:** El motor central que compara las versiones de las GPO y examina los atributos `gPCMachineExtensionNames` / `gPCUserExtensionNames` del objeto GPC para determinar qué CSE deben invocarse.
- **Client-Side Extensions (CSE):** DLLs registradas en el cliente (identificadas por GUID) que realizan el trabajo de aplicar las configuraciones específicas (políticas de registro, seguridad, scripts, redirección de carpetas, instalación de software, etc.).

Todo el procesamiento (tanto el GP Core como las CSE) se ejecuta con privilegios máximos, en el contexto de la cuenta **Local System**. Sin embargo, cuando se aplican configuraciones de usuario (*Per-User*), las CSE que necesitan acceder a recursos del perfil del usuario (como `HKEY_CURRENT_USER` o carpetas redirigidas) realizan una suplantación temporal (*impersonation*) del token del usuario que ha iniciado sesión.

Esto permite realizar configuraciones privilegiadas sin necesidad de conceder privilegios de administrador local al usuario.

## Conclusión

En este artículo hemos recorrido todo el ciclo de vida de una GPO desde que se vincula a un contenedor hasta que se aplica en el equipo del usuario. Hemos visto cómo el modelo **LSDOU** establece el orden base de procesamiento, cómo la **herencia** propaga las políticas a lo largo de la jerarquía y cómo los mecanismos de **Block Inheritance** y **Enforced** permiten romper o imponer esa herencia cuando la situación lo requiere.

También hemos explorado las herramientas de filtrado (**Security Filtering** y **WMI Filtering**) que permiten afinar a quién y bajo qué condiciones se aplica cada GPO, y cómo las **Preferencias de directiva de grupo (GPP)** cubren el hueco que las políticas clásicas dejan en tareas cotidianas, ofreciendo un nivel de granularidad que evita multiplicar OUs y GPOs innecesariamente.

Por último, hemos entrado en el procesamiento real: los modos **foreground** y **background**, la diferencia entre procesamiento síncrono y asíncrono, el mecanismo de detección de cambios basado en versiones y el contexto de ejecución **Local System** con suplantación de token para configuraciones de usuario.

Con todo esto, ya tienes una base sólida para entender no solo cómo funcionan las GPO, sino también dónde están sus puntos débiles: desde la persistencia de cambios locales cuando no hay modificación en la GPO, hasta las implicaciones de que un usuario tenga privilegios de administrador local. En el siguiente artículo seguiremos tirando del hilo.

## Referencias
- [Group Policy processing - Microsoft Learn](https://learn.microsoft.com/en-us/windows-server/identity/ad-ds/manage/group-policy/group-policy-processing)
- [A Red Teamer's Guide to GPOs and OUs - wald0](https://wald0.com/?p=179)
- [Group policies in cyberattacks - Securelist](https://securelist.com/group-policies-in-cyberattacks/115331/)
- [Understanding Group Policy Storage - SDM Software](https://sdmsoftware.com/whitepapers/understanding-group-policy-storage/)
- [Sneaky Active Directory Persistence Tricks - ADSecurity](https://adsecurity.org/?p=2716)
- Libro Mastering Windows Group Policy - Jordan Krause
- Libro Mastering Active Directory - Dishan Francis