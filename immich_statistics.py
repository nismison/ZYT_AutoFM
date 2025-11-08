from datetime import datetime, timedelta

from apis.immich_api import IMMICHApi

immich_api = IMMICHApi()

def get_night_upload_count():
    """统计昨天20:00到今天08:00(UTC+8)上传的资源数"""
    now = datetime.utcnow() + timedelta(hours=8)  # 当前北京时间
    today = now.date()
    yesterday = today - timedelta(days=1)

    start_time = f"{yesterday}T20:00:00+08:00"
    end_time = f"{today}T08:00:00+08:00"

    return immich_api.get_statistics(start_time, end_time)

def main():
    count = get_night_upload_count()
    if count is not None:
        msg = f"🌙 昨晚上传资源数: {count}"
        print(f">>>>>>>>>>msg: {msg}<<<<<<<<<<")
        # Notify().send(msg)

if __name__ == "__main__":
    main()
