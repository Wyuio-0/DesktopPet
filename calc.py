
times = ["08:00", "08:50", "09:50", "10:40", "11:30", "14:00", "14:50", "15:40", "16:30", "18:30", "19:20", "20:10", "21:00"]
import datetime
for i, t in enumerate(times):
    h, m = map(int, t.split(":"))
    dt = datetime.datetime(2023, 1, 1, h, m)
    end = dt + datetime.timedelta(minutes=45)
    print("\"" + str(i+1) + "\" to \"" + t + "\n" + end.strftime("%H:%M") + "\",")

