from datetime import datetime,date
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import backref
from flaskblog import db, login_manager
from flask_login import UserMixin
import enum

@login_manager.user_loader
def load_user(faculty_id):
    return Faculty.query.get(int(faculty_id))

class Semester(db.Model): # Semesters created by admin
    id = db.Column(db.Integer, primary_key=True)
    semester = db.Column(db.String(50, collation='NOCASE'),nullable=False)
    year = db.Column(db.Integer,nullable=False)
    def __repr__(self):
        return str(self.semester)

class Faculty(db.Model, UserMixin):  # List of all the facultys
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255, collation='NOCASE'), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=True, default='')
    role = db.Column(db.String(50), nullable=True, default='')
    is_active = db.Column('is_active', db.Boolean(), nullable=True, default=1)  # If facutly is part of IITB system or not
    # User information
    name = db.Column(db.String(60),nullable = True, default='')
    ldap =  db.Column(db.String(50), nullable=False, unique=True)
    field = db.Column(db.String(255, collation='NOCASE'),nullable = True, default='All')
    courses = association_proxy('course_faculty','course')
    facad = association_proxy('facad', 'student')
    semesters = association_proxy('faculty_semester', 'semester')
    def __repr__(self):
        return str(self.name)+' - '+str(self.ldap)

class Course(db.Model):  #List of Courses
    id = db.Column(db.Integer, primary_key=True)
    field = db.Column(db.String(255, collation='NOCASE'), default='null', nullable=True)
    code = db.Column(db.String(10), nullable=False, unique=True)
    name = db.Column(db.String(60), nullable=True, default='')
    instructors = association_proxy('course_faculty', 'faculty')
    tas = association_proxy('course_ta', 'ta')
    semesters = association_proxy('course_semester', 'semester')
    def __repr__(self):
        return str(self.code)+" - "+ str(self.name)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    alt_email = db.Column(db.String(120), unique=True, nullable=True,default='')
    roll_number = db.Column(db.String(20), unique=True, nullable=False,default='')
    phone_number = db.Column(db.String(20), unique=True, nullable=True,default='')
    program = db.Column(db.String(50), nullable=True,default='')
    field = db.Column(db.String(255, collation='NOCASE'), nullable=True, default = 'All')
    courses = association_proxy('course_ta', 'course')
    facad = association_proxy('facad', 'faculty')
    semesters = association_proxy('semester_semester', 'semester')
    hostel_no = db.Column(db.Integer)
    room_no = db.Column(db.Integer)

    def __repr__(self):
        return f"{self.name} - {self.roll_number}"

class Course_Semester(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    semester_id = db.Column(db.Integer, db.ForeignKey('semester.id'), nullable=False)
    course = db.relationship(Course, backref=backref("course_semester", cascade="all,delete"))
    semester = db.relationship(Semester, backref=backref("course_semester", cascade="all,delete"))
    is_mandatory = db.Column('is_mandatory', db.Boolean(), default=1)

class Faculty_Semester(db.Model):   # Holds Faculty Status if Entry exits faculty is inactive in that semester
    id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty.id'), nullable=False)
    semester_id = db.Column(db.Integer, db.ForeignKey('semester.id'), nullable=False)
    faculty = db.relationship(Faculty, backref=backref("faculty_semester", cascade="all,delete"))
    semester = db.relationship(Semester, backref=backref("faculty_semester", cascade="all,delete"))
    is_active = db.Column('is_active', db.Boolean(), nullable=True, default=1)

    def __repr__(self):
        return f"'{self.semester_id}' - '{self.is_active}'"

class Student_Semester(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    semester_id = db.Column(db.Integer, db.ForeignKey('semester.id'), nullable=False)
    student = db.relationship(Student, backref=backref("student_semester", cascade="all,delete"))
    semester = db.relationship(Semester, backref=backref("student_semester", cascade="all,delete"))
    is_active = db.Column('is_active', db.Boolean(), nullable=True, default=1)

    def __repr__(self):
        return f"'{self.semester_id}' - '{self.is_active}'"


class Course_Faculty(db.Model):
    id = db.Column('id', db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty.id'), nullable=False)
    semester_id = db.Column(db.Integer, db.ForeignKey('semester.id'), nullable=False)
    maxTA = db.Column(db.Integer, nullable=True, default=30)
    section = db.Column(db.String(5),nullable = False)
    course = db.relationship(Course, backref=backref("course_faculty", cascade="all,delete"))
    faculty = db.relationship(Faculty, backref=backref("course_faculty", cascade="all,delete"))
    semester = db.relationship(Semester, backref=backref("course_faculty", cascade="all,delete"))

    def __repr__(self):
        return "course: "+str(self.course_id)+"  TA: "+ str(self.faculty_id) + ' - '+ str(self.semester)

class Course_Ta(db.Model):

    id = db.Column('id', db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    semester_id = db.Column(db.Integer, db.ForeignKey('semester.id'), nullable=False)
    section = db.Column(db.String(5),nullable = False)
    course = db.relationship(Course, backref=backref("course_ta", cascade="all,delete"))
    ta = db.relationship(Student, backref=backref("course_ta", cascade="all,delete"))
    semester = db.relationship(Semester, backref=backref("course_ta", cascade="all,delete"))
    
    def __repr__(self):
        return "course: "+str(self.course_id)+"  TA: "+ str(self.student_id) + ' - '+ str(self.semester)

class Attendance(db.Model):
    id = db.Column('id', db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    student = db.relationship(Student, backref=backref("attendance", cascade="all,delete"))
    date_posted = db.Column(db.Date, nullable=False, default=date.today)
    datetime_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def __repr__(self):
        return "Student: "+str(self.student_id)+"  Date: "+ str(self.date_posted.strftime('%Y-%m-%d'))

class Student_token(db.Model):
    id = db.Column('id', db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'))
    student = db.relationship(Student, backref=backref("student_token", cascade="all,delete"))
    token = db.Column(db.String(40), unique=True)

    def __repr__(self):
        return "Student: "+str(self.student_id)+"  token: "+ self.token

class Facad(db.Model):
    id = db.Column('id', db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    student = db.relationship(Student, backref=backref("facad", cascade="all,delete"))
    facad_id = db.Column(db.Integer, db.ForeignKey('faculty.id'), nullable=False)
    facad = db.relationship(Faculty, backref=backref("facad", cascade="all,delete"))
    status = db.Column(db.String(10), nullable=False) # primary / secondary

    def __repr__(self):
        return "Student: "+str(self.student_id)+"  Faculty: "+ str(self.facad.id)+" Status:"+str(self.status)