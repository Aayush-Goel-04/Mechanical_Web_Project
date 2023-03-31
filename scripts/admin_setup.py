#change password
import os, sys
# sys.path.insert(0, '/var/www/ME/')
# sys.path.insert(0, '/var/www/ME/flaskapp')

sys.path.insert(0, "C:/Users/HP/myprojects/mechweb")
sys.path.insert(0, "C:/Users/HP/myprojects/mechweb/flaskapp")

from sqlalchemy.exc import IntegrityError
from flaskapp import db, bcrypt
import os, settings

if not os.path.exists(settings.DATABASE_FILE):
    print(db)
    db.create_all()
    db.session.commit()
    print('\nEmptied Old Database and Recreated all The Database Classes.\nCurrently no data present.\n')

from flaskapp.models import Faculty

def create_new_admin():
    ldap = input('Enter Ldap : ')
    password = input('Enter the new password (length > 8) : ')
    if password.count(' ') != 0 or not password or len(password)<9:
        print('Error ! Password not accepted, Try Again.\n')
        return create_new_admin()
    hashed_password = bcrypt.generate_password_hash(password=password)
    f = Faculty(ldap=ldap,
                name=ldap,
                email=ldap+'@iitb.ac.in',
                password=hashed_password,
                role='admin', is_active=1)
    db.session.add(f)
    print('Creating Admin Account : Ldap('+ldap+'), email('+ldap+'@iitb.ac.in), role(admin)')
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return print('Error, Ldap or Email Already Exists')
    return print('Admin Account Created email = '+ldap+'@iitb.ac.in !!')

def delete_all_admins():
    if input('Enter YES to proceed : ') == 'YES':
        admins = Faculty.query.filter_by(role='admin').all()
        if not admins:
            return print('No Admin Accounts Exist')
        for admin in admins:
            db.session.delete(admin)
        db.session.commit()
        return print(str(len(admins))+' Admin Accounts Deleted')

def change_password():
    ldap = input('Enter Ldap : ')
    admin = Faculty.query.filter_by(ldap=ldap,role='admin').first()
    if admin:
        password = input('Enter the new password (Length > 8) : ')
        if password.count(' ') != 0 or not password or len(password)<9:
            print('Error ! Password not accepted, Try Again.\n')
            return change_password(ldap)
        hashed_password = bcrypt.generate_password_hash(password=password)
        admin.password = hashed_password
        db.session.commit()
        return print('password changed !!')
    else:
        return print('Error ! Admin Ldap doesnt exist.')

def get_admin_list():
    admin = [a.ldap for a in Faculty.query.filter_by(role='admin')]
    if admin:
        return print('Ldaps = '+str(admin))
    else:
        
        return print('No Admin Account Exists')

def start_system():
    choice = int(input('\nEnter Choice : '))
    if choice == 1:
        create_new_admin()
    elif choice == 2:
        delete_all_admins()
    elif choice == 3:
        change_password()
    elif choice == 4:
        get_admin_list()
    elif choice == 5:
        return print('exited')
    else:
        print('Wrong Choice')
    return start_system()

print('You can perform the following functions : \n'
      ' 1 - Create New Admin\n'
      ' 2 - Delete All Admin Accounts\n'
      ' 3 - Change Admin Account Password\n'
      ' 4 - Get Admin List\n'
      ' 5 - Quit')

start_system()
