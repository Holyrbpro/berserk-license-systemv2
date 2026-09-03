import sqlite3
import os
import random
import string
import threading
from flask import Flask, request, jsonify
import discord
from discord.ext import commands

# ==================== CONFIGURACIÓN ====================
# LEER EL TOKEN DESDE VARIABLES DE ENTORNO (SEGURO)
TOKEN_DISCORD = os.environ.get("DISCORD_TOKEN")
if not TOKEN_DISCORD:
    raise ValueError("❌ No se encontró la variable de entorno DISCORD_TOKEN. Configúrala en Render.")

# ADMIN_IDS (puedes dejar el tuyo o usar variable de entorno también)
ADMIN_IDS = [447506915174645760]  # <--- REEMPLAZA CON TU ID DE USUARIO DE DISCORD

app = Flask(__name__)

# ==================== BASE DE DATOS ====================
DB_FILE = "licencias.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS keys (
            key TEXT PRIMARY KEY,
            hwid TEXT,
            usado BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ==================== FUNCIONES DE BASE DE DATOS ====================
def generar_key():
    caracteres = string.ascii_uppercase + string.digits
    return ''.join(random.choice(caracteres) for _ in range(16))

def crear_key():
    key = generar_key()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO keys (key, usado) VALUES (?, 0)", (key,))
    conn.commit()
    conn.close()
    return key

def validar_key(key, hwid):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT usado, hwid FROM keys WHERE key = ?", (key,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    usado, hwid_asociado = row
    if usado == 0:
        return "nueva"
    if usado == 1 and hwid_asociado == hwid:
        return "valida"
    return "invalida"

def vincular_key(key, hwid):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE keys SET usado = 1, hwid = ? WHERE key = ? AND usado = 0", (hwid, key))
    conn.commit()
    conn.close()

def listar_keys():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT key, usado, hwid FROM keys")
    rows = c.fetchall()
    conn.close()
    return rows

def eliminar_key(key):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM keys WHERE key = ?", (key,))
    conn.commit()
    conn.close()

# ==================== API (FLASK) ====================
@app.route('/validar', methods=['POST'])
def validar():
    data = request.json
    key = data.get('key')
    hwid = data.get('hwid')
    if not key or not hwid:
        return jsonify({'error': 'Faltan datos'}), 400
    resultado = validar_key(key, hwid)
    if resultado == "nueva":
        vincular_key(key, hwid)
        return jsonify({'valido': True, 'mensaje': '✅ Key vinculada a este HWID'})
    elif resultado == "valida":
        return jsonify({'valido': True, 'mensaje': '✅ Key válida'})
    elif resultado == "invalida":
        return jsonify({'valido': False, 'mensaje': '❌ Key usada en otra PC'})
    else:
        return jsonify({'valido': False, 'mensaje': '❌ Key no existe'})

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({'status': 'ok', 'mensaje': 'API funcionando correctamente'})

# ==================== BOT DE DISCORD ====================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents, help_command=None)

@bot.event
async def on_ready():
    print(f'✅ Bot conectado como {bot.user}')
    try:
        await bot.tree.sync()
        print('✅ Comandos slash sincronizados')
    except Exception as e:
        print(f'❌ Error al sincronizar comandos: {e}')

@bot.tree.command(name='generarkey', description='Genera una nueva key de licencia')
async def generarkey(interaction: discord.Interaction):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("❌ No tienes permiso para usar este comando.", ephemeral=True)
        return
    key = crear_key()
    await interaction.response.send_message(f"✅ **Nueva key generada:** `{key}`", ephemeral=True)

@bot.tree.command(name='listarkeys', description='Lista todas las keys')
async def listarkeys(interaction: discord.Interaction):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("❌ No tienes permiso.", ephemeral=True)
        return
    rows = listar_keys()
    if not rows:
        await interaction.response.send_message("📭 No hay keys registradas.", ephemeral=True)
        return
    mensaje = "**📋 Lista de keys:**\n"
    for k, usado, hwid in rows:
        estado = "✅ Usada" if usado else "🟢 Sin usar"
        hwid_mostrar = hwid if hwid else "Ninguno"
        mensaje += f"`{k}` → {estado} (HWID: {hwid_mostrar})\n"
    await interaction.response.send_message(mensaje, ephemeral=True)

@bot.tree.command(name='estadokey', description='Ver estado de una key')
async def estadokey(interaction: discord.Interaction, key: str):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("❌ No tienes permiso.", ephemeral=True)
        return
    resultado = validar_key(key, "dummy")
    if resultado is None:
        await interaction.response.send_message(f"❌ La key `{key}` no existe.", ephemeral=True)
    elif resultado == "nueva":
        await interaction.response.send_message(f"🟢 Key `{key}` está sin usar.", ephemeral=True)
    elif resultado == "valida":
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT hwid FROM keys WHERE key = ?", (key,))
        hwid = c.fetchone()[0]
        conn.close()
        await interaction.response.send_message(f"✅ Key `{key}` vinculada al HWID: `{hwid}`", ephemeral=True)
    elif resultado == "invalida":
        await interaction.response.send_message(f"❌ Key `{key}` usada en otra PC.", ephemeral=True)

@bot.tree.command(name='eliminarkey', description='Elimina una key')
async def eliminarkey(interaction: discord.Interaction, key: str):
    if interaction.user.id not in ADMIN_IDS:
        await interaction.response.send_message("❌ No tienes permiso.", ephemeral=True)
        return
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT key FROM keys WHERE key = ?", (key,))
    if not c.fetchone():
        conn.close()
        await interaction.response.send_message(f"❌ La key `{key}` no existe.", ephemeral=True)
        return
    eliminar_key(key)
    await interaction.response.send_message(f"🗑️ Key `{key}` eliminada.", ephemeral=True)

# ==================== INICIAR API Y BOT EN HILOS SEPARADOS ====================
def run_flask():
    app.run(host='0.0.0.0', port=5000)

if __name__ == '__main__':
    # Iniciar Flask en un hilo
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    print('🚀 API de licencias iniciada en puerto 5000')
    # Iniciar el bot de Discord
    bot.run(TOKEN_DISCORD)
