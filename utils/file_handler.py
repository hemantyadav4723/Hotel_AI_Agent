import os


# ==========================================================
# CHECK FILE EXISTS
# ==========================================================

def file_exists(file_path):
    """
    Check if file exists.
    """
    return os.path.exists(file_path)


# ==========================================================
# READ FILE
# ==========================================================

def read_file(file_path):
    """
    Read all lines from a file.
    """
    with open(file_path, "r") as file:
        return file.readlines()


# ==========================================================
# WRITE FILE
# ==========================================================

def write_file(file_path, data):
    """
    Write data into file.
    """
    with open(file_path, "w") as file:
        file.writelines(data)


# ==========================================================
# APPEND FILE
# ==========================================================

def append_file(file_path, data):
    """
    Append data into file.
    """
    with open(file_path, "a") as file:
        file.write(data)