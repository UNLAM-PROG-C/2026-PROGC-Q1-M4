Acceder al backend por `127.0.0.1:3001`

# Uso de Just
Las aplicaciones se corren mediante `justfile`.

## Instalación

El proyecto contiene un Justfile para el despliegue y administración del proyecto.
```bash
   winget install Casey.Just
```

Instala y configura las dependencias necesarias para trabajar con KADE y el entorno k8v.
- `just kade-install`


---------

# Requisitos para Windows + Docker Desktop

Si se va a desplegar este proyecto en Windows con Docker Desktop, es necesario configurar Docker Desktop para poder correr la imagen del worker en el ambiente de k8v.
Para ello, se debe hacer lo siguiente:

Habilitar:
`Use containerd for pulling and storing images`

Ruta:
`Configuración -> General -> Use containerd for pulling and storing images`

---------

# Uso

- `just`
  
    Ejecuta el help y muestra todos los comandos disponibles.

---

- `just up`
  
    Levanta todos los contenedores y servicios necesarios del proyecto.
    Los workers los levantara el KADE en el entorno k8v. Balanceo de carga y despliegue a demanda.

---

- `just dev`
  
    Levanta el proyecto en modo desarrollo.
    Existe un solo worker en un contenedor. No se utiliza k8v y KADE. Recordar parar el contenedor (just down) si se desea pasar a despliegue (just up).
---

- `just down`
  
    Borra el espacio de trabajo y elimina contenedores, redes y recursos temporales.
    Ideal para levantar el proyecto desde cero o limpiar conflictos.

---

- `just logs`
  
    Permite debuggear en vivo los contenedores principales.

---

- `just logs-worker`
  
    Permite visualizar los logs de los workers.
    Los workers no se pueden debuggear en vivo nativamente, por lo que este comando sirve para monitoreo y diagnóstico.

---

- `just ...`
  
    Existen más comandos auxiliares disponibles en el help.