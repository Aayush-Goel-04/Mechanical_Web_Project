from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import backref
from flaskapp import db, login_manager
from flask_login import UserMixin
import settings

@login_manager.user_loader
def load_user(faculty_id):
    return Faculty.query.get(int(faculty_id))

class Semester(db.Model): # Semesters created by admin
    id = db.Column(db.Integer, primary_key=True)
    semester = db.Column(db.String(50, collation='NOCASE'),nullable=False)
    year = db.Column(db.Integer,nullable=False)
    students = association_proxy('student_semester', 'student')
    is_current = db.Column('is_current', db.Boolean(), default=0)
    def __repr__(self):
        return str(self.semester)

class Faculty(db.Model, UserMixin):  # List of all the facultys
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255, collation='NOCASE'), nullable=False, unique=True)
    password = db.Column(db.String(255), nullable=True, default='')
    role = db.Column(db.String(50), nullable=True, default='faculty')
    is_active = db.Column('is_active', db.Boolean(), nullable=True, default=1)  # If facutly is part of IITB system or not
    # User information
    name = db.Column(db.String(60),nullable = True, default='')
    phone_number = db.Column(db.String(20), nullable=True,default='')
    ldap =  db.Column(db.String(50), nullable=False, unique=True)
    field = db.Column(db.String(255, collation='NOCASE'),nullable = True, default=settings.default_field)
    courses = association_proxy('course_faculty','course')
    facad = association_proxy('facad', 'student')
    semesters = association_proxy('faculty_semester', 'semester')
    coordinator_sems = association_proxy('coordinator_semester', 'semester')
    def __repr__(self):
        return str(self.name)+' | '+str(self.ldap)

class Coordinator_Semester(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty.id'), nullable=False)
    semester_id = db.Column(db.Integer, db.ForeignKey('semester.id'), nullable=False)
    field = db.Column(db.String(255, collation='NOCASE'),nullable = True)
    faculty = db.relationship(Faculty, backref=backref("coordinator_semester", cascade="all,delete"))
    semester = db.relationship(Semester, backref=backref("coordinator_semester", cascade="all,delete"))

    def __repr__(self):
        return f"'{self.semester_id}' - ' {self.faculty_id} ' - ' {self.field}'"

class Course(db.Model):  #List of Courses
    id = db.Column(db.Integer, primary_key=True)
    field = db.Column(db.String(255, collation='NOCASE'), default='null', nullable=True)
    code = db.Column(db.String(10), nullable=False, unique=True)
    name = db.Column(db.String(60), nullable=True, default='')
    def __repr__(self):
        return str(self.code)+" - "+ str(self.name)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=False)
    alt_email = db.Column(db.String(120), nullable=True,default='')
    roll_number = db.Column(db.String(20), unique=True, nullable=False,default='')
    phone_number = db.Column(db.String(20), nullable=True,default='')
    program = db.Column(db.String(50), nullable=True,default=settings.default_program)
    category = db.Column(db.String(50), nullable=True,default=settings.default_category)
    field = db.Column(db.String(255, collation='NOCASE'), nullable=True, default =settings.default_field)
    project = db.Column(db.String(500),nullable=True,default="NA")
    hostel_no = db.Column(db.Integer)
    room_no = db.Column(db.Integer)
    # records last grades given for project and seminar
    last_project = db.Column(db.String(100),nullable=True,default="NA")
    last_seminar = db.Column(db.String(100),nullable=True,default="NA")
    last_attendance = db.Column(db.Date,nullable=True)
    facad = association_proxy('facad', 'faculty')
    # details of the last grade given

    def __repr__(self):
        return f"{self.name} - {self.roll_number}"

class Course_Semester(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    semester_id = db.Column(db.Integer, db.ForeignKey('semester.id'), nullable=False)
    course = db.relationship(Course, backref=backref("course_semester", cascade="all,delete"))
    semester = db.relationship(Semester, backref=backref("course_semester", cascade="all,delete"))
    is_mandatory = db.Column('is_mandatory', db.Boolean(), default=1)

class Faculty_Semester(db.Model):   # Holds Faculty Status if Entry exists then faculty is inactive in that semester
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
    active_ta = db.Column('active_ta', db.Boolean(), nullable=True, default=1)
    exemption_reason = db.Column(db.String(500),nullable=True,default='NA')

    def __repr__(self):
        return str(self.semester_id)

class Course_Faculty(db.Model):
    id = db.Column('id', db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey('faculty.id'), nullable=False)
    semester_id = db.Column(db.Integer, db.ForeignKey('semester.id'), nullable=False)
    maxTA = db.Column(db.Integer, nullable=True, default=50)
    section = db.Column(db.String(5),nullable = False)
    course = db.relationship(Course, backref=backref("course_faculty", cascade="all,delete"))
    faculty = db.relationship(Faculty, backref=backref("course_faculty", cascade="all,delete"))
    semester = db.relationship(Semester, backref=backref("course_faculty", cascade="all,delete"))

    def __repr__(self):
        return "course: "+str(self.course_id)+"  Fac : "+ str(self.faculty_id) + ' - '+ str(self.semester)

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
    date_posted = db.Column(db.Date, nullable=False)
    datetime_posted = db.Column(db.DateTime, nullable=False)

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
    facad_name = db.Column(db.String(100))
    facad = db.relationship(Faculty, backref=backref("facad", cascade="all,delete"))
    status = db.Column(db.String(10), nullable=False) # primary / secondary

    def __repr__(self):
        return "Student: "+str(self.student_id)+"  Faculty: "+ str(self.facad.id)+" Status:"+str(self.status)

class Student_Project(db.Model):
    id = db.Column('id', db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    student = db.relationship(Student, backref=backref("student_project", cascade="all,delete"))
    project = db.Column(db.String(500),nullable=True,default="NA")
    faculty_id = db.Column(db.Integer,nullable=False)
    faculty_name = db.Column(db.String(50),nullable=False)
    grade = db.Column(db.String(5),nullable=False)
    year = db.Column(db.Integer, nullable=False)
    filename = db.Column(db.String(50),nullable=False)
    date_posted = db.Column(db.Date, nullable=False)
    committee = db.Column(db.String(1000),nullable=True,default="NA")
    other_committee = db.Column(db.String(1000),nullable=True,default="NA")


    def __repr__(self) -> str:
        return "Student : " + str(self.student_id)+ " | Grade : "+self.grade 

class Student_Seminar(db.Model):
    id = db.Column('id', db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    student = db.relationship(Student, backref=backref("student_seminar", cascade="all,delete"))
    project = db.Column(db.String(500),nullable=True,default="NA")
    faculty_id = db.Column(db.Integer,nullable=False)
    faculty_name = db.Column(db.String(50),nullable=False)
    grade = db.Column(db.String(5),nullable=False)
    year = db.Column(db.Integer, nullable=False)
    filename = db.Column(db.String(50),nullable=False)
    date_posted = db.Column(db.Date, nullable=False)
    committee = db.Column(db.String(1000),nullable=True,default="NA")
    other_committee = db.Column(db.String(1000),nullable=True,default="NA")


    def __repr__(self) -> str:
        return "Student : " + str(self.student_id)+ " | Grade : "+self.grade 