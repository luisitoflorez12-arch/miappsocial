from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "clave_secreta"
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Cambiar a True en producción con HTTPS

# Configuración de uploads
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Crear carpeta de uploads si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
    imagen = db.Column(db.String(255))  # Ruta de imagen
    autor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    autor = db.Column(db.String(80), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    
    likes_count = db.relationship('Like', cascade='all, delete-orphan', lazy=True)

# Modelo de likes
class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (db.UniqueConstraint('usuario_id', 'post_id', name='unique_like'),)

# Modelo de mensajes (chat privado)
class Mensaje(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    emisor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    receptor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    contenido = db.Column(db.Text, nullable=False, default="")
    imagen = db.Column(db.String(255))
    leido = db.Column(db.Boolean, default=False, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    emisor = db.relationship('Usuario', foreign_keys=[emisor_id])
    receptor = db.relationship('Usuario', foreign_keys=[receptor_id])

# Crear tablas si no existen
with app.app_context():
    db.create_all()
    # Mantener instalaciones existentes compatibles con el estado de lectura.
    if 'leido' not in {column['name'] for column in inspect(db.engine).get_columns('mensaje')}:
        with db.engine.begin() as connection:
            connection.execute(text('ALTER TABLE mensaje ADD COLUMN leido BOOLEAN NOT NULL DEFAULT 0'))
    if 'fecha' not in {column['name'] for column in inspect(db.engine).get_columns('mensaje')}:
        with db.engine.begin() as connection:
            connection.execute(text('ALTER TABLE mensaje ADD COLUMN fecha DATETIME'))
    if 'imagen' not in {column['name'] for column in inspect(db.engine).get_columns('mensaje')}:
        with db.engine.begin() as connection:
            connection.execute(text('ALTER TABLE mensaje ADD COLUMN imagen VARCHAR(255)'))

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
        posts = Post.query.order_by(Post.fecha.desc()).all()
        # Crear un diccionario de usuarios para acceso rápido
        usuarios = Usuario.query.all()
        usuarios_dict = {u.usuario: u for u in usuarios}
        
        # Crear diccionario de likes del usuario actual
        user_likes = {like.post_id for like in Like.query.filter_by(usuario_id=user.id).all()}
        unread_count = Mensaje.query.filter_by(receptor_id=user.id, leido=False).count()
        
        return render_template("home.html", usuario=user, user_id=user.id, posts=posts, 
                     usuarios_dict=usuarios_dict, user_likes=user_likes,
                     unread_count=unread_count)
    else:
        flash("Usuario no encontrado.")
        return redirect(url_for("index"))

@app.route("/add/<int:user_id>", methods=["POST"])
def add_post(user_id):
    user = Usuario.query.get(user_id)
    if user:
        texto = request.form.get("comentario", "").strip()
        imagen = None
        
        # Manejar upload de imagen
        if 'imagen' in request.files:
            file = request.files['imagen']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(f"{user.id}_{datetime.now().timestamp()}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                imagen = f"uploads/{filename}"
        
        if texto or imagen:  # Permitir posts solo con imagen
            nuevo_post = Post(texto=texto, imagen=imagen, autor_id=user.id, autor=user.usuario)
            db.session.add(nuevo_post)
            db.session.commit()
            flash("Post publicado correctamente.")
    return redirect(url_for("home", user_id=user_id))

@app.route("/like/<int:post_id>/<int:user_id>")
def like(post_id, user_id):
    post = Post.query.get(post_id)
    user = Usuario.query.get(user_id)
    
    if post and user:
        existing_like = Like.query.filter_by(usuario_id=user.id, post_id=post.id).first()
        
        if existing_like:
            # Si ya existe like, lo eliminamos (toggle off)
            db.session.delete(existing_like)
            flash("Like removido.")
        else:
            # Si no existe, lo creamos (toggle on)
            nuevo_like = Like(usuario_id=user.id, post_id=post.id)
            db.session.add(nuevo_like)
            flash("Post likeado!")
        
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

# Ruta para editar perfil
@app.route("/editar_perfil/<int:user_id>", methods=["GET", "POST"])
def editar_perfil(user_id):
    usuario = Usuario.query.get(user_id)
    if not usuario:
        flash("Usuario no encontrado.")
        return redirect(url_for("index"))
    
    if request.method == "POST":
        usuario.nombre = request.form.get("nombre", usuario.nombre)
        usuario.bio = request.form.get("bio", usuario.bio)
        usuario.foto = request.form.get("foto", usuario.foto)
        
        try:
            db.session.commit()
            flash("Perfil actualizado correctamente.")
            return redirect(url_for("perfil", user_id=usuario.id, current_user_id=usuario.id))
        except Exception as e:
            db.session.rollback()
            flash(f"Error al actualizar perfil: {str(e)}")
    
    return render_template("editar_perfil.html", usuario=usuario)

# Ruta de chat privado
@app.route("/chat/<int:emisor_id>/<int:receptor_id>", methods=["GET", "POST"])
def chat(emisor_id, receptor_id):
    emisor = Usuario.query.get(emisor_id)
    receptor = Usuario.query.get(receptor_id)

    if not emisor or not receptor:
        flash("Usuario no encontrado.")
        return redirect(url_for("index"))

    if request.method == "POST":
        contenido = request.form.get("mensaje", "").strip()
        imagen = None
        archivo = request.files.get("imagen")

        if archivo and archivo.filename:
            if not allowed_file(archivo.filename):
                flash("El formato de la imagen no está permitido.")
                return redirect(url_for("chat", emisor_id=emisor.id, receptor_id=receptor.id))

            filename = secure_filename(
                f"chat_{emisor.id}_{receptor.id}_{datetime.now().timestamp()}_{archivo.filename}"
            )
            archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            imagen = f"uploads/{filename}"

        if contenido or imagen:
            nuevo_mensaje = Mensaje(
                emisor_id=emisor.id,
                receptor_id=receptor.id,
                contenido=contenido,
                imagen=imagen,
            )
            db.session.add(nuevo_mensaje)
            db.session.commit()

    Mensaje.query.filter_by(
        emisor_id=receptor.id,
        receptor_id=emisor.id,
        leido=False
    ).update({"leido": True})
    db.session.commit()

    # Historial de chat entre ambos
    mensajes = Mensaje.query.filter(
        ((Mensaje.emisor_id == emisor.id) & (Mensaje.receptor_id == receptor.id)) |
        ((Mensaje.emisor_id == receptor.id) & (Mensaje.receptor_id == emisor.id))
    ).order_by(Mensaje.fecha.asc(), Mensaje.id.asc()).all()

    return render_template("chat.html", emisor=emisor, receptor=receptor, mensajes=mensajes)

@app.route("/mensajes/<int:user_id>")
def mensajes(user_id):
    usuario = Usuario.query.get(user_id)
    if not usuario:
        flash("Usuario no encontrado.")
        return redirect(url_for("index"))

    conversaciones = {}
    mensajes_usuario = Mensaje.query.filter(
        (Mensaje.emisor_id == user_id) | (Mensaje.receptor_id == user_id)
    ).order_by(Mensaje.fecha.desc(), Mensaje.id.desc()).all()

    for mensaje in mensajes_usuario:
        partner_id = mensaje.receptor_id if mensaje.emisor_id == user_id else mensaje.emisor_id
        if partner_id not in conversaciones:
            partner = Usuario.query.get(partner_id)
            if partner:
                conversaciones[partner_id] = {
                    "usuario": partner,
                    "ultimo": mensaje,
                    "nuevos": 0,
                }

        if (mensaje.receptor_id == user_id and not mensaje.leido
                and partner_id in conversaciones):
            conversaciones[partner_id]["nuevos"] += 1

    return render_template(
        "mensajes.html",
        usuario=usuario,
        user_id=user_id,
        conversaciones=list(conversaciones.values()),
        unread_count=Mensaje.query.filter_by(receptor_id=user_id, leido=False).count(),
    )

@app.route("/buscar/<int:user_id>")
def buscar(user_id):
    query = request.args.get("q", "").strip()
    if len(query) < 2:
        return jsonify([])

    usuarios = Usuario.query.filter(
        (Usuario.usuario.ilike(f"%{query}%")) |
        (Usuario.nombre.ilike(f"%{query}%"))
    ).limit(10).all()

    return jsonify([
        {
            "id": usuario.id,
            "usuario": usuario.usuario,
            "nombre": usuario.nombre or "",
        }
        for usuario in usuarios
        if usuario.id != user_id
    ])

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))  # Render asigna el puerto
    app.run(host="0.0.0.0", port=port, debug=True)

