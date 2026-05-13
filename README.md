# 🤖 Bot de Bolsas Extraordinarias Docentes

Monitoriza automáticamente las webs de sindicatos y boletines oficiales
y te avisa por Telegram cuando detecta una nueva convocatoria de bolsa
extraordinaria de interinos docentes (especialidad Informática/FP).

## Fuentes monitorizadas

- ANPE Andalucía
- ANPE Aragón
- ANPE Extremadura
- ANPE Comunidad Valenciana
- ANPE Castilla-La Mancha
- ANPE Navarra
- ANPE Castilla y León
- ANPE Madrid
- CSIF Extremadura
- BOE (búsqueda bolsas docentes)

## Comandos del bot

| Comando | Descripción |
|---|---|
| `/start` | Suscribirte a las alertas |
| `/comprobar` | Forzar comprobación inmediata |
| `/fuentes` | Ver todas las fuentes monitorizadas |
| `/estado` | Ver estado del bot |
| `/parar` | Darse de baja |

---

## Instalación paso a paso

### Paso 1 — Crear el bot en Telegram

1. Abre Telegram y busca **@BotFather**
2. Escribe `/newbot`
3. Ponle un nombre, por ejemplo: `Bot Bolsas Docentes`
4. Ponle un usuario, por ejemplo: `bolsas_docentes_bot`
5. BotFather te dará un **token** con este aspecto:
   ```
   7123456789:AAFxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
   ```
6. Guarda ese token, lo necesitarás en el Paso 3.

### Paso 2 — Subir el código a GitHub

1. Crea una cuenta en [github.com](https://github.com) si no tienes
2. Crea un repositorio nuevo llamado `bot-bolsas-docentes` (privado)
3. Sube los 3 archivos: `bot.py`, `requirements.txt`, `railway.toml`

   Si no sabes usar Git, puedes usar la opción "Upload files" en la web de GitHub.

### Paso 3 — Desplegar en Railway (gratis)

1. Ve a [railway.app](https://railway.app) y crea una cuenta (puedes usar tu cuenta de GitHub)
2. Haz clic en **"New Project"** → **"Deploy from GitHub repo"**
3. Selecciona tu repositorio `bot-bolsas-docentes`
4. Railway detectará automáticamente el proyecto Python
5. Ve a la pestaña **"Variables"** y añade:
   ```
   TELEGRAM_TOKEN = [el token que te dio BotFather]
   ```
6. Railway desplegará el bot automáticamente. En 1-2 minutos estará funcionando.

### Paso 4 — Probar el bot

1. Busca tu bot en Telegram por el nombre de usuario que le pusiste
2. Escribe `/start`
3. Escribe `/comprobar` para forzar una comprobación inmediata
4. ¡Listo! A partir de ahora el bot comprobará las fuentes cada 4 horas

---

## Notas técnicas

- El bot comprueba todas las fuentes cada **4 horas** automáticamente
- Usa un sistema de hashes para no repetir notificaciones ya enviadas
- Los datos de suscriptores y convocatorias vistas se guardan en archivos JSON locales
- Si Railway reinicia el servidor, los datos persisten mientras no borres el proyecto

## Añadir más fuentes

Para añadir más webs a monitorizar, edita la lista `FUENTES` en `bot.py`:

```python
{
    "nombre": "ANPE Nueva Comunidad",
    "url": "https://anpe-nuevacomunidad.es/interinos",
    "selector": "article, .entry-title, h2, h3",
    "keywords": ["bolsa", "extraordinaria", "informática", "interino"],
},
```
