import time
import math
import multiprocessing

def cpu_stress():
    """
    A simple function to generate CPU load.
    """
    start_time = time.time()
    # Run a loop for 0.2 seconds
    while time.time() - start_time < 0.2:
        _ = math.sqrt(64 * 64 * 64 * 64 * 64)

def main():
    print("Starting OCI Keep-Alive Script...")
    print("Targeting ~20-25% CPU utilization to prevent reclamation.")
    
    # Adjust sleep time to control load. 
    # Work 0.2s, Sleep 0.8s = ~20% duty cycle per core.
    # Since we want to ensure we hit the threshold, we might need to tune this.
    # VM.Standard.E2.1.Micro has 2 vCPUs (1 OCPU).
    # We will run this on all available cores.
    
    while True:
        processes = []
        for _ in range(multiprocessing.cpu_count()):
            p = multiprocessing.Process(target=cpu_stress)
            p.start()
            processes.append(p)
        
        for p in processes:
            p.join()
            
        # Sleep for the remainder of the second
        time.sleep(0.8)

if __name__ == "__main__":
    main()
