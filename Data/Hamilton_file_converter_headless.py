import glob
import os
import sys
import time

import win32com.client


def process_files(root_dir, log_file):
    o = win32com.client.Dispatch("HXCFGFILLib.HxCfgFile")
    extensions = ("cfg", "lay", "stp", "ctr", "med", "tpl", "dck", "rck", "tml")
    with open(log_file, "w") as log:
        for ext in extensions:
            for filename in glob.iglob(root_dir + "**/*." + ext, recursive=True):
                log_message = f"Processing: {filename}\n"
                print(log_message, end="")
                log.write(log_message)
                log.flush()

                temp_filename = filename + ".temp"
                try:
                    o.LoadFile(filename)
                    o.StoreFile(temp_filename, 0)

                    # Verify the temp file was written successfully
                    if not os.path.exists(temp_filename) or os.path.getsize(temp_filename) == 0:
                        msg = f"WARNING: Conversion produced empty output for {filename}, keeping original.\n"
                        print(msg, end="")
                        log.write(msg)
                        log.flush()
                        if os.path.exists(temp_filename):
                            os.remove(temp_filename)
                        continue

                    os.remove(filename)
                    os.rename(temp_filename, filename)

                except Exception as e:
                    msg = f"ERROR: Failed to convert {filename}: {e}\n"
                    print(msg, end="")
                    log.write(msg)
                    log.flush()
                    # Clean up temp file if it was created
                    if os.path.exists(temp_filename):
                        os.remove(temp_filename)
                    continue

                time.sleep(0.5)

        log.write("Processing complete.\n")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: script_name <path_to_process> <log_file_path>")
        sys.exit(1)

    input_path = sys.argv[1]
    log_file_path = sys.argv[2]
    if not os.path.exists(input_path):
        print(f"The path {input_path} does not exist.")
        sys.exit(1)

    process_files(input_path, log_file_path)
