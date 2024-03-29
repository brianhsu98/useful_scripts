import argparse
import subprocess
import time
import signal

class timeout:
    def __init__(self, seconds=1, error_message='Timeout'):
        self.seconds = seconds
        self.error_message = error_message
    def handle_timeout(self, signum, frame):
        raise TimeoutError(self.error_message)
    def __enter__(self):
        signal.signal(signal.SIGALRM, self.handle_timeout)
        signal.alarm(self.seconds)
    def __exit__(self, type, value, traceback):
        signal.alarm(0)


def main(pod_name, output_file):
    with open(output_file, 'a') as f:
        while True:
            # Run kubectl command with pod name
            print("Starting process")
            process = subprocess.Popen(['kubectl', 'logs', '-f', pod_name, '-n', 'autopilot-system'], stdout=subprocess.PIPE)

            # Continuously check if output has stopped
            last_output_time = time.time()
            while True:
                try:
                    with timeout(seconds=3):
                        output = process.stdout.readline()
                except TimeoutError:
                    print("Exiting timeout")
                    process.kill()
                    break

                if output == '' and process.poll() is not None:
                    break
                if output:
                    output = output.decode('utf-8').strip()
                    # print(output)
                    f.write(output + '\n')
                    last_output_time = time.time()

                # If output has stopped for more than 100ms, restart process
                if time.time() - last_output_time > 1:
                    print("restarting process since last output was more than 1s ago")
                    process.kill()
                    break

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pod_name', type=str,)
    parser.add_argument('output_file', type=str)
    args = parser.parse_args()
    main(args.pod_name, args.output_file)
