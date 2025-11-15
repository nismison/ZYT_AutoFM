from datetime import datetime

from apis.fm_api import FMApi
from utils.notification import Notify

today = datetime.today()
now = today.time()
month = str('{:0>2d}'.format(today.month))
day = str('{:0>2d}'.format(today.day))
hour = str('{:0>2d}'.format(now.hour))
minute = str('{:0>2d}'.format(now.minute))

fm = FMApi()
if fm.token is None:
    Notify().send(f"[2025-{month}-{day} {hour}:{minute}] Token失效，请检查")
else:
    print(f"[2025-{month}-{day} {hour}:{minute}] Token正常")

