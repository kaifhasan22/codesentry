"""Only fixed, reviewed messages may cross the scan-error API boundary."""
GENERIC_ERROR = "The scan could not be completed. Please retry or contact the administrator."
CLONE_ERROR = "Repository preparation failed. Check that the public GitHub repository exists and is accessible."
CLONE_TIMEOUT = "Repository preparation exceeded its 120-second limit. Please retry."
RESOURCE_ERROR = "The repository exceeded the scanner resource limits and could not be fully processed."
SOFT_TIMEOUT = "The scan exceeded its 270-second processing limit and was stopped."
HARD_TIMEOUT = "Scan exceeded the worker's hard processing limit and was stopped before results were saved. The analyzer workload needs to be reduced or split."
WORKER_ERROR = "The scan worker stopped unexpectedly before results were saved."
STALE_ERROR = "The scan worker did not finish within its 300-second limit. The scan was marked failed instead of remaining in progress."
QUEUE_ERROR = "Scan could not be queued. Please retry."
QUEUE_EXPIRED = "The scan did not start within 15 minutes and was marked failed. Please retry."
SAFE_ERRORS = {GENERIC_ERROR, CLONE_ERROR, CLONE_TIMEOUT, RESOURCE_ERROR, SOFT_TIMEOUT, HARD_TIMEOUT, WORKER_ERROR, STALE_ERROR, QUEUE_ERROR, QUEUE_EXPIRED}

def public_scan_error(message):
    return None if message is None else message if message in SAFE_ERRORS else GENERIC_ERROR
