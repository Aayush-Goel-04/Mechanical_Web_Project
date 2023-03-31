import sys
# sys.path.insert(0, '/var/www/ME')
# sys.path.insert(0, '/var/www/ME/flaskapp')

sys.path.insert(0, "C:/Users/HP/myprojects/mechweb")
sys.path.insert(0, "C:/Users/HP/myprojects/mechweb/flaskapp")

from flask import Flask
from flask_bcrypt import Bcrypt
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_apscheduler import APScheduler
import os, filelock, pickle, settings, secrets, mail_queue, mail_handler

class Config:
    SCHEDULER_API_ENABLED = True

app = Flask(__name__)
app.config['SECRET_KEY'] = 'efa4e75b6bc398d5dfc9b9635aa6353a' # secrets.token_hex(16)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = 0
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///%s' % (settings.DATABASE_FILE)
app.config.from_object(Config())

db = SQLAlchemy(app, session_options={"autoflush": False})
bcrypt = Bcrypt(app)
migrate = Migrate(app,db)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

#app.config['MAIL_SERVER'] = settings.mail_server
#app.config['MAIL_PORT'] = settings.mail_port
#app.config['MAIL_USE_TLS'] = True
#app.config['MAIL_USERNAME'] = settings.sender_email
#app.config['MAIL_PASSWORD'] = settings.sender_password
#mail = Mail(app)


db.init_app(app)

migrate.init_app(app, db)
scheduler = APScheduler()
scheduler.init_app(app)
scheduler.start()

mailQueue = mail_queue.MAIL_QUEUE()
mailHandler = mail_handler.MAIL_HANDLER()

from flaskapp import routes
