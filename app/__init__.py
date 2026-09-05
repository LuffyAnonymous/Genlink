from flask import Flask, flash, redirect, request, url_for, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
from app.config import Config
from app.extensions import db, login_manager, csrf, limiter


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
    csrf.init_app(app)
    limiter.init_app(app)

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
    from app.admin.routes import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(billing_bp, url_prefix="/credits")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    @app.context_processor
    def inject_globals():
        return {"admin_email": app.config["ADMIN_EMAIL"]}

    @app.template_filter("initials")
    def initials_filter(name):
        parts = [p for p in (name or "").split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][0].upper()
        return (parts[0][0] + parts[-1][0]).upper()

    @app.errorhandler(429)
    def rate_limited(e):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "rate_limited", "message": "Too many requests - please slow down and try again shortly."}), 429
        flash("Too many attempts - please wait a minute and try again.", "error")
        return redirect(request.referrer or url_for("main.index"))

    @app.after_request
    def set_security_headers(response):
        # HSTS only means anything - and is only sent - over an actual HTTPS
        # response; browsers ignore it entirely over plain http://, so this
        # is a no-op in local dev without needing a separate flag for it.
        if request.is_secure:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        # Registration-confirm and payment-return URLs carry sensitive
        # tokens in the query string - this keeps them from leaking to a
        # third-party site's server logs via the Referer header on an
        # outbound link (e.g. the "Contact support" mailto, ticket links).
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Templates rely on inline <script> blocks and Tailwind's play-CDN
        # script throughout, so this isn't as strict as a nonce-based CSP
        # could be - but it still blocks loading scripts/styles/frames from
        # anywhere unlisted, which is the bulk of what CSP defends against.
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            # form-action covers the whole redirect chain a form submission
            # can end on, not just the form's own target - our buy-credits
            # form posts to our own /credits/... route (self), but THAT
            # route responds with a redirect straight to the payment
            # provider's own checkout page, so both providers' domains
            # need to be allowed here too or the browser silently blocks
            # ever reaching them (caught by an actual live checkout test).
            "form-action 'self' https://checkout.stripe.com https://www.paypal.com https://www.sandbox.paypal.com"
        )
        return response

    return app
