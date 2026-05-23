import sys
import types
import importlib

from unittest.mock import MagicMock


# Create a minimal fake customtkinter module to allow importing the GUI module
fake_ctk = types.ModuleType("customtkinter")

class Dummy:
    def __init__(self, *a, **k):
        pass

    def grid(self, *a, **k):
        pass

    def pack(self, *a, **k):
        pass


class CTkEntry(Dummy):
    def __init__(self, *a, **k):
        self._value = ""

    def grid(self, *a, **k):
        pass

    def get(self):
        return self._value

    def delete(self, a, b):
        self._value = ""

    def insert(self, idx, val):
        self._value = val


class CTkOptionMenu(Dummy):
    def __init__(self, *a, **k):
        self._value = "Select Class"
        self._values = ["Select Class"]

    def grid(self, *a, **k):
        pass

    def get(self):
        return self._value

    def set(self, v):
        self._value = v

    def configure(self, values=None):
        if values is not None:
            self._values = values


class CTkProgressBar(Dummy):
    def set(self, v):
        self.value = v


class CTkLabel(Dummy):
    def configure(self, *a, **k):
        pass


class CTkButton(Dummy):
    def configure(self, *a, **k):
        pass


def CTkFont(*a, **k):
    return None


fake_ctk.CTkFrame = Dummy
fake_ctk.CTkEntry = CTkEntry
fake_ctk.CTkOptionMenu = CTkOptionMenu
fake_ctk.CTkProgressBar = CTkProgressBar
fake_ctk.CTkLabel = CTkLabel
fake_ctk.CTkButton = CTkButton
fake_ctk.CTkFont = CTkFont

# Insert the fake module into sys.modules before importing the GUI
sys.modules["customtkinter"] = fake_ctk

# Now import the module under test
register_mod = importlib.import_module("gui.register_page")
from gui.register_page import RegisterPage


def test_duplicate_student_id_prevents_capture(monkeypatch):
    # Patch the module-level functions used by RegisterPage
    monkeypatch.setattr(register_mod, "get_all_students", lambda: [{"student_id": "S123", "name": "Existing", "class_id": 1}])
    monkeypatch.setattr(register_mod, "get_all_classes", lambda: [{"id": 1, "name": "Class1", "section": "A"}])

    # Track if capture_face_images is called
    called = {"capture": False}

    def fake_capture(*a, **k):
        called["capture"] = True
        return True

    monkeypatch.setattr(register_mod, "capture_face_images", fake_capture)

    # Create a simple master with a notification recorder
    class Master:
        def __init__(self):
            self.last = None

        def show_notification(self, message, kind):
            self.last = (message, kind)

    master = Master()

    page = RegisterPage(master)

    # Fill form with duplicate student id
    page.id_entry._value = "S123"
    page.first_entry._value = "New"
    page.middle_entry._value = ""
    page.last_entry._value = "Student"

    # Select the populated class label
    label = page._label_for_class({"id": 1, "name": "Class1", "section": "A"})
    page.class_dropdown.set(label)

    # Call the handler
    page.handle_register_student()

    # Verify notification shown and capture not started
    assert master.last is not None
    assert "Student ID already exists" in master.last[0]
    assert called["capture"] is False
