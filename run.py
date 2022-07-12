from flaskblog import app , db, bcrypt
from flaskblog.models import Faculty

if __name__ == '__main__':
    '''
    db.drop_all()
    db.create_all()

    hashed_password = bcrypt.generate_password_hash('admin').decode('utf-8')
    admin = Faculty(name = 'admin',email="admin@iitb.ac.in",ldap='admin123',password=hashed_password,role='admin',is_active=1)
    db.session.add(admin)
    db.session.commit()

    '''
    # Start App
    app.run(debug=True)