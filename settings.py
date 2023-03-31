WEB_URL = "http://127.0.0.1:5000"

# ROOT_DIR = "/var/www/ME/"
ROOT_DIR = "C:/Users/HP/myprojects/mechweb/"
APP_DIR = ROOT_DIR + "/flaskapp/"
DATA_DIR = ROOT_DIR + "data/"
MAIL_DIR = DATA_DIR + "/mails/"  
EXCEL_DIR = DATA_DIR + '/excels/'
PDF_DIR = DATA_DIR + '/pdfs/'
DATABASE_FILE = DATA_DIR + 'site.db'



# Mail Configuration
mail_port = 587
mail_server = 'smtp-auth.iitb.ac.in'
sender_email = 'admin@me.iitb.ac.in'
server_email = "office.me@iitb.ac.in"
server_password = 'meiitb@'

attendance_mail_reciever = 'goelaayush697@gmail.com'

faculty_password_timeout = {'hours':12, 'minutes':00}
student_token_timeout = {'hours':12, 'minutes':00}


'''Send mails to student who havent marked attendance for last __ days'''
attendance_days = 7
debug = True

#----------------------------------------------------------------------------
grade_map = ['AA','AB','BB','BC','CC','CD','DD','DE','EE','EF','FF']
course_columns = ['field', 'code', 'name']
faculty_columns=['name', 'ldap', 'email', 'field', 'phone_number','status']
student_columns=['name', 'email', 'rollno', 'program', 'field', 'status','category']

pandas_course_map = {'code' : 'code', \
                     'field' : 'field', \
                     'name' : 'name'}
pandas_faculty_map = {'name': 'name',\
                      'ldap' : 'ldap', \
                      'email' : 'email',\
                      'field' : 'field', \
                      'phone_number' : 'phone_number', \
                      'status' : 'status'}
pandas_student_map = {'name' : 'name', \
                      'email' : 'email',\
                      'rollno' : 'rollno', \
                      'program' : 'program', \
                      'field' : 'field', \
                      'category' : 'category', \
                      'status' : 'status'}


# Semester Seasons
''' 1st Semester in each institute year'''
NEW_SEM = 'Fall'

''' Defines which semester comes after Fall / Spring / Summer'''
SEASONS = {'Fall':'Spring', 'Spring':'Summer', 'Summer':'Fall',}

# Default program for students
default_program = 'BTech'
''' Default program for students if not mentioned'''
PROGRAMS = ['BTech', 'Phd', 'MTech', 'DD']

# Field for Course Students Facultys
default_field = 'ALL'
'''Field for entries with no specific field'''
FIELDS = ['TFE','MFG','DES']
ALLFIELDS = FIELDS + ['ALL']

# Student Categories
CATEGORIES = ['rap', 'miscellaneous','external','externalgovernmentfellowship','instituteta','projectstaff',
            'tap','sponsored','pmrf','foreignnational','selffinance','researchassistant']
active_ta_categories = ['rap','instituteta','pmrf','miscellaneous']
default_category = 'miscellaneous'

# Mails to Coordinators.
# Don't Change dict keys
coord_mail = {
    'subject':"Assigned as Coordinator",
    'body_':"Dear Prof., <br> You have been assigned as coordinator for %s field for semester %s. <br>"
            'You can login using -<br>    <a href="%s"> Login Link </a><br>'
}


# Mails to Faculty that contains login links.
# Don't Change dict keys
faculty_login_mail = {
    'subject':"Faculty login details",
    'body_':'You can login using -<br><a href="%s"> My Link </a><br><br>'
            "This link will be valid for "+str(faculty_password_timeout['hours'])+" hours & "+str(faculty_password_timeout['minutes'])+" minutes.<br><br>"
            "If the above link doesnt work use your ldap and alond with this password : %s to login at %s.<br><br>"
            "If the link has expired you will need to generate a new link at %s<br>"
}

# Mails Send to Faculty After Course Allot.
# Don't Change dict keys
faculty_course_allot_mail = {
    'subject':'TA Allotment',
    'body_':"Dear Prof. %s,<br>"
            "You can check the courses you have been alloted for Semester : %s at<br><br>"
            '<a href="%s"> Login Link </a><br>'
            "At this point, please indicate your preference for Teaching Assistants by making your choices via the above link.<br>"
}

# Mails Send to Faculty who are part of Student Grading committee
# Don't Change dict keys
grade_mail_committee = {
    'subject':'Student Grade',
    'body_':"Dear Prof. %s,<br>"
            "Faculty Advisor %s of Student %s has graded the student."
            "%s"
}
# in body_ %s (faculty name, student name, faculty name, html table showing grade data)

# Student token mail configuration
# Don't Change dict keys
student_token_mail = {
    'subject' : 'Login Details',
    'body_' : 'Dear %s,<br><br>Go to <a href="%s"> My Link </a> to update your details and acknowledge your employement with ME @ IITB.<br><br>The provided token is valid for %s hours & %s minutes'
}

# Mail configuration for regular student mails.
# Don't Change dict keys
student_mail = {
    'subject':"Acknowldegement Notice",
    'body_':"This is a reminder to acknowldege your employment with IITB.<br>"
            'Go to <a href="%s"> Login Link </a> and generate link to update your profile data, check TA duties, Faculty advisor(s), and acknowldege your employment with ME @ IITB.<br><br> Please note that this is NOT an attendance. You still need to mark your bio-metric attendance regularly in the ME building.<br><br>'
}