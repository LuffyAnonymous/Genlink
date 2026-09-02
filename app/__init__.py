from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from app.config import Config
from app.extensions import db, login_manager, mail, csrf


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Behind a reverse proxy (nginx terminating TLS in front of gunicorn),
    # Flask otherwise has no way to know the original request was HTTPS on
    # www.genlinklab.com - url_for(_external=True) would build http:// links
    # pointing at the internal host/port instead.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please log in to continue."
    login_manager.login_message_category = "error"

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from app.main.routes import main_bp
    from app.auth.routes import auth_bp
    from app.billing.routes import billing_bp
    from app.api.routes import api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(billing_bp, url_prefix="/credits")
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.context_processor
    def inject_globals():
        return {"admin_email": app.config["ADMIN_EMAIL"]}

    return app
