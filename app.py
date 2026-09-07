from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import base64
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = "clave_secreta"
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False  # Cambiar a True en producción con HTTPS

# Configuración de uploads
UPLOAD_FOLDER = 'static/uploads'
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov', 'ogg'}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ADMIN_USERNAME = "ADMIN1"
ADMIN_PASSWORD = "LDFMLUIS"

# Crear carpeta de uploads si no existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def file_extension(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

# En Render, DATABASE_URL debe apuntar a una base PostgreSQL persistente.
# Si no existe, se conserva SQLite para desarrollo local.
database_url = os.environ.get('DATABASE_URL', 'sqlite:///usuarios.db')
if database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql+psycopg2://', 1)
elif database_url.startswith('postgresql://'):
    database_url = database_url.replace('postgresql://', 'postgresql+psycopg2://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
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
    foto_data = db.Column(db.Text)  # Imagen subida, guardada en la base de datos

# Modelo de posts
class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.Text, nullable=False)
    imagen = db.Column(db.String(255))  # Ruta de imagen
    video = db.Column(db.String(255))
    autor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    autor = db.Column(db.String(80), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    
    likes_count = db.relationship('Like', cascade='all, delete-orphan', lazy=True)
    comentarios = db.relationship('Comentario', cascade='all, delete-orphan', lazy=True,
                                  order_by='Comentario.fecha.asc()')

class Comentario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    contenido = db.Column(db.Text, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    usuario = db.relationship('Usuario', foreign_keys=[usuario_id])

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
    video = db.Column(db.String(255))
    leido = db.Column(db.Boolean, default=False, nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    emisor = db.relationship('Usuario', foreign_keys=[emisor_id])
    receptor = db.relationship('Usuario', foreign_keys=[receptor_id])

class Seguidor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seguidor_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    seguido_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint('seguidor_id', 'seguido_id', name='unique_seguidor'),)

class Bloqueo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    bloqueador_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    bloqueado_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (db.UniqueConstraint('bloqueador_id', 'bloqueado_id', name='unique_bloqueo'),)

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
    if 'video' not in {column['name'] for column in inspect(db.engine).get_columns('mensaje')}:
        with db.engine.begin() as connection:
            connection.execute(text('ALTER TABLE mensaje ADD COLUMN video VARCHAR(255)'))
    if 'video' not in {column['name'] for column in inspect(db.engine).get_columns('post')}:
        with db.engine.begin() as connection:
            connection.execute(text('ALTER TABLE post ADD COLUMN video VARCHAR(255)'))
    if 'foto_data' not in {column['name'] for column in inspect(db.engine).get_columns('usuario')}:
        with db.engine.begin() as connection:
            connection.execute(text('ALTER TABLE usuario ADD COLUMN foto_data TEXT'))

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form.get("usuario", "").strip()
        usuario_sin_arroba = usuario.lstrip("@").strip()
        password = request.form.get("password", "")

        # Validación básica
        if not usuario or not password:
            flash("Usuario y contraseña son requeridos.")
            return redirect(url_for("login"))

        if usuario.upper() == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session.clear()
            session['is_admin'] = True
            session['usuario'] = ADMIN_USERNAME
            return redirect(url_for("admin_panel"))

        try:
            user = Usuario.query.filter(
                (Usuario.usuario == usuario_sin_arroba) |
                (Usuario.usuario == usuario)
            ).first()
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

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get('is_admin'):
            flash("Acceso exclusivo del administrador.")
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped

@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        telefono = request.form.get("telefono", "").strip()
        usuario = request.form.get("usuario", "").strip().lstrip("@").strip()
        password = request.form.get("password", "")

        # Validaciones
        if not telefono.isdigit():
            flash("El número de teléfono debe contener solo dígitos.")
            return redirect(url_for("registro"))

        if not usuario:
            flash("El nombre de usuario es obligatorio.")
            return redirect(url_for("registro"))

        if usuario.upper() == ADMIN_USERNAME:
            flash("Ese nombre de usuario está reservado.")
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
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("El usuario o el número de teléfono ya están registrados.")
            return redirect(url_for("registro"))

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
        video = None
        
        # Manejar upload de imagen
        if 'imagen' in request.files:
            file = request.files['imagen']
            extension = file_extension(file.filename) if file and file.filename else ''
            if file and file.filename and extension in IMAGE_EXTENSIONS:
                filename = secure_filename(f"{user.id}_{datetime.now().timestamp()}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                imagen = f"uploads/{filename}"

        if 'video' in request.files:
            file = request.files['video']
            extension = file_extension(file.filename) if file and file.filename else ''
            if file and file.filename and extension in VIDEO_EXTENSIONS:
                filename = secure_filename(f"video_{user.id}_{datetime.now().timestamp()}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                video = f"uploads/{filename}"
        
        if texto or imagen or video:
            nuevo_post = Post(texto=texto, imagen=imagen, video=video,
                              autor_id=user.id, autor=user.usuario)
            db.session.add(nuevo_post)
            db.session.commit()
            flash("Post publicado correctamente.")
    return redirect(url_for("home", user_id=user_id))

@app.route("/comentar/<int:post_id>/<int:user_id>", methods=["POST"])
def comentar(post_id, user_id):
    contenido = request.form.get("comentario", "").strip()
    post = Post.query.get(post_id)
    user = Usuario.query.get(user_id)
    if post and user and contenido:
        db.session.add(Comentario(contenido=contenido, usuario_id=user.id, post_id=post.id))
        db.session.commit()
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
        siguiendo = Seguidor.query.filter_by(
            seguidor_id=current_user_id, seguido_id=user_id
        ).first() is not None
        bloqueado = Bloqueo.query.filter_by(
            bloqueador_id=current_user_id, bloqueado_id=user_id
        ).first() is not None
        seguidores_count = Seguidor.query.filter_by(seguido_id=user_id).count()
        seguidos_count = Seguidor.query.filter_by(seguidor_id=user_id).count()
        return render_template(
            "perfil.html", usuario=usuario, current_user_id=current_user_id,
            siguiendo=siguiendo, bloqueado=bloqueado,
            seguidores_count=seguidores_count, seguidos_count=seguidos_count,
        )
    else:
        flash("Usuario no encontrado.")
        return redirect(url_for("index"))

@app.route("/seguir/<int:target_id>/<int:current_user_id>", methods=["POST"])
def seguir(target_id, current_user_id):
    if target_id != current_user_id:
        existing = Seguidor.query.filter_by(
            seguidor_id=current_user_id, seguido_id=target_id
        ).first()
        blocked = Bloqueo.query.filter(
            ((Bloqueo.bloqueador_id == current_user_id) & (Bloqueo.bloqueado_id == target_id)) |
            ((Bloqueo.bloqueador_id == target_id) & (Bloqueo.bloqueado_id == current_user_id))
        ).first()
        if blocked:
            flash("No puedes seguir a este usuario mientras exista un bloqueo.")
        elif existing:
            db.session.delete(existing)
        else:
            db.session.add(Seguidor(seguidor_id=current_user_id, seguido_id=target_id))
        db.session.commit()
    return redirect(url_for("perfil", user_id=target_id, current_user_id=current_user_id))

@app.route("/bloquear/<int:target_id>/<int:current_user_id>", methods=["POST"])
def bloquear(target_id, current_user_id):
    if target_id != current_user_id:
        existing = Bloqueo.query.filter_by(
            bloqueador_id=current_user_id, bloqueado_id=target_id
        ).first()
        if existing:
            db.session.delete(existing)
        else:
            db.session.add(Bloqueo(bloqueador_id=current_user_id, bloqueado_id=target_id))
            relationship = Seguidor.query.filter(
                ((Seguidor.seguidor_id == current_user_id) & (Seguidor.seguido_id == target_id)) |
                ((Seguidor.seguidor_id == target_id) & (Seguidor.seguido_id == current_user_id))
            ).all()
            for item in relationship:
                db.session.delete(item)
        db.session.commit()
    return redirect(url_for("perfil", user_id=target_id, current_user_id=current_user_id))

@app.route("/seguidores/<int:user_id>/<int:current_user_id>")
def seguidores(user_id, current_user_id):
    usuario = Usuario.query.get(user_id)
    if not usuario:
        flash("Usuario no encontrado.")
        return redirect(url_for("index"))
    followers = [item.seguidor_id for item in Seguidor.query.filter_by(seguido_id=user_id).all()]
    seguidores_users = Usuario.query.filter(Usuario.id.in_(followers)).all() if followers else []
    return render_template(
        "seguidores.html", usuario=usuario, current_user_id=current_user_id,
        seguidores=seguidores_users, titulo="Seguidores", vacio="Todavía no tiene seguidores.",
    )

@app.route("/seguidos/<int:user_id>/<int:current_user_id>")
def seguidos(user_id, current_user_id):
    usuario = Usuario.query.get(user_id)
    if not usuario:
        flash("Usuario no encontrado.")
        return redirect(url_for("index"))
    followed = [item.seguido_id for item in Seguidor.query.filter_by(seguidor_id=user_id).all()]
    seguidos_users = Usuario.query.filter(Usuario.id.in_(followed)).all() if followed else []
    return render_template(
        "seguidores.html", usuario=usuario, current_user_id=current_user_id,
        seguidores=seguidos_users, titulo="Amigos agregados", vacio="Todavía no ha agregado amigos.",
    )

@app.route("/admin")
@admin_required
def admin_panel():
    return render_template(
        "admin.html", usuarios=Usuario.query.order_by(Usuario.id.desc()).all(),
        posts=Post.query.order_by(Post.fecha.desc()).all(),
        comentarios=Comentario.query.order_by(Comentario.fecha.desc()).all(),
        mensajes=Mensaje.query.order_by(Mensaje.fecha.desc()).all(),
    )

@app.route("/admin/eliminar", methods=["POST"])
@admin_required
def admin_eliminar():
    user_ids = {int(value) for value in request.form.getlist("user_ids")}
    post_ids = {int(value) for value in request.form.getlist("post_ids")}
    comment_ids = {int(value) for value in request.form.getlist("comment_ids")}
    message_ids = {int(value) for value in request.form.getlist("message_ids")}

    for user_id in user_ids:
        user_posts = Post.query.filter_by(autor_id=user_id).all()
        post_ids.update(post.id for post in user_posts)
        Seguidor.query.filter((Seguidor.seguidor_id == user_id) | (Seguidor.seguido_id == user_id)).delete(synchronize_session=False)
        Bloqueo.query.filter((Bloqueo.bloqueador_id == user_id) | (Bloqueo.bloqueado_id == user_id)).delete(synchronize_session=False)
        Comentario.query.filter_by(usuario_id=user_id).delete(synchronize_session=False)
        Mensaje.query.filter((Mensaje.emisor_id == user_id) | (Mensaje.receptor_id == user_id)).delete(synchronize_session=False)
        Like.query.filter_by(usuario_id=user_id).delete(synchronize_session=False)

    if post_ids:
        Comentario.query.filter(Comentario.post_id.in_(post_ids)).delete(synchronize_session=False)
        Like.query.filter(Like.post_id.in_(post_ids)).delete(synchronize_session=False)
        Post.query.filter(Post.id.in_(post_ids)).delete(synchronize_session=False)
    if comment_ids:
        Comentario.query.filter(Comentario.id.in_(comment_ids)).delete(synchronize_session=False)
    if message_ids:
        Mensaje.query.filter(Mensaje.id.in_(message_ids)).delete(synchronize_session=False)
    if user_ids:
        Usuario.query.filter(Usuario.id.in_(user_ids)).delete(synchronize_session=False)

    db.session.commit()
    flash("Elementos seleccionados eliminados.")
    return redirect(url_for("admin_panel"))

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
        foto = request.files.get("foto")
        if foto and foto.filename:
            extension = file_extension(foto.filename)
            if extension not in IMAGE_EXTENSIONS:
                flash("La foto debe ser PNG, JPG, JPEG, GIF o WEBP.")
                return redirect(url_for("editar_perfil", user_id=user_id))
            contenido = foto.read()
            if len(contenido) > 4 * 1024 * 1024:
                flash("La foto de perfil no puede superar 4 MB.")
                return redirect(url_for("editar_perfil", user_id=user_id))
            mime = foto.mimetype or f"image/{extension}"
            usuario.foto_data = f"data:{mime};base64,{base64.b64encode(contenido).decode('ascii')}"
        
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
        video = None
        archivo = request.files.get("imagen")
        archivo_video = request.files.get("video")

        if archivo and archivo.filename:
            if not allowed_file(archivo.filename):
                flash("El formato de la imagen no está permitido.")
                return redirect(url_for("chat", emisor_id=emisor.id, receptor_id=receptor.id))

            filename = secure_filename(
                f"chat_{emisor.id}_{receptor.id}_{datetime.now().timestamp()}_{archivo.filename}"
            )
            archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            imagen = f"uploads/{filename}"

        if archivo_video and archivo_video.filename:
            if file_extension(archivo_video.filename) not in VIDEO_EXTENSIONS:
                flash("El formato del video no está permitido.")
                return redirect(url_for("chat", emisor_id=emisor.id, receptor_id=receptor.id))
            filename = secure_filename(
                f"chat_video_{emisor.id}_{receptor.id}_{datetime.now().timestamp()}_{archivo_video.filename}"
            )
            archivo_video.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            video = f"uploads/{filename}"

        if contenido or imagen or video:
            nuevo_mensaje = Mensaje(
                emisor_id=emisor.id,
                receptor_id=receptor.id,
                contenido=contenido,
                imagen=imagen,
                video=video,
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

