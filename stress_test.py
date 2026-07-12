import time
import multiprocessing

def stress_cpu():
    # Infinite tight loop to max out a core
    while True:
        pass

if __name__ == '__main__':
    print("Starting stress test to spike CPU... (Press Ctrl+C to stop)")
    # Start one process per core to ensure we hit > 95% CPU usage overall
    cores = multiprocessing.cpu_count()
    processes = []
    
    try:
        for _ in range(cores):
            p = multiprocessing.Process(target=stress_cpu)
            p.start()
            processes.append(p)
            
        print(f"Started {cores} processes. CPU should spike shortly.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping stress test...")
        for p in processes:
            p.terminate()
        print("Stress test stopped.")
