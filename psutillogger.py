import psutil, csv, time
with open('metrics.csv','w',newline='') as f:
    w = csv.writer(f)
    w.writerow(['cpu','ram','disk_read','disk_write','net_sent','net_recv'])
    f.flush()
    try:
        while True:
            d = psutil.disk_io_counters()
            n = psutil.net_io_counters()
            w.writerow([psutil.cpu_percent(1), psutil.virtual_memory().percent,
                        d.read_bytes, d.write_bytes, n.bytes_sent, n.bytes_recv])
            f.flush()
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopped, data saved.")