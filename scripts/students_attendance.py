#change password
# sys.path.insert(0, '/var/www/ME/')
# sys.path.insert(0, '/var/www/ME/flaskapp')

import os, sys, datetime, pytz

sys.path.insert(0, "C:/Users/HP/myprojects/mechweb")
sys.path.insert(0, "C:/Users/HP/myprojects/mechweb/flaskapp")

from flaskapp.models import Semester, Student_Semester
import mail_queue, mail_handler, settings


mailQueue = mail_queue.MAIL_QUEUE()
mailHandler = mail_handler.MAIL_HANDLER()

def downloadStudentAttendanceList():
    days = int(settings.attendance_days)
    sem_id = None
    semester = Semester.query.filter_by(is_current=1).first()
    if not sem_id:
        sem_id = semester.id
    if not (days and sem_id):
        print('Error')
        return 0
    s_list = []
    students = Student_Semester.query.filter_by(semester_id=sem_id, is_active=1).all()
    absent = []
    current_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata'))
    for s in students:
        if s.student.last_attendance:
            c_time = current_time - s.student.last_attendance
            attendance = str(c_time.days) + ' Days Ago'
            if c_time.days > days:
                absent.append({'rollno':s.student.roll_number,'name':s.student.name,'email':s.student.email,'last_active':attendance})
        else:
            absent.append({'rollno':s.student.roll_number,'name':s.student.name,'email':s.student.email,'last_active':'None'})
            continue
    return absent

s_list = downloadStudentAttendanceList()
print(len(s_list))
days = int(settings.attendance_days)

html = 'Dear Prof. , this is mail containing details of students who havent marked their attendance for last '+ str(days) +' days.<br>'
html += '<table class="table table-sm table-bordered sortable">'+\
            '<thead><tr>'+\
                '<th>Name</th> <th>Roll Number</th> <th>Email</th> <th>Last Active</th>'+\
            '</tr></thead><tbody>'
for s in s_list:
    html+= '<tr><td>'+s["name"]+'</td>'
    html+= '<td>'+s["rollno"]+'</td>'
    html+= '<td>'+s["email"]+'</td>'
    html+= '<td>'+s["last_active"]+'</td></tr>'
html += '</tbody></table>'

newentry = {'subject' : 'Student Attendance Record', \
                    'content'  : html, \
                    'to' : settings.attendance_mail_reciever}

resp = mailHandler.send_email(newentry)
if not resp:
    mailQueue.add_mails_to_queue([newentry])