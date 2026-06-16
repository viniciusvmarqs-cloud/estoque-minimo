import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, session
import psycopg2
import psycopg2.extras  # Mantido: Essencial para o RealDictCursor funcionar
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash  # Segurança de senhas

# Carrega as variáveis de ambiente
load_dotenv()

app = Flask(__name__)
# Configura a chave secreta de forma segura
app.secret_key = os.getenv("SECRET_KEY", "chave-super-secreta-fallback")


def conectar():
    url_banco = os.getenv("DATABASE_URL")
    if not url_banco:
        raise ValueError(
            "ERRO: A variável DATABASE_URL não foi encontrada no ambiente ou arquivo .env!"
        )
    return psycopg2.connect(url_banco)


def criar_tabela():
    banco = conectar()
    cursor = banco.cursor()
    try:
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
    finally:
        cursor.close()
        banco.close()


def criar_usuario_admin_padrao():
    banco = conectar()
    cursor = banco.cursor()
    try:
        cursor.execute("SELECT * FROM usuarios WHERE usuario = 'admin'")
        existe = cursor.fetchone()

        if existe is None:
            # Senha padrão armazenada com Hash seguro
            senha_cripto = generate_password_hash("ViniciuS12*")
            cursor.execute(
                """
                INSERT INTO usuarios (usuario, senha, tipo, loja)
                VALUES (%s, %s, %s, %s)
                """,
                ("admin", senha_cripto, "admin", "ADMIN"),
            )
            banco.commit()
    finally:
        cursor.close()
        banco.close()


@app.route("/")
def inicio():
    if "usuario" not in session:
        return redirect("/login")

    banco = conectar()
    cursor = banco.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    loja = session["loja"]

    try:
        # 1. Busca o total de produtos da loja (Tratamento seguro para None)
        cursor.execute(
            "SELECT COUNT(*) FROM produtos WHERE loja=%s", (loja,)
        )
        resultado_total = cursor.fetchone()
        total = resultado_total["count"] if resultado_total else 0

        # 2. Busca o total de alertas (Tratamento seguro para None)
        cursor.execute(
            "SELECT COUNT(*) FROM produtos WHERE quantidade<=minimo AND loja=%s",
            (loja,),
        )
        resultado_alertas = cursor.fetchone()
        alertas = resultado_alertas["count"] if resultado_alertas else 0

        # 3. Busca a lista de produtos com estoque baixo
        cursor.execute(
            "SELECT nome, quantidade FROM produtos WHERE quantidade<=minimo AND loja=%s",
            (loja,),
        )
        produtos_baixos = cursor.fetchall()

        nomes = []
        quantidades = []
        if produtos_baixos:
            nomes = [p["nome"] for p in produtos_baixos]
            quantidades = [p["quantidade"] for p in produtos_baixos]

    finally:
        cursor.close()
        banco.close()

    return render_template(
        "index.html",
        total=total,
        alertas=alertas,
        nomes=nomes,
        quantidades=quantidades,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]

        banco = conectar()
        cursor = banco.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        try:
            # Busca pelo usuário para validar a senha criptografada em seguida
            cursor.execute(
                "SELECT * FROM usuarios WHERE usuario=%s", (usuario,)
            )
            user = cursor.fetchone()
        finally:
            cursor.close()
            banco.close()

        # Validação segura da senha usando a biblioteca do Flask
        if user and check_password_hash(user["senha"], senha):
            session["usuario"] = user["usuario"]
            session["tipo"] = user["tipo"]
            session["loja"] = user["loja"]
            return redirect("/")

        return "Login inválido", 401

    return render_template("login.html")


@app.route("/cadastrar_usuario", methods=["GET", "POST"])
def cadastrar_usuario():
    # Segurança: Apenas administradores logados podem acessar essa rota
    if "usuario" not in session or session.get("tipo") != "admin":
        return (
            "Acesso negado. Apenas administradores podem cadastrar usuários.",
            403,
        )

    if request.method == "POST":
        novo_usuario = request.form["usuario"]
        senha_limpa = request.form["senha"]
        tipo = request.form["tipo"]
        loja = request.form["loja"]

        banco = conectar()
        cursor = banco.cursor()

        try:
            # Verifica duplicidade de usuário
            cursor.execute(
                "SELECT id FROM usuarios WHERE usuario = %s", (novo_usuario,)
            )
            if cursor.fetchone():
                return "Este nome de usuário já está em uso!", 400

            # Criptografa a nova senha antes de salvar
            senha_cripto = generate_password_hash(senha_limpa)

            cursor.execute(
                """
                INSERT INTO usuarios (usuario, senha, tipo, loja)
                VALUES (%s, %s, %s, %s)
                """,
                (novo_usuario, senha_cripto, tipo, loja),
            )
            banco.commit()
        finally:
            cursor.close()
            banco.close()

        return "Usuário cadastrado com sucesso! <a href='/'>Voltar para o início</a>"

    return render_template("cadastrar_usuario.html")


@app.route("/produtos")
def produtos():
    if "usuario" not in session:
        return redirect("/login")

    banco = conectar()
    cursor = banco.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
        cursor.execute(
            "SELECT * FROM produtos WHERE loja=%s", (session["loja"],)
        )
        lista = cursor.fetchall()
    finally:
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

        try:
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
                    session["loja"],
                ),
            )
            banco.commit()
        finally:
            cursor.close()
            banco.close()

        return redirect("/produtos")

    return render_template("adicionar.html")


@app.route("/excluir/<int:id>")
def excluir(id):
    if "usuario" not in session:
        return redirect("/login")

    banco = conectar()
    cursor = banco.cursor()

    try:
        # Garante segurança: deleta apenas se o produto pertencer à loja do usuário logado
        cursor.execute(
            "DELETE FROM produtos WHERE id=%s AND loja=%s",
            (id, session["loja"]),
        )
        banco.commit()
    finally:
        cursor.close()
        banco.close()

    return redirect("/produtos")


@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    if "usuario" not in session:
        return redirect("/login")

    banco = conectar()
    cursor = banco.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    try:
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
                    session["loja"],
                ),
            )
            banco.commit()
            return redirect("/produtos")

        cursor.execute(
            "SELECT * FROM produtos WHERE id=%s AND loja=%s",
            (id, session["loja"]),
        )
        produto = cursor.fetchone()
    finally:
        cursor.close()
        banco.close()

    if not produto:
        return "Produto não encontrado ou acesso não autorizado", 404

    return render_template("editar.html", produto=produto)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# Execuções estruturadas na inicialização
criar_tabela()
criar_usuario_admin_padrao()

if __name__ == "__main__":
    app.run(debug=True)