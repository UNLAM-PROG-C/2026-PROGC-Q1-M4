Acceder al backend por 127.0.0.1:3001

Las aplicaciones se corren con justfile

Instalacion: `winget install Casey.Just`

Uso:

- `just` --> ejecuta help
- `just up` --> levanta todos los contenedores
- `just down` --> Borra espacio de trabajo (ideal para levantar el proyecto de cero)
- `just logs` --> Debbugear en vivo los contenedores
- `just logs-worker` --> Ver los logs de los worker (los worker no se pueden debbugear en vivo nativamente)
- `just ...` --> etc, son los comandos que salen en el help
