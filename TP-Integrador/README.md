Acceder al backend por 127.0.0.1:3001

Las aplicaciones se corren con justfile

Instalacion: winget install Casey.Just

Uso:

- just --> ejecuta help
- just up --> levanta todos los contenedores
- just ... --> etc, son los comandos que salen en el help

Para desarollo usar (tienen hotreload para no tener que reconstruir toda la imagen)

- just worker-dev
- just front-dev
