from datetime import datetime


# ==========================================================
# CURRENT DATE
# ==========================================================

def current_date():
    """
    Return current date.
    Format : DD-MM-YYYY
    """
    return datetime.now().strftime("%d-%m-%Y")


# ==========================================================
# CURRENT TIME
# ==========================================================

def current_time():
    """
    Return current time.
    Format : HH:MM:SS
    """
    return datetime.now().strftime("%H:%M:%S")


# ==========================================================
# CURRENT DATE & TIME
# ==========================================================

def current_datetime():
    """
    Return current date and time.
    """
    return datetime.now().strftime("%d-%m-%Y %H:%M:%S")

# ==========================================================
# CURRENT DATETIME OBJECT
# ==========================================================

def current_datetime_object():
    """
    Return datetime object.
    """
    return datetime.now()


# ==========================================================
# GENERATE ORDER ID
# ==========================================================

def generate_order_id():
    """
    Generate unique order ID.
    """
    return datetime.now().strftime("%Y%m%d%H%M%S")