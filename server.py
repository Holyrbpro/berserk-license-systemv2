from flask import Flask, request, jsonify
import sqlite3
import secrets
import string
import datetime
import os

app = Flask(__name__)

# Clave secreta para generar keys (cámbiala)
SECRET_KEY = "mi_secreto_muy_seguro_123"

def get_db():
    conn = sqlite3.connect('keys.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT UNIQUE NOT NULL,
            hwid TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            activated_at TIMESTAMP,
            active BOOLEAN DEFAULT 1
        )
    ''')
    conn.commit()
    conn.close()

@app.route('/generar_key', methods=['POST'])
def generar_key():
    auth = request.json.get('auth')
    if auth != SECRET_KEY:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Generar key de 16 caracteres alfanuméricos
    alphabet = string.ascii_letters + string.digits
    key = ''.join(secrets.choice(alphabet) for _ in range(16))
    
    conn = get_db()
    conn.execute('INSERT INTO keys (key) VALUES (?)', (key,))
    conn.commit()
    conn.close()
    
    return jsonify({'key': key})

@app.route('/validar_key', methods=['POST'])
def validar_key():
    data = request.json
    key = data.get('key')
    hwid = data.get('hwid')
    
    if not key or not hwid:
        return jsonify({'error': 'Faltan datos'}), 400
    
    conn = get_db()
    row = conn.execute('SELECT * FROM keys WHERE key = ?', (key,)).fetchone()
    conn.close()
    
    if not row:
        return jsonify({'error': 'Key inválida'}), 400
    
    if not row['active']:
        return jsonify({'error': 'Key desactivada'}), 400
    
    if row['hwid'] is None:
        # Primera activación: asignar HWID
        conn = get_db()
        conn.execute('UPDATE keys SET hwid = ?, activated_at = CURRENT_TIMESTAMP WHERE key = ?', (hwid, key))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Key activada correctamente'})
    else:
        if row['hwid'] == hwid:
            return jsonify({'success': True, 'message': 'Key válida'})
        else:
            return jsonify({'error': 'Esta key ya fue usada en otro equipo'}), 400

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=False)