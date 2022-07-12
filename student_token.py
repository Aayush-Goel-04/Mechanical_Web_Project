from mail import SEND_MAIL
import secrets
from flaskblog.models import Student_token, Student
from flaskblog import db
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

#-----------------------------------------------------------------------------
class SEND_MAIL(object):
  
  def __init__(self):
    self._sender_password = 'password'
    self._sender_email = 'email'
    self.__set_connection() 

  def __set_connection(self):
    port = 465
    context = ssl.create_default_context()
    server = smtplib.SMTP_SSL("smtp.gmail.com", port, context=context)
    server.login(self._sender_email, self._sender_password)
    self._server = server

  def send_email(self, entries):
    for entry in entries:
      #message
      msg = MIMEMultipart('alternative')
      msg['Subject'] = entry['subject']
      msg['From'] = self._sender_email
      msg['To'] = entry['email']
      part = MIMEText(entry['body_'], "html")
      msg.attach(part)

      try:
        receiver_emails  =  [msg['to']] 
        self._server.sendmail(self._sender_email, receiver_emails, msg.as_string())
        return True
      
      except:
        return False

#-----------------------------------------------------------------------------
# Send Mails To Students 

def generateToken():
    students = Student.query.all()
    deleted = Student_token.query.delete()
    for student in students:
        token= secrets.token_urlsafe(16)
        student_token = Student_token(student_id=student.id, token=token)
        db.session.add(student_token)
    db.session.commit()

generateToken() #generate Tokens
print(Student_token.query.all())
students = Student_token.query.all()
email_list = []
for student in students:
    URL = "http://127.0.0.1:5000/attendance?student_id="+str(student.student_id)+"&student_token="+str(student.token)
    body_ = "Dear Student"+str(student.student.name)+".\nYou have been assigned courses "+str(student.student.courses)+" for TAship.\n Go to URL "+URL+" to mark attendance and update your details regularly"
    email_list.append({'subject':"TA Allotment for Courses",'email':student.student.email,'body_': body_})

#mail = SEND_MAIL()
#print(mail.send_email(email_list))
