from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os

app = Flask(__name__)
app.secret_key = "clave_secreta"
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Cambiar a True en producción con HTTPS

# Configuración de la base de datos SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///usuarios.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modelo de usuarios con perfil
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    telefono = db.Column(db.String(20), unique=True, nullable=False)
    usuario = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

    # Campos extra para perfil
    nombre = db.Column(db.String(100))
    bio = db.Column(db.Text)
    foto = db.Column(db.String(200))  # URL o ruta de imagen

# Modelo de posts
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.Text, nullable=False)
    likes = db.Column(db.Integer, default=0)
    autor = db.Column(db.String(80), nullable=False)

# Modelo de mensajes (chat privado)
class Mensaje(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emisor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    receptor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    contenido = db.Column(db.Text, nullable=False)

    emisor = db.relationship('Usuario', foreign_keys=[emisor_id])
    receptor = db.relationship('Usuario', foreign_keys=[receptor_id])

# Crear tablas si no existen
with app.app_context():
    db.create_all()

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        password = request.form.get("password", "")

        # Validación básica
        if not usuario or not password:
            flash("Usuario y contraseña son requeridos.")
            return redirect(url_for("login"))

        try:
            user = Usuario.query.filter_by(usuario=usuario).first()
            if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                session['usuario'] = user.usuario
                flash("Inicio de sesión exitoso.")
                return redirect(url_for("home", user_id=user.id))
            else:
                flash("Usuario o contraseña incorrectos.")
                return redirect(url_for("login"))
        except Exception as e:
            flash(f"Error al iniciar sesión: {str(e)}")
            return redirect(url_for("login"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada.")
    return redirect(url_for("index"))

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
        if Usuario.query.filter_by(telefono=telefono).first():
            flash("Ese número de teléfono ya está registrado.")
            return redirect(url_for("registro"))
        if Usuario.query.filter_by(usuario=usuario).first():
            flash("Ese nombre de usuario ya está registrado.")
            return redirect(url_for("registro"))

        # Guardar usuario con contraseña encriptada
        hash = generate_password_hash(password)
        nuevo = Usuario(telefono=telefono, usuario=usuario, password=hash)
        db.session.add(nuevo)
        db.session.commit()

        flash("Registro exitoso. Ahora inicia sesión.")
        return redirect(url_for("login"))

    return render_template("registro.html")

@app.route("/home/<int:user_id>")
def home(user_id):
    user = Usuario.query.get(user_id)
    if user:
        posts = Post.query.all()
        return render_template("home.html", usuario=user, user_id=user.id, posts=posts)
    else:
        flash("Usuario no encontrado.")
        return redirect(url_for("index"))

@app.route("/add/<int:user_id>", methods=["POST"])
def add_post(user_id):
    user = Usuario.query.get(user_id)
    if user:
        texto = request.form.get("comentario")
        if texto:
            nuevo_post = Post(texto=texto, likes=0, autor=user.usuario)
            db.session.add(nuevo_post)
            db.session.commit()
    return redirect(url_for("home", user_id=user_id))

@app.route("/like/<int:post_id>/<int:user_id>")
def like(post_id, user_id):
    post = Post.query.get(post_id)
    if post:
        post.likes += 1
        db.session.commit()
    return redirect(url_for("home", user_id=user_id))

# Ruta para ver perfil
@app.route("/perfil/<int:user_id>/<int:current_user_id>")
def perfil(user_id, current_user_id):
    usuario = Usuario.query.get(user_id)
    if usuario:
        return render_template("perfil.html", usuario=usuario, current_user_id=current_user_id)
    else:
        flash("Usuario no encontrado.")
        return redirect(url_for("index"))

# Ruta de chat privado
@app.route("/chat/<int:emisor_id>/<int:receptor_id>", methods=["GET", "POST"])
def chat(emisor_id, receptor_id):
    emisor = Usuario.query.get(emisor_id)
    receptor = Usuario.query.get(receptor_id)

    if not emisor or not receptor:
        flash("Usuario no encontrado.")
        return redirect(url_for("index"))

    if request.method == "POST":
        contenido = request.form.get("mensaje")
        if contenido:
            nuevo_mensaje = Mensaje(emisor_id=emisor.id, receptor_id=receptor.id, contenido=contenido)
            db.session.add(nuevo_mensaje)
            db.session.commit()

    # Historial de chat entre ambos
    mensajes = Mensaje.query.filter(
        ((Mensaje.emisor_id == emisor.id) & (Mensaje.receptor_id == receptor.id)) |
        ((Mensaje.emisor_id == receptor.id) & (Mensaje.receptor_id == emisor.id))
    ).all()

    return render_template("chat.html", emisor=emisor, receptor=receptor, mensajes=mensajes)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # Render asigna el puerto
    app.run(host="0.0.0.0", port=port, debug=True)
