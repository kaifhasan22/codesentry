API_KEY = "super-secret-demo-key-12345"


def dangerous(user_input):
    return eval(user_input)


def complicated(a, b, c, d, e, f, g):
    if a:
        if b:
            if c:
                return d
            return e
        if f:
            return g
    return None
