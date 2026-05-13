"""
Bot de Telegram: Monitor de Bolsas Extraordinarias Docentes
Monitoriza webs de sindicatos y boletines para detectar nuevas convocatorias
de bolsas extraordinarias de interinos docentes (especialidad Informática/FP).
"""

import os
import json
import hashlib
import asyncio
import logging
from datetime import datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ── Configuración ──────────────────────────────────────────────────────────────
TOKEN = os.environ.get("TELEGRAM_TOKEN", "")   # Token del bot (BotFather)
CHAT_IDS_FILE = Path("chat_ids.json")          # Usuarios suscritos
SEEN_FILE = Path("seen_hashes.json")           # Convocatorias ya notificadas

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(message)s",
    level=logging.INFO
)
log = logging.getLogger(__name__)

# ── Fuentes a monitorizar ──────────────────────────────────────────────────────
# Cada fuente tiene: nombre, url, selector CSS para extraer noticias,
# y palabras clave que deben aparecer para considerarla relevante.
FUENTES = [
    {
        "nombre": "ANPE Andalucía",
        "url": "https://anpeandalucia.es/interinos",
        "selector": "article, .entry-title, h2, h3, .post-title",
        "keywords": ["bolsa", "extraordinaria", "informática", "interino", "convocatoria"],
    },
    {
        "nombre": "ANPE Aragón",
        "url": "https://anpearagon.es/interinos",
        "selector": "article, .entry-title, h2, h3, .post-title",
        "keywords": ["bolsa", "extraordinaria", "informática", "interino", "convocatoria"],
    },
    {
        "nombre": "ANPE Extremadura",
        "url": "https://anpeextremadura.es/interinos",
        "selector": "article, .entry-title, h2, h3, .post-title",
        "keywords": ["bolsa", "extraordinaria", "informática", "interino", "convocatoria", "llamamiento"],
    },
    {
        "nombre": "ANPE C. Valenciana",
        "url": "https://anpecomunidadvalenciana.es/interinos",
        "selector": "article, .entry-title, h2, h3, .post-title",
        "keywords": ["bolsa", "extraordinaria", "informática", "interino", "convocatoria"],
    },
    {
        "nombre": "ANPE Castilla-La Mancha",
        "url": "https://anpecastillalamancha.es/interinos",
        "selector": "article, .entry-title, h2, h3, .post-title",
        "keywords": ["bolsa", "extraordinaria", "informática", "interino", "convocatoria"],
    },
    {
        "nombre": "ANPE Navarra",
        "url": "https://anpenavarra.es/interinos",
        "selector": "article, .entry-title, h2, h3, .post-title",
        "keywords": ["bolsa", "extraordinaria", "informática", "interino", "convocatoria"],
    },
    {
        "nombre": "ANPE Castilla y León",
        "url": "https://anpecastillayleon.es/interinos",
        "selector": "article, .entry-title, h2, h3, .post-title",
        "keywords": ["bolsa", "extraordinaria", "informática", "interino", "convocatoria"],
    },
    {
        "nombre": "ANPE Madrid",
        "url": "https://anpemadrid.es/interinos",
        "selector": "article, .entry-title, h2, h3, .post-title",
        "keywords": ["bolsa", "extraordinaria", "informática", "interino", "convocatoria"],
    },
    {
        "nombre": "CSIF Extremadura (Telemático)",
        "url": "https://www.csif.es/es/articulo/extremadura/educacion/76496",
        "selector": "h1, h2, h3, p, li",
        "keywords": ["llamamiento", "urgente", "informática", "interino"],
    },
    {
        "nombre": "BOE (búsqueda bolsas docentes)",
        "url": "https://www.boe.es/buscar/boe.php?campo%5B0%5D=TIT&dato%5B0%5D=bolsa+interinos+docentes&operador%5B0%5D=and&campo%5B1%5D=DOC&dato%5B1%5D=&operador%5B1%5D=and&campo%5B2%5D=ART&dato%5B2%5D=&operador%5B2%5D=and&campo%5B3%5D=PUB&dato%5B3%5D=&campo%5B4%5D=FEC&dato%5B4%5D=&campo%5B5%5D=AGENCIA&dato%5B5%5D=&campo%5B6%5D=DEP&dato%5B6%5D=&accion=Buscar",
        "selector": ".resultado-busqueda, .sumario, h3",
        "keywords": ["bolsa", "interino", "informática", "extraordinaria", "docente"],
    },
]

# ── Persistencia ───────────────────────────────────────────────────────────────

def load_json(path: Path, default):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return default

def save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get_chat_ids() -> list[int]:
    return load_json(CHAT_IDS_FILE, [])

def add_chat_id(chat_id: int):
    ids = get_chat_ids()
    if chat_id not in ids:
        ids.append(chat_id)
        save_json(CHAT_IDS_FILE, ids)

def get_seen() -> set:
    return set(load_json(SEEN_FILE, []))

def mark_seen(h: str):
    seen = get_seen()
    seen.add(h)
    save_json(SEEN_FILE, list(seen))

# ── Scraping ───────────────────────────────────────────────────────────────────

def es_relevante(texto: str, keywords: list[str]) -> bool:
    t = texto.lower()
    # Al menos 2 keywords deben aparecer para evitar falsos positivos
    hits = sum(1 for kw in keywords if kw.lower() in t)
    return hits >= 2

async def scrape_fuente(fuente: dict) -> list[dict]:
    """Descarga la página y extrae los ítems de texto que coincidan con keywords."""
    resultados = []
    headers = {"User-Agent": "Mozilla/5.0 (compatible; BolsasBot/1.0)"}
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(fuente["url"], headers=headers)
            resp.raise_for_status()
    except Exception as e:
        log.warning(f"Error al acceder a {fuente['nombre']}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    elementos = soup.select(fuente["selector"])

    for el in elementos:
        texto = el.get_text(separator=" ", strip=True)
        if len(texto) < 20:
            continue
        if not es_relevante(texto, fuente["keywords"]):
            continue

        # Hash único para no repetir notificaciones
        h = hashlib.md5(f"{fuente['nombre']}|{texto[:200]}".encode()).hexdigest()
        resultados.append({
            "fuente": fuente["nombre"],
            "url": fuente["url"],
            "texto": texto[:300],
            "hash": h,
        })

    # Deduplicar por hash dentro de la misma fuente
    vistos = set()
    unicos = []
    for r in resultados:
        if r["hash"] not in vistos:
            vistos.add(r["hash"])
            unicos.append(r)

    return unicos

# ── Comprobación y notificación ────────────────────────────────────────────────

async def comprobar_y_notificar(bot: Bot):
    log.info("🔍 Iniciando comprobación de fuentes...")
    seen = get_seen()
    nuevos = []

    for fuente in FUENTES:
        items = await scrape_fuente(fuente)
        for item in items:
            if item["hash"] not in seen:
                nuevos.append(item)
                mark_seen(item["hash"])

    if not nuevos:
        log.info("✅ Sin novedades.")
        return

    log.info(f"🚨 {len(nuevos)} nueva(s) convocatoria(s) detectada(s).")
    chat_ids = get_chat_ids()

    for item in nuevos:
        mensaje = (
            f"🔔 *Nueva convocatoria detectada*\n\n"
            f"📌 *Fuente:* {item['fuente']}\n"
            f"📝 *Extracto:* {item['texto']}\n\n"
            f"🔗 [Ver convocatoria]({item['url']})\n\n"
            f"_Comprobado el {datetime.now().strftime('%d/%m/%Y a las %H:%M')}_"
        )
        for chat_id in chat_ids:
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=mensaje,
                    parse_mode="Markdown",
                    disable_web_page_preview=False,
                )
            except Exception as e:
                log.error(f"Error enviando a {chat_id}: {e}")

# ── Comandos del bot ───────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    add_chat_id(chat_id)
    await update.message.reply_text(
        "👋 *¡Hola! Soy el bot de bolsas docentes.*\n\n"
        "Te avisaré automáticamente cuando detecte nuevas *bolsas extraordinarias* "
        "de interinos docentes (Informática/FP) en las principales comunidades autónomas.\n\n"
        "📡 *Fuentes monitorizadas:*\n"
        + "\n".join(f"• {f['nombre']}" for f in FUENTES)
        + "\n\n*Comandos disponibles:*\n"
        "/start — Suscribirte a las alertas\n"
        "/comprobar — Forzar comprobación ahora\n"
        "/fuentes — Ver fuentes monitorizadas\n"
        "/estado — Estado del bot\n"
        "/parar — Darse de baja de las alertas",
        parse_mode="Markdown",
    )

async def cmd_comprobar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Comprobando fuentes ahora, espera un momento...")
    bot = context.application.bot
    await comprobar_y_notificar(bot)
    await update.message.reply_text("✅ Comprobación completada.")

async def cmd_fuentes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = "📡 *Fuentes que monitorizo:*\n\n"
    for f in FUENTES:
        texto += f"• [{f['nombre']}]({f['url']})\n"
    await update.message.reply_text(texto, parse_mode="Markdown", disable_web_page_preview=True)

async def cmd_estado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_ids = get_chat_ids()
    seen = get_seen()
    await update.message.reply_text(
        f"⚙️ *Estado del bot*\n\n"
        f"👥 Usuarios suscritos: {len(chat_ids)}\n"
        f"📋 Convocatorias registradas: {len(seen)}\n"
        f"📡 Fuentes monitorizadas: {len(FUENTES)}\n"
        f"⏰ Frecuencia de comprobación: cada 4 horas\n"
        f"🕐 Hora actual: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        parse_mode="Markdown",
    )

async def cmd_parar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    ids = get_chat_ids()
    if chat_id in ids:
        ids.remove(chat_id)
        save_json(CHAT_IDS_FILE, ids)
        await update.message.reply_text("🔕 Te has dado de baja. Usa /start para volver a suscribirte.")
    else:
        await update.message.reply_text("Ya estabas dado de baja.")

# ── Main ───────────────────────────────────────────────────────────────────────

async def post_init(application: Application):
    """Se ejecuta al arrancar: programa la comprobación periódica."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        comprobar_y_notificar,
        "interval",
        hours=4,
        args=[application.bot],
        next_run_time=datetime.now(),  # Primera comprobación al arrancar
    )
    scheduler.start()
    log.info("⏰ Scheduler iniciado — comprobación cada 4 horas.")

def main():
    if not TOKEN:
        raise ValueError("Falta TELEGRAM_TOKEN. Defínelo como variable de entorno.")

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("comprobar", cmd_comprobar))
    app.add_handler(CommandHandler("fuentes", cmd_fuentes))
    app.add_handler(CommandHandler("estado", cmd_estado))
    app.add_handler(CommandHandler("parar", cmd_parar))

    log.info("🤖 Bot arrancado.")
    app.run_polling()

if __name__ == "__main__":
    main()
