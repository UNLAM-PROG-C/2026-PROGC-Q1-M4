Acceder al backend por 127.0.0.1:3001

Las aplicaciones se corren con justfile

Instalacion: `winget install Casey.Just`

Si se va a desplegar este proyecto en Windows con docker desktop, es necesario configurar el docker desktop para poder correr la imagen del worker en el ambiente de k8v
Para ello, se debe de hacer lo siguiente:
Habilitar Use containerd for pulling and storing images 
Configuracion -> General -> Use containerd for pulling and storing images

Uso:

- `just` --> ejecuta help
- `just up` --> levanta todos los contenedores
- `just down` --> Borra espacio de trabajo (ideal para levantar el proyecto de cero)
- `just logs` --> Debbugear en vivo los contenedores
- `just logs-worker` --> Ver los logs de los worker (los worker no se pueden debbugear en vivo nativamente)
- `just ...` --> etc, son los comandos que salen en el help


