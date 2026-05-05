class AuthenticatedUser:
    def __init__(self, payload):
        self.id = payload.get("id")
        self.role = payload.get("role")
        self._payload = payload

    @property
    def is_authenticated(self):
        return True

    @property
    def is_active(self):
        return True  # or fetch dynamically

    def to_dict(self):
        return self._payload

    def __str__(self):
        return f"AuthenticatedUser(id={self.id}, role={self.role})"

    def __repr__(self):
        return self.__str__()

class AnonymousUser:
    is_authenticated = False
    is_active = False

    def __str__(self):
        return "AnonymousUser"

    def __repr__(self):
        return self.__str__()
