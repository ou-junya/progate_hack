from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import stripe
import boto3
import json
import os
from dotenv import load_dotenv


db = SQLAlchemy()


def create_app():
    """
    データベースを初期化してブループリントを登録するというアプリケーションを作成する機能がある。
    ここでは、SQLAlchemyを初期化し、設定し、ブループリントを登録する必要がある。
    """
    app = Flask(__name__)

    load_dotenv()

    AWS_KEY = os.getenv("AWS_KEY")
    AWS_SECRET_KEY = os.getenv("AWS_SECRET_KEY")

    bedrock = boto3.client(service_name='bedrock', 
    region_name='us-east-1', 
    aws_access_key_id=AWS_KEY, 
    aws_secret_access_key=AWS_SECRET_KEY)


    app.config["SECRET_KEY"] = "secret-key-goes-here"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///db.sqlite"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["STRIPE_API_KEY"] = os.getenv("STRIPE_API_KEY")
    app.config["STRIPE_PUBLISHABLE_KEY"] = os.getenv("STRIPE_PUBLISHABLE_KEY")

    stripe.api_key = app.config["STRIPE_API_KEY"]

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from .auth import auth as auth_blueprint

    app.register_blueprint(auth_blueprint)

    from .main import main as main_bluerint

    app.register_blueprint(main_bluerint)

    with app.app_context():
        db.create_all()

    return app
