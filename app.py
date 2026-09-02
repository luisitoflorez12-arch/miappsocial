from flask import Flask, render_template, request, redirect, url_for, flash

app = Flask(__name__)
app.secret_key = "clave_secreta"

usuarios = []   # Lista de usuarios registrados
posts = []      # Lista de publicaciones

@app.route("/")
def index():
    return render_template("index.html")  # Página inicial con botones

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario")
        password = request.form.get("password")

        # Buscar usuario
        for i, u in enumerate(usuarios):
            if u["usuario"].lower() == usuario.lower() and u["password"] == password:
                flash("Inicio de sesión exitoso.")
                return redirect(url_for("home", user_id=i))

        flash("Usuario o contraseña incorrectos.")
        return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        telefono = request.form.get("telefono")
        usuario = request.form.get("usuario")
        password = request.form.get("password")

        # Validaciones
        if not telefono.isdigit():
            flash("El número de teléfono debe contener solo dígitos.")
            return redirect(url_for("registro"))

        if not usuario.startswith("@"):
            flash("El usuario debe comenzar con '@'.")
            return redirect(url_for("registro"))

        if not password or len(password) < 4:
            flash("La contraseña debe tener al menos 4 caracteres.")
            return redirect(url_for("registro"))

        # Validación de duplicados
        for u in usuarios:
            if u["telefono"] == telefono:
                flash("Ese número de teléfono ya está registrado.")
                return redirect(url_for("registro"))
            if u["usuario"].lower() == usuario.lower():
                flash("Ese nombre de usuario ya está registrado.")
                return redirect(url_for("registro"))

        # Guardar usuario
        user_id = len(usuarios)
        usuarios.append({"telefono": telefono, "usuario": usuario, "password": password})
        flash("Registro exitoso. Ahora inicia sesión.")
        return redirect(url_for("login"))

    return render_template("registro.html")

@app.route("/home/<int:user_id>")
def home(user_id):
    if 0 <= user_id < len(usuarios):
        return render_template("home.html", usuario=usuarios[user_id], user_id=user_id, posts=posts)
    else:
        flash("Usuario no encontrado.")
        return redirect(url_for("index"))

@app.route("/add/<int:user_id>", methods=["POST"])
def add_post(user_id):
    if 0 <= user_id < len(usuarios):
        texto = request.form.get("comentario")
        if texto:
            posts.append({"texto": texto, "likes": 0, "autor": usuarios[user_id]["usuario"]})
    return redirect(url_for("home", user_id=user_id))

@app.route("/like/<int:post_id>/<int:user_id>")
def like(post_id, user_id):
    if 0 <= post_id < len(posts):
        posts[post_id]["likes"] += 1
    return redirect(url_for("home", user_id=user_id))

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))  # Render asigna el puerto
    app.run(host="0.0.0.0", port=port, debug=True)

