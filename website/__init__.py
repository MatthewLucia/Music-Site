from flask import Flask


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = '&jL82hB%#h@k!9l!h'

    app.config['SESSION_TYPE'] = 'filesystem'
    app.config['SESSION_PERMANENT'] = True
    app.config['SESSION_USE_SIGNER'] = True

    from .views import views

    app.register_blueprint(views, url_prefix='/')

    return app
