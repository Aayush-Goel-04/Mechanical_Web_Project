from functools import wraps
from flask import render_template, url_for, flash, redirect, request , jsonify, send_from_directory
from flaskapp.models import Coordinator_Semester, Course, Course_Faculty, Course_Semester, Course_Ta,Faculty, Faculty_Semester, Semester, Student, Attendance, Student_Project, Student_Semester, Student_token, Facad, Student_Seminar
from flaskapp.forms import LoginForm
from flaskapp import app, db, bcrypt, scheduler, mailQueue, mailHandler
from flask_mail import Message
from flask_login import login_required, login_user, current_user, logout_user
import json ,datetime, pytz, string , random, secrets, settings, os
import pandas as pd
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

def coordinator_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if current_user.role != 'coordinator':
            flash("You don't have permission to access this resource.", "warning")
            return redirect(url_for("home"))
        return func(*args, **kwargs)
    return decorated_view

def admin_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if current_user.role != 'admin':
            flash("You don't have permission to access this resource.", "warning")
            return redirect(url_for("home"))
        return func(*args, **kwargs)
    return decorated_view

def validate_student(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        token = request.form.get("student_token")
        student_id = request.form.get("student_id")
        st = Student_token.query.filter_by(student_id=student_id,token=token)
        if not st:
            flash("You don't have permission to access this resource.", "warning")
            return redirect(url_for("home"))
        return func(*args, **kwargs)
    return decorated_view

def get_random_password(length: int):
    ''' Generates a random password of length => length'''
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    num = string.digits
    password = "".join(random.sample(lower+upper+num,length))
    return password

#
#
# Login Pages 
#
#

@app.route("/")
@app.route("/home")
@login_required
def home():
    return render_template('home.html')

# Login Route
@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        faculty = Faculty.query.filter_by(ldap = form.ldap.data).first()
        if faculty and bcrypt.check_password_hash(faculty.password,form.password.data) :
            if faculty.role != 'admin':
                tout = settings.faculty_password_timeout
                duration = datetime.timedelta(hours =tout['hours'],minutes=tout['minutes'])
                login_user(faculty, remember=True, duration=duration)
            else:
                login_user(faculty, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route("/facultylogin", methods=['GET', 'POST'])
def facultylogin():
    if current_user.is_authenticated:
        logout_user()
    ldap = str(request.args.get('ldap'))
    password = str(request.args.get('password'))
    if ldap and password:
        faculty = Faculty.query.filter_by(ldap=ldap).first()
        if faculty and bcrypt.check_password_hash(faculty.password,password) :
            tout = settings.faculty_password_timeout
            duration = datetime.timedelta(hours =tout['hours'],minutes=tout['minutes'])
            login_user(faculty, remember=True, duration=duration)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Link is incorrect/expired, follow instructions given in mail.', 'danger')
            return redirect(url_for('login'))

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('change_password'))

# Create A Short Time Password For Faculty Login
@app.route("/change_password", methods=['GET','POST'])
def change_password():
    return render_template('password.html')

# Generate Password and schedule app to remove it later
@app.route("/get_password", methods=['GET','POST'])
def get_password():
    ldap = str(request.form.get('ldap')).strip()
    faculty = Faculty.query.filter(func.lower(Faculty.ldap) == func.lower(ldap)).first()

    if faculty == None or faculty.role == 'admin':
        flash('LDAP ID entered doesnt exist !', 'info')
        return redirect(url_for('change_password'))

    # Generating Random Password
    password = get_random_password(12)
    # Generating mail
    mail_entry = settings.faculty_login_mail
    login_link_url = "%s/facultylogin?ldap=%s&password=%s" % (settings.WEB_URL,faculty.ldap,password)
    login_page_url = '%s/login' % (settings.WEB_URL)
    link_generate_url = "%s/change_password" % (settings.WEB_URL)
    body_ = mail_entry['body_'] % (login_link_url, password, login_page_url, link_generate_url)
    if settings.debug == True:
        print(login_link_url)
    else:
        mailEntry = {'subject' : mail_entry['subject'], 'content': body_, 'to' : faculty.email}
        resp = mailHandler.send_email(mailEntry)
        if not resp:
            mailQueue.add_mails_to_queue([mailEntry])
    
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    faculty.password = hashed_password
    # setting password reset time to 2 hrs
    c_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
    tout = settings.faculty_password_timeout
    add = datetime.timedelta(hours=tout['hours'],minutes=tout['minutes'])
    time = c_time + add
    # Scheduling job for password reset
    scheduler.add_job(id='reset_password'+ldap, func=reset_password,
                    trigger='date',run_date=time,args=[faculty.id],replace_existing= True)
    try:
        db.session.commit()
        flash('Login details have been sent to ' + faculty.email + '. Please login using that link.', 'success')
    except Exception:
        db.session.rollback()
    return redirect(url_for('change_password'))

def reset_password(faculty_id):
    faculty = Faculty.query.get(faculty_id)
    if faculty != None:
        print("changed")
        password = get_random_password(9)
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        faculty.password = hashed_password
        db.session.commit()

# Generate Short Token for Student To Use
@app.route("/student_token", methods=['GET', 'POST'])
def student_token():
    return render_template('student_token.html')

@app.route("/get_student_token", methods=['GET','POST'])
def get_student_token():
    roll_number = str(request.form.get('roll_number')).strip()
    student = Student.query.filter(func.lower(Student.roll_number) == func.lower(roll_number)).first()
    if student == None:
        flash('Roll Number Doesnt Exist !', 'info')
        return redirect(url_for('student_token'))
    s = Student_token.query.filter_by(student_id=student.id).first()
    if s != None:
        db.session.delete(s)
        db.session.flush()
    token = secrets.token_urlsafe(16)
    student_token = Student_token(student_id=student.id, token=token)
    db.session.add(student_token)
    mail_entry = settings.student_token_mail
    tout = settings.student_token_timeout
    URL = "%s/attendance?student_id=%s&student_token=%s" % (settings.WEB_URL,student.id,token)
    body_ = mail_entry['body_'] % (student.name,URL,tout['hours'],tout['minutes'])
    
    if settings.debug == True:
        print(URL)
    else:
        mailEntry = {'subject' : mail_entry['subject'], 'content': body_, 'to' : student.email}
        resp = mailHandler.send_email(mailEntry)
        if not resp:
            mailQueue.add_mails_to_queue([mailEntry])
    

    # setting token reset time to 2 hrs
    c_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
    tout = settings.student_token_timeout
    add = datetime.timedelta(hours=tout['hours'],minutes=tout['minutes'])
    time = c_time + add
    # Scheduling job for password reset
    scheduler.add_job(id='token'+roll_number, func=reset_token,
                    trigger='date',run_date=time,args=[student.id],replace_existing= True)
    try:
        db.session.commit()
        flash('Token has been sent to '+student.email+'.', 'success')
    except Exception:
        db.session.rollback()
    return redirect(url_for('student_token'))

def reset_token(student_id):
    s = Student_token.query.filter_by(student_id=student_id).first()
    if s != None:
        db.session.delete(s)
        db.session.commit()
        print('Token has been reset for '+ str(student_id))

#
#
#
# Admin Access Pages
# Contains Update Data for Course,Student,Faculty
# Select Mandatory Courses and Faculty on Leave for Each Semester
# Assigning Field Coordinators
#
#
#
#


@app.route("/updateData", methods=['GET', 'POST'])
@login_required
@admin_required
def updateData():
    semesters = Semester.query.all()
    fields = settings.FIELDS
    semester = Semester.query.filter_by(is_current=1).first()
    if semester:
        sem = semester.semester
    else:
        sem = 'None'
    return render_template('updateData.html',semesters=semesters,fields=fields,
                            curr_sem=sem)

# check column names
def missingcolumns(to_check, given):
    given_set = set([''.join(s.split()).lower() for s in given])
    if(len(given) != len(given_set)):
        return True
    for col in to_check:
        col = ''.join(col.split()).lower()
        if col in given_set:
            continue
        else:
            return True
    return False

# Uploda Course Data
@app.route("/uploadCourseData", methods=['GET', 'POST'])
@login_required
@admin_required
def uploadCourseData():
    if request.method == 'POST' and "course_file" in request.files:
        file = request.files['course_file']
        data_xls = pd.read_excel(file)
        cols = settings.course_columns
        maps = settings.pandas_course_map
        if missingcolumns(cols, data_xls.columns):
            flash('Column Names Dont Match', 'Warning')
            return redirect(url_for('updateData'))
        # Course code must be present in each row
        if data_xls[maps['code']].isnull().values.any() or not data_xls[maps['code']].is_unique:
            flash('Identical Course Codes / Course Code not present', 'info')
        else:
            #Creating Field for Courses | Replacing empty Course Names with Course Codes
            default_field = settings.default_field
            fields = settings.ALLFIELDS
            data_xls[maps['code']] = data_xls[maps['code']].astype(str)
            data_xls[maps['field']].fillna(default_field, inplace = True)
            data_xls[maps['name']].fillna(data_xls[maps['code']], inplace = True)
            for i,data in data_xls.iterrows():
                # Checking if course field is pronounced correctly
                field = str(data[maps['field']]).strip()
                code = str(data[maps['code']]).strip()
                if field in fields:
                    c = Course.query.filter_by(code = code).first()
                    if c:
                        c.name = data[maps['name']]
                        c.field = field
                    else:
                        c = Course(field=field,code=code,name=data[maps['name']])
                        db.session.add(c)
                else:
                    db.session.rollback()
                    flash(' Data Not Uploaded, Course Field not recognisable !', 'info')
                    return redirect(url_for('updateData'))
            try:
                db.session.commit()
                flash('Course Data Uploaded Successfully !', 'success')
            except IntegrityError:
                db.session.rollback()
                flash(' Data Not Uploaded Due to Identical Course Codes!', 'info')
    return redirect(url_for('updateData'))

# Upload Faculty Data
@app.route("/uploadFacultyData", methods=['GET', 'POST'])
@login_required
@admin_required
def uploadFacultyData():
    # Same Functionality as upload course Data
    if request.method == 'POST' and "faculty_file" in request.files:
        file = request.files['faculty_file']
        data_xls = pd.read_excel(file)
        cols = settings.faculty_columns    
        maps = settings.pandas_faculty_map
        if missingcolumns(cols, data_xls.columns):
            flash('Column Names Dont Match', 'Warning')
            return redirect(url_for('updateData'))
        
        admins = [f.ldap for f in Faculty.query.with_entities(Faculty.ldap).filter_by(role='admin')]
        for ldap in data_xls[maps['ldap']]:
            if ldap in admins:
                flash("Can't change data for admin ldap : "+ldap, 'info')
                return redirect(url_for('updateData'))

        if data_xls[maps['ldap']].isnull().values.any() or not data_xls[maps['ldap']].is_unique:
            flash('Identical Ldap / Faculty Ldap not present', 'info')
        else:
            default_field = settings.default_field
            fields = settings.ALLFIELDS
            data_xls[maps["ldap"]] = data_xls[maps["ldap"]].str.strip()
            data_xls[maps["field"]].fillna(default_field, inplace = True)
            data_xls[maps["field"]] = data_xls[maps["field"]].str.strip()
            data_xls[maps["name"]].fillna(data_xls[maps["ldap"]], inplace = True)
            data_xls[maps["email"]].fillna(data_xls[maps["ldap"]]+'@iitb.ac.in', inplace = True)
            data_xls[maps["phone_number"]].fillna("", inplace = True)
            data_xls[maps["status"]].fillna('active', inplace = True)
            password = get_random_password(12)
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')  # remove Later
            for i,data in data_xls.iterrows():
                if data[maps['field']] not in fields:
                    db.session.rollback()
                    flash(' Data Not Uploaded, Field not recognisable !', 'info')
                    return redirect(url_for('updateData'))
                f = Faculty.query.filter_by(ldap = data[maps['ldap']]).first()
                curr = 0 if data[maps['status']].lower() in ['inactive'] else 1
                if f:
                    f.name = data[maps['name']]
                    f.phone_number = data[maps['phone_number']]
                    f.email = data[maps['email']]
                    f.field = data[maps['field']]
                    f.password = hashed_password
                    f.is_active = curr
                else:
                    f = Faculty(name=data[maps['name']], ldap=data[maps['ldap']],  phone_number=data[maps['phone_number']],
                                email=data[maps['email']], field=data[maps['field']], password=hashed_password,is_active=curr)
                    db.session.add(f)
            try:
                db.session.commit()
                flash('Faculty Data Uploaded Successfully !', 'success')
            except IntegrityError:
                db.session.rollback()
                flash(' Data Not Uploaded !', 'info')

    return redirect(url_for('updateData'))

# Updating Student vs Semester Relations Whether student is active or not 
# (Like Stack with latest Semester at top changes entries above the selected semester )
def create_semester_student_status(student_id,status,active_sems,allsems: list):
    if status.lower() == 'inactive':
        if active_sems:
            for semester in active_sems:
                db.session.delete(semester)
    else:
        if active_sems is None:
            for sem_id in allsems:
                sm = Student_Semester(semester_id=sem_id,student_id=student_id)
                db.session.add(sm)
        else:
            active_sem_ids = [sem.semester_id for sem in active_sems]
            for sem_id in allsems:
                if sem_id in active_sem_ids:
                    continue
                sm = Student_Semester(semester_id=sem_id,student_id=student_id)
                db.session.add(sm)
    try:
        db.session.flush()
        return False
    except:
        db.session.rollback()
        return True

# Upload Student Data
@app.route("/uploadStudentData", methods=['GET', 'POST'])
@login_required
@admin_required
def uploadStudentData():
    if request.method == 'POST' and "student_file" in request.files and request.form.get('semester'):
        file = request.files['student_file']
        semester_id = int(request.form.get('semester'))
        data_xls = pd.read_excel(file)
        cols = settings.student_columns
        maps = settings.pandas_student_map
        if missingcolumns(cols, data_xls.columns):
            flash('Column names Dont Match !', 'warning')
            return redirect(url_for('updateData'))

        if data_xls[maps['rollno']].isnull().values.any():
            flash('Student roll number missing %s' % (data_xls[data_xls[maps['rollno']].isnull()]), 'info')
        elif not data_xls[maps['rollno']].is_unique:
            flash('Student roll number not unique %s' % (data_xls[data_xls.maps['rollno'].duplicated()]), 'info')
        elif data_xls[maps['category']].isnull().values.any():
            flash('Student category not present !', 'info')
        else:
            # Data Sanitisation and checking if field and category is correct
            default_field = settings.default_field
            fields = settings.ALLFIELDS
            categories = settings.CATEGORIES
            data_xls[maps["rollno"]] = data_xls[maps['rollno']].astype(str)
            data_xls[maps["rollno"]] = data_xls[maps["rollno"]].str.strip()
            data_xls[maps["name"]].fillna(data_xls[maps["rollno"]], inplace = True)
            data_xls[maps["email"]].fillna(data_xls[maps["rollno"]]+'@iitb.ac.in', inplace = True)
            data_xls[maps["program"]].fillna(settings.default_program, inplace = True)
            data_xls[maps["field"]].fillna(default_field, inplace = True)
            data_xls[maps["field"]] = data_xls[maps["field"]].str.strip()
            data_xls[maps["status"]].fillna('active', inplace = True)
            data_xls[maps["category"]] = data_xls[maps["category"]].str.lower()
            data_xls[maps["category"]] = data_xls[maps["category"]].str.split()
            data_xls[maps["category"]] = data_xls[maps["category"]].str.join('')
            entered_fields = data_xls[maps["field"]].unique()
            entered_categories = data_xls[maps['category']].unique()
            if missingcolumns(entered_fields,fields):
                flash('Student Field not recognisable ! %s: %s' % (entered_fields, fields), 'warning')
                return redirect(url_for('updateData'))
            if missingcolumns(entered_categories,categories):
                flash('Student Category not recognisable ! %s %s' % (entered_categories, categories), 'warning')
                return redirect(url_for('updateData'))

            # Creating students Active Semesters Data
            students = Student.query.with_entities(Student.id,Student.roll_number).all()
            student_sems = []
            if students:
                student_sems = [None]*(max([s.id for s in students])+1)
            student_roll = [[{}]*10]*10
            for st in students:
                r = int(st.roll_number[-2:])
                roll_dict = student_roll[r//10][r%10]
                roll_dict[st.roll_number] = st.id
            for semester in Student_Semester.query.filter(Student_Semester.semester_id>=semester_id).all():
                a = student_sems[semester.student_id]
                if a is None:
                    a = []
                a.append(semester)
                student_sems[semester.student_id] = a
            sem_ids = [ sem.id for sem in Semester.query.filter(Semester.id>=semester_id).all()]
            found = 0
            newentry = 0
            for i,data in data_xls.iterrows():
                roll = int(data[maps['rollno']][-2:])
                p_roll = student_roll[roll//10][roll%10]
                if data[maps['rollno']] in p_roll:
                    found += 1
                    s = Student.query.get_or_404(p_roll[data[maps['rollno']]])
                    s.name = data[maps['name']]
                    s.email = data[maps['email']]
                    s.program = data[maps['program']]
                    s.field = data[maps['field']]
                    s.category = data[maps['category']]
                    entrynotdone = create_semester_student_status(s.id,data[maps['status']],student_sems[s.id],sem_ids)
                else:
                    newentry += 1
                    s = Student(name=data[maps['name']],
                                email=data[maps['email']],
                                roll_number=data[maps['rollno']],
                                category=data[maps['category']],
                                program=data[maps['program']],
                                field=data[maps['field']])
                    db.session.add(s)
                    db.session.flush()
                    entrynotdone = create_semester_student_status(s.id,data[maps['status']],None,sem_ids)
                if entrynotdone:
                    flash(' Data Not Uploaded !', 'info')
                    return redirect(url_for('updateData'))
            try:
                db.session.commit()
                flash('Student Data Uploaded Successfully. '+str(found)+' old entries edited & '+str(newentry)+' new entries made !', 'success')
            except IntegrityError:
                db.session.rollback()
                flash(' Data Not Uploaded !', 'info')
    return redirect(url_for('updateData'))

# Create New Semester
@app.route("/createNewSemester")
@login_required
@admin_required
def createNewSemester():
    season = settings.SEASONS
    semester = Semester.query.all()
    if semester:
        year = semester[-1].year
        sem = semester[-1].semester[:-7]
        prev_sem_id = semester[-1].id
        new_sem = season[sem]
        if new_sem == settings.NEW_SEM:
            year += 1
        sem1 = Semester(semester=new_sem+' - '+str(year),year=year)
    else:
        year = datetime.datetime.today().year
        sem1 = Semester(semester=settings.NEW_SEM+' - '+str(year),year=year)
        db.session.add(sem1)
        db.session.commit()
        flash(sem1.semester+' Semester Created !','success')
        return redirect("/updateData")

    db.session.add(sem1)
    db.session.flush()
    new_sem_id = sem1.id
    if new_sem_id != prev_sem_id+1 :
        db.session.rollback()
        flash('Error contact admin !', 'error')
        return redirect("/updateData")
    students = Student_Semester.query.with_entities(Student_Semester.student_id,\
                                    Student_Semester.semester_id,Student_Semester.is_active)\
                            .filter_by(semester_id=prev_sem_id,is_active=1).all()
    for student in students:
        sm = Student_Semester(semester_id=new_sem_id,student_id=student.student_id,is_active=1)
        db.session.add(sm)
    try:
        db.session.commit()
        flash(sem1.semester+' Semester Created !','success')
    except:
        db.session.rollback()
        flash('Error !', 'error')
    return redirect("/updateData")

# Change current Semester
@app.route("/currentSemester", methods=["GET","POST"])
@login_required
@admin_required
def currentSemester():
    sem_id = int(request.args.get('current_sem'))
    semesters = Semester.query.filter_by(is_current=1).all()
    for semester in semesters:
        semester.is_current = 0
    sem = Semester.query.get(sem_id)
    sem.is_current = 1
    try:
        db.session.commit()
        flash("Current Semester Changed !", 'info')
    except:
        db.session.rollback()
        flash("Error !", 'danger')
    return redirect("/updateData")

# Send Data for Selecting Facultys on Leave or Mandatory Coruses
@app.route("/semesterData_1", methods=['GET', 'POST'])
@login_required
@admin_required
def semesterData_1():
    facultys = [{'id':faculty.id, 'name':faculty.name+' | '+faculty.ldap} 
                for faculty in Faculty.query.filter(Faculty.is_active==1,Faculty.role!='admin').all()]
    courses = [{'id':course.id, 'name':course.__repr__()} for course in Course.query.all()]
    resp = {'facultys':facultys,'courses':courses}
    return jsonify(resp)

# Create Table for Faculty On Leave and Mandatory Courses Based on Semester Selected
@app.route("/semesterData_2", methods=['GET', 'POST'])
@login_required
@admin_required
def semesterData_2():
    semester_id = request.form.get('semester_id')
    facultys = [{'id':faculty.id,'faculty_id':faculty.faculty_id, 'name':faculty.faculty.name} for faculty in Faculty_Semester.query.filter_by(semester_id=semester_id,is_active=0).all()]
    courses = [{'id':course.id,'course_id':course.course_id, 'course':course.course.__repr__()} for course in Course_Semester.query.filter_by(semester_id=semester_id,is_mandatory=1).all()]
    resp = {'courses':courses,'facultys':facultys}
    return jsonify(resp)

# Marking The selected course as mandatory for the semester
@app.route("/courseMarkMandatory", methods=['GET', 'POST'])
@login_required
@admin_required
def courseMarkMandatory():
    course_id = request.form.get('course_id')
    semester_id = request.form.get('semester_id')
    cs = Course_Semester.query.filter_by(semester_id=semester_id,is_mandatory=1,course_id=course_id).first()
    if cs:
        response = {'message':'Entry already exists'}
    else:
        cs = Course_Semester(course_id=course_id,semester_id=semester_id,is_mandatory=1)
        db.session.add(cs)
        db.session.commit()
        response = {'message': 'Entry Made'}
    return jsonify(response)

# Removing a mandatory course entry
@app.route("/removeMandatoryCourse", methods=['GET', 'POST'])
@login_required
@admin_required
def removeMandatoryCourse():
    cs_id = request.form.get('course_semester_id')
    semester_id = request.form.get('semester_id')
    cs = Course_Semester.query.get_or_404(cs_id)
    response = {}
    if cs and str(cs.semester_id) == semester_id:
        db.session.delete(cs)
        db.session.commit()
        response = {'message':'Entry deleted'}
    return jsonify(response)

# Mark Faculty on Leave
@app.route("/facultyMarkInactive", methods=['GET', 'POST'])
@login_required
@admin_required
def facultyMarkInactive():
    faculty_id = request.form.get('faculty_id')
    semester_id = request.form.get('semester_id')
    fs = Faculty_Semester.query.filter_by(semester_id=semester_id,is_active=0,faculty_id=faculty_id).first()
    if fs:
        response = {'message':'Entry already exists'}
    else:
        fs = Faculty_Semester(faculty_id=faculty_id,semester_id=semester_id,is_active=0)
        db.session.add(fs)
        db.session.commit()
        response = {'message': 'Entry Made'}
    return jsonify(response)

# Remove Faculty Leave Entry
@app.route("/removeFacultyLeave", methods=['GET', 'POST'])
@login_required
@admin_required
def removeFacultyLeave():
    fs_id = request.form.get('faculty_semester_id')
    semester_id = request.form.get('semester_id')
    fs = Faculty_Semester.query.get_or_404(fs_id)
    response = {}
    if fs and str(fs.semester_id) == semester_id:
        db.session.delete(fs)
        db.session.commit()
        response = {'message':'Entry deleted'}
    return jsonify(response)

# Assign Coordinator

# Send Faculty List with Field as All or Selected Field
@app.route("/get_field_coordinators", methods=['GET', 'POST'])
@login_required
@admin_required
def get_field_coordinators():
    semester_id = int(request.form.get('semester_id'))
    field = request.form.get('field')
    facultys = Faculty.query.filter(Faculty.field.in_((field,settings.default_field))\
                                ,Faculty.is_active==1).all()
    f_list = []
    for faculty in facultys:
        sem_ids = [sems.id for sems in faculty.semesters]
        if semester_id in sem_ids or faculty.role == 'admin':
            continue
        f_list.append({'id':faculty.id,'name':faculty.name+' | '+faculty.ldap})
    return jsonify(f_list)

# Remember only One coordinator for each field
@app.route("/addCoordinator", methods=['GET', 'POST'])
@login_required
@admin_required
def addCoordinator():
    field = request.form.get('field')
    faculty_id = int(request.form.get('faculty_id'))
    semester_id = int(request.form.get('semester_id'))
    faculty = Faculty.query.get(faculty_id)
    if faculty.is_active == 0 or faculty.role == 'admin' or not faculty:
        response = {'message':'Error'}
        return jsonify(response)
    
    sems = [s.id for s in faculty.semesters]
    if faculty and (faculty.field == field or faculty.field == settings.default_field) and semester_id and semester_id not in sems:
        entry1 = Coordinator_Semester.query.filter_by(field=field,semester_id=semester_id).first()
        entry2 = Coordinator_Semester.query.filter_by(faculty_id=faculty_id,semester_id=semester_id).first()
        if entry1 or entry2:
            message = 'Coordinator already assigned.'
        else:
            faculty.role = 'coordinator'
            new_entry = Coordinator_Semester(field=field,semester_id=semester_id,faculty_id=faculty_id)
            db.session.add(new_entry)
            message = 'Assigned'
    else:
        message = "Faculty's Field and Selected Field Doesn't Match.\nOR\nFaculty on Leave"
    response = {'message':message}
    try:
        db.session.commit()
    except:
        db.session.rollback()
    return jsonify(response)

# Removing The coordinator
@app.route("/removeCoordinator", methods=['GET', 'POST'])
@login_required
@admin_required
def removeCoordinator():
    coordinator_id = request.form.get('coordinator_id')
    coordinator = Coordinator_Semester.query.get(coordinator_id)
    if coordinator and Faculty.query.get(coordinator.faculty_id):
        db.session.delete(coordinator)
        db.session.flush()
        faculty = Faculty.query.get(coordinator.faculty_id)
        if len(faculty.coordinator_sems)==0:
            faculty.role = 'faculty'
        try:
            db.session.commit()
        except:
            db.session.rollback()
    return jsonify()

# Send Data for Coordinators Appointed
@app.route("/coordinatorData", methods=['GET', 'POST'])
@login_required
@admin_required
def coordiantorData():
    semester_id = request.form.get('semester_id')
    coordinators = []
    for field in Coordinator_Semester.query.filter_by(semester_id=semester_id).all():
        coordinators.append({'id':field.id,'faculty_id':field.faculty_id,'name':field.faculty.name,
                'ldap':field.faculty.ldap,'field':field.field,'faculty_field':field.faculty.field})
    response = {'coordinators': coordinators}
    return jsonify(response)

# Send Mails to Coordinators
@app.route("/sendMailCoord/<semester_id>", methods = ["GET","POST"])
@login_required
@admin_required
def sendMailCoord(semester_id): 
    cs = Coordinator_Semester.query\
                    .filter_by(semester_id=semester_id).all()
    semester = Semester.query.get(semester_id).__repr__()
    cnt = 0
    mails_to_send = []
    for coord in cs:
        mail_entry = settings.coord_mail
        URL = '%s/change_password' % (settings.WEB_URL)
        body_ = mail_entry['body_'] % (coord.field,semester,URL)
        entry = {'subject':mail_entry['subject'],'to':coord.faculty.email,'content':body_}
        cnt += 1
        mails_to_send.append(entry)
    mailQueue.add_mails_to_queue(mails_to_send)
    flash(str(cnt) +' Mails Sent !', 'success')
    return redirect(url_for('updateData'))


#
#
#
# Admin Acess page to Download Data
#
#
#
#


@app.route("/downloadData", methods=['GET', 'POST'])
@login_required
@admin_required
def downloadData():
    semesters = Semester.query.all()
    return render_template('downloadData.html', semesters = semesters)

@app.route("/downloadSemCourseAllot", methods=['GET', 'POST'])
@login_required
@admin_required
def downloadSemCourseAllot():
    sem_id = request.args.get('download_sem_1')
    if not sem_id:
        return redirect(url_for('downloadData'))
    path = '%s/course_allot.xlsx' % settings.EXCEL_DIR
    course_facultys = Course_Faculty.query.filter_by(semester_id=sem_id).all()
    course_allot = pd.ExcelWriter(path)
    courses = []
    for c in course_facultys:
        courses.append({'Field':c.course.field,'Code':c.course.code,'Name':c.course.name,'Section':c.section,
                        'Ldap':c.faculty.ldap,'Faculty':c.faculty.name,'Max TAs':c.maxTA})
    df = pd.DataFrame(courses)
    df.to_excel(course_allot, sheet_name='Sheet1', index=False)
    course_allot.save()
    return send_from_directory(settings.EXCEL_DIR,'course_allot.xlsx', as_attachment=True)
    #return send_file(downloadpath,as_attachment=True)

@app.route("/downloadSemTAAllot", methods=['GET', 'POST'])
@login_required
@admin_required
def downloadSemTAAllot():
    sem_id = request.args.get('download_sem_2')
    if not sem_id:
        return redirect(url_for('downloadData'))
    path = '%s/ta_allot.xlsx' % settings.EXCEL_DIR
    course_Tas = Course_Ta.query.filter_by(semester_id=sem_id).all()
    ta_allot = pd.ExcelWriter(path)
    tas = []
    for c in course_Tas:
        tas.append({'Field':c.course.field,'Code':c.course.code,'Name':c.course.name,
                    'Section':c.section,'roll_no':c.ta.roll_number,'name':c.ta.name,
                    'program':c.ta.program,'field':c.ta.field,'category':c.ta.category})
    df = pd.DataFrame(tas)
    df.to_excel(ta_allot, sheet_name='Sheet1', index=False)
    ta_allot.save()
    return send_from_directory(settings.EXCEL_DIR,'ta_allot.xlsx', as_attachment=True)

@app.route("/downloadStudentGrades", methods=['GET', 'POST'])
@login_required
@admin_required
def downloadStudentGrades():
    sem_id = request.args.get('download_sem_3')
    if not sem_id:
        return redirect(url_for('downloadData'))
    path = '%s/StudentGrades.xlsx' % settings.EXCEL_DIR
    pass
    students = Student_Semester.query.filter_by(semester_id=sem_id).all()
    grades = []
    for student in students:
        projects = Student_Project.query.filter_by(student_id=student.student_id).all()
        seminars = Student_Seminar.query.filter_by(student_id=student.student_id).all()
        name = student.student.name
        rollno = student.student.roll_number
        field = student.student.field
        program = student.student.program
        category = student.student.category
        for p in projects:
            grades.append({'Roll_no':rollno,'Name':name,
                        'field':field,'category':category,
                        'Program':program,'type':'Project '+str(p.year),
                        'Faculty':p.faculty_name,'Grade':p.grade,
                        'Date':p.date_posted,'Project':p.project,
                        'committee':p.committee+p.other_committee,
                        })
        for s in seminars:
            grades.append({'Roll_no':rollno,'Name':name,
                        'field':field,'category':category,
                        'Program':program,'type':'Seminar '+str(s.year),
                        'Faculty':s.faculty_name,'Grade':s.grade,
                        'Date':s.date_posted,'Project':s.project,
                        'committee':s.committee+s.other_committee,
                        })
    student_grades = pd.ExcelWriter(path)
    df = pd.DataFrame(grades)
    df.to_excel(student_grades, sheet_name='Sheet1', index=False)
    student_grades.save()   
    return send_from_directory(settings.EXCEL_DIR,'StudentGrades.xlsx', as_attachment=True)

@app.route("/downloadStudentAttendanceList", methods=['GET', 'POST'])
@login_required
@admin_required
def downloadStudentAttendanceList():
    days = int(request.args.get('days'))
    sem_id = request.args.get('download_sem_3')
    if not (days and sem_id):
        return redirect(url_for('downloadData'))
    path = '%s/absentStudentsList.xlsx' % settings.EXCEL_DIR
    s_list = pd.ExcelWriter(path)
    students = Student_Semester.query.filter_by(semester_id=sem_id, is_active=1).all()
    absent = []
    current_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
    for s in students:
        if s.student.last_attendance:
            c_time = current_time - s.student.last_attendance
            attendance = str(c_time.days) + ' Days Ago'
            if c_time.days > days:
                absent.append({'Roll_no':s.student.roll_number,'Name':s.student.name,'Email':s.student.email,'Last Attendance':attendance})
        else:
            absent.append({'Roll_no':s.student.roll_number,'Name':s.student.name,'Email':s.student.email,'Last Attendance':'None'})
            continue
    df = pd.DataFrame(absent)
    df.to_excel(s_list, sheet_name='Sheet1', index=False)
    s_list.save()
    return send_from_directory(settings.EXCEL_DIR,'absentStudentsList.xlsx', as_attachment=True)


#
#
#
# Admin and Coordinator Access Pages
# Includes Course Allotment, TA Allotment
#
#
# Course Allotment By Coordinators and Admin
# ******************************************
#
#
#


@app.route("/courseAllotment", methods=['GET', 'POST'])
@login_required
@coordinator_required
def courseAllotment():
    coordinator_sems = Coordinator_Semester.query.filter_by(faculty_id=current_user.id).all()
    semesters = [{'id':sem.semester_id,'semester':sem.semester.__repr__(),'field':sem.field} for sem in coordinator_sems]
    return render_template('courseAllotment.html', title='Course Allotment',
                     semesters=semesters,default_field=settings.default_field)

# Adding Course
@app.route("/addCourse", methods = ["GET","POST"])
@login_required
@coordinator_required
def addCourse():
    semester_id = int(request.form.get('semester_id'))
    cs = Coordinator_Semester.query.filter_by(semester_id=semester_id,faculty_id=current_user.id).first()
    if not cs:
        resp = {'message':'error'}
        return jsonify(resp)

    field = request.form.get('field')
    code = str(request.form.get('code')).strip()
    name = str(request.form.get('name')).strip()
    if field == cs.field or field == settings.default_field:
        lowercode = ''.join(code.split(" ")).lower()
        for c in Course.query.with_entities(Course.code).all():
            if lowercode == ''.join(str(c.code).split(" ")).lower():
                resp = {'message' : 'Course Code Already Exists'}
                return jsonify(resp)
        course = Course(code=code,name=name,field=field)
        db.session.add(course)
        try:
            db.session.commit()
            resp = {'message' : 'Course Added'}
        except:
            db.session.rollback()
            resp = {'message':'error'}
    else:
        resp = {'message':'error'}
    return jsonify(resp)

# Getting Courses Based on Coordinator Field
@app.route("/get_courses", methods = ["GET","POST"])
@login_required
@coordinator_required
def get_courses():
    field = request.form.get('field')
    courses = [{'id':course.id,'name':course.__repr__()} \
                    for course in Course.query.\
                        filter(Course.field.in_((field,settings.default_field)))]
    return jsonify(courses)

# Removing Course Allotment
@app.route("/removeCourseAllotment", methods=['GET', 'POST'])
@login_required
@coordinator_required
def removeCourseAllotment():
    fac_id = request.form.get('course_faculty_id')
    semester_id = int(request.form.get('semester_id'))
    cf = Course_Faculty.query.get(fac_id)
    if cf.semester_id == semester_id :
        tas = Course_Ta.query.filter_by(course_id = cf.course_id,\
                        section = cf.section,semester_id=semester_id).all()
        for ta in tas:
            db.session.delete(ta)
        db.session.delete(cf)
        resp = {'message': "success"}
    else:
        resp = {'message': "error"}
    db.session.commit()
    return jsonify(resp)

# Sending All the Course Allotments and Mandatory Courses List based on selected Semester
@app.route("/get_course_allotments", methods = ["GET","POST"])
@login_required
@coordinator_required
def get_course_allotments():
    field = request.form.get('field')
    semester_id = int(request.form.get('semester_id'))
    default_field = settings.default_field
    # Putting course data with course ids as indexes in a list 
    # Gets all the course ids for which coodinator can make allotments
    courses = Course.query.with_entities(Course.field,Course.code,Course.id)\
                .filter(Course.field.in_((field,default_field))).all()
    maxcourseid = 0
    if len(courses):
        maxcourseid = max([c.id for c in courses])
    # creating list based on max course_id
    c_list = [None]*(1+maxcourseid)
    '''Records allotments for course_id [where idex = course_id]'''
    course_data = [None]*(1+maxcourseid)
    '''Records course code & field associated with course_id'''
    for c in courses:
        c_list[c.id]=0
        course_data[c.id] = [c.field,c.code]
    
    # Putting Faculty names based on faculty_id in a list
    facultys = Faculty.query.with_entities(Faculty.name,Faculty.field,Faculty.id)\
                .filter(Faculty.field.in_((field,default_field))).all()
    maxfacultyid = 0
    if facultys:
        maxfacultyid = max([f.id for f in facultys])
    f_list = [None]*(maxfacultyid+1)
    for f in facultys:
        f_list[f.id] = f.name

    # Getting all the allotments
    course_facultys = Course_Faculty.query\
                        .filter(Course_Faculty.semester_id==semester_id).all()
    course_fac_list = []
    course_list = []
    for cf in course_facultys:
        # Checking if course id is valid
        if cf.course_id > maxcourseid or c_list[cf.course_id] is None:
            continue
        c_list[cf.course_id] += 1
        if f_list[cf.faculty_id] == None:
            continue
        course_fac_list.append({'id': cf.id,
                    'field':course_data[cf.course_id][0],
                    'course': course_data[cf.course_id][1],
                    'course_id':cf.course_id,
                    'section': cf.section,
                    'faculty': f_list[cf.faculty_id],
                    'faculty_id':cf.faculty_id,
                    'maxTA':cf.maxTA})

    # Getting mandatory Courses List with number of allotments
    for course in Course_Semester.query.with_entities(Course_Semester.course_id)\
                    .filter(Course_Semester.semester_id==semester_id).all():
        if course.course_id > maxcourseid or c_list[course.course_id] is None:
            continue
        course_list.append({'field':course_data[course.course_id][0],
                    'course_id':course.course_id,
                    'course':course_data[course.course_id][1],
                    'allotments':c_list[course.course_id]})
    response = {'fac_list':course_fac_list,'course_list':course_list}
    return jsonify(response)

# Displaying Current and Previous Semester Allotments of the selected Course
@app.route("/get_alloted_sections", methods = ["GET","POST"])
@login_required
@coordinator_required
def get_alloted_sections():
    course_id = request.form.get('course_id')
    semester_id = int(request.form.get('semester_id'))
    # Keeping faculty names with ids in a list
    facultys = Faculty.query.with_entities(Faculty.field,Faculty.name,Faculty.id).all()
    maxfacultyid = 0
    if facultys:
        maxfacultyid = max([f.id for f in facultys])
    f_list = [None]*(maxfacultyid+1)
    for f in facultys:
        f_list[f.id] = f.name
    # Getting all allotments for course_id
    query = Course_Faculty.query.filter_by(course_id=course_id).all()
    course_sections = []
    prev_allot = {}
    for q in query:
        fac_name = f_list[q.faculty_id]
        if fac_name == None:
            continue
        if q.semester_id == semester_id:
            course_sections.append({'id':q.id,'section':q.section,'prof':fac_name,'maxTA':q.maxTA})
        else:
            if fac_name in prev_allot:
                if q.semester.__repr__() not in prev_allot[fac_name]:
                    prev_allot[fac_name] = prev_allot.get(fac_name,'')+ ' | ' + q.semester.__repr__()
            else:
                prev_allot[fac_name] = q.semester.__repr__()
    resp = {'course_sections':course_sections,'previous_allotments':prev_allot}
    return jsonify(resp)

# Getting Sections and Lists of Faculty after Selecting Number of Sections to Add
@app.route("/get_sections_and_faculty", methods = ["GET","POST"])
@login_required
@coordinator_required
def get_sections_and_faculty():
    semester_id,course_id = int(request.form.get('semester_id')),request.form.get('course_id')
    field,num_sections = request.form.get('field'),int(request.form.get('num_sections'))
    course_sections = [q.section for q in \
                    Course_Faculty.query.filter_by\
                    (course_id=course_id,semester_id=semester_id).all()]
    # get new sections that are to be alloted
    new_sections = []
    for i in range(1,num_sections+len(course_sections)+1):
        section = 'S'+str(i)
        if section not in course_sections:
            new_sections.append(section)
    facultys = []
    for fac in Faculty.query.filter\
                (Faculty.field.in_((field,settings.default_field)),\
                 Faculty.is_active==1,Faculty.role!='admin').all():
        fs = [sem.id for sem in fac.semesters]
        if semester_id in fs:
            continue
        facultys.append({'name':fac.name,'id':fac.id}) 
    response = {'sections':new_sections,'profs':facultys}
    # Get next sections
    return jsonify(response)

# Making Course Allotment
@app.route("/allot_section_fac", methods = ["GET","POST"])
@login_required
@coordinator_required
def allot_section_fac():
    section_faculty_list = json.loads(request.form.get('section_faculty_list'))
    course_id,semester_id = request.form.get('course_id'),request.form.get('semester_id')
    for ta in section_faculty_list:
        section,faculty_id,maxTAs = ta['section'],ta['faculty_id'],ta['maxTA']
        if faculty_id and maxTAs and section:
            new_entry = Course_Faculty(faculty_id=faculty_id,course_id=course_id,section=section,maxTA=maxTAs,semester_id=semester_id)
            db.session.add(new_entry)
            resp = {'message': 'Entry done'}
        else:
            resp = {'message': 'Entry Not Done, Duplicate or Empty Entries'}
            db.session.rollback()
            return jsonify(resp)
    db.session.commit()
    return jsonify(resp)

# to change maxTA for an entry
@app.route("/changemaxTA", methods = ["GET","POST"])
@login_required
@coordinator_required
def changemaxTA():
    semester_id = int(request.form.get('semester_id'))
    maxTA = int(request.form.get('maxTA'))
    cf_id = int(request.form.get('cf_id'))
    cf = Course_Faculty.query.get(cf_id)
    resp = {}
    if cf.semester_id == semester_id and maxTA >= 0:
        cf.maxTA = maxTA
        db.session.commit()
        resp['message'] = 'Entry edited'
    else:
        resp['message'] = 'Error'
    return jsonify(resp)

# Send Mails to Faculty Belonging to [Coordinator Field , All]
@app.route("/sendMailFaculty/<semester_id>", methods = ["GET","POST"])
@login_required
@coordinator_required
def sendMailFaculty(semester_id): 
    cs = Coordinator_Semester.query.filter_by(semester_id=semester_id,faculty_id=current_user.id).first()
    if not cs:
        flash("Error !" , 'danger')
        return redirect(url_for('courseAllotment'))
    semester = Semester.query.get(semester_id).__repr__()
    cnt = 0
    mails_to_send = []
    for faculty in Faculty.query.filter(Faculty.field.in_((cs.field,settings.default_field)),Faculty.is_active==1).all():
        if faculty.role == 'admin':
            continue
        mail_entry = settings.faculty_course_allot_mail
        URL = '%s/change_password' % (settings.WEB_URL)
        body_ = mail_entry['body_'] % (faculty.name,semester,URL)
        entry = {'subject':mail_entry['subject'],'to':faculty.email,'content':body_}
        cnt += 1
        mails_to_send.append(entry)
    mailQueue.add_mails_to_queue(mails_to_send)
    flash(str(cnt) +' Mails Sent !', 'success')
    return redirect(url_for('courseAllotment'))

#
#
#
# TA Allotment by Coordinators
# ****************************
#
#
#


@app.route("/studentAllotment", methods=['GET', 'POST'])
@login_required
@coordinator_required
def studentAllotment():
    coordinator_sems = Coordinator_Semester.query.filter_by(faculty_id=current_user.id).all()
    semesters = [{'id':sem.semester_id,'semester':sem.semester.__repr__(),'field':sem.field} for sem in coordinator_sems]
    return render_template('studentAllotment.html', title='Student Allotment',semesters=semesters)

# Getting Courses based on allotments made to courses.
@app.route("/get_courses_taallot", methods = ["GET","POST"])
@login_required
@coordinator_required
def get_courses_taallot():
    field = request.form.get('field')
    semester_id = int(request.form.get('semester_id'))
    default_field = settings.default_field
    course_ids = Course.query.filter(Course.field.in_((field,default_field))).all()
    if len(course_ids):
        maxcourseid = max([c.id for c in course_ids])
    c_list = [None]*(maxcourseid+1)
    for c in course_ids:
        c_list[c.id] = c.code+' - '+c.name
    facultys = [f.id for f in Faculty.query.with_entities(Faculty.field,Faculty.id)\
                        .filter(Faculty.field.in_((field,default_field))).all()]
    maxfacultyid = 0
    if facultys:
        maxfacultyid = max(facultys)
    f_list = [None]*(maxfacultyid+1)
    for f_id in facultys:
        f_list[f_id] = True
    courses = []
    for c in Course_Faculty.query.with_entities(Course_Faculty.faculty_id\
                        ,Course_Faculty.semester_id,Course_Faculty.course_id)\
                        .filter(Course_Faculty.semester_id==semester_id).all():
        if c_list[c.course_id] is None:
            continue
        if f_list[c.faculty_id] != True:
            continue
        courses.append({'id':c.course_id,'name':c_list[c.course_id]})
        c_list[c.course_id] = None
    return jsonify(courses)

# Getting All Allotments Made and Pending Allotments Table For selected Semester
@app.route("/get_student_allotments", methods = ["GET","POST"])
@login_required
@coordinator_required
def get_student_allotments():
    semester_id = request.form.get('semester_id')
    field = request.form.get('field')
    # Recording course Data in a list
    course_ids = []
    default_field = settings.default_field
    for c in Course.query.with_entities(Course.field,Course.code,Course.id)\
                    .filter(Course.field.in_((field,default_field))):
        course_ids.append(c.id)
        course_ids.append(c.code)
        course_ids.append(c.field)
    maxcourseid = 0
    if len(course_ids):
        maxcourseid = max(course_ids[::3])
    # Records Number of allotments for each section
    s_list = [None]*(maxcourseid+1)
    # Records course codes and course field in a list based on course_ids
    c_list = [None]*(maxcourseid+1)
    for i in range(0,len(course_ids),3):
        c_list[course_ids[i]]=[course_ids[i+1],course_ids[i+2]]
    # Records Faculty names in a seperate list
    facultys = Faculty.query.with_entities(Faculty.field,Faculty.name,Faculty.id)\
                            .filter(Faculty.field.in_((field,default_field))).all()
    maxfacultyid = 0
    if facultys:
        maxfacultyid = max([f.id for f in facultys])
    f_list = [None]*(maxfacultyid+1)
    for f in facultys:
        f_list[f.id] = f.name
    # Records Student names in a seperate list
    students = Student.query.with_entities(Student.name,Student.roll_number,Student.id).all()
    maxstudentid = 0
    if students:
        maxstudentid = max([s.id for s in students])
    student_list = [None]*(maxstudentid+1)
    for s in students:
        if s.name == s.roll_number:
            student_list[s.id] = s.roll_number
        else:
            student_list[s.id] = s.roll_number+' | '+s.name
    
    ta_list = []
    allotments = []  
    # Contains number of left to be alloted out of Max TAs allowed
    for course_ta in Course_Ta.query.filter(Course_Ta.semester_id==semester_id).all():
        if course_ta.course_id > maxcourseid or c_list[course_ta.course_id] is None:
            continue
        if s_list[course_ta.course_id] is None:
            a = {}
        else:
            a = s_list[course_ta.course_id]
        a[course_ta.section] = a.get(course_ta.section,0) + 1
        s_list[course_ta.course_id] = a
        ta_list.append({'id': course_ta.id,
                    'field':c_list[course_ta.course_id][1],
                    'course':c_list[course_ta.course_id][0],
                    'section': course_ta.section,
                    'student': student_list[course_ta.student_id]})
    for c in Course_Faculty.query.filter(Course_Faculty.semester_id==semester_id).all():
        if c_list[c.course_id] is None or f_list[c.faculty_id] is None:
            continue
        a = s_list[c.course_id]
        if a is None:
            done = 0
        else:
            done = a.get(c.section,0)
        allotments.append({'course_id':c.course_id,'course':c_list[c.course_id][0],
                    'section_id':int(c.section[1:]),'max':c.maxTA,'done':done,
                    'section':c.section +' - '+ f_list[c.faculty_id]})
    response = {'ta_list': ta_list,'pending_allotments':allotments}
    return jsonify(response)

# Remove TA Allotments
@app.route("/removeTaAllotment", methods=['GET', 'POST'])
@login_required
def removeTaAllotment():
    ta_id = request.form.get('ta_id')
    semester_id = int(request.form.get('semester_id'))
    ct = Course_Ta.query.get(ta_id)
    if ct and ct.semester_id == semester_id:
        db.session.delete(ct)
        resp = {'message': "success"}
    else:
        resp = {'message': "error"}
    db.session.commit()
    return jsonify(resp)

# Finding The Sections Under Selected Course
@app.route("/get_sections_fortaallot", methods = ["GET","POST"])
@login_required
@coordinator_required
def get_sections_fortaallot():
    course_id = request.form.get('course_id')
    semester_id = request.form.get('semester_id')
    field = request.form.get('field')
    query = Course_Faculty.query.filter_by(course_id=course_id,
                                semester_id=semester_id).all()
    course_sections = []
    default_field = settings.default_field
    for q in query:
        if q.faculty.field in [field,default_field]:
            course_sections.append({'section':q.section,'prof':q.faculty.name,
                                'maxTA':q.maxTA})
    resp = {'course_sections':course_sections}
    return jsonify(resp)

# Finding the student list based on field
@app.route("/get_students_fortaallot", methods = ["GET","POST"])
@login_required
@coordinator_required
def get_students_fortaallot():
    semester_id = request.form.get('semester_id')
    course_id = int(request.form.get('course_id'))
    field = Course.query.get_or_404(course_id).field
    student_ids = []
    maxstudentid = 0
    for s in Student_Semester.query.with_entities(Student_Semester.student_id,\
                            Student_Semester.active_ta,Student_Semester.semester_id)\
                            .filter_by(semester_id=semester_id,active_ta=1).all():
        if s.student_id>maxstudentid:
            maxstudentid = s.student_id
        student_ids.append(s.student_id)
    cnt:list = [None]*(maxstudentid+1)
    for id in student_ids:
        cnt[id] = 0
    for cta in Course_Ta.query.with_entities(Course_Ta.student_id,Course_Ta.semester_id)\
                              .filter_by(semester_id=semester_id).all():
        if cta.student_id > maxstudentid or cnt[cta.student_id] is None:
            continue
        cnt[cta.student_id] += 1
    student_list = []
    df:str = settings.default_field
    ta_cat = list(settings.active_ta_categories)
    if field == df:
        fields = settings.ALLFIELDS
    else:
        fields = [field,df]
    for s in Student.query.with_entities(Student.id,Student.roll_number, Student.name)\
                    .filter(Student.field.in_(fields),Student.category.in_(ta_cat)).all():
        if s.id>maxstudentid or cnt[s.id] is None:
            continue
        student_list.append({'id':s.id,
                    'name':s.roll_number+' | '+s.name+' | '+str(cnt[s.id])})
    resp = {'student_list':student_list}
    return jsonify(resp)

# Getting Allotments of Selected Course and Semester
@app.route("/get_section_tas", methods = ["GET","POST"])
@login_required
@coordinator_required
def get_section_tas():
    course_id = request.form.get('course_id')
    semester_id = request.form.get('semester_id')
    section = request.form.get('section')
    course_tas = []
    for c in Course_Ta.query.filter_by(course_id=course_id,
                        semester_id=semester_id,section=section).all():
        course_tas.append({'id':c.id, 'section':c.section,'student':c.ta.__repr__()})
    resp = {'course_tas':course_tas,'course':Course.query.get(course_id).__repr__()}
    return jsonify(resp)

# Making TA Allotment by Checking Max TA Limit for the Selected Section
@app.route("/allot_section_ta", methods = ["GET","POST"])
@login_required
def allot_section_ta():
    ta = json.loads(request.form.get('ta_list'))
    semester_id = int(ta['semester_id'])
    course_id = int(ta['course_id'])
    section = ta['section']
    student_id = int(ta['student_id'])

    # Make an Entry Check in Database
    entry_check = Course_Ta.query.filter_by(course_id=course_id,
                            student_id=student_id,section=section,
                            semester_id=semester_id).first()
    if entry_check:
        response = {'message': 'Student has already been alloted under this Course and Section','success':False}
        return jsonify(response)

    # Verifying student , course sections existence and if max TAs Limit is reached or not
    student = Student_Semester.query.filter_by(student_id=student_id,semester_id=semester_id,is_active=1,active_ta=1).first()
    course_faculty = Course_Faculty.query.filter_by(course_id=course_id, section=section, semester_id=semester_id).first()
    allTAs = Course_Ta.query.filter_by(course_id=course_id, section=section, semester_id=semester_id).count()
    c = Course.query.get(course_id)
    df = settings.default_field
    if allTAs >= course_faculty.maxTA:
        response = {'message': 'Maximum TAs Limit Reached','success':False}
        return jsonify(response)
    if student and semester_id and course_id and section and student_id:
        if c.field == df or student.student.field in [c.field,df]:
            entry = Course_Ta(course_id=course_id,
                            student_id=student_id,
                            semester_id=semester_id,
                            section=section)
            db.session.add(entry)
            response = {'message': 'Student is alloted','success':True}
        else:
            response = {'message': "Student Field and Course Field Doesn't Match",
                        'success': False}
    try:
        db.session.commit()
    except:
        db.session.rollback()
        response = {'message': 'Error','success':False}
    return jsonify(response)

#
#
#
# Faculty Access Routes
# *********************
#
# TA allotment by Faculty
# ************************
#
# List of Students With Faculty as Faculty Advisor
# ************************************************
#
#
#

@app.route("/myTeaching", methods=["GET","POST"])
@login_required
def myTeaching():
    faculty = Faculty.query.get(current_user.id)
    semesters = Semester.query.all()
    return render_template('studentAllotmentFac.html',
                    semesters=semesters,faculty=faculty)

# Getting List of alloted Courses to the Faculty for the Semester and Student List
@app.route("/get_faculty_courses", methods = ["GET","POST"])
@login_required
def get_faculty_courses():
    semester_id = request.form.get('semester_id')
    course_query = Course_Faculty.query.filter_by\
                    (faculty_id=current_user.id,semester_id=semester_id).all()
    courses = []
    for c in course_query:
        courses.append({'id':c.course_id,'name':c.course.__repr__(),
                        'section':c.section,'maxTA':c.maxTA,
                        'done':Course_Ta.query.filter_by(section=c.section,
                                semester_id=semester_id,course_id=c.course.id).count()
                       })
    resp = {'courses':courses}
    return jsonify(resp)

# Getting List of Students that can take the course selected by faculty
@app.route("/get_faculty_students", methods = ["GET","POST"])
@login_required
def get_faculty_students():
    semester_id = request.form.get('semester_id')
    course_id = request.form.get('course_id')
    field = Course.query.get_or_404(course_id).field
    student_ids = []
    maxstudentid = 0
    for s in Student_Semester.query.with_entities(Student_Semester.student_id,
                            Student_Semester.active_ta,Student_Semester.semester_id)\
                            .filter_by(semester_id=semester_id,active_ta=1).all():
        if s.student_id>maxstudentid:
            maxstudentid = s.student_id
        student_ids.append(s.student_id)
    cnt = [None]*(maxstudentid+1)
    for id in student_ids:
        cnt[id] = 0
    for course_ta in Course_Ta.query.with_entities(Course_Ta.student_id)\
                        .filter(Course_Ta.semester_id==semester_id).all():
        if course_ta.student_id > maxstudentid or cnt[course_ta.student_id] is None:
            continue
        cnt[course_ta.student_id] += 1
    student_list = []
    ta_cat = list(settings.active_ta_categories)
    df_field = settings.default_field
    if field == df_field:
        fields = settings.ALLFIELDS
    else:
        fields = [field,df_field]
    for s in Student.query.with_entities(Student.field,Student.id,Student.name,Student.roll_number)\
                .filter(Student.field.in_(fields),Student.category.in_(ta_cat)):
        if s.id>maxstudentid or cnt[s.id] is None:
            continue
        name = s.roll_number
        if name != s.name:
            name += " | " + s.name
        student_list.append({'id':s.id,'name':name+' | '+str(cnt[s.id])})
    resp = {'student_list':student_list}
    return jsonify(resp)

# remove allotment route used, is same as removeTaAllotment route mention above

# Getting List of Students Alloted Under That Facultys Courses
@app.route("/get_fac_ta_data", methods = ["GET","POST"])
@login_required
def get_fac_ta_data():
    semester_id = request.form.get('semester_id')
    course_query = Course_Faculty.query.filter_by(faculty_id=current_user.id,semester_id=semester_id).all()
    courses = [{'id':c.course_id,'field':c.course.field,'name':c.course.__repr__(), 'section':c.section} for c in course_query]
    ta_list = []
    for course in courses:
        tas = Course_Ta.query.filter_by(course_id=course['id'], section=course['section'],semester_id=semester_id).all()
        for ta in tas:
            ta_list.append({'id':ta.id, 'course':course['name'], 'section':course['section'],
                            'student':ta.ta.__repr__(),'student_id':ta.student_id,'field':course['field']})
    response = { 'ta_list':ta_list}
    return jsonify(response)

# same route is used as allot_section_ta for TA Allotment by admin
@app.route("/allot_section_ta_byfac", methods = ["GET","POST"])
@login_required
def allot_section_ta_byfac():
    semester_id,course_id = request.form.get('semester_id'),request.form.get('course_id')
    section,student_id = request.form.get('section'),request.form.get('student_id')
    # Make an Entry Check in Database
    entry_check = Course_Ta.query.filter_by(course_id=course_id, student_id=student_id, section=section,semester_id=semester_id).first()
    if entry_check:
        response = {'message': 'Student has already been alloted under this Course and Section','success':False}
        return jsonify(response)

    # Verifying student , course sections existence and if max TAs Limit is reached or not
    student = Student_Semester.query.filter_by(student_id=student_id,semester_id=semester_id,is_active=1,active_ta=1).first()
    course_faculty = Course_Faculty.query.filter_by(course_id=course_id, section=section, semester_id=semester_id).first()
    allTAs = Course_Ta.query.filter_by(course_id=course_id, section=section, semester_id=semester_id).count()
    course_field = Course.query.get(course_id).field
    response = {}
    success = False
    if allTAs >= course_faculty.maxTA:
        response = {'message': 'Maximum TAs Limit Reached'}
        return jsonify(response)
    if student and semester_id and course_id and section and student_id:
        df = settings.default_field
        if course_field == df or student.student.field in [df,course_field]:
            entry = Course_Ta(course_id=course_id, student_id=student_id, section=section,semester_id=semester_id)
            db.session.add(entry)
            db.session.commit()
            response = {'message': 'Student is alloted'}
            success = True
        else:
            response = {'message': "Student Field and Course Field Doesn't Match"}
    response['success'] = success
    return jsonify(response)


# Students's Faculty Advisor List
@app.route("/facFacad", methods=["GET","POST"])
@login_required
def facFacad():
    faculty = Faculty.query.get(current_user.id)
    facad_students = Facad.query.filter_by(facad_id=current_user.id).all()
    facad_students_list = []
    i = 1
    for student in facad_students:
        facad_students_list.append({'facad_id':student.id,'student_id':student.student_id,'name': student.student.name,
                                'roll_number':student.student.roll_number,
                                'program':student.student.program, 'field':student.student.field,
                                'status':student.status,'sno':i})
        i += 1
    return render_template('facFacad.html',facads = facad_students_list,
                            faculty={'name':faculty.name,'id':faculty.id})

# Remove Facad Allotment
@app.route("/facRemoveFacad/<faculty_id>/<facad_id>", methods=["GET","POST"])
@login_required
def facRemoveFacad(faculty_id,facad_id):
    facad = Facad.query.get(facad_id)
    if facad and current_user.id == int(faculty_id) and facad.facad_id == int(faculty_id):
        db.session.delete(facad)
        db.session.commit()
    return redirect(url_for('facFacad'))

# Students's Grade
@app.route("/studentGrade/<student_id>", methods=["GET","POST"])
@login_required
def studentGrade(student_id):
    facad = Facad.query.filter_by(student_id=student_id,facad_id=current_user.id).first()
    if facad.status != 'primary':
        flash('Only primary faculty advisor can grade the student.', 'info')
        return redirect(url_for('facFacad'))
    student_id = int(student_id)
    s = Student.query.get(student_id)
    sps = Student_Project.query.filter_by(student_id=student_id).all()
    sss = Student_Seminar.query.filter_by(student_id=student_id).all()
    cnt = {'project':len(sps),'seminar':len(sss)}
    project_grades = []
    for sp in sps:
        committee = []
        if sp.committee != 'NA':
            for fac in str(sp.committee).split(',')[:-1]:
                committee.append(fac)
        else:
            committee.append('NA')
        project_grades.append({'id':sp.id,'filename':sp.filename,'grade':sp.grade,'year':sp.year,
                    'project':sp.project,'faculty':sp.faculty_name,'date':sp.date_posted,
                    'committee':committee,'other_committee':sp.other_committee})
    seminar_grades = []
    for ss in sss:
        committee = []
        if ss.committee != 'NA':
            for fac in str(ss.committee).split(',')[:-1]:
                committee.append(fac)
        else:
            committee.append('NA')
        seminar_grades.append({'id':ss.id,'filename':ss.filename,'grade':ss.grade,'year':ss.year,
                    'project':ss.project,'faculty':ss.faculty_name,'date':ss.date_posted,
                    'committee':committee,'other_committee':ss.other_committee})

    grades = {'project_grades':project_grades,'seminar_grades':seminar_grades}
    s_data = {'id':s.id,'name':s.name,'rollno':s.roll_number,'project':s.project}
    grds = settings.grade_map
    return render_template('studentGrade.html',student=s_data,grades=grades,title="Student Grade",grds=grds,cnt=cnt)

@app.route("/get_facultys", methods=["GET","POST"])
@login_required
def get_facultys():
    facs = Faculty.query.with_entities(Faculty.id,Faculty.name,Faculty.role)\
                    .filter_by(is_active = 1).all()
    facultys = []
    for fac in facs:
        if fac.role == 'admin':
            continue
        facultys.append({'id':fac.id,'name':fac.name})
    resp = {'profs':facultys}
    return jsonify(resp)

def sendMailCommittee(main_fac,faculty_ids,student_id,data):
    student = Student.query.get(student_id)
    mails_to_send = []
    s_grade = 'Student has been graded as : <br>'\
              '<b>Type    :</b> '+data["type"]+\
              '<b>Project :</b> '+data["project"]+\
              '<b>Grade   :</b> '+data['grade']+\
              '<b>Date    :</b> '+str(data['date'])
    for faculty_id in faculty_ids:
        fac = Faculty.query.get(faculty_id)
        mail_entry = settings.grade_mail_committee
        s_name = '<b>'+student.name + ' < ' + student.roll_number+' ></b>'
        body_ = mail_entry['body_'] % (fac.name,main_fac,s_name,s_grade)
        entry = {'subject':mail_entry['subject'],'to':fac.email,'content':body_}
        mails_to_send.append(entry)
    mailQueue.add_mails_to_queue(mails_to_send)

# give grade to students
@app.route("/projectGradeStudent/<student_id>", methods=["GET","POST"])
@login_required
def projectGradeStudent(student_id):
    if request.method == 'POST' and "gradesheet" in request.files:
        facad = Facad.query.filter_by(student_id=student_id,facad_id=current_user.id).first()
        if facad.status != 'primary':
            flash('Only primary faculty advisor can grade the student.', 'info')
            return redirect(url_for('facFacad'))

        file = request.files['gradesheet']
        student = Student.query.get(student_id)
        grade = request.form.get("grade")
        project = student.project
        num_committee = request.form.get("num_committee")
        committee = 'NA'
        if not ( num_committee == 0 or num_committee == '' or num_committee == None):
            num_committee = int(num_committee)
            committee_mems = []
            committee = ''
            for i in range(num_committee):
                fac = int(request.form.get("committee_"+str(i)))
                committee_mems.append(fac)
                committee += Faculty.query.get(fac).name + ','
        other_committee = request.form.get("other_committee")
        if other_committee == '' or other_committee == None or other_committee == 'None':
            other_committee = 'NA'
        date = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).date()
        year = Student_Project.query\
                            .with_entities(Student_Project.student_id)\
                            .filter_by(student_id=student_id).count()
        if project != "NA" or project != "":
            filename = student.roll_number+'_Project_'+str(year+1)+'.pdf'
            sp = Student_Project(student_id=student_id,
                                faculty_id=current_user.id,
                                faculty_name = current_user.name,
                                project=project,year=year+1,
                                grade=grade,filename=filename,
                                committee=committee,date_posted=date,
                                other_committee=other_committee)
            file.save(settings.PDF_DIR+'/'+filename)
            db.session.add(sp)
            grade_data = {'type':'Project'+str(year+1),'project':project,'date':date,'grade':grade}
            student.last_project = 'Project '+str(year+1)+' | '+grade+' | '+current_user.name
            try:
                db.session.commit()
                sendMailCommittee(current_user.name,committee_mems,int(student_id),grade_data)
            except:
                db.session.rollback()
                flash("Error !",'info')
        else:
            flash("Can't Grade , student hasn't uploaded a project", 'info')
    return redirect(url_for("studentGrade",student_id=student_id))

@app.route("/editProjectGrade/<student_id>", methods=["GET","POST"])
@login_required
def editProjectGrade(student_id):
    if request.method == 'POST' and "editgradesheet" in request.files:
        facad = Facad.query.filter_by(student_id=student_id,facad_id=current_user.id).first()
        if facad.status != 'primary':
            flash('Only primary faculty advisor can grade the student.', 'info')
            return redirect(url_for('facFacad'))

        file = request.files['editgradesheet']
        student = Student.query.get(student_id)
        grade = request.form.get("editgrade")
        num_committee = request.form.get("edit_num_committee")
        committee = 'NA'
        if not ( num_committee == 0 or num_committee == '' or num_committee == None):
            num_committee = int(num_committee)
            committee_mems = []
            committee = ''
            for i in range(num_committee):
                fac = int(request.form.get("e_committee_"+str(i)))
                committee_mems.append(fac)
                committee += Faculty.query.get(fac).name + ','
        other_committee = request.form.get("edit_other_committee")
        if other_committee == '' or other_committee == None or other_committee == 'None':
            other_committee = 'NA'
        date = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).date()
        year = Student_Project.query\
                            .with_entities(Student_Project.student_id)\
                            .filter_by(student_id=student_id).count()
        if student.project != "NA" or student.project != '':
            filename = student.roll_number+'_Project_'+str(year)+'.pdf'
            sp = Student_Project.query.filter_by(student_id=student_id,year=year).first()
            sp.faculty_id=int(current_user.id)
            sp.faculty_name = current_user.name
            sp.project=student.project
            sp.grade=grade
            sp.filename=filename
            sp.committee = committee
            sp.date_posted = date
            sp.other_committee = other_committee
            file.save(settings.PDF_DIR+'/'+filename)
            grade_data = {'type':'Project'+str(year+1),'project':student.project,'date':date,'grade':grade}
            student.last_project = 'Project '+str(year)+' | '+grade+' | '+current_user.name
            try:
                db.session.commit()
                sendMailCommittee(current_user.name,committee_mems,int(student_id),grade_data)
            except:
                db.session.rollback()
                flash("Error !", 'info')
        else:
            flash("Can't Grade , student hasn't uploaded a project", 'info')
    return redirect(url_for("studentGrade",student_id=student_id))

# give grade to students
@app.route("/seminarGradeStudent/<student_id>", methods=["GET","POST"])
@login_required
def seminarGradeStudent(student_id):
    if request.method == 'POST' and "s_gradesheet" in request.files:
        facad = Facad.query.filter_by(student_id=student_id,facad_id=current_user.id).first()
        if facad.status != 'primary':
            flash('Only primary faculty advisor can grade the student.', 'info')
            return redirect(url_for('facFacad'))

        file = request.files['s_gradesheet']
        student = Student.query.get(student_id)
        grade = request.form.get("s_grade")
        num_committee = request.form.get("s_num_committee")
        committee = 'NA'
        if not ( num_committee == 0 or num_committee == '' or num_committee == None):
            num_committee = int(num_committee)
            committee_mems = []
            committee = ''
            for i in range(num_committee):
                fac = int(request.form.get("s_committee_"+str(i)))
                committee_mems.append(fac)
                committee += Faculty.query.get(fac).name + ','
        other_committee = request.form.get("s_other_committee")
        if other_committee == '' or other_committee == None or other_committee == 'None':
            other_committee = 'NA'
        date = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).date()
        year = Student_Seminar.query\
                            .with_entities(Student_Seminar.student_id)\
                            .filter_by(student_id=student_id).count()
        if student.project != "NA" or student.project != "":
            filename = student.roll_number+'_Seminar_'+str(year+1)+'.pdf'
            ss = Student_Seminar(student_id=student_id,
                                faculty_id=current_user.id,
                                faculty_name = current_user.name,
                                project=student.project,year=year+1,
                                grade=grade,filename=filename,
                                committee=committee,date_posted=date,
                                other_committee=other_committee)
            file.save(settings.PDF_DIR+'/'+filename)
            db.session.add(ss)
            grade_data = {'type':'Seminar'+str(year+1),'project':student.project,'date':date,'grade':grade}
            student.last_seminar = 'Seminar '+str(year+1)+' | '+grade+' | '+current_user.name
            try:
                db.session.commit()
                sendMailCommittee(current_user.name,committee_mems,int(student_id),grade_data)
            except:
                db.session.rollback()
                flash("Error !",'danger')
        else:
            flash("Can't Grade , student hasn't uploaded a project", 'info')
    return redirect(url_for("studentGrade",student_id=student_id))

@app.route("/editSeminarGrade/<student_id>", methods=["GET","POST"])
@login_required
def editSeminarGrade(student_id):
    if request.method == 'POST' and "s_editgradesheet" in request.files:
        facad = Facad.query.filter_by(student_id=student_id,facad_id=current_user.id).first()
        if facad.status != 'primary':
            flash('Only primary faculty advisor can grade the student.', 'info')
            return redirect(url_for('facFacad'))

        file = request.files['s_editgradesheet']
        student = Student.query.get(student_id)
        grade = request.form.get("s_editgrade")
        num_committee = request.form.get("s_edit_num_committee")
        committee = 'NA'
        if not ( num_committee == 0 or num_committee == '' or num_committee == None):
            num_committee = int(num_committee)
            committee_mems = []
            committee = ''
            for i in range(num_committee):
                fac = int(request.form.get("s_e_committee_"+str(i)))
                committee_mems.append(fac)
                committee += Faculty.query.get(fac).name + ','
        other_committee = request.form.get("s_edit_other_committee")
        if other_committee == '' or other_committee == None or other_committee == 'None':
            other_committee = 'NA'
        date = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).date()
        year = Student_Seminar.query\
                            .with_entities(Student_Seminar.student_id)\
                            .filter_by(student_id=student_id).count()
        if student.project != "NA" or student.project != '':
            filename = student.roll_number+'_Seminar_'+str(year)+'.pdf'
            ss = Student_Seminar.query.filter_by(student_id=student_id,year=year).first()
            ss.faculty_id=int(current_user.id)
            ss.faculty_name = current_user.name
            ss.project=student.project
            ss.grade=grade
            ss.filename=filename
            ss.committee = committee
            ss.date_posted = date
            ss.other_committee = other_committee
            file.save(settings.PDF_DIR+'/'+filename)
            grade_data = {'type':'Seminar'+str(year+1),'project':student.project,'date':date,'grade':grade}
            student.last_seminar = 'Seminar '+str(year)+' | '+grade+' | '+current_user.name
            try:
                db.session.commit()
                sendMailCommittee(current_user.name,committee_mems,int(student_id),grade_data)
            except:
                db.session.rollback()
                flash("Error !", 'info')
        else:
            flash("Can't Grade , student hasn't uploaded a project", 'info')
    return redirect(url_for("studentGrade",student_id=student_id))

@app.route("/downldStGrdPrf/<filename>", methods=["GET","POST"])
@login_required
def downldStGrdPrf(filename):
    print(filename)
    return send_from_directory(settings.PDF_DIR,filename,as_attachment=True)

#
#
#
# Student List and  Data Pages
# ****************************
# Can be viewed by faculty, coordinators and admin
# ***********************************************
#
#
#

# Get Student List
@app.route("/studentList")
@login_required
def studentList():
    semester = Semester.query.all()
    students = [{'id':student.id,'name':student.__repr__()} for student in Student.query.all()]
    return render_template("studentList.html",fields=settings.ALLFIELDS,
                            categories=settings.CATEGORIES,programs=settings.PROGRAMS,
                             students=students,semesters=semester)

# Get Student List Based on Semester
@app.route("/get_student_list", methods=["GET","POST"])
@login_required
def get_student_list():
    semester_id = request.form.get('semester_id')
    student_ids = []
    nmax = 0
    nmin = Student.query.count()
    for s in Student_Semester.query.with_entities(Student_Semester.student_id,\
                        Student_Semester.is_active,Student_Semester.active_ta,\
                        Student_Semester.exemption_reason)\
                        .filter_by(semester_id=semester_id,is_active=1).all():
        nmax = max(nmax,s.student_id)
        nmin = min(nmin,s.student_id)
        if s.active_ta==1:
            student_ids.append([s.student_id,True,''])
        else:
            student_ids.append([s.student_id,False,s.exemption_reason])
    # Creating list to store student data + ta duties + facads
    students = [None]*(nmax+1)
    ta_list = [None]*(nmax+1)
    student_facads = [None]*(nmax+1)
    for s in Student.query.all():
        if s.id > nmax or s.id < nmin:
            continue
        students[s.id] = s
    for ta in Course_Ta.query.filter_by(semester_id=semester_id).all():
        if ta.student_id > nmax:
            continue
        a = ta_list[ta.student_id]
        if a is None:
            a = []
        a.append(ta)
        ta_list[ta.student_id] = a
    for facad in Facad.query.all():
        a = student_facads[facad.student_id]
        if a is None:
            a = []
        a.append(facad)
        student_facads[facad.student_id] = a
    # Records Course names in a seperate list
    course_data = Course.query.with_entities(Course.id,Course.code).all()
    maxcourseid = 0
    if course_data:
        maxcourseid = max([c.id for c in course_data])
    c_list = [None]*(maxcourseid+1)
    for c in course_data:
        c_list[c.id] = c.code
    
    student_list = []
    current_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).date()
    for student_id in student_ids:
        s = students[student_id[0]]
        #getting course list student is part of
        courses = []
        tas = ta_list[student_id[0]]
        if tas is not None:
            for ta in tas:
                courses.append({'id':ta.course_id,'section':ta.section,'course':c_list[ta.course_id]})
        # getting latest attendance
        attendance = ""
        if s.last_attendance:
            c_time = current_time - s.last_attendance
            attendance = str(c_time.days) + ' Days Ago'
        #getting facads names
        facad_list = []
        facads = student_facads[student_id[0]]
        if facads is None:
            facads = []
        for facad in facads:
            facad_list.append({'facad_id':facad.facad_id,'status':facad.status,'facad':facad.facad_name})
        student_list.append({'id': s.id, 'name': s.name, 'email':s.email,'rollno':s.roll_number,
                             'phone_number':s.phone_number,'active_ta':student_id[1],'reason':student_id[2],
                             'program':s.program,'category':s.category, 'field':s.field,'courses': courses,
                             'facads':facad_list,'attendance':attendance,'grade':[s.last_project,s.last_seminar]})
    role = False
    if current_user.role == 'admin':
        role = True
    resp = {'students':student_list,'admin':role}
    return jsonify(resp)

# Find Student Using Name / Roll_number
@app.route("/findStudent" , methods=['GET', 'POST'])
@login_required
def findStudent():
    student_id = request.args.get('student')
    return redirect(url_for('studentData',student_id=student_id))

# Student Profile Page
@app.route("/studentData/<student_id>")
@login_required
def studentData(student_id):
    student = Student.query.get_or_404(student_id)
    course_tas = Course_Ta.query.filter_by(student_id=student_id).all()
    attendances = []
    for attendance_query in Attendance.query.filter_by(student_id=student_id).all():
        attendances.append({'id':len(attendances)+1,'date_posted':attendance_query.date_posted,
                            'datetime_posted':attendance_query.datetime_posted})
    student_data = {'name':student.name,'email':student.email, 'roll_number':student.roll_number,
                   'phone_number':student.phone_number, 'field':student.field,'alt_email':student.alt_email,
                    'program':student.program, 'hostel_no': student.hostel_no,'category':student.category,
                    'room_no': student.room_no,'project':student.project,'id':student_id}
    facads = Facad.query.filter_by(student_id=student_id).all()
    facad_list = []
    for facad in facads:
        facad_list.append({'status':facad.status,'facad_name':facad.facad.name})
    sps = Student_Project.query.filter_by(student_id=student_id).all()
    sss = Student_Seminar.query.filter_by(student_id=student_id).all()
    cnt = {'project':len(sps),'seminar':len(sss)}
    project_grades = []
    for sp in sps:
        committee = []
        if sp.committee != 'NA':
            for fac in str(sp.committee).split(',')[:-1]:
                committee.append(fac)
        else:
            committee.append('NA')
        project_grades.append({'grade':sp.grade,'year':sp.year,
                    'project':sp.project,'faculty':sp.faculty_name,'date':sp.date_posted,
                    'committee':committee,'other_committee':sp.other_committee})
    seminar_grades = []
    for ss in sss:
        committee = []
        if ss.committee != 'NA':
            for fac in str(ss.committee).split(',')[:-1]:
                committee.append(fac)
        else:
            committee.append('NA')
        seminar_grades.append({'grade':ss.grade,'year':ss.year,
                    'project':ss.project,'faculty':ss.faculty_name,'date':ss.date_posted,
                    'committee':committee,'other_committee':ss.other_committee})

    grades = {'project_grades':project_grades,'seminar_grades':seminar_grades}
    return render_template('studentData.html', student=student_data,fields=settings.ALLFIELDS,
                    programs=settings.PROGRAMS,categories=settings.CATEGORIES,grades = grades,
                    course_tas=course_tas, attendances=attendances,facads = facad_list,cnt = cnt)

@app.route("/deleteStudentProjectGrade/<student_id>", methods = ["GET","POST"])
@admin_required
@login_required
def deleteStudentProjectGrade(student_id):
    if current_user.role != 'admin':
        flash("You don't have permission to perform this action", 'info')
        return redirect(url_for('studentData', student_id=student_id))
    cnt = Student_Project.query\
                .with_entities(Student_Project.student_id)\
                .filter_by(student_id=student_id).count()
    project_grade = Student_Project.query.filter_by(student_id=student_id,year=cnt).first()
    db.session.delete(project_grade)
    student = Student.query.get(student_id)
    if cnt<2:
        student.last_project = 'NA'
    else:
        sp = Student_Project.query.filter_by(student_id=student_id,year=cnt-1).first()
        if sp:
            student.last_project = 'Project '+str(sp.year)+' | '+sp.grade+' | '+sp.faculty_name
    try:
        db.session.commit()
    except:
        db.session.rollback()
        flash("Error !", 'danger')
    return redirect(url_for('studentData', student_id=student_id))

@app.route("/deleteStudentSeminarGrade/<student_id>", methods = ["GET","POST"])
@admin_required
@login_required
def deleteStudentSeminarGrade(student_id):
    if current_user.role != 'admin':
        flash("You don't have permission to perform this action", 'info')
        return redirect(url_for('studentData', student_id=student_id))
    cnt = Student_Seminar.query\
                .with_entities(Student_Seminar.student_id)\
                .filter_by(student_id=student_id).count()
    seminar_grade = Student_Seminar.query.filter_by(student_id=student_id,year=cnt).first()
    db.session.delete(seminar_grade)
    student = Student.query.get(student_id)
    if cnt<2:
        student.last_seminar = 'NA'
    else:
        ss = Student_Seminar.query.filter_by(student_id=student_id,year=cnt-1).first()
        if ss:
            student.last_seminar = 'Seminar '+str(ss.year)+' | '+ss.grade+' | '+ss.faculty_name
    try:
        db.session.commit()
    except:
        db.session.rollback()
        flash("Error !", 'danger')
    return redirect(url_for('studentData', student_id=student_id))

# Editing Student Field Program
@app.route("/addStudentData", methods = ["GET","POST"])
@admin_required
@login_required
def addStudentData():
    name = str(request.form.get('name')).strip()
    roll_number = str(request.form.get('roll_number')).strip()
    email = str(request.form.get('email')).strip()
    program = str(request.form.get('program')).strip()
    field = str(request.form.get('field')).strip()
    category = str(request.form.get('category')).strip()
    semester_id = int(request.form.get('semester_id'))
    resp = {}
    if program in settings.PROGRAMS and field in settings.ALLFIELDS and category in settings.CATEGORIES:
        student = Student.query.filter(func.lower(Student.roll_number) == func.lower(roll_number)).first()
        sem_ids = [ sem.id for sem in Semester.query.filter(Semester.id>=semester_id).all()]
        if student and student.roll_number == roll_number:
            message = 'Student Data Updated'
            student.name = name
            student.email = email
            student.field = field
            student.program = program
            student.category = category
            entries = Student_Semester.query.filter(Student_Semester.semester_id>=semester_id,Student_Semester.student_id==student.id).all()
            entrynotdone = create_semester_student_status(student.id,'active',entries,sem_ids)
        else:
            message = 'New Student Data Added'
            s = Student(name=name,email=email,roll_number=roll_number,
                        category=category,program=program,field=field)
            db.session.add(s)
            db.session.flush()
            entrynotdone = create_semester_student_status(s.id,'active',None,sem_ids)
        if entrynotdone:
            db.session.rollback()
            resp = {'message' : 'Error','success':False}
            return jsonify(resp)
        try:
            db.session.commit()
            resp = {'message' :message,'success':True}
        except:
            db.session.rollback()
            resp = {'message' : 'Error','success':False}
    else:
        resp = {'message' : 'Error','success':False}
    return jsonify(resp)

# Edit Student Status
@app.route("/editStudentStatus",methods=["GET","POST"])
@admin_required
@login_required
def editStudentStatus():
    resp = {'message': "",'result':False}
    if current_user.role != 'admin':
        resp['message'] = "You don't have authority to edit this !"
        return jsonify(resp)
    semester_id = int(request.form.get('semester_id'))
    student_id = int(request.form.get('student_id'))
    status = str(request.form.get('status')).strip().lower()
    s = Student.query.get(student_id)

    if not s:
        resp = {'message':'Error','result':False}
        return jsonify(resp)

    entries = Student_Semester.query\
                    .filter(Student_Semester.semester_id>=semester_id,\
                        Student_Semester.student_id==student_id).all()
    if status == 'inactive':
        for entry in entries:
            db.session.delete(entry)
    elif status == 'active':
        sem_ids = [ sem.id for sem in \
                        Semester.query.filter(Semester.id>=semester_id).all()]
        entrynotdone = create_semester_student_status(s.id,'active',entries,sem_ids)
        if entrynotdone:
            resp = {'message':'Error','result':False}
            return jsonify(resp)
    try:
        db.session.commit()
        resp = {'message':'Student Status Changed','result':True}
    except:
        db.session.rollback()
        resp = {'message':'Error','result':False}
    return jsonify(resp)


# Edit Student Status
@app.route("/studentExemption",methods=["GET","POST"])
@admin_required
@login_required
def studentExemption():
    semester_id = int(request.form.get('semester_id'))
    student_id = int(request.form.get('student_id'))
    reason = str(request.form.get('reason'))
    action= str(request.form.get('action'))
    s = Student_Semester.query.filter_by(student_id=student_id,semester_id=semester_id).first()
    if not s:
        resp = {'message':'Student not found, Error !','success':False}
        return jsonify(resp)
    if action == 'exempt':
        s.active_ta = 0
        s.exemption_reason = reason
        message = 'Student has Exempted from TA Duty for this Semester'
    elif action == 'unexempt':
        s.active_ta = 1
        s.exemption_reason = ''
        message = 'Student can now perform TA duty this semester'
    try:
        db.session.commit()
        resp = {'message' :message,'success':True}
    except:
        db.session.rollback()
        resp = {'message' : 'Error !','success':False}
    return jsonify(resp)

#
#
#
# Faculty List and  Data Pages
# ****************************
# Can be viewed by faculty, coordinators and admin
# ***********************************************
#
#
#

# Get Faculty List
@app.route("/facultyList",methods=["GET","POST"])
@login_required
def facultyList():
    semester = Semester.query.all()
    fields = settings.ALLFIELDS
    facultys = [{'id':faculty.id,'name':faculty.__repr__()} 
                    for faculty in Faculty.query.all() if faculty.role != 'admin']
    return render_template("facultyList.html", facultys=facultys,
                    fields=fields,semesters=semester)

# Get Faculty List Based on Semester
@app.route("/get_faculty_list", methods=["GET","POST"])
@login_required
def get_faculty_list():
    semester_id = request.form.get('semester_id')
    facultys = Faculty.query.all()
    max_faculty_id = 0
    if facultys:
        max_faculty_id = max([f.id for f in facultys])
    f_status = [True]*(max_faculty_id+1)
    f_courses = [None]*(max_faculty_id+1)
    coordinator = [None]*(max_faculty_id+1)
    for f in Faculty_Semester.query.with_entities(Faculty_Semester.faculty_id)\
                .filter_by(semester_id=semester_id,is_active=0).all():
        f_status[f.faculty_id] = False
    for f in Coordinator_Semester.query.filter_by(semester_id=semester_id).all():
        coordinator[f.faculty_id] = f.field
    for cf in Course_Faculty.query.filter_by(semester_id=semester_id).all():
        a = f_courses[cf.faculty_id]
        if a is None:
            a = []
        a.append(cf)
        f_courses[cf.faculty_id] = a
    # Records Course names in a seperate list
    course_data = Course.query.with_entities(Course.id,Course.code).all()
    maxcourseid = 0
    if course_data:
        maxcourseid = max([c.id for c in course_data])
    c_list = [None]*(maxcourseid+1)
    for c in course_data:
        c_list[c.id] = c.code
    
    faculty_list = []
    for faculty in facultys:
        if faculty.role=="admin" or  faculty.is_active == 0:
            continue
        # Checking Faculty Status
        status = ''
        if f_status[faculty.id] == False:
            status = 'OnLeave'
        # Finding Courses Currently Taught by faculty
        courses = []
        a = f_courses[faculty.id]
        if a is None:
            a = []
        for c in a:
            courses.append({'id':c.course_id,'section':c.section,'name':c_list[c.course_id]})
        # Checking if coordinator
        coord = coordinator[faculty.id]
        if coord is None:
            coord = ""
        # Adding Entry to List
        faculty_list.append({'id':faculty.id, 'email':faculty.email,'ldap':faculty.ldap,
                            'name':faculty.name,'phone_number':faculty.phone_number,
                            'field':faculty.field,'courses': courses,'status':status,'coord':coord})
    role = False
    if current_user.role == 'admin':
        role = True
    resp = {'facultys':faculty_list,'admin':role}
    return jsonify(resp)

# Search Faculty Using Faculty name / Ldap
@app.route("/findFaculty" , methods=['GET', 'POST'])
@login_required
def findFaculty():
    faculty_id = request.args.get('faculty')
    return redirect(url_for('facultyData', faculty_id=faculty_id))

# Faculty Profile Page
@app.route("/facultyData/<faculty_id>")
@login_required
def facultyData(faculty_id):
    faculty = Faculty.query.get_or_404(faculty_id)
    faculty_list = {'email':faculty.email,'name':faculty.name,'phone_no':faculty.phone_number,
                    'field':faculty.field, 'status':faculty.is_active, 'ldap':faculty.ldap}
    facads = Facad.query.filter_by(facad_id = faculty_id).all()
    semester_data = []
    semesters = Semester.query.all()
    for sem in semesters:
        courses = Course_Faculty.query.filter_by(faculty_id=faculty_id,semester_id=sem.id).all()
        course_data = []
        for c in courses:
            course_tas = Course_Ta.query.filter_by(course_id=c.course_id,section=c.section,semester_id=sem.id).all()
            tas = [{'student_id':ta.student_id,'name':ta.ta.__repr__()} for ta in course_tas]
            course_data.append({'course_id':c.course_id,'code':c.course,'section':c.section,'tas':tas})
        if len(course_data) != 0:
            semester_data.append({'semester':sem.semester,'courses':course_data})
    return render_template('facultyData.html', faculty=faculty_list, facads = facads,semesters=semester_data)

# add A New Faculty to the database
# Update Faculty Data
@app.route("/addNewFaculty" , methods=['GET', 'POST'])
@admin_required
@login_required
def addNewFaculty():
    name = str(request.form.get("name")).strip()
    ldap = str(request.form.get("ldap")).strip()
    email = str(request.form.get("email")).strip()
    field = str(request.form.get("field")).strip()
    phone = str(request.form.get("phone_number")).strip()
    resp = {'message': '','key':False}
    ldap_check = Faculty.query.filter(func.lower(Faculty.ldap) == func.lower(ldap)).all()
    email_check = Faculty.query.filter(func.lower(Faculty.email) == func.lower(email)).all()
    if len(ldap_check) != 0 or len(email_check) != 0 :
        resp = {'message': 'Ldap or Email Already Exists','key':False}
        return jsonify(resp)
    if field not in settings.ALLFIELDS:
        resp = {'message': 'Error Invalid Field','key':False}
        return jsonify(resp)
    fac = Faculty(ldap=ldap,email=email,name=name,field=field,phone_number = phone)
    db.session.add(fac)
    try:
        db.session.commit()
        resp = {'message': 'Faculty Data Added','key':True}
    except:
        resp = {'message': 'Error','key':False}
        db.session.rollback()
    return jsonify(resp)


# add A New Faculty to the database
# Update Faculty Data
@app.route("/activateFaculty" , methods=['GET', 'POST'])
@admin_required
@login_required
def activateFaculty():
    faculty_id = int(request.args.get('faculty_name'))
    faculty = Faculty.query.get(faculty_id)
    if not faculty or faculty.role=="admin":
        flash('Error !', 'danger')
        return redirect(url_for('facultyList'))

    # Checking Faculty Status
    if faculty.is_active == 0:
        faculty.is_active = 1
    else:
        flash('Error !', 'danger')
        return redirect(url_for('facultyList'))

    try:
        db.session.commit()
        flash('Faculty Status Changed !', 'success')
    except:
        db.session.rollback()
        flash('Error !', 'danger')
    return redirect(url_for('facultyList'))

# add A New Faculty to the database
# Update Faculty Data
@app.route("/changeFacultyStatus" , methods=['GET', 'POST'])
@admin_required
@login_required
def changeFacultyStatus():
    faculty_id = int(request.form.get('faculty_id'))
    faculty = Faculty.query.get(faculty_id)
    if not faculty or faculty.role=="admin":
        resp = {'message':'Error !','key':False}
        return jsonify(resp)

    # Checking Faculty Status
    if faculty.is_active == 1:
        faculty.is_active = 0
    else:
        resp = {'message':'Error !','key':False}
        return jsonify(resp)

    try:
        db.session.commit()
        resp = {'message': 'Faculty Status Changed','key':True}
    except:
        resp = {'message': 'Error','key':False}
        db.session.rollback()
    return jsonify(resp)

# Update Faculty Data
@app.route("/updateFacultyData" , methods=['GET', 'POST'])
@admin_required
@login_required
def updateFacultyData():
    name = str(request.form.get("name")).strip()
    ldap = str(request.form.get("ldap")).strip()
    email = str(request.form.get("email")).strip()
    field = str(request.form.get("field")).strip()
    phone = str(request.form.get("phone_number")).strip()
    faculty_id = int(request.form.get("faculty_id"))
    faculty = Faculty.query.get(faculty_id)
    resp = {'message': '','key':False}

    if not faculty:
        resp = {'message': 'Error','key':False}
        return jsonify(resp)

    if str(faculty.ldap).lower() != ldap.lower():
        ldap_check = Faculty.query.filter(func.lower(Faculty.ldap) == func.lower(ldap)).all()
        if len(ldap_check) != 0:
            resp = {'message': 'Ldap Already Exists','key':False}
            return jsonify(resp)
    if str(faculty.email).lower() != email.lower():
        email_check = Faculty.query.filter(func.lower(Faculty.email) == func.lower(email)).all()
        if len(email_check) != 0:
            resp = {'message': 'Email Already Exists','key':False}
            return jsonify(resp)
    if field not in settings.ALLFIELDS:
        resp = {'message': 'Error Invalid Field','key':False}
        return jsonify(resp)

    if str(faculty.name).lower() != name:
        facads = Facad.query.filter_by(facad_id = faculty_id).all()
        for f in facads:
            f.facad_name = name
        sps = Student_Project.query.filter_by(faculty_id = faculty_id).all()
        for sp in sps:
            sp.faculty_name = name
        sss = Student_Seminar.query.filter_by(faculty_id = faculty_id).all()
        for ss in sss:
            ss.faculty_name = name
    faculty.name = name
    faculty.ldap = ldap
    faculty.email = email
    faculty.field = field
    faculty.phone_number = phone

    try:
        db.session.commit()
        resp = {'message': 'Faculty Data Updated','key':True}
    except:
        resp = {'message': 'Error','key':False}
        db.session.rollback()
    return jsonify(resp)


#
#
#
# Course List and  Data Pages
# ****************************
# Can be viewed by faculty, coordinators and admin
# ***********************************************
#
#
#

# Get Course List
@app.route("/courseList")
@login_required
def courseList():
    semester = Semester.query.all()
    fields = settings.ALLFIELDS
    courses = [{'id':course.id,'name':course.__repr__()} 
                        for course in Course.query.all()]
    return render_template("courseList.html", courses=courses,
                    fields=fields,semesters=semester)

# Get Course List Based on Semester
@app.route("/get_course_list", methods=["GET","POST"])
@login_required
def get_course_list():
    semester_id = request.form.get("semester_id")
    course_list = []
    courses = Course.query.all()
    course_ids = [c.id for c in courses]
    max_course_id = 0
    if course_ids:
        max_course_id = max(course_ids)
    c_status = [0]*(max_course_id+1)
    c_sections = [None]*(max_course_id+1)
    # Records Faculty names in a seperate list
    facultys = Faculty.query.with_entities(Faculty.name\
                        ,Faculty.id,Faculty.role,Faculty.is_active)\
                        .filter(Faculty.is_active==1,Faculty.role!='admin').all()
    maxfacultyid = 0
    if facultys:
        maxfacultyid = max([f.id for f in facultys])
    f_list = [None]*(maxfacultyid+1)
    for f in facultys:
        f_list[f.id] = f.name
    # Getting Course Mandatory Status 
    for cs in Course_Semester.query.filter_by(semester_id=semester_id,is_mandatory=1).all():
        c_status[cs.course_id] = 1
    # Getting Course Allotments
    for cf in Course_Faculty.query.filter_by(semester_id=semester_id).all():
        a = c_sections[cf.course_id]
        if a is None:
            a = []
        a.append(cf)
        c_sections[cf.course_id] = a
    for course in courses:
        # Faculty associated with this course
        instructors = []
        a = c_sections[course.id]
        if a is None:
            a = []
        for s in a:
            instructors.append({'faculty_id':s.faculty_id,'name':f_list[s.faculty_id],'section':s.section,
                                'TA': str(Course_Ta.query.filter_by(course_id=course.id,semester_id=semester_id,section=s.section).count())+'/'+str(s.maxTA)})
        course_list.append({'id':course.id,'field':course.field,'code':course.code,'is_mandatory':c_status[course.id],
                            'name':course.name,'instructors':instructors})
    admin = False
    if current_user.role == 'admin':
        admin = True
    resp = {'courses':course_list,'admin':admin}
    return jsonify(resp)

# Update Course Data
@app.route("/updateCourseData" , methods=['GET', 'POST'])
@admin_required
@login_required
def updateCourseData():
    field = str(request.form.get('field')).strip()
    code = str(request.form.get('code')).strip()
    name = str(request.form.get('name')).strip()
    course_id = int(request.form.get("course_id"))
    course = Course.query.get(course_id)
    lowercode = ''.join(code.split(" ")).lower()
    if field in settings.ALLFIELDS:
        for c in Course.query.with_entities(Course.code,Course.id).all():
            if c.id == course_id:
                continue
            if lowercode == ''.join(str(c.code).split(" ")).lower():
                resp = {'message' : 'Course Code Already Exists','key':False}
                return jsonify(resp)
        course.field = field
        course.code = code
        course.name = name
        try:
            db.session.commit()
            resp = {'message' : 'Course Updated','key':True}
        except:
            db.session.rollback()
            resp = {'message':'Error','key':False}
    else:
        resp = {'message':'Error, Field unrecognisable','key':False}

    return jsonify(resp)

# Search Course Based on Code / Name
@app.route("/findCourse" , methods=['GET', 'POST'])
@login_required
def findCourse():
    course_id = request.args.get('course')
    return redirect(url_for('courseData', course_id=course_id))

# Course Profile Page
@app.route("/courseData/<course_id>")
@login_required
def courseData(course_id):
    course = Course.query.get(course_id)
    semesters = Semester.query.all()
    semester_data = []
    for sem in semesters:
        status = Course_Semester.query.filter_by(course_id=course.id,semester_id=sem.id,is_mandatory=1).first()
        # Course Status in Semester
        mandatory = ''
        if status:
            mandatory = str(status.is_mandatory)
        course_sections = Course_Faculty.query.filter_by(course_id=course_id,semester_id=sem.id).all()
        course_tas = Course_Ta.query.filter_by(course_id=course_id,semester_id=sem.id).all()
        sections = []
        for s in course_sections:
            tas = [{'student_id':ta.student_id,'name':ta.ta.__repr__()} for ta in course_tas if ta.section == s.section]
            sections.append({'section':s.section,'maxTA':s.maxTA,'faculty_id':s.faculty_id
                            ,'faculty':s.faculty.__repr__(),'tas':tas})
        if len(sections) != 0:
            semester_data.append({'semester':sem.semester,'sections':sections,'status':mandatory})
    course_data = {'code':course.code,'name':course.name,'field':course.field,
                    'semesters':semester_data}
    return render_template('courseData.html',course=course_data)

#
#
#
# Student Access Pages
# *********************
#
# Attendance Section for TAs
# ***************************
#
# Update Data and Add Facad
# **************************
#
#
#

# Student Access Page
@app.route("/attendance", methods = ["GET","POST"])
def attendance():
    if current_user.is_authenticated:
        logout_user()
    student_id = int(request.args.get('student_id'))
    token = str(request.args.get('student_token'))
    student = Student_token.query.filter_by(student_id=student_id, token=token).first()

    # Checking for Valid Student Token and Student ID
    if student == None:
        flash('Invalid or Expired Token', 'info')
        return redirect(url_for('student_token'))

    s = Student.query.get(student_id)
    course_tas = Course_Ta.query.filter_by(student_id=student_id).all()
    attendances = []
    for attendance_query in Attendance.query.filter_by(student_id=student_id):
        attendances.append({'id':len(attendances)+1, 'date_posted':attendance_query.date_posted,
                            'datetime_posted':attendance_query.datetime_posted})
    facultys = [{'id':faculty.id, 'name':faculty.name} for faculty in Faculty.query.filter_by(is_active=1).all() if faculty.role != 'admin']
    student_data = {'id':student_id, 'token':token, 'name':s.name,'email':s.email,'category':s.category,
                    'roll_number':s.roll_number,'phone_number':s.phone_number,'field':s.field,
                    'program':s.program, 'hostel_no': s.hostel_no,'room_no': s.room_no,
                    'alt_email':s.alt_email,'project':s.project}
    sps = Student_Project.query.filter_by(student_id=student_id).all()
    project_grades = []
    for sp in sps:
        committee = []
        if sp.committee != 'NA':
            for fac in str(sp.committee).split(',')[:-1]:
                committee.append(fac)
        else:
            committee += 'NA'
        project_grades.append({'grade':sp.grade,'year':str(sp.year),'project':sp.project,
                    'faculty':sp.faculty_name,'date':str(sp.date_posted),
                    'committee':committee,'other_committee':sp.other_committee})
    sss = Student_Seminar.query.filter_by(student_id=student_id).all()
    seminar_grades = []
    for sp in sss:
        committee = []
        if sp.committee != 'NA':
            for fac in str(sp.committee).split(',')[:-1]:
                committee.append(fac)
        else:
            committee += 'NA'
        seminar_grades.append({'grade':sp.grade,'year':str(sp.year),'project':sp.project,
                    'faculty':sp.faculty_name,'date':str(sp.date_posted),
                    'committee':committee,'other_committee':sp.other_committee})
    grades = {'project_grades':project_grades,'seminar_grades':seminar_grades}
    return render_template("attendance.html", student=student_data, course_tas=course_tas,
                        attendances=attendances,grades=grades,
                        facultys=facultys,title='Student Profile')

# Marking Attendance , Can be Marked once a Day
@app.route("/markAttendance", methods = ["GET","POST"])
@validate_student
def markAttendance():
    student_id = int(request.args.get('student_id'))
    student_token = str(request.args.get('student_token'))
    date_posted=datetime.datetime.now(pytz.timezone('Asia/Kolkata')).date()
    datetime_posted = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).today()
    prev_attendance = Attendance.query.filter_by(student_id=student_id,date_posted=date_posted).first()
    if prev_attendance:
        flash("You have already marked your attendance", "info")
    else:
        attendance = Attendance(student_id=student_id,date_posted=date_posted,datetime_posted=datetime_posted)
        db.session.add(attendance)
        student = Student.query.get(student_id)
        student.last_attendance = date_posted
        db.session.commit()
        flash("Attendance Marked !", "success")
    return redirect(url_for('attendance', student_id=student_id, student_token=student_token))

# Fetching Faculty Advisors List
@app.route("/getFacadData", methods = ["GET","POST"])
@validate_student
def getFacadData():
    student_id = request.form.get('student_id')
    facads = Facad.query.filter_by(student_id=student_id).all()
    facad_list = []
    for facad in facads:
        facad_list.append({'id':facad.id,'status':facad.status,'facad_name':facad.facad.name})
    resp = {'facads':facad_list}
    return jsonify(resp)

# Removing Facad Allotment
@app.route("/facadRemove", methods = ["GET","POST"])
@validate_student
def facadRemove():
    facad_id = request.form.get('facad_id')
    student_id = request.form.get('student_id')
    facad = Facad.query.filter_by(id=facad_id, student_id=student_id).first()
    resp = {}
    if facad:
        db.session.delete(facad)
        resp = {'message':'Removed'}
    db.session.commit()
    return jsonify(resp)

# updateStudentData
@app.route("/updateStudentData", methods = ["GET","POST"])
@validate_student
def updateStudentData():

    student_id = int(request.form.get("student_id"))
    student = Student.query.get(student_id)
    if not student:
        resp = {'message': 'Error'}
        return jsonify(resp)
    
    facad_id = request.form.get('facad_id')
    project = request.form.get("project")
    facad_role = request.form.get('status')

    student.project = project
    student.phone_number = request.form.get('phone_number')
    student.hostel_no = request.form.get('hostel_no')
    student.room_no = request.form.get('room_no')
    student.alt_email = request.form.get('alt_email')
    
    try:
        db.session.commit()
        resp = {'message':'Added'}
    except:
        db.session.rollback()
        resp = {'message':'Error-1'}
        return jsonify(resp)

    if facad_id not in ["None", ""] and facad_role not in ["None", ""]:
        faculty = Faculty.query.get(facad_id)
    
        if faculty is None:
            resp = {'message': 'Error-2'}
            return jsonify(resp)
        
        facad = Facad(student_id = student_id, facad_id=facad_id, status=facad_role, facad_name=faculty.name)
        facad_check = Facad.query.filter_by(student_id=student_id, facad_id=facad_id).first()
        if facad_check:
            resp = {'message': 'Entry already exists'}
            return jsonify(resp)

        if facad_role=='secondary':
            db.session.add(facad)
        
        if facad_role=='primary':
            facad_primary = Facad.query.filter_by(student_id=student_id,status='primary').first()
            if facad_primary:
                resp = {'message': 'Only 1 primary Facad is Allowed'}
                return jsonify(resp)
            else:
                db.session.add(facad)
    
        try:
            db.session.commit()
            resp = {'message':'Added'}
        except:
            db.session.rollback()
            resp = {'message':'Error-3'}
   
    else:
        resp = {'message': 'No changes in the facad data'}

    return jsonify(resp)