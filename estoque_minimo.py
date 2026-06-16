import os
import psycopg2
import psycopg2.extras  # CORRIGIDO: Necessário para o RealDictCursor
from flask import Flask, render_template, request, redirect, session
from datetime import datetime
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash # CORRIGIDO: Para segurança de senhas

load_dotenv()

app = Flask(__name__)
# Otimizado: Pega do .env, se não existir, usa uma padrão segura temporária
app.secret_key = os.getenv("SECRET_KEY", "chave-super-secreta-fallback")

def conectar():
    return psycopg2.connect(
        os.getenv("DATABASE_URL")
    )

def criar_tabela():
    banco = conectar()
    cursor = banco.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produtos(
        id SERIAL PRIMARY KEY,
        nome TEXT,
        quantidade INTEGER,
        minimo INTEGER,
        preco REAL,
        loja TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios(
        id SERIAL PRIMARY KEY,
        usuario TEXT,
        senha TEXT,
        tipo TEXT,
        loja TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS movimentacoes(
        id SERIAL PRIMARY KEY,
        produto_id INTEGER,
        tipo TEXT,
        quantidade INTEGER,
        data TIMESTAMP,
        loja TEXT
    )
    """)

    banco.commit()
    cursor.close()
    banco.close()

def criar_usuario():
    banco = conectar()
    cursor = banco.cursor()

    cursor.execute("SELECT * FROM usuarios WHERE usuario = 'admin'")
    existe = cursor.fetchone()

    if existe is None:
        # CORRIGIDO: Agora a senha padrão é salva criptografada
        senha_cripto = generate_password_hash("ViniciuS12*")
        cursor.execute(
            """
            INSERT INTO usuarios (usuario, senha, tipo, loja)
            VALUES (%s, %s, %s, %s)
            """,
            ("admin", senha_cripto, "admin", "ADMIN")
        )

    banco.commit()
    cursor.close()
    banco.close()

@app.route("/")
def inicio():
    if "usuario" not in session:
        return redirect("/login")

    banco = conectar()
    cursor = banco.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    loja = session["loja"]

  # ... (código anterior da rota)

    # 1. Busca o total de produtos
    cursor.execute("SELECT COUNT(*) FROM produtos WHERE loja=%s", (loja,))
    resultado_total = cursor.fetchone()
    # Se resultado_total existir e tiver a chave, usa o valor. Se for None, assume 0.
    total = resultado_total["count"] if resultado_total else 0

    # 2. Busca o total de alertas
    cursor.execute("SELECT COUNT(*) FROM produtos WHERE quantidade<=minimo AND loja=%s", (loja,))
    resultado_alertas = cursor.fetchone()
    # Mesmo tratamento seguro aqui
    alertas = resultado_alertas["count"] if resultado_alertas else 0

    # 3. Busca a lista de produtos baixos
    cursor.execute("SELECT nome, quantidade FROM produtos WHERE quantidade<=minimo AND loja=%s", (loja,))
    produtos_baixos = cursor.fetchall()

    # Evita quebrar se produtos_baixos vier vazio/None
    nomes = []
    quantidades = []
    if produtos_baixos:
        nomes = [p["nome"] for p in produtos_baixos]
        quantidades = [p["quantidade"] for p in produtos_baixos]

    cursor.close()
    banco.close()

    return render_template(
        "index.html",
        total=total,
        alertas=alertas,
        nomes=nomes,
        quantidades=quantidades
    )

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]

        banco = conectar()
        cursor = banco.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # CORRIGIDO: Buscamos apenas pelo usuário para checar a senha depois
        cursor.execute("SELECT * FROM usuarios WHERE usuario=%s", (usuario,))
        user = cursor.fetchone()

        cursor.close()
        banco.close()

        # CORRIGIDO: Verificação segura de hash de senha
        if user and check_password_hash(user["senha"], senha):
            session["usuario"] = user["usuario"]
            session["tipo"] = user["tipo"]
            session["loja"] = user["loja"]
            return redirect("/")

        return "Login inválido", 401

    return render_template("login.html")

@app.route("/produtos")
def produtos():
    if "usuario" not in session:
        return redirect("/login")

    banco = conectar()
    cursor = banco.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("SELECT * FROM produtos WHERE loja=%s", (session["loja"],))
    lista = cursor.fetchall()

    cursor.close()
    banco.close()

    return render_template("produtos.html", produtos=lista)

@app.route("/adicionar", methods=["GET", "POST"])
def adicionar():
    if "usuario" not in session:
        return redirect("/login")

    if request.method == "POST":
        banco = conectar()
        cursor = banco.cursor()

        cursor.execute(
            """
            INSERT INTO produtos (nome, quantidade, minimo, preco, loja)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (
                request.form["nome"],
                request.form["quantidade"],
                request.form["minimo"],
                request.form["preco"],
                session["loja"]
            )
        )
        banco.commit()
        cursor.close()
        banco.close()

        return redirect("/produtos")

    return render_template("adicionar.html")

@app.route("/excluir/<int:id>")
def excluir(id):
    # CORRIGIDO: Proteção de rota interna
    if "usuario" not in session:
        return redirect("/login")

    banco = conectar()
    cursor = banco.cursor()

    # CORRIGIDO: Garante que o usuário só deleta o produto da própria loja dele
    cursor.execute("DELETE FROM produtos WHERE id=%s AND loja=%s", (id, session["loja"]))
    
    banco.commit()
    cursor.close()
    banco.close()

    return redirect("/produtos")

@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    # CORRIGIDO: Proteção de rota interna
    if "usuario" not in session:
        return redirect("/login")

    banco = conectar()
    cursor = banco.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if request.method == "POST":
        cursor.execute(
            """
            UPDATE produtos
            SET nome=%s, quantidade=%s, minimo=%s, preco=%s
            WHERE id=%s AND loja=%s
            """,
            (
                request.form["nome"],
                request.form["quantidade"],
                request.form["minimo"],
                request.form["preco"],
                id,
                session["loja"]
            )
        )
        banco.commit()
        cursor.close()
        banco.close()
        return redirect("/produtos")

    cursor.execute("SELECT * FROM produtos WHERE id=%s AND loja=%s", (id, session["loja"]))
    produto = cursor.fetchone()
    
    cursor.close()
    banco.close()

    if not produto:
        return "Produto não encontrado ou acesso não autorizado", 404

    return render_template("editar.html", produto=produto)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# Inicialização do Banco
criar_tabela()
criar_usuario()

if __name__ == "__main__":
    app.run(debug=True)