from functools import wraps
from re import S
from flask import render_template, url_for, flash, redirect, request , jsonify
from flaskblog.models import Course, Course_Faculty, Course_Semester, Course_Ta, Faculty, Faculty_Semester, Semester, Student, Attendance, Student_Semester, Student_token, Facad
from flaskblog.forms import LoginForm
from flaskblog import app, db, bcrypt, scheduler, mail
from flask_mail import Message
from flask_login import login_required, login_user, current_user, logout_user
import json ,datetime, pytz, string , random, secrets
from pandas import read_excel
from sqlalchemy.exc import IntegrityError

def coordinator_required(func):
    @wraps(func)
    def decorated_view(*args, **kwargs):
        if current_user.role not in ['coordinator', 'admin'] :
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

''' 

Login Pages 

'''

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
        faculty = Faculty.query.filter_by(email = form.email.data).first()
        if faculty and bcrypt.check_password_hash(faculty.password,form.password.data) :
            login_user(faculty, remember=form.remember.data)
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('home'))
        else:
            flash('Login Unsuccessful. Please check username and password', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('login'))

# Create A Short Time Password For Faculty Login
@app.route("/change_password", methods=['GET','POST'])
def change_password():
    return render_template('password.html')

# Generate Password and schedule app to remove it later
@app.route("/get_password", methods=['GET','POST'])
def get_password():
    ldap = request.form.get('ldap')
    faculty = Faculty.query.filter_by(ldap=ldap).first()

    if faculty == None:
        flash('LDAP ID entered doesnt exist !', 'info')
        return redirect(url_for('change_password'))

    # Generating Random Password
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    num = string.digits
    symbols = string.punctuation
    password = "".join(random.sample(lower+upper+num+symbols,12))
    body_ = 'New Password associated with ldap id '+ldap+' is '+password
    message = Message(subject="New Password", recipients=[faculty.email], 
                        body = body_ , sender= "myemail@gmail.com" )
    print(message)
    # mail.send(message)
    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    faculty.password = hashed_password
    # setting password reset time to 2 hrs
    c_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
    add = datetime.timedelta(hours=2)
    time = c_time + add
    # Scheduling job for password reset
    scheduler.add_job(id='reset_password'+ldap, func=reset_password,
                    trigger='date',run_date=time,args=[faculty.id],replace_existing= True)
    try:
        db.session.commit()
        flash('Password has been sent to '+faculty.email, 'success')
    except Exception:
        db.session.rollback()
    return redirect(url_for('login'))

def reset_password(faculty_id):
    faculty = Faculty.query.get(faculty_id)
    if faculty != None:
        lower = string.ascii_lowercase
        upper = string.ascii_uppercase
        num = string.digits
        symbols = string.punctuation
        password = "".join(random.sample(lower+upper+num+symbols,12))
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        faculty.password = hashed_password
        db.session.commit()
        print('Password has been reset to '+ password + ' for '+ str(faculty_id))

# Generate Short Token for Student To Use
@app.route("/student_token", methods=['GET', 'POST'])
def student_token():
    return render_template('student_token.html')

@app.route("/get_student_token", methods=['GET','POST'])
def get_student_token():
    roll_number = request.form.get('roll_number')
    student = Student.query.filter_by(roll_number=roll_number).first()
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
    URL = "http://127.0.0.1:5000/attendance?student_id="+str(student.id)+"&student_token="+token
    body_ = "Dear Student"+str(student.name)+".\n Go to URL "+URL+" to mark attendance and update your details regularly."
    message = Message(subject="Student Profile Page", recipients=[student.email], 
                        body = body_ , sender= "myemail@gmail.com" )
    # mail.send(message)
    print(URL)
    # setting token reset time to 2 hrs
    c_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
    add = datetime.timedelta(hours=2)
    time = c_time + add
    # Scheduling job for password reset
    scheduler.add_job(id='token'+roll_number, func=reset_token,
                    trigger='date',run_date=time,args=[student.id],replace_existing= True)
    try:
        db.session.commit()
        flash('Password has been sent to '+student.email, 'success')
    except Exception:
        db.session.rollback()
    return redirect(url_for('student_token'))

def reset_token(student_id):
    s = Student_token.query.filter_by(student_id=student_id).first()
    if s != None:
        db.session.delete(s)
        db.session.commit()
        print('Token has been reset for '+ str(student_id))


'''

# Admin Access Pages
Contains Update Data for Course,Student,Faculty
Select Mandatory Courses and Faculty on Leave for Each Semester
Assigning Field Coordinators


'''


@app.route("/updateData", methods=['GET', 'POST'])
@login_required
@admin_required
def updateData():
    semesters = Semester.query.all()
    fields = ['TFE','Manufacturing','Design']
    facultys = [{'id':faculty.id, 'name':faculty.name} for faculty in Faculty.query.all() if faculty.is_active == 1 and faculty.role != 'admin']
    return render_template('updateData.html', semesters = semesters,fields=fields,facultys=facultys)

# Uploda Course Data
@app.route("/uploadCourseData", methods=['GET', 'POST'])
@login_required
@admin_required
def uploadCourseData():
    if request.method == 'POST' and "course_file" in request.files:
        file = request.files['course_file']
        data_xls = read_excel(file) # names=['course_field', 'course_code', 'course_name']
        
        # Course code must be present in each row
        if data_xls['course_code'].isnull().values.any():
            flash('Course Code not present', 'info')
        else:
            #Creating Field for Courses |Replacing empty Course Names with Course Codes
            fields = ['TFE','Manufacturing','Design','All']
            data_xls['course_code'] = data_xls['course_code'].astype(str)
            data_xls["course_field"].fillna("All", inplace = True)
            data_xls["course_name"].fillna(data_xls["course_code"], inplace = True)

            for i,data in data_xls.iterrows():
                # Checking if course field is pronounced correctly
                if data['course_field'] in fields:
                    c = Course.query.filter_by(code = data['course_code']).first()
                    if c:
                        c.name = data['course_name']
                        c.field = data['course_field']
                    else:
                        c = Course(field=data['course_field'],code=data['course_code'],name=data['course_name'])
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
                flash(' Data Not Uploaded !', 'info')
    return redirect(url_for('updateData'))

# Upload Faculty Data
@app.route("/uploadFacultyData", methods=['GET', 'POST'])
@login_required
@admin_required
def uploadFacultyData():
    # Same Functionality as upload course Data
    if request.method == 'POST' and "faculty_file" in request.files:
        file = request.files['faculty_file']
        data_xls = read_excel(file) # names=['faculty_name', 'faculty_ldap', 'faculty_email', 'faculty_field', 'status']
        if data_xls[['faculty_email','faculty_ldap']].isnull().values.any():
            flash('Faculty Email / Ldap not present', 'info')
        else:
            fields = ['TFE','Manufacturing','Design','All']
            data_xls["faculty_field"].fillna("All", inplace = True)
            data_xls["faculty_name"].fillna(data_xls["faculty_ldap"], inplace = True)
            data_xls["status"].fillna('active', inplace = True)
            hashed_password = bcrypt.generate_password_hash('admin').decode('utf-8')  # remove Later
            for i,data in data_xls.iterrows():
                if data['faculty_field'] not in fields:
                    db.session.rollback()
                    flash(' Data Not Uploaded, Field not recognisable !', 'info')
                    return redirect(url_for('updateData'))
                f = Faculty.query.filter_by(ldap = data['faculty_ldap']).first()
                curr = 0 if data['status'] == 'inactive' else 1
                if f:
                    f.name = data['faculty_name']
                    f.email = data['faculty_email']
                    f.field = data['faculty_field']
                    f.password = hashed_password
                    f.is_active = curr
                else:
                    f = Faculty(name=data['faculty_name'],ldap=data['faculty_ldap'],email=data['faculty_email'],field=data['faculty_field'],password=hashed_password,is_active=curr)
                    db.session.add(f)
            try:
                db.session.commit()
                flash('Faculty Data Uploaded Successfully !', 'success')
            except IntegrityError:
                db.session.rollback()
                flash(' Data Not Uploaded !', 'info')

    return redirect(url_for('updateData'))

#   Updating Student vs Semester Relations Whether student is active or not 
# ( Like Stack with latest Semester at top changes entries above the selected semester )
def create_semester_student_status(semester_id,student_id,status):
    semesters = Student_Semester.query.filter(Student_Semester.semester_id>=semester_id,Student_Semester.student_id==student_id).all()
    curr = 0 if status == 'inactive' else 1
    if semesters:
        for semester in semesters:
            semester.is_active = curr
    else:
        for semester in Semester.query.filter(Semester.id >= semester_id):
            student = Student_Semester(student_id=student_id,semester_id=semester.id,is_active=curr)
            db.session.add(student)
    db.session.commit()

# Upload Student Data
@app.route("/uploadStudentData", methods=['GET', 'POST'])
@login_required
@admin_required
def uploadStudentData():
    if request.method == 'POST' and "student_file" in request.files and request.form.get('semester'):
        file = request.files['student_file']
        semester_id = request.form.get('semester')
        data_xls = read_excel(file) # names=['student_name', 'student_email', 'student_rollno', 'student_program', 'student_field', 'status']
        if data_xls['student_rollno'].isnull().values.any() or len(data_xls['student_rollno'].unique()) != len(data_xls):
            flash('Student Roll Number not present or Identical Roll Numbers', 'info')
        else:
            # Data Sanitisation
            fields = ['TFE','Manufacturing','Design','All']
            data_xls['student_rollno'] = data_xls['student_rollno'].astype(str)
            data_xls["student_field"].fillna("All", inplace = True)
            data_xls["student_program"].fillna("None", inplace = True)
            data_xls["student_name"].fillna(data_xls["student_rollno"], inplace = True)
            data_xls["student_email"].fillna(data_xls["student_rollno"]+'@iitb.ac.in', inplace = True)
            data_xls["status"].fillna('active', inplace = True)
            for i,data in data_xls.iterrows():
                if data['student_field'] not in fields:
                    db.session.rollback()
                    flash(' Data Not Uploaded, Field not recognisable !', 'info')
                    return redirect(url_for('updateData'))
                s = Student.query.filter_by(roll_number = data['student_rollno']).first()
                if s:
                    s.name = data['student_name']
                    s.email = data['student_email']
                    s.program = data['student_program']
                    s.field = data['student_field']
                else:
                    s = Student(name=data['student_name'],email=data['student_email'],roll_number=data['student_rollno'],program=data['student_program'],field=data['student_field'])
                    db.session.add(s)
                db.session.flush()
                create_semester_student_status(semester_id,s.id,data['status'])
            try:
                db.session.commit()
                flash('Student Data Uploaded Successfully !', 'success')
            except IntegrityError:
                db.session.rollback()
                flash(' Data Not Uploaded !', 'info')
    return redirect(url_for('updateData'))

# Create New Semester
@app.route("/createNewSemester")
@login_required
@admin_required
def createNewSemester():
    semester = Semester.query.all()
    if semester:
        year = semester[-1].year + 1
        sem1 = Semester(semester='Spring - '+str(year),year=year)
        sem2 = Semester(semester='Summer - '+str(year),year=year)
        sem3 = Semester(semester='Fall - '+str(year),year=year)
        db.session.add_all([sem1,sem2,sem3])
    else:
        year = datetime.datetime.today().year
        sem1 = Semester(semester='Spring - '+str(year),year=year)
        sem2 = Semester(semester='Summer - '+str(year),year=year)
        sem3 = Semester(semester='Fall - '+str(year),year=year)
        db.session.add_all([sem1,sem2,sem3])
    db.session.commit()
    return redirect("/updateData")

# Send Data for Selecting Facultys on Leave or Mandatory Coruses
@app.route("/semesterData_1", methods=['GET', 'POST'])
@login_required
@admin_required
def semesterData_1():
    facultys = [{'id':faculty.id, 'name':faculty.name} for faculty in Faculty.query.filter(Faculty.is_active==1,Faculty.role!='admin').all()]
    courses = [{'id':course.id, 'name':course.__repr__()} for course in Course.query.all()]
    resp = {'facultys':facultys,'courses':courses}
    return jsonify(resp)

# Create Table for Faculty OnLeave and Mandatory Courses Based on Semester Selected
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
# Remember only One coordinator for each field
@app.route("/addCoordinator", methods=['GET', 'POST'])
@login_required
@admin_required
def addCoordinator():
    field = request.form.get('subfield')
    faculty_id = request.form.get('faculty_id')
    faculty = Faculty.query.get(faculty_id)
    if faculty and faculty.field == field:
        f = Faculty.query.filter_by(is_active=1,field=field,role='coordinator').first()
        if f:
            message = 'Coordinator has already been assigned to this field.'
        else:
            faculty.role = 'coordinator'
            message = 'Assigned'
    else:
        message = "Faculty's Field and Selected Field Doesn't Match "
    response = {'message':message}
    db.session.commit()
    return jsonify(response)

# Removing The coordinator
@app.route("/removeCoordinator", methods=['GET', 'POST'])
@login_required
@admin_required
def removeCoordinator():
    faculty_id = request.form.get('faculty_id')
    faculty = Faculty.query.get(faculty_id)
    if faculty and faculty.role == 'coordinator':
        faculty.role = ''
        db.session.commit()
    return jsonify()

# Send Data for Coordinators Appointed
@app.route("/coordinatorData", methods=['GET', 'POST'])
@login_required
@admin_required
def coordiantorData():
    coordinators = []
    for faculty in Faculty.query.filter_by(is_active=1,role='coordinator').all():
        coordinators.append({'id':faculty.id,'name':faculty.name,'ldap':faculty.ldap,
                            'role':faculty.role,'field':faculty.field})
    response = {'coordinators': coordinators}
    return jsonify(response)



'''


# Admin and Coordinator Access Pages
# Includes Course Allotment, TA Allotment


# Course Allotment By Coordinators and Admin
********************************************


'''


@app.route("/courseAllotment", methods=['GET', 'POST'])
@login_required
@coordinator_required
def courseAllotment():
    semesters = [{'id':semester.id,'semester':semester.__repr__()} for semester in Semester.query.all()]
    return render_template('courseAllotment.html', title='Course Allotment', semesters=semesters)

# Getting Courses Based on Coordinator Field
@app.route("/get_courses", methods = ["GET","POST"])
@login_required
@coordinator_required
def get_courses():
    if current_user.role == 'admin':
        courses = [{'id':course.id,'name':course.__repr__()} for course in Course.query.all()]
    else:
        courses = [{'id':course.id,'name':course.__repr__()} for course in Course.query.filter(Course.field.in_((current_user.field,'All')))]
    return jsonify(courses)

# Removing Course Allotment
@app.route("/removeCourseAllotment", methods=['GET', 'POST'])
@login_required
@coordinator_required
def removeCourseAllotment():
    fac_id = request.form.get('course_faculty_id')
    semester_id = request.form.get('semester_id')
    cf = Course_Faculty.query.get(fac_id)
    if cf and str(cf.semester_id) == semester_id :
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
    if current_user.role == 'admin':
        course_ids = [course.id for course in Course.query.all()]
    else:
        course_ids = [course.id for course in Course.query.filter(Course.field.in_((current_user.field,'All')))]
    semester_id = request.form.get('semester_id')
    course_facultys = Course_Faculty.query.filter_by(semester_id=semester_id).all()
    course_fac_list = []
    course_list = []
    for course_faculty in course_facultys:
        if course_faculty.course_id in course_ids:
            course_fac_list.append({'id': course_faculty.id,
                      'field':course_faculty.course.field,
                      'course': course_faculty.course.__repr__(),
                      'section': course_faculty.section,
                      'professor': course_faculty.faculty.__repr__(),
                      'maxTA':course_faculty.maxTA})
    for course in Course_Semester.query.filter_by(is_mandatory=1,semester_id=semester_id).all():
        if course.course_id in course_ids:
            course_list.append({'field':course.course.field,
                      'course': course.course.__repr__(),
                      'allotments':len(Course_Faculty.query.filter_by(course_id=course.id,semester_id=semester_id).all())})
    response = {'fac_list':course_fac_list,'course_list':course_list}
    return jsonify(response)

# Displaying Current and Previous Semester Allotments of the selected Course
@app.route("/get_alloted_sections", methods = ["GET","POST"])
@login_required
@coordinator_required
def get_alloted_sections():
    course_id = request.form.get('course_id')
    semester_id = request.form.get('semester_id')
    query = Course_Faculty.query.filter_by(course_id=course_id).all()
    course_sections = []
    prev_allot = {}
    for q in query:
        if str(q.semester_id) == semester_id:
            course_sections.append({'section':q.section,'prof':q.faculty.name,'maxTA':q.maxTA})
        else:
            if q.faculty.name in prev_allot:
                if q.semester.__repr__() not in prev_allot[q.faculty.name]:
                    prev_allot[q.faculty.name] = prev_allot.get(q.faculty.name,'')+ ' | ' + q.semester.__repr__()
            else:
                prev_allot[q.faculty.name] = prev_allot.get(q.faculty.name,'')+ q.semester.__repr__()
    resp = {'course_sections':course_sections,'previous_allotments':prev_allot}
    return jsonify(resp)

# Getting Sections and Lists of Faculty after Selecting Number of Sections to Add
@app.route("/get_sections_and_faculty", methods = ["GET","POST"])
@login_required
@coordinator_required
def get_sections_and_faculty():
    semester_id,course_id,num_sections = request.form.get('semester_id'),request.form.get('course_id'),int(request.form.get('num_sections'))
    query = Course_Faculty.query.filter_by(course_id=course_id,semester_id=semester_id).all()
    course_sections = [q.section for q in query]
    # get new sections that are to be alloted
    new_sections = []
    for i in range(1,num_sections+len(course_sections)+1):
        section = 'S'+str(i)
        if section not in course_sections:
            new_sections.append(section)
    facultys = []
    c = Course.query.get(course_id)
    for fac in Faculty.query.filter(Faculty.is_active==1,Faculty.role!='admin').all():
        fs = Faculty_Semester.query.filter_by(semester_id=semester_id,faculty_id=fac.id).first()
        if fs and fs.is_active == 0:
            continue
        if c.field == 'All' or fac.field in ['All',c.field]:
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



'''


# TA Allotment by Coordinators and Admin
****************************************


'''

@app.route("/studentAllotment", methods=['GET', 'POST'])
@login_required
@coordinator_required
def studentAllotment():
    semesters = [{'id':semester.id,'semester':semester.__repr__()} for semester in Semester.query.all()]
    return render_template('studentAllotment.html', title='Student Allotment',semesters=semesters)

# get_courses route is same as get_courses route for faculty allotment

# Getting Allotments of Selected Course and Semester
@app.route("/get_course_tas_allotments", methods = ["GET","POST"])
@login_required
@coordinator_required
def get_course_tas_allotments():
    course_id = request.form.get('course_id')
    semester_id = request.form.get('semester_id')
    course_tas = []
    for c in Course_Ta.query.filter_by(course_id=course_id,semester_id=semester_id).all():
        course_tas.append({'id':c.id, 'section':c.section,'student':c.ta.__repr__()})
    resp = {'course_tas':course_tas,'course':Course.query.get(course_id).__repr__()}
    return jsonify(resp)

# Getting All Allotments Made and Pending Allotments Table For selected Semester
@app.route("/get_student_allotments", methods = ["GET","POST"])
@login_required
@coordinator_required
def get_student_allotments():
    if current_user.role == 'admin':
        course_ids = [course.id for course in Course.query.all()]
    else:
        course_ids = [course.id for course in Course.query.filter(Course.field.in_((current_user.field,'All')))]
    semester_id = request.form.get('semester_id')
    ta_list = []
    allotments = []  # Contains number of left to be alloted out of Max TAs allowed
    for course_ta in Course_Ta.query.filter_by(semester_id=semester_id).all():
        if course_ta.course_id in course_ids:
            ta_list.append({'id': course_ta.id,
                      'field':course_ta.course.field,
                      'course':course_ta.course.__repr__(),
                      'section': course_ta.section,
                      'student': course_ta.ta.name})
    for c in Course_Faculty.query.filter_by(semester_id=semester_id).all():
        if c.course_id in course_ids:
            allotments.append({'course':c.course.__repr__(),
                        'section':c.section +' - '+ c.faculty.__repr__(),
                        'done':len(Course_Ta.query.filter_by(section=c.section,semester_id=semester_id,course_id=c.course.id).all()),
                        'max':c.maxTA})
    response = {'ta_list': ta_list,'pending_allotments':allotments}
    return jsonify(response)

# Remove TA Allotments
@app.route("/removeTaAllotment", methods=['GET', 'POST'])
@login_required
def removeTaAllotment():
    ta_id = request.form.get('ta_id')
    semester_id = request.form.get('semester_id')
    ct = Course_Ta.query.get(ta_id)
    if ct and ct.semester_id == int(semester_id) :
        db.session.delete(ct)
        resp = {'message': "success"}
    else:
        resp = {'message': "error"}
    db.session.commit()
    return jsonify(resp)

# Finding The Sections Under Selected Course and List of Students
@app.route("/get_sections_and_students", methods = ["GET","POST"])
@login_required
@coordinator_required
def get_sections_and_students():
    course_id = request.form.get('course_id')
    semester_id = request.form.get('semester_id')
    query = Course_Faculty.query.filter_by(course_id=course_id,semester_id=semester_id).all()
    course_sections = []
    for q in query:
        course_sections.append({'section':q.section,'prof':q.faculty.name,'maxTA':q.maxTA})
    student_list = []
    c = Course.query.get(course_id)
    for student in Student_Semester.query.filter_by(semester_id=semester_id,is_active=1).all():
        if c.field == 'All' or student.student.field in ['All',c.field]:
            student_list.append({'id':student.student_id,'name':student.student.__repr__()})
    resp = {'course_sections':course_sections,'student_list':student_list}
    return jsonify(resp)

# Making TA Allotment by Checking Max TA Limit for the Selected Sectionh
@app.route("/allot_section_ta", methods = ["GET","POST"])
@login_required
def allot_section_ta():
    ta = json.loads(request.form.get('ta_list'))
    semester_id,course_id,section,student_id = int(ta['semester_id']),int(ta['course_id']),ta['section'],int(ta['student_id'])

    # Make an Entry Check in Database
    entry_check = Course_Ta.query.filter_by(course_id=course_id, student_id=student_id, section=section,semester_id=semester_id).first()
    if entry_check:
        response = {'message': 'Student has already been alloted under this Course and Section'}
        return jsonify(response)

    # Verifying student , course sections existence and if max TAs Limit is reached or not
    student = Student_Semester.query.filter_by(student_id=student_id,semester_id=semester_id,is_active=1).first()
    course_faculty = Course_Faculty.query.filter_by(course_id=course_id, section=section, semester_id=semester_id).first()
    allTAs = Course_Ta.query.filter_by(course_id=course_id, section=section, semester_id=semester_id).all()
    response = {}
    if len(allTAs) >= course_faculty.maxTA:
        response = {'message': 'Maximum TAs Limit Reached'}
        return jsonify(response)
    if student and semester_id and course_id and section and student_id:
        entry = Course_Ta(course_id=course_id, student_id=student_id, section=section,semester_id=semester_id)
        db.session.add(entry)
        db.session.commit()
        response = {'message': 'Student is alloted'}
    return jsonify(response)

'''

# Faculty Access Routes
***********************

# TA allotment by Faculty
*************************

# List of Students With Faculty as Faculty Advisor
**************************************************


'''

@app.route("/studentAllotmentFac", methods=["GET","POST"])
@login_required
def studentAllotmentFac():
    faculty = Faculty.query.get(current_user.id)
    semesters = Semester.query.all()
    return render_template('studentAllotmentFac.html',semesters=semesters,faculty=faculty)

# Getting List of alloted Courses to the Faculty for the Semester
@app.route("/get_faculty_courses", methods = ["GET","POST"])
@login_required
def get_faculty_courses():
    semester_id = request.form.get('semester_id')
    course_query = Course_Faculty.query.filter_by(faculty_id=current_user.id,semester_id=semester_id)
    courses = []
    for c in course_query:
        courses.append({'id':c.course_id,'field':c.course.field,'name':c.course.__repr__(),
                        'section':c.section,'maxTA':c.maxTA,
                        'done':len(Course_Ta.query.filter_by(section=c.section,semester_id=semester_id,course_id=c.course.id).all())})
    students = []
    for student in Student_Semester.query.filter_by(semester_id=semester_id,is_active=1).all():
        students.append({'id':student.student_id,'name':student.student.__repr__()})
    resp = {'courses':courses,'students':students}
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

# same route is used as line 577 allot_section_ta for TA Allotment by fac

# Students's Faculty Advisor List
@app.route("/facFacad", methods=["GET","POST"])
@login_required
def facFacad():
    faculty = Faculty.query.get(current_user.id)
    facad_students = Facad.query.filter_by(facad_id=current_user.id).all()
    facad_students_list = []
    for student in facad_students:
        facad_students_list.append({'id':student.id,'name': student.student.name, 'roll_number':student.student.roll_number,
                                'program':student.student.program, 'field':student.student.field,
                                'status':student.status,'sno':len(facad_students_list)+1})
    return render_template('facFacad.html',facads = facad_students_list,
                            faculty={'name':faculty.name,'id':faculty.id})

# Remove Facad Allotment
@app.route("/facRemoveFacad<faculty_id><id>", methods=["GET","POST"])
@login_required
def facRemoveFacad(faculty_id,id):
    facad = Facad.query.filter_by(id=id, facad_id=current_user.id).first()
    if facad and str(current_user.id) == faculty_id :
        db.session.delete(facad)
        db.session.commit()
    return redirect(url_for('facFacad'))

'''


# Student , Faculty, Course List and  Data Pages
************************************************


'''

# Get Student List
@app.route("/studentList")
@login_required
def studentList():
    semester = Semester.query.all()
    students = [{'id':student.id,'name':student.__repr__()} for student in Student.query.all()]
    return render_template("studentList.html", students=students,semesters=semester)

# Get Student List Based on Semester
@app.route("/get_student_list", methods=["GET","POST"])
@login_required
def get_student_list():
    semester_id = request.form.get('semester_id')
    student_ids = [s.student_id for s in Student_Semester.query.filter_by(semester_id=semester_id,is_active=1).all()]
    # students = Student.query.filter(Student.is_active==1)
    student_list = []
    for student_id in student_ids:
        s = Student.query.get(student_id)
        tas = Course_Ta.query.filter_by(student_id=student_id,semester_id=semester_id).all()
        #getting course list student is part of
        courses = []
        for ta in tas:
            courses.append(ta.section+' - '+ta.course.__repr__())
        # getting latest attendance
        attendances = Attendance.query.filter_by(student_id=student_id).all()
        if len(attendances) > 0:
            attendance = attendances[-1].date_posted
        else:
            attendance = ""
        #getting facads names
        facad_list = []
        facads = Facad.query.filter_by(student_id=student_id).all()
        for facad in facads:
            facad_list.append(facad.status+' - '+facad.facad.__repr__())
        student_list.append({'id': s.id, 'name': s.name, 'email':s.email,
                             'rollno':s.roll_number, 'phone_number':s.phone_number,
                             'program':s.program, 'field':s.field,'courses': courses,
                             'facads':facad_list,'attendance':attendance})
    resp = {'students':student_list}
    return jsonify(resp)

# Find Student Using Name / Roll_number
@app.route("/findStudent" , methods=['GET', 'POST'])
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
                    'program':student.program, 'hostel_no': student.hostel_no,
                    'room_no': student.room_no}
    facads = Facad.query.filter_by(student_id=student_id).all()
    facad_list = []
    for facad in facads:
        facad_list.append({'status':facad.status,'facad_name':facad.facad.name})
    
    return render_template('studentData.html', student=student_data, course_tas=course_tas, attendances=attendances,facads = facad_list)

# Get Faculty List
@app.route("/facultyList")
@login_required
def facultyList():
    semester = Semester.query.all()
    facultys = [{'id':faculty.id,'name':faculty.__repr__()} for faculty in Faculty.query.all() if faculty.role != 'admin']
    return render_template("facultyList.html", facultys=facultys,semesters=semester)

# Get Faculty List Based on Semester
@app.route("/get_faculty_list", methods=["GET","POST"])
@login_required
def get_faculty_list():
    semester_id = request.form.get('semester_id')
    faculty_list = []
    for faculty in Faculty.query.all():
        # Checking Faculty Status
        status = 'active'
        faculty_status = Faculty_Semester.query.filter_by(faculty_id=faculty.id,semester_id=semester_id,is_active=0).first()
        if faculty.is_active == 0:
            status = 'Inactive'
        elif faculty_status:
            status = 'OnLeave'
        # Finding Courses Currently Taught by faculty
        courses = []
        for c in Course_Faculty.query.filter_by(faculty_id=faculty.id,semester_id=semester_id).all():
            courses.append({'id':c.course_id,'name':c.section+'-'+c.course.__repr__()})
        # Adding Entry to List
        faculty_list.append({'id':faculty.id, 'email':faculty.email,'ldap':faculty.ldap,'name':faculty.name,
                            'field':faculty.field,'courses': courses,'status':status})
    resp = {'facultys':faculty_list}
    return jsonify(resp)

# Search Faculty Using Faculty name / Ldap
@app.route("/findFaculty" , methods=['GET', 'POST'])
def findFaculty():
    faculty_id = request.args.get('faculty')
    return redirect(url_for('facultyData', faculty_id=faculty_id))

# Faculty Profile Page
@app.route("/facultyData/<faculty_id>")
@login_required
def facultyData(faculty_id):
    faculty = Faculty.query.get_or_404(faculty_id)
    faculty_list = {'email':faculty.email,'name':faculty.name, 'field':faculty.field, 'status':faculty.is_active, 'ldap':faculty.ldap}
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

# Get Course List
@app.route("/courseList")
@login_required
def courseList():
    semester = Semester.query.all()
    courses = [{'id':course.id,'name':course.__repr__()} for course in Course.query.all()]
    return render_template("courseList.html", courses=courses,semesters=semester)

# Get Course List Based on Semester
@app.route("/get_course_list", methods=["GET","POST"])
@login_required
def get_course_list():
    semester_id = request.form.get("semester_id")
    course_list = []
    for course in Course.query.all():
        status = Course_Semester.query.filter_by(course_id=course.id,semester_id=semester_id,is_mandatory=1).first()
        # Course Status in Semester
        mandatory = ''
        if status:
            mandatory = str(status.is_mandatory)
        # Faculty associated with this course
        course_sections = Course_Faculty.query.filter_by(course_id=course.id, semester_id=semester_id).all()
        instructors = []
        for s in course_sections:
            instructors.append({'faculty_id':s.faculty_id,'name':s.faculty.name,'section':s.section,
                                'TA': str(Course_Ta.query.filter_by(course_id=course.id,semester_id=semester_id,section=s.section).count())+'/'+str(s.maxTA)})
        course_list.append({'id':course.id,'field':course.field,'code':course.code,'is_mandatory':mandatory,
                            'name':course.name,'instructors':instructors})
    resp = {'courses':course_list}
    return jsonify(resp)

# Search Course Based on Code / Name
@app.route("/findCourse" , methods=['GET', 'POST'])
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


'''


# Student Access Pages
**********************

# Attendance Section for TAs
****************************

# Update Data and Add Facad
***************************


'''

# Student Access Page
@app.route("/attendance", methods = ["GET","POST"])
def attendance():
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
    student_data = {'id':student_id, 'token':token, 'name':s.name,'email':s.email,
                    'roll_number':s.roll_number,'phone_number':s.phone_number,'field':s.field,
                    'program':s.program, 'hostel_no': s.hostel_no,'room_no': s.room_no,
                    'alt_email':s.alt_email}
    fields = ['All', 'TFE', 'Manufacturing', 'Design']
    programs = ['BTech', 'MTech', 'Phd']
    return render_template("attendance.html", student=student_data, course_tas=course_tas, attendances=attendances,
                            facultys=facultys,fields=fields,programs=programs)

# Marking Attendance , Can be Marked once a Day
@app.route("/markAttendance", methods = ["GET","POST"])
def markAttendance():
    student_id = int(request.args.get('student_id'))
    student_token = str(request.args.get('student_token'))
    present_date = datetime.date.today()
    prev_attendance = Attendance.query.filter_by(student_id=student_id, date_posted = present_date).first()
    if prev_attendance:
        flash("You have already marked your attendance", "info")
    else:
        attendance = Attendance(student_id=student_id)
        db.session.add(attendance)
        db.session.commit()
        flash("Attendace Marked !", "success")
    return redirect(url_for('attendance', student_id=student_id, student_token=student_token))

# Editing Student Phone, Hostel, Room, Alt_email, Program, Field
@app.route("/editStudentData", methods = ["GET","POST"])
def editStudentData():
    student_id = request.form.get('student_id')
    student = Student.query.filter_by(id=student_id).first()
    student.phone_number = request.form.get('phone_number')
    student.hostel_no = request.form.get('hostel_no')
    student.room_no = request.form.get('room_no')
    student.alt_email = request.form.get('alt_email')
    fields = ['TFE','Manufacturing','Design','All']
    field = request.form.get('field')
    if field in fields:
        student.field = field
    else:
        db.session.rollback()
        resp = {'message': 'error'}
        return jsonify(resp)
    student.program = request.form.get('program')
    try:
        db.session.commit()
        resp = {'message':'success'}
    except:
        db.session.rollback()
        resp = {'message': 'error'}
    return jsonify(resp)

# Fetching Faculty Advisors List
@app.route("/getFacadData", methods = ["GET","POST"])
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

# Adding Faculty Advisor
@app.route("/addFacad", methods = ["GET","POST"])
def addFacad():
    facad_id = request.form.get('facad_id')
    status = request.form.get('status')
    student_id = request.form.get('student_id')
    facad = Facad(student_id=student_id,facad_id=facad_id,status=status)
    facad_check = Facad.query.filter_by(student_id=student_id,facad_id=facad_id).first()
    if facad_check:
        resp = {'message': 'Entry already exists'}
        return jsonify(resp)

    if status=='secondary':
        db.session.add(facad)
        resp = {'message': 'Added'}
    if status=='primary':
        facad_primary = Facad.query.filter_by(student_id=student_id,status='primary').first()
        if facad_primary:
            resp = {'message': 'Only 1 primary Facad is Allowed'}
        else:
            db.session.add(facad)
            resp = {'message': 'Added'}
    try:
        db.session.commit()
    except:
        db.session.rollback()
        resp = {'message': 'Error'}

    return jsonify(resp)


# ==========================================================
# ==========================================================
# ==========================================================