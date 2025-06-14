import sys
from master_process import MasterProcess


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <config_file_path>")
        sys.exit(1)

    if sys.argv[1] == "-h" or sys.argv[1] == "--help":
        print("Usage: python main.py <config_file_path>")
        sys.exit(1)
    config_file_path = sys.argv[1]
    master_proc = MasterProcess(config_path = config_file_path)
    try:
        master_proc.start_process()
    except Exception as e:
        print(e);
    