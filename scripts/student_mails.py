import sys
# sys.path.insert(0, '/var/www/ME')
# sys.path.insert(0, '/var/www/ME/flaskapp')

sys.path.insert(0, "C:/Users/HP/myprojects/mechweb")
sys.path.insert(0, "C:/Users/HP/myprojects/mechweb/flaskapp")

from flaskapp.models import Student_Semester, Semester
import settings, datetime, pytz
import mail_queue

mailQueue = mail_queue.MAIL_QUEUE()


semester = Semester.query.filter_by(is_current=1).first()
semester_id = semester.id
days = settings.attendance_days

# Adding entries to the data
entries_ = []
mail_entry = settings.student_mail
URL = settings.WEB_URL+'/student_token'

students = Student_Semester.query.filter_by(semester_id=semester_id, is_active=1).all()
content = mail_entry['body_'] % (URL)
for student in students:
    attendance = student.student.last_attendance
    if attendance:
        c_time = datetime.datetime.now(pytz.timezone('Asia/Kolkata')).date() - attendance
        if c_time.days > days:
          entry = {'subject':mail_entry['subject'],
              'to':student.student.email,
              'content':content}
          entries_.append(entry)
    else:
        entry = {'subject':mail_entry['subject'],
              'to':student.student.email,
              'content':content}
        entries_.append(entry)

#adding data to file
mailQueue.add_mails_to_queue(entries_)

