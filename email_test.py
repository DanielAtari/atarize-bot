from email.mime.text import MIMEText
import smtplib

EMAIL_USER = "danielatari95@gmail.com"
EMAIL_PASS = "pxixwkthqhptutvn"
EMAIL_TARGET = "danielatari95@gmail.com"

msg = MIMEText("בדיקת שליחת מייל מהבוט")
msg["Subject"] = "בדיקה"
msg["From"] = EMAIL_USER
msg["To"] = EMAIL_TARGET

with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(EMAIL_USER, EMAIL_PASS)
    server.send_message(msg)

print("נשלח ✅")
