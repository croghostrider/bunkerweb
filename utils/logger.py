import datetime

def log(title, severity, msg):
    when = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    what = f"{title} - {severity} - {msg}"
    print(f"{when} {what}", flush=True)