# miappsocial
proyeto personal

## Base de datos en Render

En desarrollo local la aplicación usa `usuarios.db`. Para que los registros,
publicaciones, comentarios y chats permanezcan disponibles desde cualquier
país, el servicio de Render debe usar una base PostgreSQL persistente.

1. Crea una base **PostgreSQL** en Render.
2. En el servicio web, agrega la variable `DATABASE_URL` usando la **Internal Database URL** de esa base.
3. Haz un nuevo deploy.

La aplicación detecta `DATABASE_URL` automáticamente. No uses la URL de SQLite
en Render, porque sus datos pueden perderse al reiniciar el servicio.
