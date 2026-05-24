def status_class(status_code: int) -> str:
    if 100 <= status_code < 200:
        return "Informational"
    if 200 <= status_code < 300:
        return "Successful"
    if 300 <= status_code < 400:
        return "Redirection"
    if 400 <= status_code < 500:
        return "Client Error"
    if 500 <= status_code < 600:
        return "Server Error"
    return "Unknown"
