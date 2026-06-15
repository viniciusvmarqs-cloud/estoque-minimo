import sqlite3
from flask import render_template, Flask, request, redirect, session
from datetime import datetime

app = Flask(__name__)
app.secret_key = "chave-super-secreta"


def conectar():
    banco = sqlite3.connect("estoque.db")
    banco.row_factory = sqlite3.Row  # Isso nos permite usar user["nome_da_coluna"]
    return banco


@app.route("/movimentar/<int:id>", methods=["GET", "POST"])
def movimentar(id):
    if "usuario" not in session:
        return redirect("/login")

    banco = conectar()

    produto = banco.execute(
        """
        SELECT *
        FROM produtos
        WHERE id=?
        AND loja=?
        """,
        (id, session["loja"]),
    ).fetchone()

    if request.method == "POST":
        tipo = request.form["tipo"]
        quantidade = int(request.form["quantidade"])

        if tipo == "entrada":
            banco.execute(
                """
                UPDATE produtos
                SET quantidade = quantidade + ?
                WHERE id=?
                """,
                (quantidade, id),
            )
        else:
            banco.execute(
                """
                UPDATE produtos
                SET quantidade = quantidade - ?
                WHERE id=?
                """,
                (quantidade, id),
            )

        banco.execute(
            """
            INSERT INTO movimentacoes
            (produto_id,tipo,quantidade,data,loja)
            VALUES(?,?,?,?,?)
            """,
            (id, tipo, quantidade, datetime.now(), session["loja"]),
        )

        banco.commit()
        banco.close()

        return redirect("/produtos")

    banco.close()
    return render_template("movimentar.html", produto=produto)


@app.route("/movimento_rapido/<int:id>/<tipo>")
def movimento_rapido(id, tipo):
    if "usuario" not in session:
        return redirect("/login")

    banco = conectar()

    if tipo == "entrada":
        banco.execute(
            """
            UPDATE produtos
            SET quantidade = quantidade + 1
            WHERE id=?
            AND loja=?
            """,
            (id, session["loja"]),
        )

    if tipo == "saida":
        banco.execute(
            """
            UPDATE produtos
            SET quantidade = quantidade - 1
            WHERE id=?
            AND loja=?
            """,
            (id, session["loja"]),
        )

    banco.execute(
        """
        INSERT INTO movimentacoes
        (produto_id,tipo,quantidade,data,loja)
        VALUES(?,?,?,?,?)
        """,
        (id, tipo, 1, datetime.now(), session["loja"]),
    )

    banco.commit()
    banco.close()
    return redirect("/produtos")


def criar_tabela():
    banco = conectar()

    banco.execute(
        """
    CREATE TABLE IF NOT EXISTS produtos(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT,
        quantidade INTEGER,
        minimo INTEGER,
        preco REAL,
        loja TEXT
    )
    """
    )
    banco.execute(
        """
        CREATE TABLE IF NOT EXISTS movimentacoes(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        produto_id INTEGER,
        tipo TEXT,
        quantidade INTEGER,
        data TEXT,
        loja TEXT
        )"""
    )

    banco.execute(
        """
    CREATE TABLE IF NOT EXISTS usuarios(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        usuario TEXT,
        senha TEXT,
        tipo TEXT,
        loja TEXT
    )
    """
    )

    banco.commit()
    banco.close()


def criar_usuario():
    banco = conectar()
    existe = banco.execute("SELECT * FROM usuarios").fetchone()

    if existe == None:
        banco.execute(
            """
            INSERT INTO usuarios
            (usuario,senha,tipo,loja)
            VALUES(?,?,?,?)
            """,
            ("admin", "ViniciuS12*", "admin", "ADMIN"),
        )

    banco.commit()
    banco.close()


@app.route("/")
def inicio():
    if "usuario" not in session:
        return redirect("/login")

    banco = conectar()
    loja = session["loja"]

    total = banco.execute(
        """
        SELECT COUNT(*)
        FROM produtos
        WHERE loja=?
        """,
        (loja,),
    ).fetchone()[0]

    alertas = banco.execute(
        """
        SELECT COUNT(*)
        FROM produtos
        WHERE quantidade<=minimo
        AND loja=?
        """,
        (loja,),
    ).fetchone()[0]

    produtos_baixos = banco.execute(
        """
        SELECT nome, quantidade
        FROM produtos
        WHERE quantidade<=minimo
        AND loja=?
        """,
        (loja,),
    ).fetchall()

    banco.close()

    nomes = []
    quantidades = []

    for produto in produtos_baixos:
        nomes.append(produto["nome"])
        quantidades.append(produto["quantidade"])

    return render_template(
        "index.html",
        total=total,
        alertas=alertas,
        nomes=nomes,
        quantidades=quantidades,
    )


@app.route("/produtos")
def produtos():
    if "usuario" not in session:
        return redirect("/login")

    banco = conectar()
    lista = banco.execute(
        """
        SELECT *
        FROM produtos
        WHERE loja=?
        """,
        (session["loja"],),
    ).fetchall()

    banco.close()
    return render_template("produtos.html", produtos=lista)


@app.route("/adicionar", methods=["GET", "POST"])
def adicionar():
    if "usuario" not in session:
        return redirect("/login")

    if request.method == "POST":
        nome = request.form["nome"]
        quantidade = request.form["quantidade"]
        minimo = request.form["minimo"]
        preco = request.form["preco"]

        banco = conectar()
        banco.execute(
            """
            INSERT INTO produtos
            (nome,quantidade,minimo,preco,loja)
            VALUES(?,?,?,?,?)
            """,
            (nome, quantidade, minimo, preco, session["loja"]),
        )

        banco.commit()
        banco.close()
        return redirect("/produtos")

    return render_template("adicionar.html")


@app.route("/excluir/<int:id>")
def excluir(id):
    if "usuario" not in session:
        return redirect("/login")

    banco = conectar()
    banco.execute(
        """
        DELETE FROM produtos
        WHERE id=?
        AND loja=?
        """,
        (id, session["loja"]),
    )

    banco.commit()
    banco.close()
    return redirect("/produtos")


@app.route("/editar/<int:id>", methods=["GET", "POST"])
def editar(id):
    if "usuario" not in session:
        return redirect("/login")

    banco = conectar()

    if request.method == "POST":
        banco.execute(
            """
            UPDATE produtos
            SET nome=?,
            quantidade=?,
            minimo=?,
            preco=?
            WHERE id=?
            AND loja=?
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
        banco.close()
        return redirect("/produtos")

    produto = banco.execute(
        """
        SELECT *
        FROM produtos
        WHERE id=?
        AND loja=?
        """,
        (id, session["loja"]),
    ).fetchone()

    banco.close()
    return render_template("editar.html", produto=produto)

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        usuario=request.form["usuario"]
        senha=request.form["senha"]

        banco=conectar()

        user=banco.execute(
        """
        SELECT *
        FROM usuarios
        WHERE usuario=?
        AND senha=?
        """,
        (usuario, senha)).fetchone()

        banco.close()

        if user:
            print(user.keys())
            # Certifique-se de que está escrito exatamente assim:
            session["usuario"] = user["usuario"]
            session["tipo"] = user["tipo"]
            session["loja"] = user["loja"]

            return redirect("/")

        return "Login inválido"

    return render_template("login.html")
@app.route("/gerenciar")
def gerenciar():

    if "usuario" not in session:
        return redirect("/login")


    banco = conectar()


    produtos = banco.execute(
    """
    SELECT *

    FROM produtos

    WHERE loja=?

    """,
    (session["loja"],)

    ).fetchall()


    banco.close()


    return render_template(
        "gerenciar.html",
        produtos=produtos
    )
@app.route("/ver_produtos")
def ver_produtos():

    if "usuario" not in session:
        return redirect("/login")


    banco = conectar()


    produtos = banco.execute(
    """
    SELECT *

    FROM produtos

    WHERE loja=?

    """,
    (session["loja"],)

    ).fetchall()


    banco.close()


    return render_template(
        "ver_produtos.html",
        produtos=produtos
    )
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/cadastrar_usuario", methods=["GET", "POST"])
def cadastrar_usuario():
    if "tipo" not in session or session["tipo"] != "admin":
        return "Acesso negado"

    if request.method == "POST":
        usuario = request.form["usuario"]
        senha = request.form["senha"]

        banco = conectar()
        banco.execute(
            """
            INSERT INTO usuarios
            (usuario,senha,tipo,loja)
            VALUES(?,?,?,?)
            """,
            (usuario, senha, "cliente", usuario),
        )

        banco.commit()
        banco.close()
        return redirect("/")

    return render_template("cadastrar_usuario.html")


@app.route("/historico")
def historico():
    if "usuario" not in session:
        return redirect("/login")

    banco = conectar()
    movimentos = banco.execute(
        """
        SELECT *
        FROM movimentacoes
        WHERE loja=?
        ORDER BY id DESC
        """,
        (session["loja"],),
    ).fetchall()

    banco.close()
    return render_template("historico.html", movimentos=movimentos)


# Inicialização do banco
criar_tabela()
criar_usuario()

if __name__ == "__main__":
    app.run(debug=True)